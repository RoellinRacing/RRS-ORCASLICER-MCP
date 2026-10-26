"""Versioned local-file protocol shared by the external client and standalone plugin."""

import hashlib
import json
import os
import re
import tempfile
from time import sleep as bridge_sleep
from pathlib import Path

BRIDGE_PROTOCOL = 1
MAX_REQUEST_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
WRITE_OPERATIONS = {"preset.update", "project.export"}


def bridge_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Expected a 32-character lowercase hexadecimal ID")
    return value


def bridge_read(path: Path, limit: int = MAX_RESPONSE_BYTES) -> dict:
    if (
        path.is_symlink()
        or any(p.is_symlink() for p in path.parents)
        or not path.is_file()
        or path.stat().st_size > limit
    ):
        raise ValueError("Missing, linked or oversized bridge document")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected bridge JSON object")
    return value


def bridge_write(path: Path, value: dict, limit: int = MAX_RESPONSE_BYTES) -> None:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(raw) > limit:
        raise ValueError("Bridge response exceeds its size limit; request a smaller page")
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("Linked bridge document rejected")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".rrs-", dir=path.parent)
    try:
        try:
            # Keep the mkstemp descriptor: fdopen would emit an untargeted open
            # audit event in the embedded host. The original open had a full path.
            pending = memoryview(raw)
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise OSError("Incomplete bridge document write")
                pending = pending[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        # NTFS can deny replacement briefly while a concurrent reader or scanner
        # holds the destination. Retry persistence only, never the native action.
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 9:
                    raise
                bridge_sleep(0.01 * (attempt + 1))
    finally:
        Path(temporary).unlink(missing_ok=True)


def bridge_fingerprint(operation: str, params: dict) -> str:
    raw = json.dumps(
        {"operation": operation, "params": params}, sort_keys=True, allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()
