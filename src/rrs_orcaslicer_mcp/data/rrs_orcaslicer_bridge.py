# ruff: noqa: E402
# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.orcaslicer.plugin]
# name = "RRS OrcaSlicer Bridge"
# description = "Local MCP bridge: live project/preset reads and staged preset transactions."
# author = "RoellinRacing"
# version = "0.3.0"
# ///
"""Generated standalone plugin for the official Orca Python host.

Source, architecture and tests: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
AGPL-3.0-or-later. No network listener, arbitrary eval or printer-control endpoint.
Start with Plugins -> Run. Closing its panel stops new requests.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from time import sleep as worker_sleep
import html

import orca

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

"""Host-side allowlisted operations. GUI reads and Script-worker mutations stay separate."""

import collections
import hmac
import secrets
import time
import uuid
import math
from pathlib import Path



def secret_setting(key: str) -> bool:
    lowered = key.lower()
    return any(
        part in lowered
        for part in ("password", "passwd", "token", "api_key", "apikey", "access_code", "secret")
    )


def host_values(preset, params: dict) -> dict:
    keys = sorted(preset.config_keys())
    requested = params.get("keys")
    offset, limit = (
        max(0, int(params.get("offset", 0))),
        min(200, max(1, int(params.get("limit", 100)))),
    )
    if requested is not None:
        if (
            not isinstance(requested, list)
            or len(requested) > 200
            or any(not isinstance(k, str) for k in requested)
        ):
            raise ValueError("keys must be a list of at most 200 strings")
        selected = requested
    else:
        selected = keys[offset : offset + limit]
    return {
        "total_keys": len(keys),
        "offset": offset,
        "values": {
            k: "[redacted]" if secret_setting(k) else preset.config_value(k) for k in selected
        },
    }


class HostService:
    def __init__(self, orca_module, directory: Path, export_roots: list[Path]):
        self.orca = orca_module
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.export_roots = [p.expanduser().resolve() for p in export_roots]
        self.session_id = uuid.uuid4().hex
        self.token = secrets.token_hex(32)
        self.folder = self.directory / self.session_id
        self.queue = collections.deque()
        self.busy = False
        self.closed = False
        self.seen = set()
        self.last_heartbeat = 0
        self.capabilities = self.detect()

    def detect(self) -> list[str]:
        host = self.orca.host
        result = ["bridge.ping"]
        for name, attr in (
            ("host.snapshot", "plater"),
            ("model.read", "model"),
            ("presets.list", "preset_bundle"),
            ("preset.read", "preset_bundle"),
        ):
            if hasattr(host, attr):
                result.append(name)
        # Export and transaction support are checked against concrete handles at
        # execution. The transaction API is opt-in and advertised only when bound.
        if hasattr(host, "Plater") and hasattr(host.Plater, "export_3mf_copy"):
            result.append("project.export")
        preset = getattr(host, "preset", None)
        if preset is not None and all(
            hasattr(getattr(preset, kind, None), "begin_update")
            for kind in ("process", "printer", "filament")
        ):
            result.append("preset.update")
        return result

    def heartbeat(self, state: str = "online") -> None:
        self.last_heartbeat = time.time()
        bridge_write(
            self.directory / "session.json",
            {
                "protocol": BRIDGE_PROTOCOL,
                "session_id": self.session_id,
                "token": self.token,
                "state": state,
                "last_seen": time.time(),
                "capabilities": self.capabilities,
                "preset_updates_saved": False,
            },
        )

    def receipt(self, request: dict, status: str, **fields) -> None:
        value = {
            "session_id": self.session_id,
            "request_id": request["request_id"],
            "fingerprint": request.get("fingerprint"),
            "status": status,
            "updated": time.time(),
            **fields,
        }
        bridge_write(self.folder / "journal" / f"{request['request_id']}.json", value)
        if status in ("succeeded", "failed", "rejected"):
            bridge_write(self.folder / "responses" / f"{request['request_id']}.json", value)

    def poll_ui(self) -> None:
        if self.closed:
            return
        if time.time() - self.last_heartbeat >= 2:
            self.heartbeat()
        if self.busy:
            return
        requests = self.folder / "requests"
        if not requests.is_dir():
            return
        pending = (p for p in sorted(requests.glob("*.json")) if p.name not in self.seen)
        for index, path in enumerate(pending):
            if index >= 8:
                break
            ident = path.stem
            try:
                self.seen.add(path.name)  # Immutable documents, including malformed ones.
                bridge_id(ident)
                if (self.folder / "journal" / path.name).exists():
                    self.seen.add(path.name)
                    continue  # Includes indeterminate operations after a crash.
                request = bridge_read(path, MAX_REQUEST_BYTES)
                if (
                    request.get("request_id") != ident
                    or request.get("session_id") != self.session_id
                    or request.get("protocol") != BRIDGE_PROTOCOL
                ):
                    continue
                if not hmac.compare_digest(str(request.get("token", "")), self.token):
                    continue
                self.seen.add(path.name)
                if not isinstance(request.get("params"), dict) or request.get(
                    "fingerprint"
                ) != bridge_fingerprint(request.get("operation"), request["params"]):
                    self.receipt(request, "rejected", error="Invalid request fingerprint")
                    continue
                expires = request.get("expires")
                if (
                    type(expires) not in (int, float)
                    or not math.isfinite(expires)
                    or expires < time.time()
                    or expires > time.time() + 300
                ):
                    self.receipt(request, "rejected", error="Request expired before execution")
                    continue
                if request["operation"] not in self.capabilities:
                    self.receipt(request, "rejected", error="Operation not supported by this host")
                    continue
                if request["operation"] == "preset.update":
                    self.receipt(request, "accepted")
                    self.queue.append(request)
                else:
                    self.execute(request, worker=False)
            except (OSError, ValueError, TypeError):
                # Unauthenticated or malformed mailbox data never calls the host.
                continue

    def poll_worker(self) -> None:
        if self.closed or not self.queue or self.busy:
            return
        request = self.queue.popleft()
        if request["expires"] < time.time():
            self.receipt(request, "rejected", error="Request expired before worker execution")
            return
        self.busy = True
        try:
            self.execute(request, worker=True)
        finally:
            self.busy = False

    def execute(self, request: dict, worker: bool) -> None:
        self.receipt(request, "started")  # Durable before any host-side effect.
        try:
            data = (
                self.update(request["params"])
                if worker
                else self.read_or_export(request["operation"], request["params"])
            )
        except Exception as exc:
            # Native execution failed; persistence failures remain indeterminate.
            self.receipt(request, "failed", error=str(exc), error_type=type(exc).__name__)
        else:
            # Do not relabel an applied native effect as failed if saving its
            # success receipt fails. The durable started journal remains honest.
            self.receipt(request, "succeeded", result=data)

    def collection(self, kind: str):
        attribute = {"process": "prints", "printer": "printers", "filament": "filaments"}.get(kind)
        if not attribute:
            raise ValueError("kind must be process, printer or filament")
        return getattr(self.orca.host.preset_bundle(), attribute)

    def read_or_export(self, operation: str, params: dict) -> dict:
        host = self.orca.host
        if operation == "bridge.ping":
            return {"protocol": BRIDGE_PROTOCOL, "capabilities": self.capabilities}
        if operation == "host.snapshot":
            plater = host.plater()
            bundle = host.preset_bundle()
            return {
                "app": host.app_info() if hasattr(host, "app_info") else {"version": "not_exposed"},
                "project_dirty": plater.is_project_dirty(),
                "project_path": plater.project_path() if hasattr(plater, "project_path") else None,
                "presets_dirty": plater.is_presets_dirty(),
                "object_count": host.model().object_count(),
                "selected_process": bundle.current_process_preset().name,
                "selected_printer": bundle.current_printer_preset().name,
                "filament_presets": list(bundle.current_filament_preset_names()),
            }
        if operation == "presets.list":
            collection = self.collection(params["kind"])
            names = [
                n
                for n in collection.preset_names()
                if str(params.get("query", "")).lower() in n.lower()
            ]
            offset, limit = (
                max(0, int(params.get("offset", 0))),
                max(1, min(200, int(params.get("limit", 100)))),
            )
            return {
                "total": len(names),
                "names": names[offset : offset + limit],
                "selected": collection.get_selected_preset_name(),
            }
        if operation == "preset.read":
            collection = self.collection(params["kind"])
            preset = (
                collection.find_preset(params["name"])
                if params.get("name")
                else collection.get_edited_preset()
            )
            if preset is None:
                raise ValueError("Preset not found")
            return {"name": preset.name, "dirty": preset.is_dirty, **host_values(preset, params)}
        if operation == "model.read":
            model = host.model()
            offset, limit = (
                max(0, int(params.get("offset", 0))),
                max(1, min(50, int(params.get("limit", 20)))),
            )
            objects = []
            for index in range(offset, min(model.object_count(), offset + limit)):
                obj = model.object(index)
                objects.append(
                    {
                        "index": index,
                        "id": obj.id(),
                        "name": obj.name,
                        "volume_count": obj.volume_count(),
                        "instance_count": obj.instance_count(),
                        "facets": obj.facets_count(),
                        "painted_supports": obj.is_fdm_support_painted(),
                        "painted_seams": obj.is_seam_painted(),
                        "painted_materials": obj.is_mm_painted(),
                        "settings": host_values(obj, {"limit": 100}),
                    }
                )
            return {"total": model.object_count(), "objects": objects}
        if operation == "project.export":
            path = Path(params["destination"]).expanduser()
            if not path.is_absolute():
                raise ValueError("Export needs an absolute path")
            path = path.resolve()
            if path.suffix.lower() != ".3mf" or not any(
                root in path.parents for root in self.export_roots
            ):
                raise ValueError("Export must be a .3mf inside configured export_roots")
            if path.exists():
                raise ValueError("Export destination already exists")
            path.parent.mkdir(parents=True, exist_ok=True)
            host.plater().export_3mf_copy(str(path))
            return {
                "path": str(path),
                "bytes": path.stat().st_size,
                "project_saved_state_changed": False,
            }
        raise ValueError("Unsupported host operation")

    def update(self, params: dict) -> dict:
        kind, name, changes = params.get("kind"), params.get("preset_name"), params.get("changes")
        if kind not in ("process", "printer", "filament") or not isinstance(name, str) or not name:
            raise ValueError("Mutation requires a kind and explicit preset_name")
        if (
            not isinstance(changes, dict)
            or not 1 <= len(changes) <= 200
            or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or secret_setting(k)
                for k, v in changes.items()
            )
        ):
            raise ValueError("Provide 1..200 non-secret serialized string settings")
        editor = getattr(self.orca.host.preset, kind)
        if kind == "filament":
            slot = params.get("slot")
            if type(slot) is not int or slot < 1:
                raise ValueError("Filament updates require a 1-based slot")
            transaction = editor.begin_update(slot, name)
        else:
            transaction = editor.begin_update(name)
        for key, value in changes.items():
            transaction.set(key, value)
        outcome = transaction.commit()
        return {
            "target_name": outcome.target_name,
            "category": outcome.category,
            "keys": list(outcome.keys),
            "dirty": outcome.dirty,
            "selection_changed": outcome.selection_changed,
            "slot_assignment_changed": outcome.slot_assignment_changed,
            "shared_slots": list(outcome.shared_slots),
            "saved_to_disk": False,
        }

    def close(self) -> None:
        self.closed = True
        while self.queue:
            self.receipt(
                self.queue.popleft(), "rejected", error="Bridge closed before worker execution"
            )
        self.heartbeat("offline")



class RRSHostBridge(orca.script.ScriptPluginCapabilityBase):
    def get_name(self):
        return "RRS MCP local bridge"

    def get_default_config(self):
        return {"export_roots": []}

    def _message(self, message):
        if not self.stopping and (message or {}).get("command") == "tick":
            self.service.poll_ui()

    def execute(self):
        if getattr(self, "running", False):
            return orca.ExecutionResult.skipped("Bridge is already running")
        self.running = True
        self.stopping = False
        self.service = None
        self.window = None
        try:
            storage = Path(orca.host.plugin.storage()) / "rrs-mcp-bridge"
            config = json.loads(self.get_config())
            roots = config.get("export_roots", [])
            if not isinstance(roots, list) or any(
                not isinstance(p, str) or not Path(p).expanduser().is_absolute() for p in roots
            ):
                raise ValueError("export_roots must contain absolute directory paths")
            self.service = HostService(
                orca, storage, [storage / "exports"] + [Path(p) for p in roots]
            )
            self.service.heartbeat("starting")
            page = """<!doctype html><meta charset="utf-8"><title>RRS MCP Bridge</title>
              <style>body{font:15px system-ui;padding:20px;overflow-wrap:anywhere}code{display:block;padding:12px;background:#ddd;color:#222}button{padding:8px}</style>
              <h2>RRS MCP local bridge</h2><p>The bridge is active while this panel stays open.</p>
              <p>Set ORCA_MCP_BRIDGE in your MCP client to:</p><code>__STORE__</code>
              <p>Preset changes remain unsaved. Orca's native validation and unsaved-edit dialogs apply.</p>
              <p>Close this window to stop new requests. A started native transaction may still finish.</p>
              <script>setInterval(()=>{if(window.orca)orca.postMessage({command:'tick'});},250);</script>"""
            self.window = orca.host.ui.create_window(
                html=page.replace("__STORE__", html.escape(str(storage))),
                title="RRS MCP Bridge",
                width=650,
                height=430,
                on_message=self._message,
                on_close=lambda: setattr(self, "stopping", True),
            )
            while not self.stopping and self.window.is_open():
                self.service.poll_worker()
                worker_sleep(0.1)
            return orca.ExecutionResult.success("RRS MCP bridge stopped")
        finally:
            try:
                if self.service is not None:
                    self.service.close()
            finally:
                try:
                    if self.window is not None and self.window.is_open():
                        self.window.close()
                finally:
                    self.running = False

    def on_cancelled(self):
        self.stopping = True


@orca.plugin
class RRSBridgePackage(orca.base):
    def register_capabilities(self):
        orca.register_capability(RRSHostBridge)
