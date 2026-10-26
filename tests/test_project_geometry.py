import zipfile

import pytest

from rrs_orcaslicer_mcp import project_geometry as geometry
from rrs_orcaslicer_mcp.storage import Files, digest


@pytest.fixture
def scene(tmp_path):
    src = tmp_path / "scene.3mf"
    model = f'''<model xmlns="{geometry.CORE}" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p" unit="millimeter">
    <resources><object id="1"><mesh><vertices><vertex x="0" y="0" z="0"/>
    <vertex x="10" y="0" z="0"/><vertex x="0" y="10" z="0"/></vertices>
    <triangles><triangle v1="0" v2="1" v3="2" paint_color="0C" paint_seam="8" future="keep"/></triangles></mesh></object>
    <object id="2"><components><component objectid="1" p:path="/3D/Objects/object_1.model"/></components></object></resources>
    <build><item objectid="2"/></build></model>'''
    with zipfile.ZipFile(src, "w") as archive:
        archive.comment = b"retain"
        archive.writestr("3D/3dmodel.model", model)
        archive.writestr("Metadata/plate_1.gcode", "STALE")
        archive.writestr("Metadata/slice_info.config", "STALE")
        archive.writestr(
            "Metadata/model_settings.config",
            '<config><plate><metadata key="gcode_file" value="Metadata/plate_1.gcode"/></plate></config>',
        )
        archive.writestr("unknown.bin", b"\x00\xffopaque")
    return Files([tmp_path]), src, digest(src)


def test_transform_preserves_payload_masks_and_extension_prefix(scene):
    files, src, sha = scene
    report = geometry.inspect(files, str(src))
    assert report["objects"][0]["triangles"] == 1
    matrix = [-2, 0, 0, 0, 3, 0, 0, 0, 1, 20, 30, 0]
    result = geometry.set_transform(files, str(src), "transformed.3mf", sha, matrix)
    assert result["requires_reslice"] and digest(src) == sha
    with zipfile.ZipFile(result["path"]) as archive:
        assert archive.comment == b"retain"
        assert archive.read("unknown.bin") == b"\x00\xffopaque"
        raw = archive.read("3D/3dmodel.model")
        assert b"xmlns:p=" in raw and b'requiredextensions="p"' in raw
        assert b'paint_color="0C"' in raw and b'future="keep"' in raw
        assert not any("gcode" in n for n in archive.namelist())
        assert b"gcode_file" not in archive.read("Metadata/model_settings.config")
    assert geometry.inspect(files, result["path"])["build"][0]["transform"] == matrix
    with pytest.raises(ValueError, match="new .3mf"):
        geometry.set_transform(files, str(src), result["path"], sha, matrix)


def test_component_transform_and_revision_rejection(scene):
    files, src, sha = scene
    geometry.set_transform(
        files, str(src), "component.3mf", sha, geometry.IDENTITY, "component", 0, "2"
    )
    with pytest.raises(ValueError, match="Source changed"):
        geometry.set_transform(files, str(src), "stale.3mf", "0" * 64, geometry.IDENTITY)
    with pytest.raises(ValueError, match="Singular"):
        geometry.set_transform(files, str(src), "bad.3mf", sha, [0] * 12)
    assert not files.path("bad.3mf").exists()


def test_painting_channels_and_subtriangle_tree_roundtrip(scene):
    files, src, sha = scene
    # Root splits once, children have enforcer/blocker states, reverse nibble order.
    assert geometry.validate_mask("841", "support") == [1, 2]
    result = geometry.painting_write(
        files, str(src), "painted.3mf", sha, "1", "support", [{"triangle": 0, "mask": "841"}]
    )
    row = geometry.painting_read(files, result["path"], "1")["triangles"][0]
    assert row["painting"] == {"support": "841", "seam": "8", "material": "0C", "fuzzy_skin": None}
    assert row["vertices"] == ["0", "1", "2"]
    cleared = geometry.painting_write(
        files,
        result["path"],
        "clear.3mf",
        result["sha256"],
        "1",
        "support",
        [{"triangle": 0, "mask": None}],
    )
    assert (
        geometry.painting_read(files, cleared["path"], "1")["triangles"][0]["painting"]["support"]
        is None
    )
    for code in ("1", "C", "84D", "840", "ZZ", "FC", "0C"):
        with pytest.raises(ValueError):
            geometry.validate_mask(code, "support")
    assert geometry.validate_mask(geometry.mask_state(16), "material") == [16]


def test_paint_validation_is_atomic(scene):
    files, src, sha = scene
    for changes in (
        [{"triangle": 0, "state": 1}, {"triangle": 1, "state": 2}],
        [{"triangle": 0, "state": 1}, {"triangle": 0, "state": 2}],
        [{"triangle": 0, "state": 1, "mask": "4"}],
    ):
        with pytest.raises(ValueError):
            geometry.painting_write(files, str(src), "invalid.3mf", sha, "1", "support", changes)
        assert not files.path("invalid.3mf").exists()
    assert digest(src) == sha


def test_dtd_and_nonfinite_transforms_rejected():
    with pytest.raises(ValueError, match="DTD"):
        geometry.parse(b"<!DOCTYPE model><model/>")
    for v in ([float("nan")] + geometry.IDENTITY[1:], [True] + geometry.IDENTITY[1:]):
        with pytest.raises(ValueError, match="finite"):
            geometry.transform(v)
