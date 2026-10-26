"""Host-side allowlisted operations. GUI reads and Script-worker mutations stay separate."""

import collections
import hmac
import secrets
import time
import uuid
import math
import threading
from pathlib import Path

from .protocol import (
    BRIDGE_PROTOCOL,
    hashlib,
    json,
    MAX_REQUEST_BYTES,
    bridge_fingerprint,
    bridge_id,
    bridge_read,
    bridge_write,
)


class SliceEvents:
    """Bounded copied observations, never retain ctx/Print/Model native references."""

    def __init__(self):
        self.lock = threading.Lock()
        self.epoch = uuid.uuid4().hex
        self.sequence = 0
        self.events = collections.deque(maxlen=512)

    def observe(self, ctx):
        event = {
            "time": time.time(),
            "step": str(ctx.step),
            "orca_version": str(ctx.orca_version),
            "cancelled": bool(ctx.cancelled()),
            "object_id": ctx.object.id() if ctx.object is not None else None,
            "postprocess": bool(getattr(ctx, "gcode_path", "")),
        }
        with self.lock:
            self.sequence += 1
            self.events.append({"sequence": self.sequence, **event})

    def read(self, after=0, limit=100):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("after >= 0 and limit 1..200 required")
        with self.lock:
            first = self.events[0]["sequence"] if self.events else self.sequence + 1
            return {
                "epoch": self.epoch,
                "latest_sequence": self.sequence,
                "oldest_sequence": first,
                "gap": after < first - 1,
                "events": [dict(e) for e in self.events if e["sequence"] > after][:limit],
                "selection_required": "RRS MCP slicing observer in process slicing_pipeline_plugin",
                "notice": "Stage observations, not percent progress or proof of a physical print",
            }


SLICE_EVENTS = SliceEvents()


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
        if hasattr(host, "ModelObject") and hasattr(host.ModelObject, "volume"):
            result.extend(["model.detail", "scene.read"])
        if hasattr(host, "selected_printer"):
            result.append("printer.read")
        if hasattr(getattr(self.orca, "slicing", None), "SlicingPipelineCapabilityBase"):
            result.append("slicing.events")
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
        if operation == "scene.read":
            model = host.model()
            if model.object_count() > 50:
                raise ValueError("Native GUI workflows currently support up to 50 objects")
            objects = []
            for index in range(model.object_count()):
                obj = model.object(index)
                if obj.volume_count() > 50 or obj.instance_count() > 50:
                    raise ValueError(
                        "Native GUI workflows support up to 50 volumes/instances per object"
                    )
                detail = self.read_or_export(
                    "model.detail", {"index": index, "object_id": obj.id(), "limit": 50}
                )
                for item in detail["volumes"]:
                    box = obj.volume(item["index"]).bounding_box()
                    item["bounds_mm"] = (
                        {"min": list(box.min), "max": list(box.max)} if box.defined else None
                    )
                objects.append(detail)

            def normalize(value):
                if isinstance(value, float):
                    return 0.0 if abs(value) < 1e-10 else round(value, 9)
                if isinstance(value, list):
                    return [normalize(v) for v in value]
                if isinstance(value, dict):
                    return {k: normalize(v) for k, v in value.items()}
                return value

            objects = normalize(objects)
            raw = json.dumps(objects, sort_keys=True, allow_nan=False).encode()
            return {
                "revision": hashlib.sha256(raw).hexdigest(),
                "objects": objects,
                "app": host.app_info(),
                "revision_scope": "Copied identities, poses, bounds, facet counts and exposed settings; not a full mesh-content hash",
            }
        if operation == "printer.read":
            return {"printer": host.selected_printer(), "physical_print_started": False}
        if operation == "slicing.events":
            return SLICE_EVENTS.read(params.get("after", 0), params.get("limit", 100))
        if operation == "model.detail":
            model = host.model()
            index = params.get("index")
            if type(index) is not int or not 0 <= index < model.object_count():
                raise ValueError("Object index out of range")
            obj = model.object(index)
            if obj.id() != params.get("object_id"):
                raise ValueError("Object identity changed; read model again")
            offset, limit = params.get("offset", 0), params.get("limit", 20)
            if (
                type(offset) is not int
                or offset < 0
                or type(limit) is not int
                or not 1 <= limit <= 50
            ):
                raise ValueError("offset >= 0 and limit 1..50 required")

            def pose(handle):
                return {
                    key: list(getattr(handle, key)())
                    for key in ("offset", "rotation", "scaling_factor", "mirror")
                }

            volumes = []
            for n in range(offset, min(obj.volume_count(), offset + limit)):
                vol = obj.volume(n)
                volumes.append(
                    {
                        "index": n,
                        "id": vol.id(),
                        "name": vol.name,
                        "type": str(vol.type()),
                        "extruder_id": vol.extruder_id(),
                        "facets": vol.facets_count(),
                        "manifold": vol.is_manifold(),
                        "mesh_errors": vol.mesh_errors_count(),
                        **pose(vol),
                        "settings": host_values(vol, {"limit": 100}),
                    }
                )
            instances = []
            for n in range(offset, min(obj.instance_count(), offset + limit)):
                instance = obj.instance(n)
                instances.append(
                    {
                        "index": n,
                        "id": instance.id(),
                        "printable": instance.is_printable(),
                        **pose(instance),
                    }
                )
            return {
                "index": index,
                "id": obj.id(),
                "name": obj.name,
                "volume_count": obj.volume_count(),
                "instance_count": obj.instance_count(),
                "volumes": volumes,
                "instances": instances,
                "offset": offset,
                "rotation_unit": "radians",
                "offset_unit": "millimeters",
            }
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
