"""Reopen transformed/painted copies in stock Orca and inspect native roundtrip output.

Reuses smoke profiles/model; saves each result and resumes completed work. No GUI
interaction or physical printer involved. Run with ORCA_TEST_OUTPUT and engine env.
"""

import asyncio
import json
import os
import sys
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rrs_orcaslicer_mcp.storage import atomic_json


async def main():
    root = Path(os.environ["ORCA_TEST_OUTPUT"]).resolve()
    output = root / "semantics"
    output.mkdir(exist_ok=True)
    checkpoint = output / "report.json"
    report = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    if report.get("status") == "succeeded":
        print("Existing semantic verification passed; not repeating")
        return
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "rrs_orcaslicer_mcp.server"],
        env={**os.environ, "ORCA_MCP_ROOTS": str(root), "ORCA_MCP_STATE": str(output / "state")},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()

        async def call(name, args):
            result = await client.call_tool(name, args)
            if result.isError:
                raise RuntimeError(f"{name}: {result.content}")
            return result.structuredContent

        source = root / "output/cube-sliced.3mf"
        scene = await call("project_geometry_read", {"path": str(source)})
        matrix = scene["build"][0]["transform"][:]
        matrix[0] *= 1.1
        transformed = output / "transform.3mf"
        if not transformed.exists():
            await call(
                "project_transform_write",
                {
                    "source": str(source),
                    "destination": str(transformed),
                    "expected_source_sha256": scene["sha256"],
                    "matrix": matrix,
                },
            )
        observed = await call("project_geometry_read", {"path": str(transformed)})
        assert observed["build"][0]["transform"] == matrix
        with zipfile.ZipFile(transformed) as archive:
            members = [
                n for n in archive.namelist() if n.startswith("3D/") and n.endswith(".model")
            ]
        member, object_id = None, None
        for candidate in members:
            info = await call(
                "project_geometry_read", {"path": str(transformed), "member": candidate}
            )
            meshes = [o for o in info["objects"] if o["triangles"]]
            if meshes:
                member, object_id = candidate, meshes[0]["object_id"]
                break
        assert member and object_id
        current = transformed
        for kind in ("support", "seam", "material", "fuzzy_skin"):
            painting = await call(
                "project_painting_read",
                {"source": str(current), "object_id": object_id, "member": member},
            )
            destination = output / f"{kind}.3mf"
            if not destination.exists():
                await call(
                    "project_painting_write",
                    {
                        "source": str(current),
                        "destination": str(destination),
                        "expected_source_sha256": painting["sha256"],
                        "object_id": object_id,
                        "member": member,
                        "kind": kind,
                        "changes": [{"triangle": 0, "state": 1}],
                    },
                )
            current = destination
            report.update(status="painted", last_channel=kind, file=str(current))
            atomic_json(checkpoint, report)
        batch = await call(
            "batch_slice",
            {
                "inputs": [str(current)],
                "output_directory": str(output / "sliced"),
                "idempotency_key": "semantic-roundtrip-v1",
                "timeout_seconds": 300,
            },
        )
        report.update(status="slicing", batch_id=batch["id"])
        atomic_json(checkpoint, report)
        for _ in range(3000):
            state = await call("batch_status", {"batch_id": batch["id"]})
            if state["status"] != "running":
                break
            await asyncio.sleep(0.1)
        assert state["status"] == "succeeded", state
        sliced = Path(state["entries"][0]["output_directory"]) / "sliced.3mf"
        masks = []
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(sliced) as archive:
            for name in archive.namelist():
                if name.startswith("3D/") and name.endswith(".model"):
                    model = ET.fromstring(archive.read(name))
                    masks.extend(
                        t.attrib
                        for t in model.iter()
                        if t.tag.endswith("}triangle") and t.get("paint_supports")
                    )
        expected = {
            "paint_supports": "4",
            "paint_seam": "4",
            "paint_color": "4",
            "paint_fuzzy_skin": "4",
        }
        assert any(all(m.get(k) == v for k, v in expected.items()) for m in masks), masks
        final_scene = await call("project_geometry_read", {"path": str(sliced)})
        assert abs(final_scene["build"][0]["transform"][0] - matrix[0]) < 1e-5
        stats = await call("gcode_analyze", {"path": str(sliced.parent / "plate_1.gcode")})
        assert stats["declared_statistics"]["declared_layers"] > 0
        report.update(
            status="succeeded",
            native_roundtrip_masks=expected,
            transform_after=final_scene["build"][0]["transform"],
            gcode_sha256=stats["sha256"],
            physical_print_started=False,
        )
        atomic_json(checkpoint, report)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
