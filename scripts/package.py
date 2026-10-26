"""Build distributable wheel, source tarball, source ZIP and checksums."""

import hashlib
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=root, check=True)
dist = root / "dist"
name = f"rrs-orcaslicer-mcp-{version}"
with zipfile.ZipFile(dist / f"{name}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    included = [
        root / p
        for p in (
            "README.md",
            "LICENSE",
            "NOTICE",
            "WORK_STATE.md",
            "pyproject.toml",
            "MANIFEST.in",
        )
    ]
    for directory in ("src", "scripts", "docs", "tests", ".github"):
        included += [
            p
            for p in (root / directory).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and not any(part.endswith(".egg-info") for part in p.parts)
        ]
    for path in sorted(set(included)):
        info = zipfile.ZipInfo(
            f"{name}/{path.relative_to(root).as_posix()}", date_time=(2026, 1, 1, 0, 0, 0)
        )
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o755 if path.suffix == ".sh" else 0o644) << 16
        archive.writestr(info, path.read_bytes())
artifacts = sorted(p for p in dist.iterdir() if p.suffix in (".whl", ".gz", ".zip"))
(dist / "SHA256SUMS").write_text(
    "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts)
)
for path in artifacts:
    print(f"{path.name}: {path.stat().st_size} bytes")
