"""Verify downloaded 0.5.0 assets against checksums and operation-level acceptance.

Purpose: a successful build does not prove that the published files contain the
tested native workflows. Bind all distributions, native receipts and optional
GitHub asset digests before reporting a release as verified.
"""

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--release-metadata", type=Path)
    args = parser.parse_args()
    directory, version = args.directory, "0.5.0"
    expected = {
        f"rrs-orcaslicer-mcp-{version}.zip",
        f"rrs_orcaslicer_mcp-{version}-py3-none-any.whl",
        f"rrs_orcaslicer_mcp-{version}.tar.gz",
        "rrs_orcaslicer_bridge.py",
    }
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        assert name not in checksums, "Duplicate checksum name"
        checksums[name] = digest
    assert set(checksums) == expected
    for name, digest in checksums.items():
        assert sha(directory / name) == digest, name
    prefix = f"rrs-orcaslicer-mcp-{version}/"
    with zipfile.ZipFile(directory / f"rrs-orcaslicer-mcp-{version}.zip") as archive:
        assert archive.testzip() is None
        native_source = archive.read(prefix + "src/rrs_orcaslicer_mcp/native_ui.py")
        plugin_source = archive.read(
            prefix + "src/rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py"
        )
        host = json.loads(archive.read(prefix + f"docs/evidence/host-{version}.json"))
        native = json.loads(archive.read(prefix + f"docs/evidence/native-workflows-{version}.json"))
        for name in ["docs/BUSINESS_LOGIC.md", "docs/NATIVE_WORKFLOWS.md", "WORK_STATE.md"]:
            assert archive.read(prefix + name)
    report = host["report"]
    raw = native["report"]
    assert host["source_commit"] == native["source_commit"]
    assert report["status"] == "succeeded" and report["stdio_mcp_verified"] is True
    assert raw["status"] == "succeeded"
    assert raw["sections"] == ["calibration", "editing", "text"]
    assert raw["actual_native_undo_redo"] is True and raw["editable_native_text"] is True
    assert set(raw["text_modes"]) == {"join", "cut", "modifier"}
    assert set(raw["native_generators"]) == {
        "temperature",
        "pressure_advance",
        "retraction",
        "max_volumetric_speed",
        "flow_ratio",
        "vfa",
        "cornering",
        "input_shaping_frequency",
        "input_shaping_damping",
    }
    assert len(raw["operations"]) >= 30
    assert all(o["result"]["status"] == "succeeded" for o in raw["operations"])
    assert raw["physical_print_started"] is False
    with zipfile.ZipFile(directory / f"rrs_orcaslicer_mcp-{version}-py3-none-any.whl") as wheel:
        assert wheel.testzip() is None
        assert wheel.read("rrs_orcaslicer_mcp/native_ui.py") == native_source
        assert wheel.read("rrs_orcaslicer_mcp/data/rrs_orcaslicer_bridge.py") == plugin_source
    assert (directory / "rrs_orcaslicer_bridge.py").read_bytes() == plugin_source
    with tarfile.open(directory / f"rrs_orcaslicer_mcp-{version}.tar.gz") as source:
        prefix_tar = f"rrs_orcaslicer_mcp-{version}/"
        for name in ["src/rrs_orcaslicer_mcp/native_ui.py", "docs/BUSINESS_LOGIC.md"]:
            member = source.extractfile(prefix_tar + name)
            assert member and member.read()
    if args.release_metadata:
        release = json.loads(args.release_metadata.read_text())
        assert release["tag_name"] == "v" + version
        assert release["target_commitish"] == host["source_commit"]
        assert {a["name"] for a in release["assets"]} == expected | {"SHA256SUMS"}
        for asset in release["assets"]:
            assert asset["digest"] == "sha256:" + sha(directory / asset["name"])
    result = {
        "status": "succeeded",
        "version": version,
        "source_commit": host["source_commit"],
        "native_operations": len(raw["operations"]),
        "app": raw["app"],
        "sha256": {n: sha(directory / n) for n in sorted(expected)},
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
