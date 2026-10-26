"""Typed stock-Orca workflows with native readback and durable no-repeat receipts."""

import asyncio
import hashlib
import json
import math
import sys
import time
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.parsers import expat

from .host_bridge.protocol import bridge_id
from .native_ui import NativeControls
from .storage import Files, atomic_json, digest

CALIBRATIONS = {
    "temperature": ("Temperature", [("start", "Start temp"), ("end", "End temp")]),
    "pressure_advance": (
        "Pressure advance",
        [("start", "Start PA"), ("end", "End PA"), ("step", "PA step")],
    ),
    "max_volumetric_speed": (
        "Max flowrate",
        [("start", "Start volumetric speed"), ("end", "End volumetric speed"), ("step", "Step")],
    ),
    "retraction": (
        "Retraction",
        [("start", "Start retraction length"), ("end", "End retraction length"), ("step", "Step")],
    ),
    "vfa": ("VFA", [("start", "Start speed"), ("end", "End speed"), ("step", "Step")]),
    "cornering": ("Cornering", [("start", "Start"), ("end", "End")]),
    "flow_ratio": ("Flow ratio", []),
    "input_shaping_frequency": (
        "Input Shaping Frequency",
        [
            ("x_start", "X Start End", 0),
            ("x_end", "X Start End", 1),
            ("y_start", "Y Start End", 0),
            ("y_end", "Y Start End", 1),
        ],
    ),
    "input_shaping_damping": (
        "Input Shaping Damping/zeta factor",
        [
            ("freq_x", "Frequency X Y", 0),
            ("freq_y", "Frequency X Y", 1),
            ("start", "Damp Start End", 0),
            ("end", "Damp Start End", 1),
        ],
    ),
}


def validate_calibration(kind, parameters):
    if kind not in CALIBRATIONS or not isinstance(parameters, dict):
        raise ValueError("Unknown native calibration kind")
    fields = {f[0] for f in CALIBRATIONS[kind][1]}
    allowed = (
        fields
        | ({"method"} if kind == "pressure_advance" else set())
        | ({"test"} if kind == "flow_ratio" else set())
    )
    if set(parameters) - allowed or fields - set(parameters):
        raise ValueError(
            f"Native {kind} needs numeric fields {sorted(fields)} and known options only"
        )
    for field in fields:
        value = parameters[field]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Calibration values must be finite nonnegative numbers")
    if kind == "temperature":
        if (
            any(parameters[k] != int(parameters[k]) for k in fields)
            or not 155 <= parameters["end"] <= parameters["start"] - 5 <= 495
        ):
            raise ValueError(
                "Native temperature: integer Celsius, 155 <= end <= start-5, start <= 500"
            )
        if (parameters["start"] - parameters["end"]) % 5:
            raise ValueError("Native temperature tower uses fixed 5 C steps")
    elif {"start", "end"} <= fields:
        if parameters["end"] <= parameters["start"]:
            raise ValueError("Calibration end must exceed start")
        if "step" in fields and (
            parameters["step"] <= 0
            or (parameters["end"] - parameters["start"]) / parameters["step"] > 200
        ):
            raise ValueError("Supply a positive step and at most 200 segments")
    if kind == "pressure_advance":
        if (
            parameters["end"] > 2
            or parameters["step"] < 0.001
            or parameters.get("method", "tower") not in ("tower", "line", "pattern")
        ):
            raise ValueError("Native PA: end <= 2, step >= 0.001; method tower/line/pattern")
    if kind == "flow_ratio" and parameters.get("test", "pass_1") not in (
        "pass_1",
        "pass_2",
        "yolo",
        "yolo_perfectionist",
    ):
        raise ValueError("Unknown native flow-ratio test")
    if kind == "input_shaping_frequency" and not all(0 < parameters[k] <= 500 for k in fields):
        raise ValueError("Input shaping frequency range is 0..500 Hz")
    if kind == "input_shaping_damping" and not (
        0 <= parameters["start"] < parameters["end"] <= 1
        and 0 < parameters["freq_x"] <= 500
        and 0 < parameters["freq_y"] <= 500
    ):
        raise ValueError("Native damping requires 0 <= start < end <= 1 and 0..500 Hz frequencies")


def verify_transform(before, after, parameters):
    old, new = before["objects"][0], after["objects"][0]
    if (
        len(after["objects"]) != 1
        or old["id"] != new["id"]
        or old["instance_count"] != new["instance_count"]
    ):
        raise ValueError("Native transform changed an unexpected object/instance identity")
    a, b = old["instances"][0], new["instances"][0]
    axis, kind, value = "xyz".index(parameters["axis"]), parameters["kind"], parameters["value"]
    key = {"move": "offset", "rotate": "rotation", "scale": "scaling_factor"}[kind]
    expected = (
        a[key][axis] + value
        if kind == "move"
        else a[key][axis] + math.radians(value)
        if kind == "rotate"
        else value / 100
    )
    difference = b[key][axis] - expected
    if kind == "rotate":
        difference = (difference + math.pi) % (2 * math.pi) - math.pi
    if not math.isclose(difference, 0, abs_tol=0.002):
        raise ValueError(f"Native {kind} readback did not match the requested axis/value")
    if kind == "move" and any(
        not math.isclose(a[key][n], b[key][n], abs_tol=0.002) for n in range(3) if n != axis
    ):
        raise ValueError("Native move unexpectedly changed another axis")
    return {
        "field": key,
        "axis": parameters["axis"],
        "before": a[key],
        "after": b[key],
        "expected_axis_value": expected,
    }


def archive_metadata(path):
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("Metadata/model_settings.config")
        if info.file_size > 32 * 1024**2:
            raise ValueError("Native model metadata exceeds 32 MiB")
        raw = archive.read(info)
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("DTD/entity declarations are not accepted in native metadata")
        # Orca writes raw slic3rpe:text/shape names in this config without an
        # xmlns declaration and reads them with namespace-unaware Expat itself.
        builder = ET.TreeBuilder()
        parser = expat.ParserCreate()
        parser.StartElementHandler = builder.start
        parser.EndElementHandler = builder.end
        parser.CharacterDataHandler = builder.data
        parser.Parse(raw, True)
        root = builder.close()
        texts = []
        for part in root.iter("part"):
            for text in part:
                if text.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1] == "text":
                    shapes = [
                        c.attrib
                        for c in part
                        if c.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1] == "shape"
                    ]
                    texts.append(
                        {"text": dict(text.attrib), "shapes": shapes, "part": dict(part.attrib)}
                    )
        settings = json.loads(archive.read("Metadata/project_settings.config"))
        return {
            "editable_texts": texts,
            "object_count": len(root.findall("object")),
            "calibration_settings": {
                k: v for k, v in settings.items() if "calib" in k or "temp" in k
            },
        }


class NativeWorkflows:
    def __init__(
        self, host, desktop, files: Files, directory: Path, controls_factory=NativeControls
    ):
        self.host, self.desktop, self.files, self.directory = host, desktop, files, directory
        self.controls_factory = controls_factory
        self.lock = asyncio.Lock()

    async def scene(self):
        receipt = await self.host.call("scene.read", {})
        if receipt.get("status") != "succeeded":
            raise ValueError(
                f"Native scene unavailable: {receipt.get('error', receipt.get('status'))}"
            )
        return receipt["result"]

    def result(self, request_id):
        path = self.directory / bridge_id(request_id) / "request.json"
        if not path.is_file():
            raise ValueError("Unknown native GUI request ID")
        result = json.loads(path.read_text())
        if result["status"] == "running":
            result.update(
                status="outcome_unknown",
                notice="May be running or interrupted; inspect native state and screenshots. Never repeat under a fresh ID automatically.",
            )
        return result

    async def export(self, destination, session):
        path = self.files.path(destination)
        if path.exists() or path.suffix.lower() != ".3mf":
            raise ValueError(
                "Native copy needs a new .3mf inside configured client and host export roots"
            )
        result = await self.host.call(
            "project.export",
            {"destination": str(path)},
            timeout=60,
            session_id=session,
            request_id=uuid.uuid4().hex,
        )
        if result.get("status") != "succeeded":
            raise ValueError("Native project copy did not complete; inspect its host receipt")
        return {"path": str(path), "sha256": digest(path), "host_receipt": result}

    @staticmethod
    def single(scene):
        if len(scene["objects"]) != 1 or scene["objects"][0]["instance_count"] != 1:
            raise ValueError(
                "This transform/text workflow requires exactly one object and one instance"
            )
        return scene["objects"][0]

    async def run(self, operation, parameters, session_id, request_id, expected_revision):
        bridge_id(session_id)
        bridge_id(request_id)
        raw = {
            "operation": operation,
            "parameters": parameters,
            "session_id": session_id,
            "expected_revision": expected_revision,
        }
        fingerprint = hashlib.sha256(
            json.dumps(raw, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        folder = self.directory / request_id
        path = folder / "request.json"
        async with self.lock:
            if path.exists():
                previous = self.result(request_id)
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("Native request ID conflicts with different parameters")
                return previous
            if operation == "calibration":
                validate_calibration(parameters["kind"], parameters["values"])
                if parameters.get("replace_scene") is not True:
                    raise ValueError(
                        "Native calibration replaces the scene; supply replace_scene=true and backup path explicitly"
                    )
            elif operation == "transform":
                if parameters.get("kind") not in ("move", "rotate", "scale") or parameters.get(
                    "axis"
                ) not in ("x", "y", "z"):
                    raise ValueError("Native transform: move/rotate/scale and x/y/z")
                value = parameters.get("value")
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or abs(value) > 10000
                    or (parameters["kind"] == "scale" and value <= 0)
                ):
                    raise ValueError(
                        "Native transform value must be finite and bounded (scale > 0)"
                    )
            elif operation == "history":
                if (
                    parameters.get("direction") not in ("undo", "redo")
                    or type(parameters.get("steps")) is not int
                    or not 1 <= parameters["steps"] <= 20
                ):
                    raise ValueError("Native history requires undo/redo and 1..20 explicit steps")
            elif operation == "text":
                if (
                    not isinstance(parameters.get("text"), str)
                    or not parameters["text"].strip()
                    or len(parameters["text"]) > 500
                ):
                    raise ValueError("Native text needs 1..500 nonblank characters")
                for key in ("height_mm", "depth_mm"):
                    if (
                        type(parameters.get(key)) not in (int, float)
                        or not math.isfinite(parameters[key])
                        or not 0 < parameters[key] <= 100
                    ):
                        raise ValueError("Native text height/depth must be 0..100 mm")
                if parameters.get("mode") not in ("join", "cut", "modifier"):
                    raise ValueError("Native text mode: join/cut/modifier")
            else:
                raise ValueError("Unknown typed native operation")
            if operation in ("text", "calibration"):
                paths = [self.files.path(parameters[k]) for k in ("backup", "destination")]
                if paths[0] == paths[1] or any(
                    p.exists() or p.suffix.lower() != ".3mf" for p in paths
                ):
                    raise ValueError("Backup and result need distinct new .3mf paths")
            session = self.host.status()
            if not session.get("online") or session.get("session_id") != session_id:
                raise ValueError("Native bridge session changed/offline")
            before = await self.scene()
            if before["revision"] != expected_revision:
                raise ValueError("Observed scene revision changed; inspect again")
            if not before["app"].get("language", "").startswith("en"):
                raise ValueError(
                    "This native UI adapter currently requires an English Orca interface"
                )
            if operation in ("transform", "text"):
                obj = self.single(before)
                if operation == "transform" and parameters["kind"] == "rotate":
                    axis = "xyz".index(parameters["axis"])
                    if any(
                        abs(v) > 1e-6
                        for n, v in enumerate(obj["instances"][0]["rotation"])
                        if n != axis
                    ):
                        raise ValueError(
                            "Verified relative rotation currently requires other rotation axes to be zero"
                        )
            ui = self.controls_factory(self.desktop, folder / "screenshots")
            await asyncio.to_thread(ui.main)
            # Exclusive directory creation prevents a second server process dispatching
            # the same request. Persist intent before any native input/copy.
            folder.mkdir(parents=True)
            record = {
                **raw,
                "request_id": request_id,
                "fingerprint": fingerprint,
                "status": "running",
                "phase": "prepared",
                "before": before,
                "created": time.time(),
            }
            atomic_json(path, record)

            def phase(name):
                record["phase"] = name
                atomic_json(path, record)

            try:
                phase("parking_modeless_bridge")
                record["bridge_window"] = await asyncio.to_thread(ui.park_bridge)
                record["before_screenshot"] = await asyncio.to_thread(ui.capture, "before")
                await asyncio.to_thread(ui.key, "escape")
                await asyncio.to_thread(ui.canvas)
                if operation == "transform":
                    phase("opening_native_transform")
                    await asyncio.to_thread(
                        ui.key, "ctrl" if sys.platform != "darwin" else "command", "a"
                    )
                    await asyncio.to_thread(
                        ui.key, {"move": "m", "rotate": "r", "scale": "s"}[parameters["kind"]]
                    )
                    await asyncio.sleep(0.5)
                    label = {"move": "Position", "rotate": "Relative", "scale": "Scale"}[
                        parameters["kind"]
                    ]
                    phase("setting_native_transform")
                    options = (
                        {"delta": parameters["value"]}
                        if parameters["kind"] in ("move", "rotate")
                        else {"value": parameters["value"]}
                    )
                    record["control"] = await asyncio.to_thread(
                        ui.numeric,
                        label,
                        index="xyz".index(parameters["axis"]),
                        columns=3,
                        commit="enter",
                        required_unit="mm" if parameters["kind"] == "move" else None,
                        **options,
                    )
                    await asyncio.to_thread(ui.key, "escape")
                elif operation == "history":
                    phase("native_history")
                    for step in range(parameters["steps"]):
                        await asyncio.to_thread(
                            ui.key,
                            "ctrl" if sys.platform != "darwin" else "command",
                            "z" if parameters["direction"] == "undo" else "y",
                        )
                        record["completed_steps"] = step + 1
                        atomic_json(path, record)
                elif operation == "text":
                    record["backup"] = await self.export(parameters["backup"], session_id)
                    phase("opening_native_text")
                    await asyncio.to_thread(
                        ui.key, "ctrl" if sys.platform != "darwin" else "command", "a"
                    )
                    await asyncio.to_thread(ui.key, "t")
                    await asyncio.sleep(2)
                    phase("editing_native_text")
                    await asyncio.to_thread(ui.click, "Embossed text")
                    await asyncio.to_thread(
                        ui.key, "ctrl" if sys.platform != "darwin" else "command", "a"
                    )
                    await asyncio.to_thread(ui.paste, parameters["text"])
                    # Clicking a numeric setting commits the native text rebuild.
                    await asyncio.to_thread(
                        ui.numeric, "Height", value=parameters["height_mm"], commit="enter"
                    )
                    await asyncio.to_thread(
                        ui.numeric, "Depth", value=parameters["depth_mm"], commit="enter"
                    )
                    if parameters["mode"] != "join":
                        await asyncio.to_thread(
                            ui.click, {"cut": "Cut", "modifier": "Modifier"}[parameters["mode"]]
                        )
                    await asyncio.to_thread(ui.key, "escape")
                    await asyncio.sleep(1)
                    phase("exporting_editable_native_text")
                    record["export"] = await self.export(parameters["destination"], session_id)
                    record["native_metadata"] = archive_metadata(record["export"]["path"])
                    entries = record["native_metadata"]["editable_texts"]
                    matching = [e for e in entries if e["text"].get("text") == parameters["text"]]
                    if not matching or not any(
                        math.isclose(
                            float(e["text"].get("line_height", -1)),
                            parameters["height_mm"],
                            abs_tol=0.05,
                        )
                        and any(
                            math.isclose(
                                float(s.get("depth", -1)), parameters["depth_mm"], abs_tol=0.02
                            )
                            for s in e["shapes"]
                        )
                        for e in matching
                    ):
                        raise ValueError("Native export did not prove editable text/height/depth")
                elif operation == "calibration":
                    record["backup"] = await self.export(parameters["backup"], session_id)
                    kind, values = parameters["kind"], parameters["values"]
                    phase("opening_native_calibration")
                    left, top, right = await asyncio.to_thread(ui.main)
                    await asyncio.to_thread(ui.click, "Calibration", (left, top, right, top + 36))
                    if kind.startswith("input_shaping_"):
                        await asyncio.to_thread(ui.click, "Input Shaping")
                    await asyncio.to_thread(ui.click, CALIBRATIONS[kind][0])
                    await asyncio.sleep(0.5)
                    phase("setting_native_calibration_parameters")
                    if kind == "pressure_advance":
                        await asyncio.to_thread(
                            ui.click,
                            {"tower": "PA Tower", "line": "PA Line", "pattern": "PA Pattern"}[
                                values.get("method", "tower")
                            ],
                        )
                    if kind == "flow_ratio":
                        await asyncio.to_thread(
                            ui.click,
                            {
                                "pass_1": "Pass 1 Coarse",
                                "pass_2": "Pass 2 Fine",
                                "yolo": "YOLO Recommended",
                                "yolo_perfectionist": "YOLO Perfectionist",
                            }[values.get("test", "pass_1")],
                        )
                    for field in CALIBRATIONS[kind][1]:
                        await asyncio.to_thread(
                            ui.numeric,
                            field[1],
                            value=values[field[0]],
                            index=field[2] if len(field) == 3 else 0,
                            commit="tab",
                            verify=True,
                        )
                    record["parameters_screenshot"] = await asyncio.to_thread(
                        ui.capture, "parameters"
                    )
                    phase("generating_native_calibration")
                    await asyncio.to_thread(ui.click, "OK")
                    await asyncio.sleep(1)
                    # Only an explicitly authorized scene replacement backed by a
                    # completed native copy can dismiss the save-current-project prompt.
                    for label in ("Don't save", "Discard"):
                        try:
                            await asyncio.to_thread(ui.label, label)
                        except ValueError:
                            continue
                        await asyncio.to_thread(ui.click, label)
                        break
                    await asyncio.sleep(1)
                    phase("exporting_native_calibration")
                    record["export"] = await self.export(parameters["destination"], session_id)
                    record["native_metadata"] = archive_metadata(record["export"]["path"])
                after = await self.scene()
                if after["revision"] == before["revision"]:
                    raise ValueError("No native model change was observed")
                if operation == "transform":
                    record["verified_transform"] = verify_transform(before, after, parameters)
                if operation == "calibration" and (
                    not after["objects"]
                    or record["native_metadata"]["object_count"] < 1
                    or not any(v["facets"] > 0 for o in after["objects"] for v in o["volumes"])
                ):
                    raise ValueError("Native generator did not produce a nonempty scene")
                if operation == "text":
                    old_ids = {v["id"] for o in before["objects"] for v in o["volumes"]}
                    added = [
                        v for o in after["objects"] for v in o["volumes"] if v["id"] not in old_ids
                    ]
                    required = {
                        "join": "ModelPart",
                        "cut": "NegativeVolume",
                        "modifier": "ParameterModifier",
                    }[parameters["mode"]]
                    if not any(v["type"].endswith("." + required) for v in added):
                        raise ValueError(
                            "Native text volume type does not match requested operation"
                        )
                record["after"] = after
                record["after_screenshot"] = await asyncio.to_thread(ui.capture, "after")
                record.update(
                    status="succeeded", phase="verified_native_result", physical_print_started=False
                )
            except Exception as exc:
                record.update(
                    status="outcome_unknown",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    notice="Inspect native state/screenshots/backup. Native input may have partially applied; never automatically repeat with a new ID.",
                )
                try:
                    record["failure_screenshot"] = await asyncio.to_thread(ui.capture, "failure")
                except Exception:
                    pass
            # Persistence failure after an effect leaves the previous running phase.
            atomic_json(path, record)
            return record
