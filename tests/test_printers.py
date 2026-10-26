import json

import httpx
import pytest

from rrs_orcaslicer_mcp.printers import Printers
from rrs_orcaslicer_mcp.storage import Files, digest


@pytest.fixture
def hosts(tmp_path, monkeypatch):
    config = tmp_path / "printers.json"
    config.write_text(
        json.dumps(
            {
                "test": {
                    "provider": "octoprint",
                    "url": "https://example.invalid/octo",
                    "api_key_env": "TEST_PRINT_KEY",
                }
            }
        )
    )
    monkeypatch.setenv("ORCA_MCP_PRINTERS", str(config))
    monkeypatch.setenv("TEST_PRINT_KEY", "SECRET")
    return config


async def test_explicit_pause_resume_duplicate_and_id_conflict(hosts, tmp_path):
    seen = []

    def handler(request):
        assert request.headers["X-Api-Key"] == "SECRET"
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(204)

    printers = Printers(tmp_path / "state", httpx.MockTransport(handler))
    first = await printers.dispatch("test", "a" * 32, "pause")
    assert first["status"] == "acknowledged"
    assert await printers.dispatch("test", "a" * 32, "pause") == first
    assert seen == [("/octo/api/job", {"command": "pause", "action": "pause"})]
    with pytest.raises(ValueError, match="different parameters"):
        await printers.dispatch("test", "a" * 32, "resume")
    assert "SECRET" not in json.dumps(printers.capabilities())
    assert "SECRET" not in (tmp_path / "state" / ("a" * 32 + ".json")).read_text()


async def test_transport_uncertainty_survives_restart(hosts, tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        raise httpx.ReadTimeout("secret response")

    state = tmp_path / "state"
    first = Printers(state, httpx.MockTransport(handler))
    result = await first.dispatch("test", "b" * 32, "start", "cube.gcode")
    assert result["status"] == "outcome_unknown"
    second = Printers(state, httpx.MockTransport(handler))
    assert await second.dispatch("test", "b" * 32, "start", "cube.gcode") == result
    assert len(seen) == 1 and "secret response" not in json.dumps(result)


async def test_moonraker_upload_is_separate_from_start(hosts, tmp_path):
    hosts.write_text(
        json.dumps({"test": {"provider": "moonraker", "url": "http://example.invalid"}})
    )
    path = tmp_path / "cube.gcode"
    path.write_text("G1 X1\n")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"result": "ok"})

    printers = Printers(tmp_path / "state", httpx.MockTransport(handler))
    result = await printers.dispatch(
        "test", "c" * 32, "upload", "cube.gcode", Files([tmp_path]), str(path), digest(path)
    )
    assert result["status"] == "acknowledged"
    assert seen[0].url.path == "/server/files/upload"
    assert b'filename="cube.gcode"' in seen[0].content
    assert b"false" in seen[0].content
    await printers.dispatch("test", "d" * 32, "start", "cube.gcode")
    assert seen[1].url.path == "/printer/print/start"
    assert json.loads(seen[1].content) == {"filename": "cube.gcode"}
    with pytest.raises(ValueError, match="checksum"):
        await printers.dispatch(
            "test", "e" * 32, "upload", "cube.gcode", Files([tmp_path]), str(path), "wrong"
        )
    assert len(seen) == 2


async def test_invalid_target_or_name_never_dispatches(hosts, tmp_path):
    printers = Printers(tmp_path / "state")
    for name in ("../cube.gcode", "cube.gcode?print=true", "cube\ngcode", "cube.bgcode"):
        with pytest.raises(ValueError, match="filename"):
            await printers.dispatch("test", "a" * 32, "start", name)
    hosts.write_text(
        json.dumps({"test": {"provider": "octoprint", "url": "https://name:secret@host"}})
    )
    with pytest.raises(ValueError, match="without credentials"):
        printers.capabilities()
