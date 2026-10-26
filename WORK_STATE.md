# Published checkpoint — 0.2.0

Last successful step: GitHub Actions 40278472600 passed all six Windows/macOS/Linux
Python 3.11/3.13 matrix entries (25 tests each), official OrcaSlicer 2.4.2 reference
slicing, global-settings MCP roundtrip and the new object/plate/profile/batch tests.
Version 0.2.0 public release published; downloaded ZIP checksum and integrity passed.

Release source commit: 735a5f0e4d18beeda71e86ffacb13431a09b5da7.
Repository: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
Release: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.2.0
CI: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40278472600
ZIP SHA256: 739e3821f25cce76ff39c6db4fa3cb2b697db90dbf35d6ccdd67311e6d695174

Saved results/files:
- 30 MCP tools, including direct object/part/plate settings and profile helpers.
- batches.py: durable manifests, input fingerprints, idempotency and cancellation.
- gcode.py: streamed declared statistics and explicit temperature commands.
- project_settings.py/settings.py: semantic settings and flattened profile export.
- tests/test_extensions.py and scripts/verify_extensions.py: new reproducible tests.
- docs/evidence/extensions-0.2.0.json, wheel-tests-0.2.0.txt,
  github-release-0.2.0.json: actual local/wheel/public-release validation results.
- docs/BUSINESS_LOGIC.md: behavior and reasons; FEATURE_COVERAGE.md and packaged
  coverage.json explicitly describe supported families and remaining gaps.
- docs/UPSTREAM_CONTACT.md: official contact location and reviewed factual draft.
- Public release assets: ZIP, wheel, source tarball and SHA256SUMS.

User's full goal remains broader than this release. Complete semantic coverage is
NOT achieved: painting, calibration, live model/preset APIs and printer/cloud
integration remain explicit gaps. GUI input is not proof of full API coverage.
Official experimental plugin APIs exist at upstream source revision
5817a76da6a783a992009c8f3aa6cd6b88efc9b8. No embedded host bridge has been implemented
or tested, and no every-version guarantee is claimed.

Next development step: test a matching official nightly and its host API, then
connect live capabilities individually with actual operation-level evidence.
Consult docs/FEATURE_COVERAGE.md before implementing. Reuse saved source catalog,
reference models and completed results; do not regenerate them without a reason.

Contact location for the user's intended later discussion:
https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878
No upstream message, comment or PR has been posted.
