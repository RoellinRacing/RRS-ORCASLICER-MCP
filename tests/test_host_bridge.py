import asyncio
import json
import runpy
import sys
import threading
import time
import types
import uuid
from pathlib import Path

import pytest

from rrs_orcaslicer_mcp.host_bridge.client import HostClient
from rrs_orcaslicer_mcp.host_bridge.protocol import (
    BRIDGE_PROTOCOL,
    MAX_REQUEST_BYTES,
    bridge_fingerprint,
    bridge_read,
    bridge_write,
)
from rrs_orcaslicer_mcp.host_bridge.service import HostService


@pytest.fixture
def host(tmp_path):
    gui_thread = threading.get_ident()
    values = {"wall_loops": "2", "layer_height": "0.2", "printhost_apikey": "DO-NOT-EXPOSE"}
    preset = types.SimpleNamespace(
        name="Test Process",
        is_dirty=False,
        config_keys=lambda: list(values),
        config_value=lambda k: values.get(k),
    )
    stats = {"commits": 0, "delay": 0}

    def on_gui(value):
        assert threading.get_ident() == gui_thread
        return value

    collection = types.SimpleNamespace(
        get_edited_preset=lambda: on_gui(preset),
        find_preset=lambda n: on_gui(preset if n == preset.name else None),
        preset_names=lambda: on_gui([preset.name]),
        get_selected_preset_name=lambda: on_gui(preset.name),
    )

    def begin_update(name):
        assert threading.get_ident() != gui_thread
        if name != preset.name:
            raise ValueError("Target not selectable")
        changes = {}

        def commit():
            if "unknown" in changes:
                raise ValueError("Unknown setting")
            time.sleep(stats["delay"])
            values.update(changes)
            preset.is_dirty = True
            stats["commits"] += 1
            return types.SimpleNamespace(
                target_name=name,
                category="process",
                keys=list(changes),
                dirty=True,
                selection_changed=False,
                slot_assignment_changed=False,
                shared_slots=[],
            )

        return types.SimpleNamespace(set=lambda k, v: changes.update({k: v}), commit=commit)

    class Plater:
        def export_3mf_copy(self, path):
            on_gui(None)
            Path(path).write_bytes(b"test project")

    editor = types.SimpleNamespace(begin_update=begin_update)
    bundle = types.SimpleNamespace(prints=collection, printers=collection, filaments=collection)
    module = types.SimpleNamespace(
        host=types.SimpleNamespace(
            Plater=Plater,
            plater=lambda: Plater(),
            preset_bundle=lambda: on_gui(bundle),
            preset=types.SimpleNamespace(process=editor, printer=editor, filament=editor),
        )
    )
    service = HostService(module, tmp_path / "bridge", [tmp_path / "exports"])
    service.heartbeat()
    return service, HostClient(tmp_path / "bridge"), values, stats


async def exchange(service, client, operation, params, **kwargs):
    task = asyncio.create_task(client.call(operation, params, **kwargs))
    for _ in range(100):
        if task.done():
            return await task
        service.poll_ui()
        await asyncio.to_thread(service.poll_worker)
        await asyncio.sleep(0.01)
    raise AssertionError("Exchange did not complete")


def params(changes=None):
    return {
        "kind": "process",
        "preset_name": "Test Process",
        "changes": changes or {"wall_loops": "4"},
    }


async def test_reads_stay_on_gui_thread_and_redact_secrets(host):
    service, client, _, _ = host
    reply = await exchange(service, client, "preset.read", {"kind": "process"})
    assert reply["status"] == "succeeded"
    assert reply["result"]["values"]["printhost_apikey"] == "[redacted]"
    assert "DO-NOT-EXPOSE" not in json.dumps(reply)
    assert "token" not in client.status()


async def test_transaction_runs_once_on_worker_and_remains_unsaved(host):
    service, client, values, stats = host
    ident = uuid.uuid4().hex
    reply = await exchange(
        service, client, "preset.update", params(), session_id=service.session_id, request_id=ident
    )
    assert reply["status"] == "succeeded"
    assert reply["result"]["saved_to_disk"] is False
    assert values["wall_loops"] == "4"
    repeated = await client.call(
        "preset.update", params(), session_id=service.session_id, request_id=ident
    )
    assert repeated == reply and stats["commits"] == 1
    with pytest.raises(ValueError, match="different"):
        await client.call(
            "preset.update",
            params({"wall_loops": "6"}),
            session_id=service.session_id,
            request_id=ident,
        )


async def test_failed_host_validation_preserves_existing_settings(host):
    service, client, values, stats = host
    reply = await exchange(
        service,
        client,
        "preset.update",
        params({"wall_loops": "4", "unknown": "x"}),
        session_id=service.session_id,
        request_id=uuid.uuid4().hex,
    )
    assert reply["status"] == "failed"
    assert values["wall_loops"] == "2" and stats["commits"] == 0


async def test_mutations_require_session_and_explicit_request_identity(host):
    service, client, _, _ = host
    with pytest.raises(ValueError, match="require"):
        await client.call("preset.update", {})
    with pytest.raises(ValueError, match="session changed"):
        await client.call(
            "preset.update", {}, session_id=uuid.uuid4().hex, request_id=uuid.uuid4().hex
        )
    assert not (service.folder / "requests").exists()


async def test_export_is_bounded_and_never_overwrites(host, tmp_path):
    service, client, _, _ = host
    good = tmp_path / "exports/copy.3mf"
    ident = uuid.uuid4().hex
    reply = await exchange(
        service,
        client,
        "project.export",
        {"destination": str(good)},
        session_id=service.session_id,
        request_id=ident,
    )
    assert reply["status"] == "succeeded" and good.read_bytes() == b"test project"
    for destination in (str(good), str(tmp_path / "outside.3mf"), "relative.3mf"):
        result = await exchange(
            service,
            client,
            "project.export",
            {"destination": destination},
            session_id=service.session_id,
            request_id=uuid.uuid4().hex,
        )
        assert result["status"] == "failed"


def write_request(service, operation, arguments, **overrides):
    ident = uuid.uuid4().hex
    request = {
        "protocol": BRIDGE_PROTOCOL,
        "session_id": service.session_id,
        "request_id": ident,
        "token": service.token,
        "operation": operation,
        "params": arguments,
        "fingerprint": bridge_fingerprint(operation, arguments),
        "expires": time.time() + 30,
        **overrides,
    }
    bridge_write(service.folder / "requests" / f"{ident}.json", request)
    return ident


def test_wrong_token_expiry_and_arbitrary_operations_do_not_call_host(host):
    service, client, _, stats = host
    wrong = write_request(service, "preset.update", {}, token="incorrect")
    expired = write_request(service, "preset.update", {}, expires=0)
    unknown = write_request(service, "python.eval", {"code": "anything"})
    service.poll_ui()
    assert client.result(service.session_id, wrong)["status"] == "not_observed"
    assert client.result(service.session_id, expired)["status"] == "rejected"
    assert client.result(service.session_id, unknown)["status"] == "rejected"
    assert stats["commits"] == 0 and not service.queue


def test_requests_beyond_first_64_are_processed_without_repeating(host):
    service, client, _, _ = host
    identifiers = [write_request(service, "bridge.ping", {}) for _ in range(70)]
    for _ in range(12):
        service.poll_ui()
    assert all(
        client.result(service.session_id, ident)["status"] == "succeeded" for ident in identifiers
    )


async def test_timeout_is_indeterminate_and_receipt_is_recoverable(host):
    service, client, _, stats = host
    stats["delay"] = 1.2
    ident = uuid.uuid4().hex
    task = asyncio.create_task(
        client.call(
            "preset.update", params(), timeout=1, session_id=service.session_id, request_id=ident
        )
    )
    await asyncio.sleep(0.05)
    service.poll_ui()
    worker = asyncio.create_task(asyncio.to_thread(service.poll_worker))
    result = await task
    assert result["status"] == "outcome_unknown"
    await worker
    assert client.result(service.session_id, ident)["status"] == "succeeded"
    assert stats["commits"] == 1


def test_shutdown_rejects_unstarted_mutations(host):
    service, client, _, stats = host
    ident = write_request(service, "preset.update", {})
    service.poll_ui()
    service.close()
    service.poll_worker()
    assert client.result(service.session_id, ident)["status"] == "rejected"
    assert client.status()["online"] is False and stats["commits"] == 0


def test_limits_and_symlinks(tmp_path):
    with pytest.raises(ValueError):
        bridge_write(tmp_path / "large.json", {"x": "x" * MAX_REQUEST_BYTES}, MAX_REQUEST_BYTES)
    path = tmp_path / "data.json"
    bridge_write(path, {"value": "ok"})
    link = tmp_path / "link.json"
    try:
        link.symlink_to(path)
    except OSError:
        return
    with pytest.raises(ValueError):
        bridge_read(link)


def test_standalone_plugin_registers_without_external_dependencies(monkeypatch):
    module = types.ModuleType("orca")
    registered = []
    module.base = type("Package", (), {})
    module.script = types.SimpleNamespace(ScriptPluginCapabilityBase=type("Script", (), {}))
    module.plugin = lambda cls: cls
    module.register_capability = registered.append
    monkeypatch.setitem(sys.modules, "orca", module)
    path = Path(__file__).parents[1] / "src/rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py"
    values = runpy.run_path(str(path))
    values["RRSBridgePackage"]().register_capabilities()
    assert len(registered) == 1 and registered[0]().get_name() == "RRS MCP local bridge"
