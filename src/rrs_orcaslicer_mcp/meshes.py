"""Optional offline mesh operations; STL outputs have explicit, measured geometry."""

import hashlib
import io
import math
from importlib.metadata import version

from .storage import Files, atomic_bytes, atomic_json, digest


def backend():
    try:
        import trimesh
        import numpy as np
    except ImportError:
        raise ValueError(
            "Install rrs-orcaslicer-mcp[geometry] for offline mesh operations"
        ) from None
    return trimesh, np


def load(files, path, expected):
    trimesh, np = backend()
    src = files.path(path, True)
    if src.suffix.lower() not in (".stl", ".ply") or src.stat().st_size > 128 * 1024**2:
        raise ValueError("Mesh input must be STL/PLY up to 128 MiB")
    raw = src.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Mesh source changed; read SHA256 again")
    mesh = trimesh.load_mesh(io.BytesIO(raw), file_type=src.suffix[1:].lower(), process=True)
    if (
        not isinstance(mesh, trimesh.Trimesh)
        or not len(mesh.faces)
        or not np.isfinite(mesh.vertices).all()
    ):
        raise ValueError("Expected a nonempty finite triangle mesh")
    return mesh


def metrics(mesh):
    return {
        "vertices": len(mesh.vertices),
        "triangles": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": float(mesh.volume) if mesh.is_volume else None,
        "bounds_mm": mesh.bounds.tolist(),
        "area_mm2": float(mesh.area),
    }


def inspect(files, source, expected):
    mesh = load(files, source, expected)
    return {
        "source": str(files.path(source)),
        "sha256": expected,
        **metrics(mesh),
        "units": "Assumed millimeters; STL has no intrinsic unit",
    }


def operation(
    files: Files, sources: list[dict], destination: str, action: str, parameters: dict | None = None
):
    trimesh, np = backend()
    parameters = parameters or {}
    if not isinstance(sources, list) or not 1 <= len(sources) <= 32:
        raise ValueError("Provide 1..32 sources with path and sha256")
    supported = {
        "repair",
        "split",
        "cut",
        "merge",
        "union",
        "difference",
        "intersection",
        "convex_hull",
        "simplify",
        "transform",
    }
    if action not in supported:
        raise ValueError("Unknown mesh operation")
    allowed = {
        "cut": {"origin", "normal", "cap"},
        "simplify": {"face_count"},
        "transform": {"matrix"},
    }
    if set(parameters) - allowed.get(action, set()):
        raise ValueError("Unknown parameters for mesh operation")
    if action not in {"merge", "union", "difference", "intersection"} and len(sources) != 1:
        raise ValueError("This operation requires exactly one input")
    if action in {"union", "difference", "intersection"} and len(sources) < 2:
        raise ValueError("Boolean operations need at least two input volumes")
    folder = files.path(destination)
    if folder.exists():
        raise ValueError("Choose a new mesh output directory")
    meshes = [load(files, item["path"], item["sha256"]) for item in sources]
    mesh = meshes[0].copy()
    # Save intent before potentially expensive geometry. Inputs remain recoverable.
    folder.mkdir(parents=True)
    checkpoint = folder / "mesh-operation.json"
    report = {
        "status": "computing",
        "action": action,
        "parameters": parameters,
        "inputs": sources,
        "before": [metrics(m) for m in meshes],
        "outputs": [],
        "engine_versions": {k: version(k) for k in ("trimesh", "numpy")},
        "scope": "Offline STL results; reimport into Orca. No 3MF settings/painting transferred.",
    }
    atomic_json(checkpoint, report)
    try:
        if action == "repair":
            mesh.merge_vertices()
            mesh.update_faces(mesh.unique_faces())
            mesh.update_faces(mesh.nondegenerate_faces())
            mesh.remove_unreferenced_vertices()
            trimesh.repair.fix_normals(mesh, multibody=True)
            trimesh.repair.fill_holes(mesh)
            results = [mesh]
        elif action == "split":
            results = list(mesh.split(only_watertight=False))
        elif action == "merge":
            results = [trimesh.util.concatenate(meshes)]
        elif action in {"union", "difference", "intersection"}:
            if not all(m.is_volume for m in meshes):
                raise ValueError(
                    "Boolean input must consist of consistently oriented watertight volumes"
                )
            results = [
                getattr(trimesh.boolean, action)(meshes, engine="manifold", check_volume=True)
            ]
        elif action == "convex_hull":
            results = [mesh.convex_hull]
        elif action == "simplify":
            faces = parameters.get("face_count")
            if type(faces) is not int or not 4 <= faces < len(mesh.faces):
                raise ValueError("face_count must be 4..current triangle count minus one")
            results = [mesh.simplify_quadric_decimation(face_count=faces)]
        elif action == "transform":
            matrix = np.asarray(parameters.get("matrix"), dtype=float)
            if (
                matrix.shape != (4, 4)
                or not np.isfinite(matrix).all()
                or not np.allclose(matrix[3], [0, 0, 0, 1])
                or abs(np.linalg.det(matrix[:3, :3])) < 1e-12
            ):
                raise ValueError("Provide a finite invertible affine 4x4 column-vector matrix")
            mesh.apply_transform(matrix)
            results = [mesh]
        elif action == "cut":
            origin = parameters.get("origin")
            normal = parameters.get("normal")
            if any(
                not isinstance(v, list)
                or len(v) != 3
                or any(type(x) not in (float, int) or not math.isfinite(x) for x in v)
                for v in (origin, normal)
            ):
                raise ValueError("Cut origin and normal need three finite coordinates")
            if np.linalg.norm(normal) < 1e-12 or type(parameters.get("cap", True)) is not bool:
                raise ValueError("Nonzero normal and boolean cap required")
            results = [
                mesh.slice_plane(origin, normal, cap=parameters.get("cap", True)),
                mesh.slice_plane(origin, [-v for v in normal], cap=parameters.get("cap", True)),
            ]
        if not results or len(results) > 128:
            raise ValueError("Operation produced no meshes or more than 128 components")
        for index, result in enumerate(results):
            if not len(result.faces) or not np.isfinite(result.vertices).all():
                raise ValueError("Operation produced empty/nonfinite geometry")
            target = folder / f"{index:03d}-{action}.stl"
            atomic_bytes(target, result.export(file_type="stl"))
            # Measure the serialized and reloaded result, not just in-memory intent.
            reloaded = load(files, str(target), digest(target))
            report["outputs"].append(
                {"path": str(target), "sha256": digest(target), **metrics(reloaded)}
            )
            atomic_json(checkpoint, report)
    except BaseException as exc:
        report.update(
            status="failed", error=type(exc).__name__, completed_outputs=len(report["outputs"])
        )
        atomic_json(checkpoint, report)
        raise
    report["status"] = "succeeded"
    atomic_json(checkpoint, report)
    return report
