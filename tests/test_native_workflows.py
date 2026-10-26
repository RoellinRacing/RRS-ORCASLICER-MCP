import copy
import sys
import types
import json
import zipfile

import pytest

from rrs_orcaslicer_mcp.native_ui import NativeControls
from rrs_orcaslicer_mcp.native_workflows import (
    NativeWorkflows,
    archive_metadata,
    validate_calibration,
    verify_transform,
)
from rrs_orcaslicer_mcp.storage import Files


def scene():
    return {
        "revision": "before",
        "app": {"language": "en_US"},
        "objects": [
            {
                "id": 1,
                "instance_count": 1,
                "instances": [
                    {"offset": [10, 20, 5], "rotation": [0, 0, 0], "scaling_factor": [1, 1, 1]}
                ],
            }
        ],
    }


def test_calibration_parameters_reject_bad_native_ranges():
    validate_calibration("temperature", {"start": 220, "end": 200})
    validate_calibration("pressure_advance", {"start": 0, "end": 0.05, "step": 0.005})
    validate_calibration("flow_ratio", {"test": "pass_2"})
    for kind, params in (
        ("temperature", {"start": 220, "end": 201}),
        ("pressure_advance", {"start": 0, "end": 0.05, "step": 0}),
        ("retraction", {"start": 2, "end": 1, "step": 0.1}),
        ("flow_ratio", {"test": "invented"}),
        ("flow_ratio", {"unknown": 3}),
    ):
        with pytest.raises(ValueError):
            validate_calibration(kind, params)


def test_readback_does_not_equate_any_change_with_success():
    before = scene()
    after = copy.deepcopy(before)
    after["objects"][0]["instances"][0]["offset"][0] += 3
    parameters = {"kind": "move", "axis": "x", "value": 3}
    assert verify_transform(before, after, parameters)["expected_axis_value"] == 13
    after["objects"][0]["instances"][0]["offset"][0] += 1
    with pytest.raises(ValueError, match="readback"):
        verify_transform(before, after, parameters)


def test_control_locator_rejects_missing_ambiguous_and_resolves_phrase():
    def word(text, x, y):
        return {"text": text, "tokens": text.lower().split(), "x": x, "y": y, "w": 25, "h": 12}

    words = [word("Start", 10, 10), word("temp", 45, 10), word("220", 100, 10)]
    assert NativeControls.locate(words, "Start temp")["x"] == 10
    with pytest.raises(ValueError):
        NativeControls.locate(words, "End temp")
    with pytest.raises(ValueError, match="ambiguous"):
        NativeControls.locate(words + [word("Start", 10, 40), word("temp", 45, 40)], "Start temp")


async def test_native_receipt_no_replay_and_stale_revision_rejection(tmp_path):
    current = scene()
    actions = []

    class Host:
        def status(self):
            return {"online": True, "session_id": "a" * 32}

        async def call(self, operation, params):
            return {"status": "succeeded", "result": copy.deepcopy(current)}

    class Controls:
        def __init__(self, desktop, folder):
            pass

        def main(self):
            return (0, 0, 100)

        def park_bridge(self):
            return {"kept_running": True}

        def canvas(self):
            pass

        def capture(self, phase):
            return phase + ".png"

        def key(self, *keys):
            actions.append(keys)
            if keys[-1] == "z":
                current["revision"] = "after"

    service = NativeWorkflows(Host(), None, Files([tmp_path]), tmp_path / "requests", Controls)
    with pytest.raises(ValueError, match="revision changed"):
        await service.run("history", {"direction": "undo", "steps": 1}, "a" * 32, "b" * 32, "stale")
    assert actions == []
    first = await service.run(
        "history", {"direction": "undo", "steps": 1}, "a" * 32, "b" * 32, "before"
    )
    assert first["status"] == "succeeded"
    repeated = await service.run(
        "history", {"direction": "undo", "steps": 1}, "a" * 32, "b" * 32, "before"
    )
    assert repeated == first and actions == [
        ("escape",),
        ("command" if sys.platform == "darwin" else "ctrl", "z"),
    ]
    with pytest.raises(ValueError, match="conflicts"):
        await service.run("history", {"direction": "redo", "steps": 1}, "a" * 32, "b" * 32, "after")


async def test_partial_native_input_retains_uncertainty(tmp_path):
    class Host:
        def status(self):
            return {"online": True, "session_id": "a" * 32}

        async def call(self, operation, params):
            return {"status": "succeeded", "result": scene()}

    class Controls:
        def __init__(self, desktop, folder):
            pass

        def main(self):
            return (0, 0, 100)

        def park_bridge(self):
            return {"kept_running": True}

        def canvas(self):
            pass

        def capture(self, phase):
            return phase

        def key(self, *keys):
            raise RuntimeError("Native control vanished after input")

    service = NativeWorkflows(Host(), None, Files([tmp_path]), tmp_path / "requests", Controls)
    result = await service.run(
        "history", {"direction": "undo", "steps": 1}, "a" * 32, "b" * 32, "before"
    )
    assert result["status"] == "outcome_unknown"
    assert service.result("b" * 32)["status"] == "outcome_unknown"


def test_native_export_parser_requires_real_editable_text_metadata(tmp_path):
    path = tmp_path / "native.3mf"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Metadata/model_settings.config",
            '<config xmlns:s="http://example.com"><object id="1"><part id="2"><s:text text="RRS" line_height="8"/><s:shape depth="1"/></part></object></config>',
        )
        archive.writestr(
            "Metadata/project_settings.config", json.dumps({"nozzle_temperature": ["220"]})
        )
    result = archive_metadata(path)
    assert result["editable_texts"][0]["text"]["text"] == "RRS"
    assert result["editable_texts"][0]["shapes"][0]["depth"] == "1"


def test_native_metadata_accepts_upstream_unbound_slic3rpe_names(tmp_path):
    path = tmp_path / "stock-text.3mf"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Metadata/model_settings.config",
            '<config><object id="1"><part id="2"><slic3rpe:text text="RRS" line_height="8"/><slic3rpe:shape depth="1"/></part></object></config>',
        )
        archive.writestr("Metadata/project_settings.config", "{}")
    assert archive_metadata(path)["editable_texts"][0]["text"]["text"] == "RRS"


def test_bridge_window_search_intersects_title_and_pid(tmp_path, monkeypatch):
    from rrs_orcaslicer_mcp import native_ui

    actions = []

    def output(command, **kwargs):
        if command[1] == "getactivewindow":
            return "4242\n"
        assert command[1] == "search"
        assert "--all" in command
        assert command[command.index("--pid") + 1] == "4242"
        return "12345\n"

    monkeypatch.setattr(native_ui.sys, "platform", "linux")
    monkeypatch.setattr(native_ui.subprocess, "check_output", output)
    monkeypatch.setattr(native_ui.subprocess, "run", lambda args, **kw: actions.append(args))
    monkeypatch.setattr(native_ui.time, "sleep", lambda _: None)
    desktop = types.SimpleNamespace(_api=lambda: types.SimpleNamespace(size=lambda: (1440, 1000)))
    ui = NativeControls(desktop, tmp_path)
    assert ui.park_bridge()["kept_running"]
    assert actions[0] == ["xdotool", "windowsize", "12345", "350", "180"]
    assert actions[1] == ["xdotool", "windowmove", "12345", "0", "800"]


@pytest.mark.parametrize(
    "visible,expected",
    [("220°C", 220), ("220℃", 220), ("30Hz", 30), ("5mm3/s", 5), ("5mm³/s", 5), ("1.2mm", 1.2)],
)
def test_native_numeric_units_do_not_change_value(tmp_path, visible, expected):
    from rrs_orcaslicer_mcp.native_ui import tokens

    def word(text, x):
        return {"text": text, "tokens": tokens(text), "x": x, "y": 10, "w": 30, "h": 12}

    ui = NativeControls(None, tmp_path)
    ui.words = lambda region=None: [word("Start", 10), word(visible, 100)]
    assert ui.read_numeric("Start")[1] == expected
