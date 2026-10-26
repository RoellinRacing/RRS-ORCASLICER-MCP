"""Explicit configured print hosts; durable at-most-once dispatch, no automatic retries."""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from .storage import Files, atomic_json, digest

ACTIONS = {"start", "pause", "resume", "cancel"}


class Printers:
    def __init__(self, state: Path, transport=None):
        self.state, self.transport = state, transport

    def config(self):
        name = os.environ.get("ORCA_MCP_PRINTERS")
        if not name:
            return {}
        path = Path(name).expanduser()
        if path.stat().st_size > 128 * 1024:
            raise ValueError("Printer configuration exceeds 128 KiB")
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Expected printer configuration object")
        for ident, entry in config.items():
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ident) or not isinstance(entry, dict):
                raise ValueError("Invalid printer ID/config")
            url = urlsplit(entry.get("url", ""))
            if (
                entry.get("provider") not in ("moonraker", "octoprint")
                or url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    "Use Moonraker/OctoPrint HTTP(S) base URLs without credentials/query"
                )
            if entry.get("api_key_env") and not re.fullmatch(
                r"[A-Za-z_][A-Za-z_0-9]*", entry["api_key_env"]
            ):
                raise ValueError("Invalid API key environment variable")
        return config

    def capabilities(self):
        return {
            "printers": [
                {
                    "id": k,
                    "provider": v["provider"],
                    "operations": ["status", "upload", *sorted(ACTIONS)],
                }
                for k, v in self.config().items()
            ],
            "cloud_and_ams": "not_supported",
            "verification": "HTTP contract tests; no physical printer acceptance",
        }

    def target(self, ident):
        config = self.config()
        if ident not in config:
            raise ValueError("Unknown configured printer ID")
        entry = config[ident]
        key_env = entry.get("api_key_env")
        key = os.environ.get(key_env) if key_env else None
        if key_env and not key:
            raise ValueError("Configured API key environment variable is missing")
        headers = {"X-Api-Key": key} if key else {}
        return entry, headers

    async def request(self, entry, headers, method, path, **kwargs):
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=False, trust_env=False, transport=self.transport
        ) as client:
            async with client.stream(
                method, entry["url"].rstrip("/") + "/" + path.lstrip("/"), headers=headers, **kwargs
            ) as response:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2 * 1024**2:
                        raise ValueError("Printer response exceeds 2 MiB")
                if not 200 <= response.status_code < 300:
                    # No raw host response: some servers echo credentials in errors.
                    raise ValueError(f"Printer rejected request: HTTP {response.status_code}")
                if not data:
                    return None
                try:
                    return json.loads(data)
                except (ValueError, UnicodeDecodeError):
                    raise ValueError("Printer returned an invalid JSON acknowledgement") from None

    async def status(self, ident):
        entry, headers = self.target(ident)
        try:
            if entry["provider"] == "octoprint":
                result = await self.request(entry, headers, "GET", "api/job")
                return {
                    "printer_id": ident,
                    "provider": "octoprint",
                    "state": result.get("state"),
                    "job": result.get("job"),
                    "progress": result.get("progress"),
                }
            result = await self.request(
                entry,
                headers,
                "GET",
                "printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed&toolhead",
            )
            return {
                "printer_id": ident,
                "provider": "moonraker",
                "objects": result.get("result", {}).get("status", {}),
            }
        except httpx.HTTPError:
            raise ValueError("Printer transport failed; no command was issued") from None

    def receipt_path(self, request_id):
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("request_id must be 32 lowercase hexadecimal characters")
        return self.state / f"{request_id}.json"

    def result(self, request_id):
        path = self.receipt_path(request_id)
        if not path.is_file():
            raise ValueError("Unknown printer request ID")
        result = json.loads(path.read_text())
        if result["status"] == "dispatching":
            return {
                **result,
                "status": "outcome_unknown",
                "notice": "May be running or interrupted; inspect printer state before any new command",
            }
        return result

    async def dispatch(
        self,
        ident,
        request_id,
        action,
        remote_name=None,
        files: Files | None = None,
        source=None,
        expected=None,
    ):
        entry, headers = self.target(ident)
        if action not in ACTIONS | {"upload"}:
            raise ValueError("Unsupported printer operation")
        if action in ("upload", "start"):
            if not isinstance(remote_name, str) or not re.fullmatch(
                r"[A-Za-z0-9_.-]{1,120}\.gcode", remote_name
            ):
                raise ValueError("remote_name needs a simple ASCII .gcode filename")
        elif remote_name is not None:
            raise ValueError("This action does not accept a filename")
        # Snapshot uploads before committing dispatch so source changes cannot alter
        # the bytes associated with this request's fingerprint.
        upload = None
        if action == "upload":
            src = files.path(source, True)
            if src.suffix.lower() != ".gcode" or src.stat().st_size > 256 * 1024**2:
                raise ValueError("Upload requires text .gcode up to 256 MiB")
            upload = tempfile.SpooledTemporaryFile(max_size=1024**2)
            try:
                with src.open("rb") as inp:
                    import shutil

                    shutil.copyfileobj(inp, upload)
                upload.seek(0)
                calculated = hashlib.file_digest(upload, "sha256").hexdigest()
                upload.seek(0)
                if expected != calculated or digest(src) != expected:
                    raise ValueError("G-code source changed; read checksum again")
            except BaseException:
                upload.close()
                raise
        try:
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "printer": ident,
                        "provider": entry["provider"],
                        "url": entry["url"],
                        "action": action,
                        "filename": remote_name,
                        "sha256": expected,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            path = self.receipt_path(request_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "request_id": request_id,
                "printer_id": ident,
                "action": action,
                "filename": remote_name,
                "fingerprint": fingerprint,
                "status": "dispatching",
                "time": time.time(),
            }
            try:
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(record))
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                previous = self.result(request_id)
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("Printer request ID belongs to different parameters") from None
                return previous
            try:
                if action == "upload":
                    route = (
                        "api/files/local"
                        if entry["provider"] == "octoprint"
                        else "server/files/upload"
                    )
                    data = (
                        {"select": "false", "print": "false"}
                        if entry["provider"] == "octoprint"
                        else {"root": "gcodes", "print": "false"}
                    )
                    await self.request(
                        entry,
                        headers,
                        "POST",
                        route,
                        data=data,
                        files={"file": (remote_name, upload, "application/octet-stream")},
                    )
                elif entry["provider"] == "octoprint":
                    route, body = "api/job", {"command": action}
                    if action == "start":
                        route, body = (
                            "api/files/local/" + quote(remote_name, safe=""),
                            {"command": "select", "print": True},
                        )
                    elif action in ("pause", "resume"):
                        body = {"command": "pause", "action": action}
                    await self.request(entry, headers, "POST", route, json=body)
                else:
                    await self.request(
                        entry,
                        headers,
                        "POST",
                        "printer/print/" + action,
                        json={"filename": remote_name} if action == "start" else {},
                    )
            except (httpx.HTTPError, ValueError):
                # Even an HTTP error may follow a provider side effect. Never retry.
                result = {
                    **record,
                    "status": "outcome_unknown",
                    "notice": "No reliable acknowledgement; inspect printer before issuing another command",
                }
            else:
                result = {
                    **record,
                    "status": "acknowledged",
                    "device_state_verified": False,
                    "notice": "Provider acknowledged the request; query printer_status for actual state",
                }
            atomic_json(path, result)
            return result
        finally:
            if upload is not None:
                upload.close()
