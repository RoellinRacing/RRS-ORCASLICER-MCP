# Active checkpoint — 0.2.0

Last successful step: 25 tests/lint passed; real MCP extension verification using
saved official 2.4.2 inputs succeeded. Object wall_loops=4 and plate name changed;
profile export/diff/validation passed; two-input batch produced G-code; a repeated
request returned the same jobs without reslicing. Evidence saved in
 docs/evidence/extensions-0.2.0.json. Source generation and earlier successful
reference slicing were not repeated.

Base release: 0.1.1, completed checkpoint ea84b238d054707a09cdd2f6586ae498efd11ae3.
Extension plan saved to GitHub: 07941871faffe9c5e82d22f8c95f3a3010d8a0f3.
Files added: batches.py, settings.py, project_settings.py, gcode.py, coverage.json,
test_extensions.py, verify_extensions.py, FEATURE_COVERAGE.md, UPSTREAM_CONTACT.md.
Business reasons documented in docs/BUSINESS_LOGIC.md. Total MCP tools: 30.

User clarified goal is all Orca functions. Complete semantic coverage is NOT achieved:
painting, calibration, live model/preset APIs and printer/cloud integration remain
explicitly documented gaps. Official experimental plugin APIs found in source;
no untested host bridge is claimed. Contact location and draft prepared:
https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878
Nothing posted upstream.

Next: build/verify wheel, publish 0.2.0, inspect all CI matrix entries and release
assets. Continue remaining live-plugin integration separately with actual nightly
execution rather than claiming generic GUI clicks equal full API coverage.

Distribution built locally (0.2.0 ZIP, wheel, source tarball, checksums).
Installed-wheel verification: all 25 tests passed; saved as
 docs/evidence/wheel-tests-0.2.0.txt. Next: publish source and verify remote CI/release.
