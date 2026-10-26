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
Next: publish final source and inspect GitHub CI/release results. Desktop and physical printing are not locally validated.
