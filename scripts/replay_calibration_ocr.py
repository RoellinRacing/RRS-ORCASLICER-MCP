"""Check saved native failure screenshots without desktop input.

The manifest binds artifact/image hashes, observed client bounds and exact values.
Download the referenced artifacts first; keep them outside the source repository.
"""

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from rrs_orcaslicer_mcp.native_ui import NativeControls
from rrs_orcaslicer_mcp.native_workflows import CALIBRATIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text())["cases"]
    results = []
    for case in cases:
        path = args.evidence_root / case["image"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["sha256"]
        picture = Image.open(path)
        ui = NativeControls(
            SimpleNamespace(
                _api=lambda picture=picture: SimpleNamespace(screenshot=lambda: picture)
            ),
            args.output.parent / "ocr-observations",
        )
        ui.bounds = lambda bounds=case["bounds"]: tuple(bounds)
        observed = {}
        if case["kind"] == "flow_ratio":
            ui.window_title = lambda: "Flow Ratio Calibration"
            clicked = []
            ui.point_click = clicked.append
            ui.radio_choice("Calibration Test Type", "Pass 1 Coarse", "Coarse")
            assert len(clicked) == 1
            observed["radio_target"] = clicked[0]
        for field in CALIBRATIONS[case["kind"]][1]:
            observed[field[0]] = ui.read_numeric(field[1], index=field[2] if len(field) > 2 else 0)[
                1
            ]
            assert observed[field[0]] == case["expected"][field[0]], (case["kind"], observed)
        results.append({"kind": case["kind"], "observed": observed, "status": "succeeded"})
        args.output.write_text(json.dumps({"cases": results, "status": "in_progress"}, indent=2))
    result = {"status": "succeeded", "no_desktop_input": True, "cases": results}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
