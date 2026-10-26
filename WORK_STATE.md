# Work checkpoint

Last successful step: 13 automated tests and lint passed; official OrcaSlicer 2.4.2
produced real G-code + sliced 3MF. A separate official MCP client read/edited the
3MF, removed stale slicing caches, sliced it again and verified layer_height=0.25.
Evidence: docs/VALIDATION.md, docs/evidence/*.json; scripts/smoke_orca.py and
scripts/verify_roundtrip.py reproduce the checks. Original files were preserved.
Source catalog: 966 definitions, upstream 5817a76da6a783a992009c8f3aa6cd6b88efc9b8.
Files: src/, scripts/, tests/, docs/, pyproject.toml, LICENSE, NOTICE, CI workflow.
GitHub checkpoint already confirmed: d419a69c28844596f476c388c7c883dd6b9475a1.
Distribution built: wheel, source tarball, source ZIP and SHA256SUMS in dist/.
Installed-wheel check: same 13 tests passed using the installed distribution.
Published source: f45ee121d44688e64c0a4dad2ce220979b78c4e4.
First CI: Linux/macOS passed; Windows exposed default codepage decoding of UTF-8
catalog, now fixed explicitly for all JSON/state readers. Added Unicode job-path
coverage. Linux runner lacked OpenGL runtime; CI dependencies corrected.
Next: rerun CI and publish version 0.1.0 assets after all checks pass.
Desktop and physical printing remain unvalidated.
