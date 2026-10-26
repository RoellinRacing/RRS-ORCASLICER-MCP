import os
import sys
import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_real_stdio_protocol(tmp_path):
    env = {**os.environ, "ORCA_MCP_ROOTS": str(tmp_path), "ORCA_MCP_STATE": str(tmp_path / "state")}
    env.pop("ORCA_SLICER_BIN", None)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            result = await client.initialize()
            assert result.serverInfo.name == "RRS OrcaSlicer MCP"
            tools = await client.list_tools()
            assert {"slice_project", "desktop_action", "project_metadata_write"} <= {
                t.name for t in tools.tools
            }
            created = await client.call_tool(
                "settings_write", {"path": "p.json", "changes": {"future": "yes"}}
            )
            assert not created.isError
            readback = await client.call_tool("settings_read", {"path": "p.json"})
            assert readback.structuredContent["settings"]["future"] == "yes"
            denied = await client.call_tool(
                "settings_write", {"path": "p.json", "changes": {"future": "no"}}
            )
            assert denied.isError
            catalog = await client.call_tool("settings_catalog", {"query": "layer_height"})
            assert not catalog.isError
            assert catalog.structuredContent["total"] > 0


async def test_disconnect_cancels_running_job(tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text("import time; time.sleep(30)", encoding="utf-8")
    env = {
        **os.environ,
        "ORCA_MCP_ROOTS": str(tmp_path),
        "ORCA_MCP_STATE": str(tmp_path / "state"),
        "ORCA_SLICER_BIN": sys.executable,
    }
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            result = await client.call_tool("cli_run", {"arguments": [str(worker)]})
            assert not result.isError
            ident = result.structuredContent["id"]
            for _ in range(100):
                state = await client.call_tool("job_status", {"job_id": ident})
                if state.structuredContent["status"] == "running":
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("Worker did not start")
    saved = json.loads((tmp_path / "state/jobs" / ident / "job.json").read_text(encoding="utf-8"))
    assert saved["status"] == "cancelled"
