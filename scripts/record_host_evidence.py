"""Record successful native CI evidence in release source, bound to this plugin."""

import json
import os
import sys
import tomllib
from pathlib import Path

from rrs_orcaslicer_mcp.storage import atomic_json, digest

root = Path(__file__).resolve().parents[1]
artifacts = Path(sys.argv[1])
report = json.loads(next(artifacts.rglob("report.json")).read_text(encoding="utf-8"))
prepared = json.loads(next(artifacts.rglob("prepared.json")).read_text(encoding="utf-8"))
plugin = root / "src/rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py"
if not (
    report.get("status") == "succeeded"
    and report.get("real_embedded_host") is True
    and report.get("stdio_mcp_verified") is True
    and prepared.get("plugin_sha256") == digest(plugin)
):
    raise SystemExit("Native evidence failed or does not match this plugin")
checksum = next(artifacts.rglob("nightly-SHA256SUMS")).read_text(encoding="utf-8").strip()
result = {
    "report": report,
    "fixture": prepared,
    "official_nightly_checksum": checksum,
    "source_commit": os.environ.get("GITHUB_SHA"),
    "workflow": (
        f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        if os.environ.get("GITHUB_RUN_ID")
        else None
    ),
}
package_version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
atomic_json(root / f"docs/evidence/host-{package_version}.json", result)
print("Recorded native evidence matching plugin SHA256", prepared["plugin_sha256"])
