"""Replay an exact saved native spiral prompt without desktop input."""

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from rrs_orcaslicer_mcp.native_ui import NativeControls

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", type=Path)
parser.add_argument("--bounds", nargs=4, type=int, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
picture = Image.open(args.image)
ui = NativeControls(
    SimpleNamespace(_api=lambda: SimpleNamespace(screenshot=lambda: picture)),
    args.output.parent / "spiral-replay-screenshots",
)
ui.bounds = lambda: tuple(args.bounds)
ui.window_title = lambda: "Orca Slicer info"
clicked = []
ui.point_click = clicked.append
result = ui.resolve_calibration_dialog("flow_ratio")
assert len(clicked) == 1 and clicked[0]["y"] >= args.bounds[3] - 55
receipt = {
    "status": "succeeded",
    "test": "Read-only exact native spiral prompt replay; no desktop input",
    "source_image_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
    "source_artifact": 12669488298,
    "source_run": 40363467681,
    "target": clicked[0],
    "cancelled_inherited_spiral_mode": result["cancelled_inherited_spiral_mode"],
    "upstream_source": "https://github.com/OrcaSlicer/OrcaSlicer/blob/0b4e7e9e2a7968df544e7f52e71e18dac8041d85/src/slic3r/GUI/ConfigManipulation.cpp",
}
args.output.write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
