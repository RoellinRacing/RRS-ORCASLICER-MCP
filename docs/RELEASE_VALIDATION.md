# Release verification business rules

A successful build alone does not prove that the public downloads contain the
accepted native workflows. verify_release_bundle.py requires the four expected
distribution checksums, matching Python/JSON source files in ZIP and wheel, matching
bridge copies, source business rules, successful combined native receipts, three
text modes, nine generator families and exact source-commit provenance. With the
GitHub release JSON it also checks every public asset digest. Installed-wheel tests
follow separately. An independent native report can never substitute for the full
combined acceptance.

Reproduce after downloading all five v0.5.0 assets:

```sh
python scripts/verify_release_bundle.py /path/to/downloads verified.json --release-metadata docs/evidence/release-metadata-0.5.0.json
```

Actual result: all public files verified; source/wheel/bridge consistency passed;
30 native operations passed on official Orca 2.5.0-dev 0b4e7e9e (English Linux X11);
all six platform/Python checks passed 95 tests with two Pillow-dependent skips;
all 97 installed-wheel tests passed. See
docs/evidence/github-release-0.5.0.json and wheel-tests-0.5.0.txt. Other native GUI
platforms/locales still require acceptance.
