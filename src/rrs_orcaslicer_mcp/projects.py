"""Edit Orca project metadata without rebuilding meshes or stripping unknown ZIP members."""

import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from .storage import Files, check_revision, digest

SETTINGS = "Metadata/project_settings.config"


def generated_member(name: str) -> bool:
    return name == "Metadata/slice_info.config" or bool(
        re.fullmatch(
            r"Metadata/plate_\d+\.(?:gcode(?:\.md5)?|bgcode(?:\.md5)?|json|statistics\.json)", name
        )
    )


def clear_slice_references(name: str, raw: bytes, removed: set[str]) -> bytes:
    """Keep project geometry/painting, but never pair changed settings with old G-code."""
    from xml.etree import ElementTree as ET

    if name not in (
        "Metadata/model_settings.config",
        "Metadata/_rels/model_settings.config.rels",
        "[Content_Types].xml",
    ):
        return raw
    root = ET.fromstring(raw)
    changed = False
    for parent in root.iter():
        for child in list(parent):
            target = child.get("Target", child.get("PartName", "")).lstrip("/")
            if target in removed or child.get("key") in ("gcode_file", "gcode_file_md5"):
                parent.remove(child)
                changed = True
    if not changed:
        return raw
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def inspect(files: Files, name: str, member: str = SETTINGS) -> dict:
    path = files.path(name, True)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len({i.filename for i in entries}) != len(entries):
            raise ValueError("Ambiguous archive: duplicate member names")
        result = {
            "path": str(path),
            "sha256": digest(path),
            "members": [{"name": i.filename, "size": i.file_size} for i in entries],
        }
        if member in archive.namelist():
            info = archive.getinfo(member)
            if info.file_size > 32 * 1024 * 1024:
                raise ValueError("Metadata exceeds 32 MiB")
            raw = archive.read(member).decode("utf-8-sig")
            try:
                result["settings"] = json.loads(raw)
            except json.JSONDecodeError:
                result["text"] = raw
        return result


def patch(
    files: Files,
    source: str,
    destination: str,
    changes: dict,
    expected_source: str,
    expected_destination: str | None = None,
    remove: list[str] | None = None,
    metadata_member: str = SETTINGS,
    metadata_text: str | None = None,
) -> dict:
    src = files.path(source, True)
    dst = files.path(destination)
    if src == dst:
        raise ValueError("Write to a new 3MF destination so the original stays recoverable")
    if digest(src) != expected_source:
        raise ValueError("Source changed; inspect again")
    check_revision(dst, expected_destination)
    if dst.exists():
        raise ValueError("3MF destination must be new; choose another filename")
    data = inspect(files, source, metadata_member)
    if generated_member(metadata_member):
        raise ValueError(
            "Generated slicing caches cannot be edited as settings; reslice the project"
        )
    if metadata_text is not None:
        if not metadata_member.startswith("Metadata/") or ".." in metadata_member.split("/"):
            raise ValueError("Only existing Metadata members can be replaced")
        if metadata_member not in {m["name"] for m in data["members"]}:
            raise ValueError("Metadata member does not exist")
        encoded = metadata_text.encode("utf-8")
        if len(encoded) > 32 * 1024 * 1024:
            raise ValueError("Metadata exceeds 32 MiB")
        if metadata_member.endswith((".xml", ".model")) or metadata_text.lstrip().startswith("<"):
            from xml.etree import ElementTree

            ElementTree.fromstring(metadata_text)
        else:
            json.loads(metadata_text)
    else:
        settings = data.get("settings")
        if not isinstance(settings, dict):
            raise ValueError(
                "No Orca JSON project settings found; open/save this project in OrcaSlicer first"
            )
        settings.update(changes)
        for key in remove or []:
            settings.pop(key, None)
        encoded = json.dumps(settings, ensure_ascii=False, indent=2, allow_nan=False).encode()
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=dst.parent, suffix=".3mf")
    os.close(fd)
    try:
        with zipfile.ZipFile(src) as before, zipfile.ZipFile(temp, "w") as after:
            if sum(i.file_size for i in before.infolist()) > 2 * 1024**3:
                raise ValueError("Expanded archive exceeds 2 GiB")
            after.comment = before.comment
            removed = {i.filename for i in before.infolist() if generated_member(i.filename)}
            for info in before.infolist():
                if info.filename in removed:
                    continue
                if info.filename == metadata_member:
                    after.writestr(info, clear_slice_references(info.filename, encoded, removed))
                elif info.filename in (
                    "Metadata/model_settings.config",
                    "Metadata/_rels/model_settings.config.rels",
                    "[Content_Types].xml",
                ):
                    if info.file_size > 32 * 1024 * 1024:
                        raise ValueError("XML metadata exceeds 32 MiB")
                    after.writestr(
                        info, clear_slice_references(info.filename, before.read(info), removed)
                    )
                else:
                    with before.open(info) as inp, after.open(info, "w") as out:
                        import shutil

                        shutil.copyfileobj(inp, out, 1024 * 1024)
        # Same-directory hard link publishes a complete archive without overwriting
        # another writer's result. Supported on local NTFS/APFS/ext4 filesystems.
        os.link(temp, dst)
    finally:
        Path(temp).unlink(missing_ok=True)
    result = inspect(files, str(dst), metadata_member)
    result.update(requires_reslice=True, removed_slice_artifacts=sorted(removed))
    return result


def rewrite(
    files: Files, source: str, destination: str, expected: str, replacements: dict[str, bytes]
) -> dict:
    """Publish a new revision-bound archive; remove all affected slicing caches."""
    import shutil

    src, dst = files.path(source, True), files.path(destination)
    if src == dst or dst.exists() or dst.suffix.lower() != ".3mf":
        raise ValueError("Choose a new .3mf destination")
    if digest(src) != expected:
        raise ValueError("Source changed; inspect again")
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=dst.parent, suffix=".3mf")
    os.close(fd)
    try:
        with zipfile.ZipFile(src) as before, zipfile.ZipFile(temporary, "w") as after:
            entries = before.infolist()
            names = {i.filename for i in entries}
            if len(names) != len(entries):
                raise ValueError("Ambiguous archive: duplicate member names")
            if not replacements or not set(replacements) <= names:
                raise ValueError("Only existing archive members can be replaced")
            if sum(i.file_size for i in entries) > 2 * 1024**3:
                raise ValueError("Expanded archive exceeds 2 GiB")
            removed = {n for n in names if generated_member(n)}
            after.comment = before.comment
            for info in entries:
                if info.filename in removed:
                    continue
                if info.filename in replacements:
                    after.writestr(info, replacements[info.filename])
                elif info.filename in (
                    "Metadata/model_settings.config",
                    "Metadata/_rels/model_settings.config.rels",
                    "[Content_Types].xml",
                ):
                    if info.file_size > 32 * 1024**2:
                        raise ValueError("XML metadata exceeds 32 MiB")
                    after.writestr(
                        info, clear_slice_references(info.filename, before.read(info), removed)
                    )
                else:
                    with before.open(info) as inp, after.open(info, "w") as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
        if digest(src) != expected:
            raise ValueError("Source changed during editing; inspect again")
        os.link(temporary, dst)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {
        "path": str(dst),
        "sha256": digest(dst),
        "requires_reslice": True,
        "removed_slice_artifacts": sorted(removed),
    }
