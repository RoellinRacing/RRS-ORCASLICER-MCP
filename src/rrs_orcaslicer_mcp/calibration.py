"""Recoverable calibration coupons: one controlled parameter per project, never auto-print."""

import hashlib
import json
import math
from pathlib import Path

from . import projects
from .storage import Files, atomic_json, digest

KINDS = {
    "temperature": ("nozzle_temperature", "nozzle_temperature_initial_layer"),
    "flow_ratio": ("filament_flow_ratio",),
    "pressure_advance": ("pressure_advance",),
    "max_volumetric_speed": ("filament_max_volumetric_speed",),
}


def series(
    files: Files,
    source: str,
    destination: str,
    expected: str,
    kind: str,
    values: list,
    slot: int = 1,
):
    if kind not in KINDS or not isinstance(values, list) or not 2 <= len(values) <= 32:
        raise ValueError(
            "Choose temperature/flow_ratio/pressure_advance/max_volumetric_speed and 2..32 values"
        )
    if type(slot) is not int or slot < 1:
        raise ValueError("slot must be a 1-based filament slot")
    src, folder = files.path(source, True), files.path(destination)
    original = projects.inspect(files, str(src))
    if original["sha256"] != expected:
        raise ValueError("Source changed; inspect again")
    settings = original.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("Calibration needs Orca JSON project settings")
    variants = []
    for value in values:
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            # Pressure advance zero is a valid baseline.
            if not (kind == "pressure_advance" and type(value) in (int, float) and value == 0):
                raise ValueError(
                    "Calibration values must be finite positive numbers (PA may be zero)"
                )
        if kind == "temperature" and (value != int(value) or value > 500):
            raise ValueError(
                "Temperature values must be integer Celsius, at most 500; match printer limits"
            )
        if kind in ("flow_ratio", "pressure_advance") and value > 2:
            raise ValueError("Flow ratio/pressure advance exceeds the Orca setting range")
        changes = {}
        for key in KINDS[kind]:
            baseline = settings.get(key)
            if not isinstance(baseline, list) or slot > len(baseline):
                raise ValueError(f"Project lacks explicit filament slot {slot} for {key}")
            changed = list(baseline)
            changed[slot - 1] = str(int(value)) if kind == "temperature" else format(value, ".12g")
            changes[key] = changed
        if kind == "pressure_advance":
            enabled = settings.get("enable_pressure_advance")
            if not isinstance(enabled, list) or slot > len(enabled):
                raise ValueError("Project lacks explicit enable_pressure_advance slots")
            changes["enable_pressure_advance"] = list(enabled)
            changes["enable_pressure_advance"][slot - 1] = "1"
        variants.append({"value": value, "changes": changes})
    request = {"source_sha256": expected, "kind": kind, "slot": slot, "variants": variants}
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    checkpoint = folder / "calibration.json"
    if folder.exists():
        if not checkpoint.is_file():
            raise ValueError("Destination exists without this calibration manifest")
        report = json.loads(checkpoint.read_text(encoding="utf-8"))
        if report.get("fingerprint") != fingerprint:
            raise ValueError("Calibration destination belongs to a different request")
    else:
        folder.mkdir(parents=True)
        report = {
            **request,
            "fingerprint": fingerprint,
            "status": "generating",
            "completed": [],
            "model": str(src),
            "physical_print_started": False,
            "method": "Independent constant-setting coupons from supplied model; not Orca native towers/dialogs",
        }
        atomic_json(checkpoint, report)
    for index, variant in enumerate(variants):
        target = folder / f"{index:02d}-{kind}.3mf"
        completed = next((e for e in report["completed"] if e["index"] == index), None)
        if completed:
            if not target.is_file() or digest(target) != completed["sha256"]:
                raise ValueError(
                    "Completed calibration output changed; preserve it and choose a new destination"
                )
            continue
        if target.exists():
            # A crash can publish a file before its manifest checkpoint. Verify
            # its exact metadata against this variant before recovering the entry.
            actual = projects.inspect(files, str(target))
            if any(actual.get("settings", {}).get(k) != v for k, v in variant["changes"].items()):
                raise ValueError(
                    "Uncheckpointed calibration output does not match requested settings"
                )
            # Also compare the payload against a freshly constructed variant.
            import tempfile

            with tempfile.TemporaryDirectory(dir=folder) as temporary:
                reference = Path(temporary) / "reference.3mf"
                projects.patch(files, str(src), str(reference), variant["changes"], expected)
                if digest(reference) != actual["sha256"]:
                    raise ValueError(
                        "Uncheckpointed calibration payload differs; use a new destination"
                    )
            outcome = actual
        else:
            outcome = projects.patch(files, str(src), str(target), variant["changes"], expected)
        report["completed"].append(
            {
                "index": index,
                "value": variant["value"],
                "path": str(target),
                "sha256": outcome["sha256"],
            }
        )
        atomic_json(checkpoint, report)
    report["status"] = "ready_to_slice"
    atomic_json(checkpoint, report)
    return report
