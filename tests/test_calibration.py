import json
import zipfile

import pytest

from rrs_orcaslicer_mcp.calibration import series
from rrs_orcaslicer_mcp.storage import Files, digest


def test_calibration_keeps_other_filaments_and_resumes(tmp_path):
    path = tmp_path / "coupon.3mf"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Metadata/project_settings.config",
            json.dumps(
                {
                    "filament_flow_ratio": ["0.95", "0.99"],
                    "nozzle_temperature": ["200", "210"],
                    "nozzle_temperature_initial_layer": ["205", "215"],
                    "pressure_advance": ["0.03", "0.04"],
                    "enable_pressure_advance": ["0", "0"],
                }
            ),
        )
        archive.writestr("mesh.payload", b"geometry-and-painting")
    files, sha = Files([tmp_path]), digest(path)
    for kind, values in (
        ("flow_ratio", [0.9, 1.0]),
        ("temperature", [200, 215]),
        ("pressure_advance", [0, 0.03]),
    ):
        result = series(files, str(path), kind, sha, kind, values, 2)
        assert result["status"] == "ready_to_slice"
        repeated = series(files, str(path), kind, sha, kind, values, 2)
        assert repeated == result
        with zipfile.ZipFile(result["completed"][0]["path"]) as archive:
            settings = json.loads(archive.read("Metadata/project_settings.config"))
            assert settings["filament_flow_ratio"][0] == "0.95"
            if kind == "pressure_advance":
                assert settings["enable_pressure_advance"] == ["0", "1"]
            assert archive.read("mesh.payload") == b"geometry-and-painting"
    assert digest(path) == sha
    with pytest.raises(ValueError, match="different request"):
        series(files, str(path), "flow_ratio", sha, "flow_ratio", [1.0, 1.1], 2)
    with pytest.raises(ValueError, match="slot"):
        series(files, str(path), "invalid", sha, "flow_ratio", [0.9, 1.0], 3)
    assert not files.path("invalid").exists()
