"""Compare serialized profiles and flag source-known problems without claiming engine validation."""

import math
import json

from .catalog import snapshot
from .profiles import resolve
from .storage import Files


def compare(left: dict, right: dict) -> dict:
    added = {k: right[k] for k in sorted(right.keys() - left.keys())}
    removed = {k: left[k] for k in sorted(left.keys() - right.keys())}
    changed = {
        k: {"before": left[k], "after": right[k]}
        for k in sorted(left.keys() & right.keys())
        if json.dumps(left[k], sort_keys=True, allow_nan=False)
        != json.dumps(right[k], sort_keys=True, allow_nan=False)
    }
    return {
        "identical": not (added or removed or changed),
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }


def validate(values: dict) -> dict:
    definitions = snapshot()
    findings = []
    unknown = []
    metadata = {
        "name",
        "type",
        "from",
        "inherits",
        "version",
        "setting_id",
        "filament_id",
        "instantiation",
    }
    for key, value in values.items():
        definition = definitions["options"].get(key)
        if not definition:
            if key not in metadata:
                unknown.append(key)
            continue
        kind = definition["type"]
        vector = kind in {
            "coFloats",
            "coInts",
            "coBools",
            "coStrings",
            "coPercents",
            "coFloatsOrPercents",
            "coPoints",
            "coEnums",
        }
        if vector and not isinstance(value, list):
            findings.append({"key": key, "problem": "expected_list", "value": value})
            continue
        for element in value if vector else [value]:
            issue = None
            if kind in ("coBool", "coBools"):
                if element not in (True, False, 0, 1, "0", "1"):
                    issue = "expected_boolean_0_or_1"
            elif kind in {
                "coFloat",
                "coFloats",
                "coInt",
                "coInts",
                "coPercent",
                "coPercents",
                "coFloatOrPercent",
                "coFloatsOrPercents",
            }:
                try:
                    if isinstance(element, bool):
                        raise ValueError("Boolean is not a numeric setting")
                    text = str(element)
                    percent = text.endswith("%")
                    number = float(text[:-1] if percent else text)
                    if not math.isfinite(number):
                        issue = "expected_finite_number"
                    elif kind in ("coInt", "coInts") and (not number.is_integer() or percent):
                        issue = "expected_integer"
                    elif percent and kind not in (
                        "coPercent",
                        "coPercents",
                        "coFloatOrPercent",
                        "coFloatsOrPercents",
                    ):
                        issue = "unexpected_percentage"
                    elif not (percent and kind in ("coFloatOrPercent", "coFloatsOrPercents")):
                        if "min" in definition and number < definition["min"]:
                            issue = "below_source_minimum"
                        if "max" in definition and number > definition["max"]:
                            issue = "above_source_maximum"
                except (ValueError, TypeError):
                    issue = "expected_number"
            elif kind in ("coEnum", "coEnums") and definition.get("enum_values"):
                if element not in definition["enum_values"]:
                    issue = "not_in_source_enum"
            if issue:
                findings.append(
                    {"key": key, "problem": issue, "value": element, "source_type": kind}
                )
    return {
        "scope": "advisory_source_snapshot",
        "engine_validated": False,
        "findings": findings,
        "unknown_keys_preserved": sorted(unknown),
        "upstream": definitions["upstream"],
        "notice": "OrcaSlicer must validate final settings. Source hints can differ from the installed version; unknown keys are not errors.",
    }


def export_profile(
    files: Files, source: str, destination: str, name: str, directories: list[str]
) -> dict:
    target = files.path(destination)
    if target.exists():
        raise ValueError("Profile export needs a new destination")
    if not name.strip():
        raise ValueError("Supply a nonempty profile name")
    resolved = resolve(files, source, directories)
    values = resolved["settings"].copy()
    values.pop("inherits", None)
    values.pop("setting_id", None)
    values.update(name=name.strip(), **{"from": "User"})
    result = files.write(destination, values, [], None)
    return {**result, "inheritance_chain": resolved["chain"], "validation": validate(values)}
