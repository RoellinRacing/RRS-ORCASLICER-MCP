"""Durable batch manifests with deterministic job IDs and content-sensitive idempotency."""

import asyncio
import collections
import hashlib
import json
import re
import time
from pathlib import Path

from .engine import Engine
from .storage import atomic_json


class Batches:
    def __init__(self, directory: Path, engine: Engine):
        self.directory = directory
        self.engine = engine
        self.lock = asyncio.Lock()

    def path(self, ident: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", ident):
            raise ValueError("Invalid batch ID")
        return self.directory / f"{ident}.json"

    def get(self, ident: str) -> dict:
        path = self.path(ident)
        if not path.is_file():
            raise ValueError("Unknown batch ID")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        jobs = []
        for entry in manifest["entries"]:
            if (self.engine.state / entry["job_id"] / "job.json").is_file():
                job = self.engine.get(entry["job_id"])
                jobs.append(
                    {
                        **entry,
                        "status": job["status"],
                        "error": job.get("error"),
                        "returncode": job.get("returncode"),
                        "log": job.get("log"),
                    }
                )
            else:
                jobs.append(
                    {
                        **entry,
                        "status": "cancelled"
                        if manifest.get("cancel_requested")
                        else "not_submitted",
                    }
                )
        counts = collections.Counter(j["status"] for j in jobs)
        if counts["running"] or counts["queued"]:
            status = "running"
        elif counts["not_submitted"]:
            status = "incomplete"
        elif counts["succeeded"] == len(jobs):
            status = "succeeded"
        elif counts["cancelled"] == len(jobs):
            status = "cancelled"
        else:
            status = "completed_with_errors"
        return {**manifest, "status": status, "counts": dict(counts), "entries": jobs}

    async def create(
        self,
        key: str,
        request: dict,
        entries: list[dict],
        timeout: int,
        expected_files: dict[str, str],
    ) -> dict:
        if not 1 <= len(key) <= 200 or not key.strip():
            raise ValueError("Supply an idempotency key of 1..200 characters")
        if not entries or len(entries) > 64:
            raise ValueError("A batch needs 1..64 inputs")
        ident = hashlib.sha256(key.encode()).hexdigest()[:32]
        fingerprint = hashlib.sha256(
            json.dumps(
                {"request": request, "files": expected_files, "timeout": timeout}, sort_keys=True
            ).encode()
        ).hexdigest()
        async with self.lock:
            path = self.path(ident)
            if path.exists():
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if manifest["fingerprint"] != fingerprint:
                    raise ValueError(
                        "Idempotency key conflicts with changed inputs, profiles or parameters"
                    )
                if manifest.get("cancel_requested"):
                    return self.get(ident)
            else:
                manifest = {
                    "id": ident,
                    "fingerprint": fingerprint,
                    "created": time.time(),
                    "request": request,
                    "entries": [
                        {
                            **entry,
                            "job_id": hashlib.sha256(f"{ident}:{i}".encode()).hexdigest()[:32],
                        }
                        for i, entry in enumerate(entries)
                    ],
                }
                atomic_json(path, manifest)
            # Manifest exists before any job. Each job is durably saved before it
            # starts; reusing a key returns it instead of repeating completed work.
            try:
                for entry in manifest["entries"]:
                    if not (
                        self.engine.state / entry["job_id"] / "job.json"
                    ).exists() and entry.get("output_directory"):
                        # Orca's create_directory handles only a single level.
                        Path(entry["output_directory"]).mkdir(parents=True, exist_ok=True)
                    await self.engine.submit(
                        entry["arguments"],
                        timeout,
                        job_id=entry["job_id"],
                        expected_files=entry.get("expected_files", expected_files),
                    )
            except (ValueError, OSError, TimeoutError) as exc:
                manifest["submission_error"] = str(exc)
                atomic_json(path, manifest)
                raise
            manifest.pop("submission_error", None)
            atomic_json(path, manifest)
            return self.get(ident)

    async def cancel(self, ident: str) -> dict:
        async with self.lock:
            manifest = self.get(ident)
            manifest.pop("status", None)
            manifest.pop("counts", None)
            manifest["cancel_requested"] = True
            atomic_json(self.path(ident), manifest)
            for entry in manifest["entries"]:
                if entry["status"] != "not_submitted":
                    await self.engine.cancel(entry["job_id"])
            return self.get(ident)
