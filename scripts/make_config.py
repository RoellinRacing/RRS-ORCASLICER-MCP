"""Generate an absolute-path local MCP configuration for this installed environment."""

import argparse
import json
import os
import sys
from pathlib import Path

from rrs_orcaslicer_mcp.engine import find_binary
from rrs_orcaslicer_mcp.storage import atomic_json

parser = argparse.ArgumentParser()
parser.add_argument("--binary")
parser.add_argument("--root", action="append", default=[])
parser.add_argument("--desktop", action="store_true")
parser.add_argument("--output", type=Path, default=Path("mcp-config.json"))
args = parser.parse_args()
binary = args.binary or find_binary()
if not binary or not Path(binary).expanduser().is_file():
    raise SystemExit("Supply --binary with the installed OrcaSlicer executable")
binary = Path(binary).expanduser().resolve()
roots = [Path(p).expanduser().resolve() for p in args.root] or [Path.home() / "OrcaMCP"]
roots[0].mkdir(parents=True, exist_ok=True)
# Discover paths only; never copy or mutate Orca's live data during installation.
candidates = [
    binary.parent / "resources/profiles",
    binary.parent.parent / "Resources/profiles",
    binary.parent.parent / "resources/profiles",
    Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "OrcaSlicer",
    Path.home() / ".config/OrcaSlicer",
    Path.home() / "Library/Application Support/OrcaSlicer",
]
for path in candidates:
    if path.is_dir() and path.resolve() not in roots:
        roots.append(path.resolve())
config = {
    "mcpServers": {
        "rrs-orcaslicer": {
            "command": sys.executable,
            "args": ["-m", "rrs_orcaslicer_mcp.server"],
            "env": {
                "ORCA_SLICER_BIN": str(binary),
                "ORCA_MCP_ROOTS": os.pathsep.join(map(str, roots)),
                "ORCA_MCP_STATE": str(roots[0] / ".rrs-orca"),
                "ORCA_MCP_DESKTOP": "1" if args.desktop else "0",
            },
        }
    }
}
atomic_json(args.output.resolve(), config)
print(f"Saved {args.output.resolve()}")
print(json.dumps(config, ensure_ascii=False, indent=2))
