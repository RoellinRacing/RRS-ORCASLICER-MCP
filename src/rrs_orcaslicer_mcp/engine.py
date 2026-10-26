"""Discover the installed CLI and supervise durable, cancellable subprocess jobs."""

import asyncio
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .storage import atomic_json, digest


def find_binary() -> str | None:
    configured = os.environ.get("ORCA_SLICER_BIN")
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise ValueError("ORCA_SLICER_BIN must point to an installed executable")
        return str(path)
    for name in ("orca-slicer", "OrcaSlicer", "orcaslicer", "orca-slicer.exe"):
        if found := shutil.which(name):
            return found
    candidates = [Path("/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")]
    if sys.platform == "win32":
        candidates += [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "OrcaSlicer/orca-slicer.exe"
        ]
    return next((str(p) for p in candidates if p.is_file()), None)


async def stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await process.wait()


def process_options() -> dict:
    return (
        {"start_new_session": True}
        if os.name != "nt"
        else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    )


async def capture(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **process_options()
    )
    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout)
        return process.returncode, raw.decode(errors="replace")[-2_000_000:]
    except BaseException:
        await stop_process(process)
        raise


class Engine:
    def __init__(self, state: Path, binary: str | None = None):
        self.state = state
        self.state.mkdir(parents=True, exist_ok=True)
        self._lock = (self.state / ".server.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self._lock.seek(0)
                self._lock.write(b"0")
                self._lock.flush()
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            raise ValueError(
                "Another server uses this job directory; use a separate ORCA_MCP_STATE"
            ) from exc
        self.binary = binary or find_binary()
        self.tasks: dict[str, asyncio.Task] = {}
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self.submissions = asyncio.Lock()
        self.slots = asyncio.Semaphore(1)  # Slicing is memory intensive; avoid resource contention.
        self._capabilities = None
        for path in self.state.glob("*/job.json"):
            import json

            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] in ("queued", "running"):
                job.update(
                    status="interrupted",
                    finished=time.time(),
                    note="Server stopped; inspect outputs before resubmitting. No automatic duplicate slicing.",
                )
                atomic_json(path, job)

    async def capabilities(self, refresh: bool = False) -> dict:
        if self._capabilities and not refresh:
            return self._capabilities
        if not self.binary:
            return {
                "available": False,
                "reason": "Set ORCA_SLICER_BIN to the installed OrcaSlicer executable",
                "flags": [],
            }
        code, output = await capture([self.binary, "--help"])
        flags = sorted(set(re.findall(r"(?<![\w-])--([a-zA-Z][\w-]*)", output)))
        if code or not flags:
            raise ValueError(f"OrcaSlicer --help failed ({code}): {output[-4000:]}")
        self._capabilities = {
            "available": True,
            "binary": self.binary,
            "flags": flags,
            "help": output,
            "probed_at": time.time(),
            "binary_mtime": Path(self.binary).stat().st_mtime,
        }
        atomic_json(self.state / "capabilities.json", self._capabilities)
        return self._capabilities

    async def submit(
        self,
        arguments: list[str],
        timeout: int = 3600,
        job_id: str | None = None,
        expected_files: dict[str, str] | None = None,
    ) -> dict:
        if not 1 <= timeout <= 86400:
            raise ValueError("Timeout must be 1..86400 seconds")
        if not arguments or len(arguments) > 1000 or any("\x00" in a for a in arguments):
            raise ValueError("Expected 1..1000 non-NUL CLI arguments")
        ident = job_id or uuid.uuid4().hex
        if not re.fullmatch(r"[0-9a-f]{32}", ident):
            raise ValueError("Invalid job ID")
        # A capability probe yields; reserve/check IDs under one lock so two
        # reconnects cannot both create the same durable job.
        async with self.submissions:
            if (self.state / ident / "job.json").exists():
                existing = self.get(ident)
                if (
                    existing["arguments"] != arguments
                    or existing["timeout"] != timeout
                    or existing.get("expected_files", {}) != (expected_files or {})
                ):
                    raise ValueError("Job ID was already used with different inputs")
                return existing
            caps = await self.capabilities(refresh=True)
            if not caps["available"]:
                raise ValueError(caps["reason"])
            for argument in arguments:
                if argument.startswith("--") and argument != "--":
                    flag = argument[2:].split("=", 1)[0]
                    if flag not in caps["flags"]:
                        raise ValueError(
                            f"Installed OrcaSlicer does not advertise --{flag}; refresh capabilities"
                        )
                elif re.match(r"^-[A-Za-z]", argument):
                    raise ValueError("Use documented long flags, not short aliases")
            folder = self.state / ident
            folder.mkdir()
            job = {
                "id": ident,
                "status": "queued",
                "arguments": arguments,
                "timeout": timeout,
                "created": time.time(),
                "directory": str(folder),
                "log": str(folder / "output.log"),
                "expected_files": expected_files or {},
            }
            atomic_json(folder / "job.json", job)
            self.tasks[ident] = asyncio.create_task(self._run(job))
            return job

    def get(self, ident: str) -> dict:
        import json

        if not re.fullmatch(r"[0-9a-f]{32}", ident):
            raise ValueError("Invalid job ID")
        path = self.state / ident / "job.json"
        if not path.is_file():
            raise ValueError("Unknown job ID")
        return json.loads(path.read_text(encoding="utf-8"))

    def read_log(self, ident: str, offset: int = 0, limit: int = 8000) -> dict:
        """Read bounded byte ranges. The returned cursor is reusable after reconnect."""
        if offset < 0 or not 1 <= limit <= 100000:
            raise ValueError("Log offset must be >= 0 and limit 1..100000 bytes")
        job = self.get(ident)
        path = Path(job["log"])
        size = path.stat().st_size if path.exists() else 0
        if offset > size:
            raise ValueError("Log offset exceeds saved log size")
        raw = b""
        if size:
            with path.open("rb") as stream:
                stream.seek(offset)
                raw = stream.read(limit)
        # Decode complete UTF-8 sequences only; leave a split suffix for the next
        # read. A caller-supplied cursor inside a sequence uses replacement text.
        end = offset + len(raw)
        import codecs

        terminal = job["status"] not in ("queued", "running")
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        text = decoder.decode(raw, final=terminal and end == size)
        pending = decoder.getstate()[0]
        end -= len(pending)
        if pending and end == offset and offset + len(raw) < size:
            raise ValueError("Log limit is too small for the next UTF-8 character")
        return {
            "id": ident,
            "status": job["status"],
            "offset": offset,
            "next_offset": end,
            "size_bytes": size,
            "text": text,
            "at_end": end == size,
            "log_truncated": job.get("log_truncated", False),
        }

    async def wait(self, ident: str, timeout: float = 10) -> dict:
        """Bounded observation: neither timeout nor caller cancellation cancels work."""
        import math

        if not math.isfinite(timeout) or not 0 <= timeout <= 30:
            raise ValueError("Wait timeout must be finite and 0..30 seconds")
        self.get(ident)
        task = self.tasks.get(ident)
        if task and not task.done() and timeout:
            await asyncio.wait({task}, timeout=timeout)
        return self.get(ident)

    async def _run(self, job: dict) -> None:
        path = Path(job["directory"]) / "job.json"
        process = None
        try:
            async with self.slots:
                # A queued batch must not silently print changed input/profile data.
                for filename, expected in job.get("expected_files", {}).items():
                    if digest(Path(filename)) != expected:
                        raise ValueError(f"Input changed while queued: {filename}")
                job.update(status="running", started=time.time())
                atomic_json(path, job)
                process = await asyncio.create_subprocess_exec(
                    self.binary,
                    *job["arguments"],
                    cwd=job["directory"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    **process_options(),
                )
                self.processes[job["id"]] = process
                job["pid"] = process.pid
                atomic_json(path, job)

                async def drain():
                    size = 0
                    with Path(job["log"]).open("wb") as log:
                        while chunk := await process.stdout.read(65536):
                            remaining = max(0, 10 * 1024 * 1024 - size)
                            if remaining:
                                log.write(chunk[:remaining])
                                log.flush()
                            size += len(chunk)
                    job["log_truncated"] = size > 10 * 1024 * 1024
                    return await process.wait()

                async with asyncio.timeout(job["timeout"]):
                    code = await drain()
                job.update(status="succeeded" if code == 0 else "failed", returncode=code)
        except TimeoutError:
            job["status"] = "timed_out"
        except asyncio.CancelledError:
            job["status"] = "cancelled"
        except Exception as exc:
            job.update(status="failed", error=str(exc))
        finally:
            if process and process.returncode is None:
                await stop_process(process)
            self.processes.pop(job["id"], None)
            job["finished"] = time.time()
            atomic_json(path, job)

    async def cancel(self, ident: str) -> dict:
        job = self.get(ident)
        task = self.tasks.get(ident)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # A queued task can be cancelled before its coroutine starts.
                job.update(status="cancelled", finished=time.time())
                atomic_json(Path(job["directory"]) / "job.json", job)
        return self.get(ident)

    async def close(self):
        for ident in list(self.tasks):
            await self.cancel(ident)
        self._lock.close()
