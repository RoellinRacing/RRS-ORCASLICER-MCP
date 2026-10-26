"""Exercise the full stdio MCP client -> 3MF edit -> real-engine slicing path."""

import asyncio
import json
import os
import sys
import time
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rrs_orcaslicer_mcp.storage import atomic_json, digest


async def main():
    root = Path(os.environ["ORCA_TEST_OUTPUT"]).resolve()
    report_path = root / "roundtrip-report.json"
    if (
        report_path.exists()
        and json.loads(report_path.read_text(encoding="utf-8")).get("status") == "succeeded"
    ):
        print("Verified roundtrip already saved; use a new ORCA_TEST_OUTPUT to run another test.")
        return
    source = root / "output/cube-sliced.3mf"
    changed = root / "changed.3mf"
    env = {**os.environ, "ORCA_MCP_ROOTS": str(root), "ORCA_MCP_STATE": str(root / "mcp-state")}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
    )
    report = {"status": "started", "original_sha256": digest(source)}
    atomic_json(report_path, report)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()

            async def call(name, args):
                result = await client.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(f"{name}: {result.content}")
                return result.structuredContent

            caps = await call("orca_capabilities", {})
            report["engine"] = caps["cli"]["help"].splitlines()[0]
            original = await call("project_inspect", {"path": str(source)})
            if not changed.exists():
                edited = await call(
                    "project_settings_write",
                    {
                        "source": str(source),
                        "destination": str(changed),
                        "changes": {"layer_height": "0.25"},
                        "expected_source_sha256": original["sha256"],
                    },
                )
                report["removed_slice_artifacts"] = edited["removed_slice_artifacts"]
            assert digest(source) == report["original_sha256"]
            with zipfile.ZipFile(changed) as archive:
                assert "Metadata/plate_1.gcode" not in archive.namelist()
                assert (
                    json.loads(archive.read("Metadata/project_settings.config"))["layer_height"]
                    == "0.25"
                )
            job = await call(
                "slice_project",
                {
                    "inputs": [str(changed)],
                    "output_directory": str(root / "roundtrip-output"),
                    "export_3mf": "verified.3mf",
                    "timeout_seconds": 300,
                },
            )
            report.update(status="slicing", job_id=job["id"])
            atomic_json(report_path, report)
            started = time.monotonic()
            while True:
                state = await call("job_status", {"job_id": job["id"]})
                if state["status"] not in ("queued", "running"):
                    break
                if time.monotonic() - started > 310:
                    raise TimeoutError("MCP slicing exceeded its timeout")
                await asyncio.sleep(0.1)
            report["job_status"] = state["status"]
            assert state["status"] == "succeeded", state.get("log_tail")
            result_project = root / "roundtrip-output/verified.3mf"
            with zipfile.ZipFile(result_project) as archive:
                settings = json.loads(archive.read("Metadata/project_settings.config"))
                assert settings["layer_height"] == "0.25"
                assert len(archive.read("Metadata/plate_1.gcode")) > 10000
            gcode = root / "roundtrip-output/plate_1.gcode"
            assert gcode.stat().st_size > 10000
            report.update(
                status="succeeded",
                layer_height=settings["layer_height"],
                gcode_sha256=digest(gcode),
                gcode_bytes=gcode.stat().st_size,
                project_sha256=digest(result_project),
            )
            atomic_json(report_path, report)
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
