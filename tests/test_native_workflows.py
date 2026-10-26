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
    assert NativeControls.locate([word("PATower", 10, 10)], "PA Tower")["x"] == 10
    assert (
        NativeControls.locate(
            [word("P", 10, 10), word("A", 40, 10), word("Tower", 70, 10)], "PA Tower"
        )["x"]
        == 10
    )
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
    [
        ("220°C", 220),
        ("220℃", 220),
        ("30Hz", 30),
        ("5mm3/s", 5),
        ("5mm³/s", 5),
        ("1.2mm", 1.2),
        ("(1.00", 1),
        ("90.00|", 90),
        ("1.20]", 1.2),
    ],
)
def test_native_numeric_units_do_not_change_value(tmp_path, visible, expected):
    from rrs_orcaslicer_mcp.native_ui import tokens

    def word(text, x):
        return {"text": text, "tokens": tokens(text), "x": x, "y": 10, "w": 30, "h": 12}

    ui = NativeControls(None, tmp_path)
    ui.words = lambda region=None: [word("Start", 10), word(visible, 100)]
    assert ui.read_numeric("Start")[1] == expected


def test_native_numeric_reacquires_editor_after_hover_layout_change(tmp_path, monkeypatch):
    from rrs_orcaslicer_mcp import native_ui

    actions = []
    api = types.SimpleNamespace(
        moveTo=lambda *a, **k: None,
        write=lambda value, **k: actions.append(("write", value)),
        position=lambda: (95, 16),
    )
    ui = NativeControls(types.SimpleNamespace(_api=lambda: api), tmp_path)
    boxes = iter([110, 90, 90])
    ui.read_numeric = lambda *a: ({"x": next(boxes), "y": 10, "w": 10, "h": 12}, 100)
    ui.point_click = lambda box: actions.append(("click", box["x"]))
    ui.key = lambda *keys: None
    ui.capture = lambda phase: phase
    monkeypatch.setattr(native_ui.time, "sleep", lambda _: None)
    result = ui.numeric("Scale", value=110, columns=3)
    assert actions == [("click", 90), ("write", "110")]
    assert result == {"before": 100, "requested": 110}


def test_native_numeric_rejects_changed_value_before_click(tmp_path, monkeypatch):
    from rrs_orcaslicer_mcp import native_ui

    actions = []
    api = types.SimpleNamespace(moveTo=lambda *a, **k: None)
    ui = NativeControls(types.SimpleNamespace(_api=lambda: api), tmp_path)
    values = iter([100, 101])
    ui.read_numeric = lambda *a: ({"x": 90, "y": 10, "w": 10, "h": 12}, next(values))
    ui.point_click = lambda box: actions.append(box)
    monkeypatch.setattr(native_ui.time, "sleep", lambda _: None)
    with pytest.raises(ValueError, match="changed while acquiring"):
        ui.numeric("Scale", value=110)
    assert actions == []


def test_emboss_editor_accepts_remembered_text_in_identified_area(tmp_path):
    actions = []
    ui = NativeControls(None, tmp_path)
    ui.label = lambda phrase: {"x": 600, "y": 300}
    ui.bounds = lambda: (0, 0, 1000, 800)
    ui.words = lambda region: [{"text": "RRS", "x": 610, "y": 210}]
    ui.point_click = lambda box: actions.append(("focus", box["text"]))
    ui.key = lambda *keys: None
    ui.paste = lambda value: actions.append(("text", value))
    ui.replace_emboss_text("Neu")
    assert actions == [("focus", "RRS"), ("text", "Neu")]


def test_native_generator_confirmation_rejects_unexpected_dialog(tmp_path):
    actions = []
    ui = NativeControls(None, tmp_path)
    ui.window_title = lambda: "Other Orca dialog"
    ui.click = lambda *args: actions.append(args)
    with pytest.raises(ValueError, match="not active"):
        ui.dialog_button("OK", "Temperature calibration")
    assert actions == []


def test_native_button_selector_ignores_matching_body_text(tmp_path):
    from rrs_orcaslicer_mcp.native_ui import tokens

    def word(y):
        return {
            "text": "Transfer",
            "tokens": tokens("Transfer"),
            "x": 200,
            "y": y,
            "w": 60,
            "h": 12,
        }

    clicked = []
    ui = NativeControls(None, tmp_path)
    ui.window_title = lambda: "Creating a new project: unsaved changes"
    ui.bounds = lambda: (0, 0, 600, 500)
    ui.main_bounds = (0, 0, 1200, 800)
    ui.words = lambda region=None: [word(100), word(455)]
    ui.point_click = lambda box: clicked.append(box)
    ui.dialog_button("Transfer", "Creating a new project: unsaved changes")
    assert len(clicked) == 1 and clicked[0]["y"] == 455


def test_native_label_waits_for_painted_dialog_without_input(tmp_path, monkeypatch):
    from rrs_orcaslicer_mcp import native_ui
    from rrs_orcaslicer_mcp.native_ui import tokens

    observations = iter(
        [[], [{"text": "PATower", "tokens": tokens("PATower"), "x": 10, "y": 10, "w": 60, "h": 12}]]
    )
    ui = NativeControls(None, tmp_path)
    ui.words = lambda region=None: next(observations)
    monkeypatch.setattr(native_ui.time, "sleep", lambda _: None)
    assert ui.label("PA Tower")["x"] == 10


def test_native_dialog_does_not_repeat_click_after_input_error(tmp_path):
    from rrs_orcaslicer_mcp.native_ui import tokens

    ui = NativeControls(None, tmp_path)
    ui.window_title = lambda: "Temperature calibration"
    ui.bounds = lambda: (0, 0, 600, 500)
    ui.main_bounds = (0, 0, 1200, 800)
    ui.words = lambda region=None: [
        {"text": "OK", "tokens": tokens("OK"), "x": 300, "y": 455, "w": 20, "h": 12}
    ]
    actions = []

    def fail(box):
        actions.append(box)
        raise ValueError("input failed after dispatch")

    ui.point_click = fail
    with pytest.raises(ValueError, match="after dispatch"):
        ui.dialog_button("OK", "Temperature calibration")
    assert len(actions) == 1


def test_native_radio_fallback_stays_in_identified_group(tmp_path):
    ui = NativeControls(None, tmp_path)
    ui.bounds = lambda: (0, 0, 600, 500)
    clicked = []

    def label(phrase, region=None):
        if phrase == "Method":
            return {"y": 100, "h": 15}
        if phrase == "Settings":
            return {"y": 200}
        assert region == (0, 115, 600, 200)
        if phrase == "PA Tower":
            raise ValueError("painted radio prefix unreadable")
        assert phrase == "Tower"
        return {"x": 40, "y": 150, "w": 35, "h": 12}

    ui.label = label
    ui.point_click = lambda box: clicked.append(box)
    ui.radio_choice("Method", "PA Tower", "Tower")
    assert len(clicked) == 1 and clicked[0]["y"] == 150
