"""Operation-level acceptance on the disposable stock-Orca X11 desktop.

Called by verify_host_gui.py after baseline native acceptance. Reuses the running
app, profiles, model and bridge; never creates a user printer/account connection.
Every completed operation is checkpointed before proceeding.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rrs_orcaslicer_mcp.storage import atomic_json


async def verify(client, root, evidence, main_window):
    output = client.directory / "exports/native"
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "operations": [], "physical_print_started": False}
    report_path = evidence / "native-workflows.json"
    env = {
        **os.environ,
        "ORCA_MCP_DESKTOP": "1",
        "ORCA_MCP_BRIDGE": str(client.directory),
        "ORCA_MCP_ROOTS": str(client.directory),
        "ORCA_MCP_STATE": str(root / "native-mcp-state"),
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as mcp:
        await mcp.initialize()

        async def call(name, arguments):
            response = await mcp.call_tool(name, arguments)
            if response.isError:
                raise AssertionError((name, response.content))
            return response.structuredContent

        async def scene():
            return await call("native_scene_read", {})

        async def operate(name, arguments):
            current = await scene()
            subprocess.run(["xdotool", "windowactivate", "--sync", main_window], check=True)
            args = {
                **arguments,
                "expected_revision": current["revision"],
                "session_id": client.status()["session_id"],
                "request_id": uuid.uuid4().hex,
            }
            result = await call(name, args)
            report["operations"].append({"tool": name, "arguments": args, "result": result})
            atomic_json(report_path, report)
            assert result["status"] == "succeeded", result
            repeated = await call(name, args)
            assert repeated == result, (
                "Typed GUI request replayed instead of returning saved receipt"
            )
            return result

        baseline = await scene()
        for kind, axis, value in (("move", "x", 7), ("rotate", "z", 15), ("scale", "x", 110)):
            before = await scene()
            moved = await operate("native_transform", {"kind": kind, "axis": axis, "value": value})
            undone = await operate("native_history", {"direction": "undo"})
            assert undone["after"]["revision"] == before["revision"], (kind, before, undone)
            redone = await operate("native_history", {"direction": "redo"})
            assert redone["after"]["revision"] == moved["after"]["revision"], kind
            await operate("native_history", {"direction": "undo"})
        assert (await scene())["revision"] == baseline["revision"]

        text = await operate(
            "native_text",
            {
                "text": "RRS",
                "height_mm": 8,
                "depth_mm": 1.2,
                "mode": "join",
                "backup": str(output / "before-text.3mf"),
                "destination": str(output / "editable-text.3mf"),
            },
        )
        assert any(e["text"]["text"] == "RRS" for e in text["native_metadata"]["editable_texts"])
        # Closing Orca's gizmo collapses its own action history. Use actual native
        # steps until the added text has been undone; retain every result.
        for _ in range(8):
            current = await scene()
            if len(current["objects"]) == 1 and current["objects"][0]["volume_count"] == 1:
                break
            await operate("native_history", {"direction": "undo"})
        current = await scene()
        assert len(current["objects"]) == 1 and current["objects"][0]["volume_count"] == 1

        for kind, values in (
            ("temperature", {"start": 220, "end": 210}),
            ("pressure_advance", {"start": 0, "end": 0.02, "step": 0.005, "method": "tower"}),
            ("retraction", {"start": 0, "end": 1, "step": 0.2}),
            ("max_volumetric_speed", {"start": 5, "end": 7, "step": 0.5}),
            ("flow_ratio", {"test": "pass_1"}),
        ):
            result = await operate(
                "native_calibration",
                {
                    "kind": kind,
                    "values": values,
                    "backup": str(output / f"before-{kind}.3mf"),
                    "destination": str(output / f"native-{kind}.3mf"),
                    "replace_scene": True,
                },
            )
            assert result["native_metadata"]["object_count"] > 0
            assert Path(result["export"]["path"]).stat().st_size > 1000
        report.update(
            status="succeeded",
            app=baseline["app"],
            actual_native_undo_redo=True,
            editable_native_text=True,
            native_generators=[
                "temperature",
                "pressure_advance",
                "retraction",
                "max_volumetric_speed",
                "flow_ratio",
            ],
        )
        atomic_json(report_path, report)
        print(json.dumps({k: v for k, v in report.items() if k != "operations"}), flush=True)
    return {k: v for k, v in report.items() if k != "operations"}
