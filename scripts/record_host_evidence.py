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
package_version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
if tuple(map(int, package_version.split("."))) >= (0, 5, 0):
    native = report.get("native_workflows", {})
    if not (
        native.get("status") == "succeeded"
        and native.get("actual_native_undo_redo") is True
        and native.get("editable_native_text") is True
        and native.get("sections") == ["calibration", "editing", "text"]
        and len(native.get("native_generators", [])) == 9
        and set(native.get("text_modes", [])) == {"join", "cut", "modifier"}
    ):
        raise SystemExit("Typed native workflow acceptance is missing or failed")
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

if tuple(map(int, package_version.split("."))) >= (0, 5, 0):
    raw_native = json.loads(next(artifacts.rglob("native-workflows.json")).read_text())
    if raw_native.get("status") != "succeeded" or raw_native.get("sections") != [
        "calibration",
        "editing",
        "text",
    ]:
        raise SystemExit("Combined operation receipts are missing")
    atomic_json(
        root / f"docs/evidence/native-workflows-{package_version}.json",
        {
            "source_commit": result["source_commit"],
            "workflow": result["workflow"],
            "report": raw_native,
        },
    )
    app = raw_native["app"]
    checkpoint = (
        f"# Validated package checkpoint — {package_version}\n\n"
        f"Source commit: {result['source_commit']}\n"
        f"Native workflow: {result['workflow']}\n\n"
        f"Official Linux Orca {app['version']}, build {app['build']}, English X11. "
        f"{len(raw_native['operations'])} actual native operations completed. "
        "Move/rotate/scale with native Undo/Redo, editable Join/Cut/Modifier text and "
        "nine native generator families passed. Exact receipts are bundled in "
        f"docs/evidence/native-workflows-{package_version}.json.\n\n"
        "63 MCP tools. Limits and business rules: docs/NATIVE_WORKFLOWS.md and "
        "docs/BUSINESS_LOGIC.md. Other GUI platforms/layouts/locales require acceptance.\n\n"
        "## Earlier checkpoints (historical)\n\n"
    )
    state = root / "WORK_STATE.md"
    state.write_text(checkpoint + state.read_text(), encoding="utf-8")

atomic_json(root / f"docs/evidence/host-{package_version}.json", result)
print("Recorded native evidence matching plugin SHA256", prepared["plugin_sha256"])
