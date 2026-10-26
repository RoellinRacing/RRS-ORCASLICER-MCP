"""Regenerate metadata from a user-provided official source checkout; never fetch implicitly."""

import argparse
import json
import subprocess
from pathlib import Path

from rrs_orcaslicer_mcp.catalog import extract

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--output", type=Path, default=Path("src/rrs_orcaslicer_mcp/data/options.json"))
args = parser.parse_args()
revision = subprocess.check_output(
    ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
).strip()
source = args.source / "src/libslic3r/PrintConfig.cpp"
data = {
    "upstream": {
        "repository": "https://github.com/OrcaSlicer/OrcaSlicer",
        "revision": revision,
        "file": "src/libslic3r/PrintConfig.cpp",
    },
    "options": extract(source.read_text(encoding="utf-8")),
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(data['options'])} option definitions to {args.output}")
