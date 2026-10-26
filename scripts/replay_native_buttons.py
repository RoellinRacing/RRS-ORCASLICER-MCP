"""Check primary buttons in saved calibration screenshots without desktop input."""

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from rrs_orcaslicer_mcp.native_ui import NativeControls
from rrs_orcaslicer_mcp.native_workflows import CALIBRATION_TITLES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    results, seen = [], set()
    for case in manifest["cases"]:
        if case["kind"] in seen:
            continue
        seen.add(case["kind"])
        path = args.evidence_root / case["image"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["sha256"]
        picture = Image.open(path)
        ui = NativeControls(
            SimpleNamespace(
                _api=lambda picture=picture: SimpleNamespace(screenshot=lambda: picture)
            ),
            args.output.parent / "button-ocr-observations",
        )
        ui.bounds = lambda bounds=case["bounds"]: tuple(bounds)
        title = CALIBRATION_TITLES[case["kind"]]
        ui.window_title = lambda title=title: title
        clicked = []
        ui.point_click = clicked.append
        ui.dialog_button("OK", title)
        assert len(clicked) == 1 and clicked[0]["y"] >= case["bounds"][3] - 75
        assert 20 <= clicked[0]["h"] <= 45
        if "expected_target" in case:
            assert clicked == [case["expected_target"]], (case["kind"], clicked)
        results.append(
            {
                "kind": case["kind"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "target": clicked[0],
            }
        )
        args.output.write_text(json.dumps({"status": "running", "cases": results}, indent=2) + "\n")
    receipt = {
        "status": "succeeded",
        "test": "Read-only exact primary OK button replays; no desktop input",
        "cases": results,
    }
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
