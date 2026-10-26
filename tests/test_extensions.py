import asyncio
import sys
import zipfile
from xml.etree import ElementTree as ET

import pytest

from rrs_orcaslicer_mcp import gcode, project_settings, settings
from rrs_orcaslicer_mcp.batches import Batches
from rrs_orcaslicer_mcp.engine import Engine
from rrs_orcaslicer_mcp.storage import Files, digest


def test_settings_compare_preserves_serialized_type_differences():
    diff = settings.compare(
        {"a": "1", "nested": {"b": [True]}, "old": "x"}, {"a": 1, "nested": {"b": [1]}, "new": "y"}
    )
    assert diff["counts"] == {"added": 1, "removed": 1, "changed": 2}
    assert not diff["identical"]
    assert settings.compare({"a": "1"}, {"a": "1"})["identical"]


def test_validation_reports_bad_types_and_preserves_future_keys():
    result = settings.validate(
        {
            "layer_height": "-1",
            "wall_loops": "2.5",
            "nozzle_diameter": "0.4",
            "future_option": ["hello"],
        }
    )
    assert result["engine_validated"] is False
    assert {r["key"] for r in result["findings"]} == {
        "layer_height",
        "wall_loops",
        "nozzle_diameter",
    }
    assert result["unknown_keys_preserved"] == ["future_option"]
    assert not settings.validate(
        {"layer_height": "0.2", "wall_loops": "3", "nozzle_diameter": ["0.4"]}
    )["findings"]


def test_profile_export_is_flat_and_never_overwrites(tmp_path):
    files = Files([tmp_path])
    files.write("base.json", {"name": "base", "layer_height": "0.2", "unknown": "keep"}, [], None)
    source = files.write(
        "leaf.json",
        {"name": "leaf", "inherits": "base", "setting_id": "system-id", "wall_loops": "3"},
        [],
        None,
    )
    result = settings.export_profile(files, "leaf.json", "flat.json", "My profile", [str(tmp_path)])
    assert result["settings"]["layer_height"] == "0.2"
    assert result["settings"]["unknown"] == "keep"
    assert result["settings"]["from"] == "User"
    assert "inherits" not in result["settings"]
    assert "setting_id" not in result["settings"]
    assert files.read("leaf.json")["sha256"] == source["sha256"]
    with pytest.raises(ValueError, match="new destination"):
        settings.export_profile(files, "leaf.json", "flat.json", "Overwrite", [str(tmp_path)])


def scene(path):
    xml = """<config><object id="4"><metadata key="name" value="Part A"/>
      <metadata key="wall_loops" value="2"/><part id="8" subtype="normal_part">
      <metadata key="matrix" value="keep geometry"/><metadata key="extruder" value="1"/>
      <unknown preserved="yes"/></part></object>
      <object id="5"><metadata key="wall_loops" value="9"/></object>
      <plate><metadata key="plater_id" value="1"/><metadata key="gcode_file" value="Metadata/plate_1.gcode"/>
      <model_instance><metadata key="object_id" value="4"/></model_instance></plate></config>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Metadata/model_settings.config", xml)
        archive.writestr("Metadata/project_settings.config", '{"layer_height":"0.2"}')
        archive.writestr("Metadata/plate_1.gcode", "old")
        archive.writestr("3D/Objects/mesh.model", "original geometry")


def test_semantic_object_part_and_plate_edits(tmp_path):
    files = Files([tmp_path])
    source = tmp_path / "src.3mf"
    scene(source)
    original = project_settings.inspect(files, "src.3mf")
    assert original["objects"][0]["parts"][0]["part_id"] == "8"
    edited = project_settings.write(
        files, "src.3mf", "object.3mf", "object", "4", {"wall_loops": "4"}, original["sha256"]
    )
    assert edited["structure"]["objects"][0]["settings"]["wall_loops"] == "4"
    assert edited["structure"]["objects"][1]["settings"]["wall_loops"] == "9"
    part = project_settings.write(
        files,
        "object.3mf",
        "part.3mf",
        "object",
        "4",
        {"extruder": "2"},
        edited["sha256"],
        part_id="8",
    )
    plate = project_settings.write(
        files, "part.3mf", "plate.3mf", "plate", "1", {"plater_name": "Batch plate"}, part["sha256"]
    )
    assert plate["structure"]["plates"][0]["settings"]["plater_name"] == "Batch plate"
    with zipfile.ZipFile(tmp_path / "plate.3mf") as archive:
        assert archive.read("3D/Objects/mesh.model") == b"original geometry"
        assert "Metadata/plate_1.gcode" not in archive.namelist()
        xml = ET.fromstring(archive.read("Metadata/model_settings.config"))
        assert xml.find("object/part/unknown").get("preserved") == "yes"
    assert digest(source) == original["sha256"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_id": "not-present"},
        {"changes": {"matrix": "change"}},
        {"changes": {"wall_loops": 4}},
    ],
)
def test_semantic_edits_reject_bad_targets_and_geometry(tmp_path, kwargs):
    files = Files([tmp_path])
    source = tmp_path / "src.3mf"
    scene(source)
    parameters = dict(
        target="object", target_id="4", changes={"wall_loops": "4"}, expected=digest(source)
    )
    parameters.update(kwargs)
    with pytest.raises(ValueError):
        project_settings.write(files, "src.3mf", "bad.3mf", **parameters)
    assert not (tmp_path / "bad.3mf").exists()


def test_gcode_analysis_declared_values_and_commands(tmp_path):
    path = tmp_path / "sample.gcode"
    path.write_text(
        """; generated by OrcaSlicer test
; model printing time: 1m 2s; total estimated time: 1h 2m 3s
; total layer number: 2
; CONFIG_BLOCK_START
; layer_height = 0.2
; machine_start_gcode = M104 S999
; CONFIG_BLOCK_END
M104 S210 ; heater
M109 R205
M140 S60
M104 S0
; layer num/total_layer_count: 1/2
G1X10Y20
; FEATURE: Outer wall
; layer num/total_layer_count: 2/2
; filament used [g] = 1.5, 2.5
; filament cost = 0.10
""",
        encoding="utf-8",
    )
    result = gcode.analyze(Files([tmp_path]), str(path))
    assert result["estimated_seconds"]["total estimated time"] == 3723
    assert result["explicit_temperature_targets"]["nozzle"] == [0, 205, 210]
    assert result["observed_layer_markers"] == 2
    assert result["commands"]["G1"] == 1
    assert result["declared_statistics"]["filament used [g]"] == [1.5, 2.5]
    assert result["sha256"] == digest(path)


@pytest.fixture
def engine(tmp_path):
    value = Engine(tmp_path / "jobs", binary=sys.executable)

    async def capabilities(refresh=False):
        return {"available": True, "flags": []}

    value.capabilities = capabilities
    return value


async def test_batch_idempotency_survives_restart_and_conflicts(engine, tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text('done')", encoding="utf-8"
    )
    store = Batches(tmp_path / "batches", engine)
    nested = tmp_path / "output/nested/batch"
    entries = [
        {
            "input": "model",
            "output_directory": str(nested),
            "arguments": [str(worker), str(nested / "result.txt")],
        }
    ]
    first = await store.create("same-key", {"inputs": ["model"]}, entries, 60, {})
    job_id = first["entries"][0]["job_id"]
    await engine.tasks[job_id]
    again = await store.create("same-key", {"inputs": ["model"]}, entries, 60, {})
    assert again["entries"][0]["job_id"] == job_id
    assert again["status"] == "succeeded"
    assert (nested / "result.txt").read_text(encoding="utf-8") == "done"
    assert len(list(engine.state.glob("*/job.json"))) == 1
    with pytest.raises(ValueError, match="conflicts"):
        await store.create("same-key", {"inputs": ["different"]}, entries, 60, {})
    await engine.close()
    restarted = Engine(tmp_path / "jobs", binary=sys.executable)
    try:
        result = await Batches(tmp_path / "batches", restarted).create(
            "same-key", {"inputs": ["model"]}, entries, 60, {}
        )
        assert result["status"] == "succeeded"
        assert not restarted.tasks
    finally:
        await restarted.close()


async def test_queued_inputs_are_verified_before_engine_runs(engine, tmp_path):
    pause = tmp_path / "pause.py"
    pause.write_text("import time; time.sleep(0.2)", encoding="utf-8")
    model = tmp_path / "model.txt"
    model.write_text("original", encoding="utf-8")
    first = await engine.submit([str(pause)])
    second = await engine.submit([str(pause)], expected_files={str(model): digest(model)})
    model.write_text("changed", encoding="utf-8")
    await asyncio.gather(engine.tasks[first["id"]], engine.tasks[second["id"]])
    assert engine.get(first["id"])["status"] == "succeeded"
    failed = engine.get(second["id"])
    assert failed["status"] == "failed"
    assert "Input changed" in failed["error"]
    assert "pid" not in failed
    await engine.close()


async def test_batch_cancel_preserves_completed_results(engine, tmp_path):
    fast = tmp_path / "fast.py"
    slow = tmp_path / "slow.py"
    fast.write_text("pass", encoding="utf-8")
    slow.write_text("import time; time.sleep(30)", encoding="utf-8")
    store = Batches(tmp_path / "batches", engine)
    result = await store.create(
        "cancel", {}, [{"arguments": [str(fast)]}, {"arguments": [str(slow)]}], 60, {}
    )
    await engine.tasks[result["entries"][0]["job_id"]]
    cancelled = await store.cancel(result["id"])
    assert cancelled["counts"] == {"succeeded": 1, "cancelled": 1}
    await engine.close()
