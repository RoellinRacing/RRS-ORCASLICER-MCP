import json
import zipfile
from xml.etree.ElementTree import ParseError

import pytest

from rrs_orcaslicer_mcp import profiles, projects
from rrs_orcaslicer_mcp.storage import Files, digest


def test_settings_roundtrip_unknown_keys_revision_backup(tmp_path):
    files = Files([tmp_path])
    first = files.write("p.json", {"name": "PLA ä", "future_key": ["v"], "layer_height": "0.2"}, [], None)
    with pytest.raises(ValueError, match="SHA256"):
        files.write("p.json", {"layer_height": "0.3"}, [], None)
    second = files.write("p.json", {"layer_height": "0.3"}, [], first["sha256"])
    assert second["settings"]["future_key"] == ["v"]
    assert files.read(second["backup"])["settings"]["layer_height"] == "0.2"
    with pytest.raises(ValueError, match="SHA256"):
        files.write("p.json", {}, [], first["sha256"])
    assert files.read("p.json")["sha256"] == second["sha256"]


def test_roots_and_symlink_escape(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    files = Files([root])
    with pytest.raises(ValueError, match="outside"):
        files.path("../escape")
    try:
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="outside"):
        files.path("link/escape")


def test_profile_inheritance_and_cycle(tmp_path):
    files = Files([tmp_path])
    files.write("base.json", {"name": "base", "speed": "50", "unknown": "keep"}, [], None)
    files.write("leaf.json", {"name": "leaf", "inherits": "base", "speed": "75"}, [], None)
    result = profiles.resolve(files, "leaf.json", [str(tmp_path)])
    assert result["settings"]["speed"] == "75"
    assert result["settings"]["unknown"] == "keep"
    first = files.read("base.json")
    files.write("base.json", {"inherits": "leaf"}, [], first["sha256"])
    with pytest.raises(ValueError, match="Cyclic"):
        profiles.resolve(files, "leaf.json", [str(tmp_path)])


def make_project(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(projects.SETTINGS, json.dumps({"layer_height": "0.2", "future": ["x"]}))
        archive.writestr("3D/3dmodel.model", b"mesh payload\x00")
        archive.writestr("Metadata/model_settings.config", '<config><object id="1"/></config>')
        archive.writestr("vendor/unknown.bin", b"\x00\x01\xff")
        archive.comment = b"preserved"


def test_project_lossless_edit(tmp_path):
    files = Files([tmp_path])
    src = tmp_path / "source.3mf"
    make_project(src)
    checksum = digest(src)
    result = projects.patch(files, "source.3mf", "out.3mf", {"layer_height": "0.3"}, checksum)
    assert result["settings"] == {"layer_height": "0.3", "future": ["x"]}
    assert digest(src) == checksum
    with zipfile.ZipFile(src) as before, zipfile.ZipFile(tmp_path / "out.3mf") as after:
        assert before.comment == after.comment
        for member in before.namelist():
            if member != projects.SETTINGS:
                assert before.read(member) == after.read(member)
    with pytest.raises(ValueError, match="requires"):
        projects.patch(files, "source.3mf", "out.3mf", {}, checksum)
    with pytest.raises(ValueError, match="Source changed"):
        projects.patch(files, "source.3mf", "bad.3mf", {}, "bad")


def test_object_metadata_edit(tmp_path):
    files = Files([tmp_path])
    src = tmp_path / "source.3mf"
    make_project(src)
    member = "Metadata/model_settings.config"
    changed = '<config><object id="1"><metadata key="extruder" value="2"/></object></config>'
    result = projects.patch(files, "source.3mf", "object.3mf", {}, digest(src), metadata_member=member, metadata_text=changed)
    assert result["text"] == changed
    with pytest.raises(ParseError):
        projects.patch(files, "source.3mf", "bad.3mf", {}, digest(src), metadata_member=member, metadata_text="<broken")
    assert not (tmp_path / "bad.3mf").exists()
