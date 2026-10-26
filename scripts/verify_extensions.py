"""Verify semantic project edits, profile helpers, batch identity and real output via MCP.

Reuses the saved smoke model/profiles; does not rerun their generation. Results are
checkpointed before slicing and after each finished section.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rrs_orcaslicer_mcp.storage import atomic_json


async def main():
    root = Path(os.environ["ORCA_TEST_OUTPUT"]).resolve()
    output = root / "extensions"
    output.mkdir(exist_ok=True)
    report_path = output / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    if report.get("status") == "succeeded":
        print("Saved extension verification already succeeded; not repeating it.")
        return
    source = root / "output/cube-sliced.3mf"
    env = {
        **os.environ,
        "ORCA_MCP_ROOTS": str(root),
        "ORCA_MCP_STATE": str(output / "server-state"),
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()

            async def call(name, arguments):
                result = await client.call_tool(name, arguments)
                if result.isError:
                    raise RuntimeError(f"{name}: {result.content}")
                return result.structuredContent

            original = await call("project_objects_read", {"path": str(source)})
            object_id = original["objects"][0]["object_id"]
            modified = output / "object.3mf"
            if not modified.exists():
                await call(
                    "project_target_settings_write",
                    {
                        "source": str(source),
                        "destination": str(modified),
                        "target": "object",
                        "target_id": object_id,
                        "changes": {"wall_loops": "4"},
                        "expected_source_sha256": original["sha256"],
                    },
                )
            modified_state = await call("project_objects_read", {"path": str(modified)})
            assert modified_state["objects"][0]["settings"]["wall_loops"] == "4"
            plate_project = output / "plate.3mf"
            if not plate_project.exists():
                await call(
                    "project_target_settings_write",
                    {
                        "source": str(modified),
                        "destination": str(plate_project),
                        "target": "plate",
                        "target_id": modified_state["plates"][0]["plate_id"],
                        "changes": {"plater_name": "MCP Testplatte"},
                        "expected_source_sha256": modified_state["sha256"],
                    },
                )
            plate_state = await call("project_objects_read", {"path": str(plate_project)})
            assert plate_state["plates"][0]["settings"]["plater_name"] == "MCP Testplatte"
            report.update(
                status="project_edits_verified",
                object_id=object_id,
                object_wall_loops="4",
                plate_name="MCP Testplatte",
            )
            atomic_json(report_path, report)

            flat_profile = output / "process-flat.json"
            if not flat_profile.exists():
                await call(
                    "profile_export",
                    {
                        "source": str(root / "process.json"),
                        "destination": str(flat_profile),
                        "name": "MCP independent process",
                        "search_directories": [],
                    },
                )
            difference = await call(
                "settings_compare",
                {"left_path": str(root / "process.json"), "right_path": str(flat_profile)},
            )
            assert difference["changed"]["name"]["after"] == "MCP independent process"
            invalid = await call(
                "settings_validate", {"values": {"wall_loops": "2.5", "future_key": "keep"}}
            )
            assert invalid["findings"] and invalid["unknown_keys_preserved"] == ["future_key"]
            report["profile_checks"] = "passed"
            atomic_json(report_path, report)

            request = {
                "inputs": [str(source), str(plate_project)],
                "output_directory": str(output / "batch-output"),
                "idempotency_key": os.environ.get(
                    "ORCA_EXT_BATCH_KEY", "reference-extensions-v0.2.0"
                ),
                "timeout_seconds": 300,
            }
            batch = await call("batch_slice", request)
            report.update(status="batch_running", batch_id=batch["id"])
            atomic_json(report_path, report)
            for _ in range(3000):
                state = await call("batch_status", {"batch_id": batch["id"]})
                if state["status"] not in ("running",):
                    break
                await asyncio.sleep(0.1)
            assert state["status"] == "succeeded", state
            repeated = await call("batch_slice", request)
            assert [e["job_id"] for e in repeated["entries"]] == [
                e["job_id"] for e in state["entries"]
            ]
            assert repeated["status"] == "succeeded"
            results = []
            for entry in state["entries"]:
                folder = Path(entry["output_directory"])
                analysis = await call("gcode_analyze", {"path": str(folder / "plate_1.gcode")})
                assert analysis["declared_statistics"]["declared_layers"] > 0
                assert analysis["estimated_seconds"]["total estimated time"] > 0
                result_objects = await call(
                    "project_objects_read", {"path": str(folder / "sliced.3mf")}
                )
                results.append(
                    {
                        "gcode_sha256": analysis["sha256"],
                        "gcode_bytes": analysis["bytes"],
                        "declared_statistics": analysis["declared_statistics"],
                        "estimated_seconds": analysis["estimated_seconds"],
                        "object_settings": result_objects["objects"][0]["settings"],
                    }
                )
            assert results[1]["object_settings"]["wall_loops"] == "4"
            report.update(
                status="succeeded",
                batch_status=state["status"],
                duplicate_jobs_on_retry=False,
                results=results,
            )
            atomic_json(report_path, report)
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
