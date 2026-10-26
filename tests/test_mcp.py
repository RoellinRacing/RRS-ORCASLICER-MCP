import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_real_stdio_protocol(tmp_path):
    env = {**os.environ, "ORCA_MCP_ROOTS": str(tmp_path), "ORCA_MCP_STATE": str(tmp_path / "state")}
    env.pop("ORCA_SLICER_BIN", None)
    params = StdioServerParameters(command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            result = await client.initialize()
            assert result.serverInfo.name == "RRS OrcaSlicer MCP"
            tools = await client.list_tools()
            assert {"slice_project", "desktop_action", "project_metadata_write"} <= {t.name for t in tools.tools}
            created = await client.call_tool("settings_write", {"path": "p.json", "changes": {"future": "yes"}})
            assert not created.isError
            readback = await client.call_tool("settings_read", {"path": "p.json"})
            assert readback.structuredContent["settings"]["future"] == "yes"
            denied = await client.call_tool("settings_write", {"path": "p.json", "changes": {"future": "no"}})
            assert denied.isError
            catalog = await client.call_tool("settings_catalog", {"query": "layer_height"})
            assert not catalog.isError
            assert catalog.structuredContent["total"] > 0
