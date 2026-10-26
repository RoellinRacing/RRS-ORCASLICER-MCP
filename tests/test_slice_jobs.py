"""Public MCP contracts: a lost submission response must never duplicate slicing."""

import asyncio
import sys

import pytest

from rrs_orcaslicer_mcp import server
from rrs_orcaslicer_mcp.engine import Engine


async def test_single_slice_retry_hashes_profiles_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCA_MCP_ROOTS", str(tmp_path))
    monkeypatch.setenv("ORCA_MCP_STATE", str(tmp_path / "state"))
    engines = []

    def factory(state):
        value = Engine(state, binary=sys.executable)

        async def caps(refresh=False):
            await asyncio.sleep(0)
            return {"available": True, "flags": ["slice", "outputdir", "load-settings"]}

        value.capabilities = caps
        engines.append(value)
        return value

    monkeypatch.setattr(server, "Engine", factory)
    model, profile = tmp_path / "cube.stl", tmp_path / "profile.json"
    model.write_text("model bytes")
    profile.write_text('{"layer_height":"0.2"}')
    mcp = server.create_server()
    # FastMCP's registered function exercises the public tool arguments directly.
    tool = mcp._tool_manager.get_tool("slice_project").fn
    request = dict(
        inputs=[str(model)],
        settings=[str(profile)],
        output_directory=str(tmp_path / "out"),
        idempotency_key="lost-response",
    )
    try:
        first, duplicate = await asyncio.gather(tool(**request), tool(**request))
        assert first["id"] == duplicate["id"]
        assert set(first["expected_files"]) == {str(model), str(profile)}
        await engines[0].wait(first["id"], 5)
        await engines[0].close()
        fresh_tool = server.create_server()._tool_manager.get_tool("slice_project").fn
        again = await fresh_tool(**request)
        assert again["id"] == first["id"]
        assert not engines[-1].tasks
        for path in (model, profile):
            original = path.read_bytes()
            path.write_bytes(original + b" changed")
            with pytest.raises(ValueError, match="different inputs"):
                await fresh_tool(**request)
            path.write_bytes(original)
        with pytest.raises(ValueError, match="different inputs"):
            await fresh_tool(**{**request, "plate": 1})
        for key in ("", " ", "x" * 201):
            with pytest.raises(ValueError, match="idempotency key"):
                await fresh_tool(**{**request, "idempotency_key": key})
    finally:
        for engine in engines:
            if not engine._lock.closed:
                await engine.close()
