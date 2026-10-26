#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$project_dir/.venv"
"$project_dir/.venv/bin/python" -m pip install "$project_dir"
echo 'Installed. Run .venv/bin/python scripts/make_config.py --binary /path/to/OrcaSlicer --root /path/to/models'
