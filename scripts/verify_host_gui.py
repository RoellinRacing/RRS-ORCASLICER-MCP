"""Real official-host test on an isolated X11 CI desktop, never on a user's session.

Prerequisites: matching nightly AppImage/resources, completed smoke_orca outputs,
Xvfb, xdotool, screenshot support and Tesseract. Save diagnostics on every failure.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import time
import uuid
import sys
import zipfile
from pathlib import Path

from rrs_orcaslicer_mcp.host_bridge.client import HostClient
from rrs_orcaslicer_mcp.storage import atomic_json, digest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


root = Path(os.environ["ORCA_TEST_OUTPUT"]).resolve()
evidence = root / "host-evidence"
data = root / "isolated-host-data"
evidence.mkdir(parents=True, exist_ok=True)
data.mkdir(parents=True, exist_ok=True)
source_root = Path(__file__).resolve().parents[1]


def prepare():
    for kind, directory in (
        ("machine", "machine"),
        ("process", "process"),
        ("filament", "filament"),
    ):
        value = json.loads((root / f"{kind}.json").read_text(encoding="utf-8"))
        value.update(name=f"RRS Test {kind}", **{"from": "User"})
        value.pop("inherits", None)
        value.pop("setting_id", None)
        if kind == "machine":
            value["default_print_profile"] = "RRS Test process"
            value["default_filament_profile"] = ["RRS Test filament"]
        else:
            value["compatible_printers"] = ["RRS Test machine"]
        atomic_json(data / "user/default" / directory / f"RRS Test {kind}.json", value)
    atomic_json(
        data / "OrcaSlicer.conf",
        {
            "app": {
                "version": "2.5.0",
                "preset_folder": "default",
                "translation_language": "en_US",
                "stealth_mode": True,
                "sync_system_preset": False,
                "sync_user_preset": False,
                "check_update": False,
                "auto_check_update": False,
                "remember_printer_config": True,
            },
            "presets": {
                "printer": "RRS Test machine",
                "print": "RRS Test process",
                "filaments": ["RRS Test filament"],
            },
        },
    )
    plugin = source_root / "src/rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py"
    install = data / "orca_plugins" / plugin.name
    install.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plugin, install / plugin.name)
    atomic_json(
        install / ".install_state.json",
        {
            "installed_from": "local",
            "installed_version": "0.3.0",
            "plugin_name": "RRS OrcaSlicer Bridge",
            "enabled": True,
            "capabilities": [{"RRS MCP local bridge": True}],
        },
    )
    atomic_json(
        evidence / "prepared.json",
        {
            "plugin_sha256": digest(plugin),
            "data_directory": str(data),
            "source_project_sha256": digest(root / "output/cube-sliced.3mf"),
        },
    )


def screenshot(label):
    import pyautogui
    import pytesseract

    image = pyautogui.screenshot()
    image.save(evidence / f"{label}.png")
    text = pytesseract.image_to_string(image)
    (evidence / f"{label}.txt").write_text(text, encoding="utf-8")
    print(label, text[:1500], flush=True)
    return image


def click_word(word, partial=False):
    import pyautogui
    import pytesseract

    words = pytesseract.image_to_data(pyautogui.screenshot(), output_type=pytesseract.Output.DICT)
    for i, value in enumerate(words["text"]):
        normalized = value.strip(" .,:!()[]").lower()
        if normalized == word.lower() or (partial and normalized.startswith(word.lower())):
            pyautogui.click(
                words["left"][i] + words["width"][i] // 2, words["top"][i] + words["height"][i] // 2
            )
            return True
    return False


def open_bridge(process):
    import pyautogui

    time.sleep(12)
    if process.poll() is not None:
        raise RuntimeError("Orca exited during startup")
    screenshot("01-startup")
    # Standard File menu entry is present in the official Linux MainFrame source.
    pyautogui.hotkey("alt", "f")
    time.sleep(1)
    screenshot("02-file-menu")
    if not click_word("Plugins"):
        raise RuntimeError("Could not locate the official Plugins menu item")
    time.sleep(8)
    screenshot("03-plugins")
    if not click_word("RRS", partial=True):
        raise RuntimeError("Installed host plugin did not appear in Plugins")
    time.sleep(2)
    screenshot("04-selected-plugin")
    if not click_word("Run"):
        raise RuntimeError("Could not locate the selected Script capability's Run button")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        for path in data.glob("orca_plugins/plugin_data/**/rrs-mcp-bridge/session.json"):
            candidate = HostClient(path.parent)
            if candidate.status().get("online"):
                screenshot("05-live-bridge")
                return candidate
        time.sleep(1)
    screenshot("05-bridge-start-failed")
    raise RuntimeError("No running bridge session appeared")


async def verify(client):
    session = client.status()["session_id"]

    async def call(operation, params, mutation=False, request_id=None):
        result = await client.call(
            operation,
            params,
            timeout=60,
            session_id=session if mutation else None,
            request_id=request_id or (uuid.uuid4().hex if mutation else None),
        )
        assert result["status"] == "succeeded", result
        return result

    snapshot = await call("host.snapshot", {})
    model = await call("model.read", {})
    assert model["result"]["total"] > 0
    preset = await call("preset.read", {"kind": "process", "keys": ["wall_loops"]})
    name = preset["result"]["name"]
    original = preset["result"]["values"]["wall_loops"]
    changed = "5" if original != "5" else "4"
    ident = uuid.uuid4().hex
    parameters = {"kind": "process", "preset_name": name, "changes": {"wall_loops": changed}}
    updated = await call("preset.update", parameters, mutation=True, request_id=ident)
    assert updated["result"]["saved_to_disk"] is False
    repeated = await call("preset.update", parameters, mutation=True, request_id=ident)
    assert repeated == updated
    readback = await call("preset.read", {"kind": "process", "keys": ["wall_loops"]})
    assert readback["result"]["values"]["wall_loops"] == changed
    invalid = await client.call(
        "preset.update",
        {
            "kind": "process",
            "preset_name": name,
            "changes": {"wall_loops": "7", "rrs_unknown_setting": "bad"},
        },
        session_id=session,
        request_id=uuid.uuid4().hex,
        timeout=30,
    )
    assert invalid["status"] == "failed", invalid
    still = await call("preset.read", {"kind": "process", "keys": ["wall_loops"]})
    assert still["result"]["values"]["wall_loops"] == changed
    category_checks = {}
    for category, key, value, slot in (
        ("printer", "machine_max_speed_z", "13", None),
        ("filament", "filament_flow_ratio", "0.98", 1),
    ):
        active = await call("preset.read", {"kind": category, "keys": [key]})
        change = {
            "kind": category,
            "preset_name": active["result"]["name"],
            "changes": {key: value},
            "slot": slot,
        }
        outcome = await call("preset.update", change, mutation=True)
        checked = await call("preset.read", {"kind": category, "keys": [key]})
        assert checked["result"]["values"][key] == value, checked
        category_checks[category] = {"setting": key, "value": value, "result": outcome["result"]}
    destination = client.directory / "exports/live-project.3mf"
    before_export = await call("host.snapshot", {})
    exported = await call("project.export", {"destination": str(destination)}, mutation=True)
    assert destination.is_file() and destination.stat().st_size > 1000
    with zipfile.ZipFile(destination) as archive:
        config = json.loads(archive.read("Metadata/project_settings.config"))
        assert config["wall_loops"] == changed
    after_export = await call("host.snapshot", {})
    for field in ("project_path", "project_dirty", "presets_dirty"):
        assert before_export["result"][field] == after_export["result"][field]
    # Verify the public MCP entry points as well as the embedded protocol.
    env = {
        **os.environ,
        "ORCA_MCP_BRIDGE": str(client.directory),
        "ORCA_MCP_ROOTS": str(client.directory),
        "ORCA_MCP_STATE": str(root / "host-mcp-state"),
    }
    async with stdio_client(
        StdioServerParameters(
            command=sys.executable, args=["-m", "rrs_orcaslicer_mcp.server"], env=env
        )
    ) as (read, write):
        async with ClientSession(read, write) as mcp:
            await mcp.initialize()
            status = await mcp.call_tool("host_bridge_status", {})
            assert not status.isError and status.structuredContent["online"]
            result = await mcp.call_tool(
                "host_preset_update",
                {
                    "kind": "process",
                    "preset_name": name,
                    "changes": {"wall_loops": "6"},
                    "session_id": session,
                    "request_id": uuid.uuid4().hex,
                },
            )
            assert not result.isError and result.structuredContent["status"] == "succeeded", result
            readback = await mcp.call_tool(
                "host_preset_read", {"kind": "process", "keys": ["wall_loops"]}
            )
            assert readback.structuredContent["result"]["values"]["wall_loops"] == "6"
            # A repeat must return the receipt even though the original output exists.
            repeated_export = await mcp.call_tool(
                "host_project_export",
                {
                    "destination": str(destination),
                    "session_id": session,
                    "request_id": exported["request_id"],
                },
            )
            assert not repeated_export.isError and repeated_export.structuredContent == exported
    report = {
        "status": "succeeded",
        "real_embedded_host": True,
        "stdio_mcp_verified": True,
        "mcp_updated_wall_loops": "6",
        "additional_preset_categories": category_checks,
        "app": snapshot["result"]["app"],
        "object_count": model["result"]["total"],
        "preset_name": name,
        "before": original,
        "after": changed,
        "mutation_id_reused_without_reexecution": repeated == updated,
        "native_invalid_batch_preserved_existing_value": True,
        "export_contains_unsaved_wall_loops": changed,
        "export_preserved_project_path_and_dirty_state": True,
        "project_export_bytes": exported["result"]["bytes"],
        "project_export_sha256": digest(destination),
        "session_capabilities": client.status()["capabilities"],
    }
    atomic_json(evidence / "report.json", report)
    print(json.dumps(report, indent=2), flush=True)


def main():
    prepare()
    log = (evidence / "orca-stdout.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            os.environ["ORCA_SLICER_BIN"],
            "--datadir",
            str(data),
            "--debug",
            "3",
            str(root / "output/cube-sliced.3mf"),
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        client = open_bridge(process)
        asyncio.run(verify(client))
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        log.close()
        # Logs are scoped to the disposable fixture, not the user's Orca data.
        logs = data / "log"
        if logs.exists():
            shutil.copytree(logs, evidence / "host-logs", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
