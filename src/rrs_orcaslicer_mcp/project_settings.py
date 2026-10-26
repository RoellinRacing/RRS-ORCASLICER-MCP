"""Semantic edits of Orca object/part/plate metadata, identified by stable stored IDs."""

from xml.etree import ElementTree as ET

from . import projects
from .storage import Files

MEMBER = "Metadata/model_settings.config"


def metadata(element) -> dict:
    result = {}
    for child in element.findall("metadata"):
        key = child.get("key")
        if key in result:
            raise ValueError(f"Ambiguous duplicate metadata key: {key}")
        if key:
            result[key] = child.get("value", "")
    return result


def load(files: Files, path: str):
    result = projects.inspect(files, path, MEMBER)
    if "text" not in result:
        raise ValueError("Expected Orca XML model settings; open/save the project in Orca first")
    root = ET.fromstring(result["text"])
    if root.tag != "config":
        raise ValueError("Unrecognized Orca object metadata format")
    return result, root


def inspect(files: Files, path: str) -> dict:
    result, root = load(files, path)
    objects = []
    for item in root.findall("object"):
        objects.append(
            {
                "object_id": item.get("id"),
                "settings": metadata(item),
                "parts": [
                    {"part_id": p.get("id"), "subtype": p.get("subtype"), "settings": metadata(p)}
                    for p in item.findall("part")
                ],
            }
        )
    plates = []
    for item in root.findall("plate"):
        data = metadata(item)
        plates.append(
            {
                "plate_id": data.get("plater_id"),
                "settings": data,
                "instances": [metadata(i) for i in item.findall("model_instance")],
            }
        )
    return {
        "path": result["path"],
        "sha256": result["sha256"],
        "objects": objects,
        "plates": plates,
    }


def write(
    files: Files,
    source: str,
    destination: str,
    target: str,
    target_id: str,
    changes: dict,
    expected: str,
    remove: list[str] | None = None,
    part_id: str | None = None,
) -> dict:
    original, root = load(files, source)
    if original["sha256"] != expected:
        raise ValueError("Source changed; inspect again")
    if target == "object":
        candidates = [o for o in root.findall("object") if o.get("id") == target_id]
    elif target == "plate":
        if part_id is not None:
            raise ValueError("part_id is only supported for objects")
        candidates = [p for p in root.findall("plate") if metadata(p).get("plater_id") == target_id]
    else:
        raise ValueError("Target must be object or plate")
    if len(candidates) != 1:
        raise ValueError("Target ID is missing or ambiguous; use project_objects_read")
    item = candidates[0]
    if part_id is not None:
        candidates = [p for p in item.findall("part") if p.get("id") == part_id]
        if len(candidates) != 1:
            raise ValueError("Part ID is missing or ambiguous")
        item = candidates[0]
    metadata(item)  # Reject duplicate keys before changing the document.
    reserved = {
        "plater_id",
        "object_id",
        "instance_id",
        "identify_id",
        "matrix",
        "source_file",
        "source_object_id",
        "source_volume_id",
        "source_offset_x",
        "source_offset_y",
        "source_offset_z",
        "gcode_file",
        "gcode_file_md5",
    }
    if reserved.intersection(set(changes) | set(remove or [])):
        raise ValueError(
            "Identity, geometry and generated-file references cannot be edited as print settings"
        )
    for key, value in changes.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise ValueError(
                "Orca object/plate metadata uses nonempty string keys and string values"
            )
    by_key = {child.get("key"): child for child in item.findall("metadata")}
    for key in remove or []:
        if key in by_key:
            item.remove(by_key[key])
    for key, value in changes.items():
        if key in by_key and key not in (remove or []):
            by_key[key].set("value", value)
        else:
            ET.SubElement(item, "metadata", {"key": key, "value": value})
    result = projects.patch(
        files,
        source,
        destination,
        {},
        expected,
        metadata_member=MEMBER,
        metadata_text=ET.tostring(root, encoding="unicode"),
    )
    return {
        "path": result["path"],
        "sha256": result["sha256"],
        "requires_reslice": True,
        "removed_slice_artifacts": result["removed_slice_artifacts"],
        "structure": inspect(files, destination),
    }
