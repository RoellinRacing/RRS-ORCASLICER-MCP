# Published checkpoint — 0.3.0

Last successful step: GitHub Actions 40288598146 passed all six Windows/macOS/Linux
Python 3.11/3.13 matrix entries (43 tests each), official OrcaSlicer 2.4.2 reference
slicing and project/profile/batch checks, real embedded-host integration and package
build. Public release files were downloaded and checksum/archive checks passed.
The actual published wheel was separately installed and all 43 tests passed.

Release source commit: de282ab59b013dd80806de4be59e2aebe61186a0.
Repository: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
Release: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.3.0
CI: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40288598146
ZIP SHA256: 350aa9d3d960477086ffbb0ae975b1bae5534df726d9ee50233bef25e7419ee6
Plugin SHA256: e3bdda34d5ebe7b320ae2b8858696706e86aed2621ee1a71281ff7d98771560b

## Saved implementation and evidence

- 39 MCP tools: existing independent CLI/file tools and nine optional host tools.
- host_bridge/: versioned mailbox, GUI reads, official Script-worker transactions,
  duplicate suppression, conservative timeout recovery and bounded atomic writes.
- Generated standalone rrs_orcaslicer_bridge.py, shipped in wheel/source/ZIP and as
  a separate release asset; build_host_plugin.py --check verifies its source.
- Native host: official Linux nightly 2.5.0-dev build 2dfcba39. Real reads, updates
  to process/printer/filament, invalid-setting rejection, duplicate receipt reuse,
  unsaved-settings export and public MCP stdio calls succeeded with audit enabled.
- docs/evidence/host-0.3.0.json, github-release-0.3.0.json and
  wheel-tests-0.3.0.txt contain completed results.
- HOST_BRIDGE.md, BUSINESS_LOGIC.md and MAINTAINER_REVIEW.md document threading,
  target/slot semantics, persistence, indeterminate outcomes and native limits.
- Reviewed/fixed real issues: missing native user-profile version metadata,
  transient Windows journal replacement locks, receipt failure after applied
  effects, and unnecessary asyncio socket permissions. Regression coverage saved.

## Remaining scope and next step

Complete semantic coverage is NOT achieved. Live geometry/painting mutation,
calibration, slicing hooks and physical printer/cloud control remain explicit gaps.
No every-version guarantee is claimed. Older Orca versions can retain CLI/file
workflows; the optional plugin requires a compatible background Script host.
Windows/macOS native GUI operations were not tested. No physical print was started.

For further work, use docs/FEATURE_COVERAGE.md and the saved reference artifacts.
Add capabilities only when an actual supported API and operation-level proof exist.
Do not repeat reference generation without a reason. Retained mailboxes are useful
for recovery; never resubmit an indeterminate mutation under a fresh ID blindly.

The user intends to contact the upstream team personally. No message/issue/PR was
sent. Suggested discussion and factual draft: docs/UPSTREAM_CONTACT.md,
https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878.

## Extension checkpoint — project geometry and painting

Completed locally: four typed tools for 3MF geometry inspection, build/component
transform replacement, painting inspection and channel-specific triangle/subtriangle
painting. Source/payload preservation, stale-output invalidation, revision checks,
invalid paint trees and atomic validation covered. `python -m pytest -q`: 48 passed.
Generation source: project_geometry.py; no expensive native work repeated.
Next: native reopen/reslice evidence, detailed host reads and synchronous slicing
observations; then reconcile calibration/device gaps. No complete-API claim.
