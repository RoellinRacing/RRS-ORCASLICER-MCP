# Completed checkpoint — v0.1.1

Last successful step: GitHub Actions run 40276480510 passed all six OS/Python
matrix entries (14 tests each), the official OrcaSlicer 2.4.2 slicing + full MCP
roundtrip, and packaging. Public v0.1.1 release published with ZIP, wheel,
source tarball and SHA256SUMS. Downloaded release ZIP checksum/integrity verified.

Release source commit: b801692e51f5bfba880466941eac258e0781dcc3.
Repository: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
Release: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.1.1
CI: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40276480510

Saved results and files:
- src/: 20-tool standalone stdio MCP server, profiles, 3MF, jobs and desktop adapter.
- src/rrs_orcaslicer_mcp/data/options.json: 966 source-derived definitions.
- scripts/: source generation, installation/configuration, packaging and real tests.
- tests/: 14 automated checks including real stdio and disconnect cancellation.
- docs/BUSINESS_LOGIC.md: intended behavior, reasons, constraints and recovery rules.
- docs/VALIDATION.md and docs/evidence/: real slicing hashes, roundtrip, wheel and CI.
- README.md, LICENSE, NOTICE: installation, compatibility and source attribution.
- Release assets preserve the actual published packages; dist/ is local build output.

Next step: install the release on the user's OrcaSlicer computer and import the
provided MCP configuration into a local stdio-capable client. No development work
is pending for this release. GUI interaction and physical printing are not tested;
new Orca versions are capability-probed and checked by the weekly CI workflow.
Do not rerun completed generation/tests unless code, engine or requirements change.
