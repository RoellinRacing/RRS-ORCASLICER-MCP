"""External MCP side of the host mailbox. Never retries a mutation automatically."""

import asyncio
import os
import time
import uuid
from pathlib import Path

from .protocol import (
    BRIDGE_PROTOCOL,
    MAX_REQUEST_BYTES,
    WRITE_OPERATIONS,
    bridge_fingerprint,
    bridge_id,
    bridge_read,
    bridge_write,
)


class HostClient:
    def __init__(self, directory: Path | None = None):
        configured = directory or os.environ.get("ORCA_MCP_BRIDGE")
        self.directory = Path(configured).expanduser().resolve() if configured else None

    def _session(self) -> dict:
        if self.directory is None:
            raise ValueError("Set ORCA_MCP_BRIDGE to the path shown by the running host plugin")
        session = bridge_read(self.directory / "session.json")
        if session.get("protocol") != BRIDGE_PROTOCOL:
            raise ValueError("Unsupported host-bridge protocol")
        bridge_id(session.get("session_id"))
        if not isinstance(session.get("token"), str) or len(session["token"]) < 32:
            raise ValueError("Invalid host-bridge session token")
        return session

    def status(self) -> dict:
        if self.directory is None:
            return {"configured": False, "online": False}
        try:
            session = self._session()
            return {
                k: v
                for k, v in {
                    **session,
                    "configured": True,
                    "online": session.get("state") == "online"
                    and 0 <= time.time() - session.get("last_seen", 0) <= 15,
                    "directory": str(self.directory),
                }.items()
                if k != "token"
            }
        except (OSError, ValueError, TypeError) as exc:
            return {"configured": True, "online": False, "reason": str(exc)}

    def result(self, session_id: str, request_id: str) -> dict:
        if self.directory is None:
            raise ValueError("Bridge is not configured")
        folder = self.directory / bridge_id(session_id)
        ident = bridge_id(request_id)
        response = folder / "responses" / f"{ident}.json"
        if response.exists():
            return bridge_read(response)
        journal = folder / "journal" / f"{ident}.json"
        if journal.exists():
            return bridge_read(journal)
        return {
            "request_id": ident,
            "session_id": session_id,
            "status": "not_observed",
            "notice": "No execution receipt. Do not assume a mutation failed or retry with a new ID without checking Orca.",
        }

    async def call(
        self,
        operation: str,
        params: dict,
        timeout: int = 30,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        if not 1 <= timeout <= 120:
            raise ValueError("Timeout must be 1..120 seconds")
        session = self._session()
        if (
            session.get("state") != "online"
            or not 0 <= time.time() - session.get("last_seen", 0) <= 15
        ):
            raise ValueError("Host plugin is offline or its heartbeat is stale")
        if operation in WRITE_OPERATIONS and (session_id is None or request_id is None):
            raise ValueError("Mutations require the current session_id and an explicit request_id")
        if session_id is not None and session_id != session["session_id"]:
            raise ValueError(
                "Host session changed; inspect the previous receipt before submitting new work"
            )
        sid = session["session_id"]
        ident = bridge_id(request_id or uuid.uuid4().hex)
        folder = self.directory / sid
        path = folder / "requests" / f"{ident}.json"
        fingerprint = bridge_fingerprint(operation, params)
        if path.exists():
            previous = bridge_read(path, MAX_REQUEST_BYTES)
            if previous.get("fingerprint") != fingerprint:
                raise ValueError(
                    "Request ID already belongs to a different operation or parameters"
                )
        else:
            bridge_write(
                path,
                {
                    "protocol": BRIDGE_PROTOCOL,
                    "session_id": sid,
                    "request_id": ident,
                    "token": session["token"],
                    "operation": operation,
                    "params": params,
                    "fingerprint": fingerprint,
                    "expires": time.time() + timeout,
                },
                MAX_REQUEST_BYTES,
            )
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            result = self.result(sid, ident)
            if result.get("status") in ("succeeded", "failed", "rejected"):
                if result.get("fingerprint") != fingerprint:
                    raise ValueError("Host receipt does not match the submitted request")
                return result
            await asyncio.sleep(0.1)
        return {
            "request_id": ident,
            "session_id": sid,
            "status": "outcome_unknown",
            "notice": "Client timed out. A native dialog or started operation may still finish. Query host_request_status with these IDs; do not repeat the mutation under a new ID.",
        }
