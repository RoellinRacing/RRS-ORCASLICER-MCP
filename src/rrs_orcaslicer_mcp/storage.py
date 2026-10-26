"""Lossless settings edits with optimistic concurrency and recoverable backups."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".rrs-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path: Path, data: object) -> None:
    atomic_bytes(
        path, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    )


def check_revision(path: Path, expected: str | None) -> None:
    if path.exists():
        if not expected or digest(path) != expected:
            raise ValueError(
                "Existing destination requires its current SHA256; read it again first"
            )
    elif expected is not None:
        raise ValueError("Expected an existing destination, but it no longer exists")


class Files:
    def __init__(self, roots: list[Path]):
        self.roots = [p.expanduser().resolve() for p in roots]

    def path(self, name: str, exists: bool = False) -> Path:
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = self.roots[0] / path
        path = path.resolve()
        if not any(path == root or root in path.parents for root in self.roots):
            raise ValueError("Path outside configured ORCA_MCP_ROOTS")
        if exists and not path.is_file():
            raise ValueError(f"File not found: {path}")
        return path

    def read(self, name: str) -> dict:
        path = self.path(name, True)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("JSON exceeds 32 MiB")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        return {"path": str(path), "sha256": digest(path), "settings": data}

    def write(self, name: str, changes: dict, remove: list[str], expected: str | None) -> dict:
        path = self.path(name)
        check_revision(path, expected)
        data = self.read(name)["settings"] if path.exists() else {}
        for key in remove:
            data.pop(key, None)
        data.update(changes)
        # Validate before creating backup or touching the destination.
        encoded = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        backup = None
        if path.exists():
            backup = path.with_name(path.name + "." + digest(path)[:16] + ".bak")
            atomic_bytes(backup, path.read_bytes())
        atomic_bytes(path, encoded)
        return {**self.read(name), "backup": str(backup) if backup else None}
