"""Revision-bound 3MF transforms and facet masks without remeshing or losing extensions."""

import io
import math
import re
import zipfile
import threading
from xml.sax.saxutils import quoteattr
from xml.etree import ElementTree as ET

from . import projects
from .storage import Files, digest

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PAINT = {
    "support": "paint_supports",
    "seam": "paint_seam",
    "material": "paint_color",
    "fuzzy_skin": "paint_fuzzy_skin",
}
XML_ENCODING_LOCK = threading.Lock()
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def parse(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not accepted")
    namespaces = dict(value for _, value in ET.iterparse(io.BytesIO(raw), events=("start-ns",)))
    return ET.fromstring(raw), namespaces


def encode(root, namespaces):
    # Orca's Expat handlers compare lexical tag names, not expanded namespaces.
    # Preserve its unprefixed core tags and original extension prefixes. Merely
    # equivalent XML using ns0:model is rejected as an empty model by stock Orca.
    with XML_ENCODING_LOCK:
        for prefix, uri in namespaces.items():
            if prefix and not re.fullmatch(r"ns[0-9]+", prefix):
                ET.register_namespace(prefix, uri)
        ET.register_namespace("", CORE)
        raw = ET.tostring(root, encoding="unicode")
        head, tail = raw.split(">", 1)
        for prefix, uri in namespaces.items():
            if prefix and f"xmlns:{prefix}=" not in head:
                head += f" xmlns:{prefix}={quoteattr(uri)}"
        return (head + ">" + tail).encode()


def load(files: Files, path: str, member: str):
    src = files.path(path, True)
    with zipfile.ZipFile(src) as archive:
        entries = archive.infolist()
        if len({i.filename for i in entries}) != len(entries):
            raise ValueError("Ambiguous archive: duplicate member names")
        if (
            member not in archive.namelist()
            or not member.startswith("3D/")
            or not member.endswith(".model")
        ):
            raise ValueError("Choose an existing 3D/*.model archive member")
        info = archive.getinfo(member)
        if info.file_size > 64 * 1024**2:
            raise ValueError("Model XML exceeds 64 MiB")
        raw = archive.read(member)
    root, namespaces = parse(raw)
    if root.tag != f"{{{CORE}}}model":
        raise ValueError("Unsupported 3MF model namespace")
    return src, root, namespaces


def transform(value):
    if (
        not isinstance(value, list)
        or len(value) != 12
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
    ):
        raise ValueError("transform must contain 12 finite numbers in 3MF row-vector order")
    a, b, c, d, e, f, g, h, i = value[:9]
    if abs(a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)) < 1e-12:
        raise ValueError("Singular transforms are not printable")
    return list(value)


def read_transform(element):
    return transform(
        [float(x) for x in element.get("transform", " ".join(map(str, IDENTITY))).split()]
    )


def object_element(root, object_id):
    found = root.findall(f"{{{CORE}}}resources/{{{CORE}}}object")
    found = [o for o in found if o.get("id") == object_id]
    if len(found) != 1:
        raise ValueError("Object ID missing or ambiguous in this model member")
    return found[0]


def inspect(files: Files, path: str, member="3D/3dmodel.model", offset=0, limit=50):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("offset >= 0 and limit 1..100 required")
    src, root, _ = load(files, path, member)
    objects = root.findall(f"{{{CORE}}}resources/{{{CORE}}}object")
    build = root.findall(f"{{{CORE}}}build/{{{CORE}}}item")
    return {
        "path": str(src),
        "sha256": digest(src),
        "member": member,
        "unit": root.get("unit", "millimeter"),
        "total_objects": len(objects),
        "objects": [
            {
                "object_id": o.get("id"),
                "name": o.get("name"),
                "vertices": len(o.findall(f"{{{CORE}}}mesh/{{{CORE}}}vertices/{{{CORE}}}vertex")),
                "triangles": len(
                    o.findall(f"{{{CORE}}}mesh/{{{CORE}}}triangles/{{{CORE}}}triangle")
                ),
                "components": [
                    {"index": n, "attributes": dict(c.attrib), "transform": read_transform(c)}
                    for n, c in enumerate(o.findall(f"{{{CORE}}}components/{{{CORE}}}component"))
                ],
            }
            for o in objects[offset : offset + limit]
        ],
        "total_build_items": len(build),
        "build": [
            {"index": n, "attributes": dict(b.attrib), "transform": read_transform(b)}
            for n, b in enumerate(build)
            if offset <= n < offset + limit
        ],
    }


def set_transform(
    files,
    source,
    destination,
    expected,
    matrix,
    target="build",
    index=0,
    object_id=None,
    member="3D/3dmodel.model",
):
    _, root, namespaces = load(files, source, member)
    matrix = transform(matrix)
    if target == "build" and object_id is None:
        items = root.findall(f"{{{CORE}}}build/{{{CORE}}}item")
    elif target == "component" and object_id is not None:
        items = object_element(root, object_id).findall(f"{{{CORE}}}components/{{{CORE}}}component")
    else:
        raise ValueError("Use build or component with an explicit object_id")
    if type(index) is not int or not 0 <= index < len(items):
        raise ValueError("Target index out of range")
    before = read_transform(items[index])
    items[index].set("transform", " ".join(format(v, ".17g") for v in matrix))
    result = projects.rewrite(
        files, source, destination, expected, {member: encode(root, namespaces)}
    )
    return {
        **result,
        "target": target,
        "index": index,
        "before": before,
        "after": matrix,
        "unit": root.get("unit", "millimeter"),
        "live_scene_changed": False,
    }


def mask_state(state):
    if type(state) is not int or not 0 <= state <= 16:
        raise ValueError("Paint state must be 0..16; material slots are 1..16")
    if state < 3:
        return format(state << 2, "X")
    return format(state - 3, "X") + "C"


def validate_mask(code, kind):
    if not isinstance(code, str) or not re.fullmatch(r"[0-9A-F]{1,4096}", code):
        raise ValueError("Mask must contain 1..4096 uppercase hex digits")
    # Serialized nibbles are reversed. Each split node is followed by sides+1
    # children. Consume iteratively to bound malicious depth and validate framing.
    nibbles = list(reversed(code))
    position, pending, states = 0, 1, set()
    while pending:
        if position >= len(nibbles):
            raise ValueError("Truncated triangle paint tree")
        node = int(nibbles[position], 16)
        position += 1
        pending -= 1
        sides = node & 3
        if sides:
            if sides != 3 and node >> 2 == 3:
                raise ValueError("Invalid split side")
            pending += sides + 1
        else:
            state = node >> 2
            if state == 3:
                if position >= len(nibbles):
                    raise ValueError("Truncated paint state")
                state = int(nibbles[position], 16) + 3
                position += 1
                if state == 18:
                    if position >= len(nibbles):
                        raise ValueError("Truncated extended paint state")
                    state += int(nibbles[position], 16)
                    position += 1
            if state > (16 if kind == "material" else 2):
                raise ValueError("Paint state not supported for this channel (material max 16)")
            states.add(state)
    if position != len(nibbles):
        raise ValueError("Trailing triangle paint data")
    return sorted(states)


def triangles(root, object_id):
    obj = object_element(root, object_id)
    items = obj.findall(f"{{{CORE}}}mesh/{{{CORE}}}triangles/{{{CORE}}}triangle")
    if not items:
        raise ValueError("Object has no direct mesh; inspect component model members")
    return items


def painting_read(files, source, object_id, member="3D/3dmodel.model", offset=0, limit=100):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("offset >= 0 and limit 1..200 required")
    src, root, _ = load(files, source, member)
    items = triangles(root, object_id)
    return {
        "sha256": digest(src),
        "member": member,
        "object_id": object_id,
        "total_triangles": len(items),
        "triangles": [
            {
                "index": n,
                "vertices": [t.get(k) for k in ("v1", "v2", "v3")],
                "painting": {kind: t.get(attr) for kind, attr in PAINT.items()},
            }
            for n, t in enumerate(items)
            if offset <= n < offset + limit
        ],
    }


def painting_write(
    files, source, destination, expected, object_id, kind, changes, member="3D/3dmodel.model"
):
    if kind not in PAINT or not isinstance(changes, list) or not 1 <= len(changes) <= 10000:
        raise ValueError("Choose support/seam/material/fuzzy_skin and 1..10000 triangle changes")
    _, root, namespaces = load(files, source, member)
    items = triangles(root, object_id)
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) - {"triangle", "state", "mask"}:
            raise ValueError("Each change needs triangle and exactly one of state or mask")
        index = change.get("triangle")
        if type(index) is not int or not 0 <= index < len(items) or index in seen:
            raise ValueError("Triangle index missing, duplicated or out of range")
        seen.add(index)
        if ("state" in change) == ("mask" in change):
            raise ValueError("Provide exactly one of state or mask (null clears the channel)")
        code = mask_state(change["state"]) if "state" in change else change["mask"]
        if code is not None:
            validate_mask(code, kind)
            items[index].set(PAINT[kind], code)
        else:
            items[index].attrib.pop(PAINT[kind], None)
    result = projects.rewrite(
        files, source, destination, expected, {member: encode(root, namespaces)}
    )
    return {**result, "kind": kind, "changed_triangles": len(seen), "live_scene_changed": False}
