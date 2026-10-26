"""Real-engine smoke test. Save inputs/report before running expensive slicing.

ORCA_SLICER_BIN and ORCA_TEST_RESOURCES must reference the same official release.
No printer connection or physical print is started.
"""

import asyncio
import json
import os
from pathlib import Path

from rrs_orcaslicer_mcp.engine import Engine
from rrs_orcaslicer_mcp.profiles import resolve
from rrs_orcaslicer_mcp.storage import Files, atomic_json, digest


async def main():
    root = Path(os.environ.get("ORCA_TEST_OUTPUT", "smoke-output")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    resources = Path(os.environ["ORCA_TEST_RESOURCES"]).resolve()
    files = Files([root, resources])
    choices = {
        "machine": "BBL/machine/Bambu Lab A1 mini 0.4 nozzle.json",
        "process": "BBL/process/0.20mm Standard @BBL A1M.json",
        "filament": "BBL/filament/Bambu PLA Basic @BBL A1M.json",
    }
    for key, relative in choices.items():
        if (root / f"{key}.json").exists():
            continue
        profile = resolve(
            files, str(resources / "profiles" / relative), [str(resources / "profiles/BBL")]
        )["settings"]
        profile.pop("inherits", None)
        atomic_json(root / f"{key}.json", profile)
    vertices = [
        (85, 85, 0),
        (95, 85, 0),
        (95, 95, 0),
        (85, 95, 0),
        (85, 85, 10),
        (95, 85, 10),
        (95, 95, 10),
        (85, 95, 10),
    ]
    faces = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    stl = ["solid cube"]
    for face in faces:
        stl += ["facet normal 0 0 0", "outer loop"]
        stl += ["vertex " + " ".join(map(str, vertices[i])) for i in face]
        stl += ["endloop", "endfacet"]
    stl += ["endsolid cube"]
    (root / "cube.stl").write_text("\n".join(stl))
    engine = Engine(root / "jobs")
    report = {
        "phase": "inputs_saved",
        "capabilities": await engine.capabilities(),
        "inputs": choices,
    }
    atomic_json(root / "report.json", report)
    try:
        args = [
            "--slice",
            "0",
            "--load-settings",
            f"{root / 'machine.json'};{root / 'process.json'}",
            "--load-filaments",
            str(root / "filament.json"),
            "--outputdir",
            str(root / "output"),
            "--export-3mf",
            "cube-sliced.3mf",
            str(root / "cube.stl"),
        ]
        job = await engine.submit(args, timeout=300)
        report.update(phase="slicing", job=job)
        atomic_json(root / "report.json", report)
        await engine.tasks[job["id"]]
        job = engine.get(job["id"])
        report.update(phase="finished", job=job)
        artifacts = [p for p in root.rglob("*") if p.is_file() and p.suffix in (".gcode", ".3mf")]
        report["artifacts"] = [
            {"path": str(p.relative_to(root)), "size": p.stat().st_size, "sha256": digest(p)}
            for p in artifacts
        ]
        atomic_json(root / "report.json", report)
        if job["status"] != "succeeded" or not any(p.suffix == ".gcode" for p in artifacts):
            print(Path(job["log"]).read_text(errors="replace")[-10000:])
            raise SystemExit("Real OrcaSlicer slicing did not produce G-code")
        print(json.dumps({"status": job["status"], "artifacts": report["artifacts"]}, indent=2))
    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
