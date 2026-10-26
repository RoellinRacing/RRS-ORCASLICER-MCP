"""Replay native MainFrame detection against a saved real screenshot, without input."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from rrs_orcaslicer_mcp.native_ui import NativeControls

parser = argparse.ArgumentParser()
parser.add_argument("image")
parser.add_argument(
    "--bounds", nargs=4, type=int, required=True, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM")
)
parser.add_argument("--output", required=True)
args = parser.parse_args()
image = Image.open(args.image)
ui = NativeControls(
    SimpleNamespace(_api=lambda: SimpleNamespace(screenshot=lambda: image)),
    Path("/tmp/unused-native-input"),
)
ui.bounds = lambda: tuple(args.bounds)
observed = ui.main()
result = {
    "status": "succeeded",
    "test": "Read-only replay of a saved native screenshot; no input/app mutation",
    "source_image_sha256": hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),
    "driver_sha256": hashlib.sha256(
        (Path(__file__).resolve().parents[1] / "src/rrs_orcaslicer_mcp/native_ui.py").read_bytes()
    ).hexdigest(),
    "source_artifact": "https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40335959668/artifacts/12657167909",
    "tesseract": subprocess.check_output(["tesseract", "--version"], text=True).splitlines()[0],
    "observed_mainframe": observed,
    "selectors": ["Prepare", "Project"],
    "ocr_timeout_seconds": 12,
    "omp_thread_limit_per_child": 1,
}
Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
