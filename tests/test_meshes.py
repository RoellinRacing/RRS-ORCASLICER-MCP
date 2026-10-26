import pytest

from rrs_orcaslicer_mcp import meshes
from rrs_orcaslicer_mcp.storage import Files, digest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("manifold3d")
pytest.importorskip("shapely")


def cubes(tmp_path):
    a = trimesh.creation.box(extents=[10, 10, 10])
    b = a.copy()
    b.apply_translation([5, 0, 0])
    result = []
    for i, mesh in enumerate([a, b]):
        path = tmp_path / f"{i}.stl"
        mesh.export(path)
        result.append({"path": str(path), "sha256": digest(path)})
    return result


def test_manifold_boolean_volumes_are_measured_from_stl(tmp_path):
    sources = cubes(tmp_path)
    files = Files([tmp_path])
    for action, volume in (("union", 1500), ("difference", 500), ("intersection", 500)):
        result = meshes.operation(files, sources, action, action)
        assert result["status"] == "succeeded"
        assert result["outputs"][0]["watertight"]
        assert result["outputs"][0]["volume_mm3"] == pytest.approx(volume)
    assert digest(files.path(sources[0]["path"])) == sources[0]["sha256"]


def test_cut_split_repair_and_transform(tmp_path):
    sources = cubes(tmp_path)
    files = Files([tmp_path])
    cut = meshes.operation(
        files, sources[:1], "cut", "cut", {"origin": [0, 0, 0], "normal": [1, 0, 0]}
    )
    assert len(cut["outputs"]) == 2
    assert all(o["watertight"] and o["volume_mm3"] == pytest.approx(500) for o in cut["outputs"])
    repair = meshes.operation(files, sources[:1], "repair", "repair")
    assert repair["outputs"][0]["volume_mm3"] == pytest.approx(1000)
    matrix = [[2, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    moved = meshes.operation(files, sources[:1], "transform", "transform", {"matrix": matrix})
    assert moved["outputs"][0]["volume_mm3"] == pytest.approx(2000)
    assert moved["outputs"][0]["bounds_mm"][0][0] == pytest.approx(0)
    # Disconnected bodies exercise split with real distinct connected components.
    separated = trimesh.creation.box()
    other = separated.copy()
    other.apply_translation([3, 0, 0])
    path = tmp_path / "separate.stl"
    trimesh.util.concatenate([separated, other]).export(path)
    result = meshes.operation(
        files, [{"path": str(path), "sha256": digest(path)}], "split", "split"
    )
    assert len(result["outputs"]) == 2


def test_hull_simplify_and_rejection(tmp_path):
    sources = cubes(tmp_path)
    files = Files([tmp_path])
    hull = meshes.operation(files, sources[:1], "hull", "convex_hull")
    assert hull["outputs"][0]["watertight"]
    simplified = meshes.operation(files, sources[:1], "simple", "simplify", {"face_count": 8})
    assert simplified["outputs"][0]["triangles"] <= 8
    with pytest.raises(ValueError, match="changed"):
        meshes.operation(files, [{**sources[0], "sha256": "wrong"}], "invalid", "repair")
    assert not files.path("invalid").exists()
    with pytest.raises(ValueError, match="new mesh"):
        meshes.operation(files, sources[:1], "hull", "repair")
