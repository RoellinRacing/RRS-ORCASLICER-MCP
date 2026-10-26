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

## Extension checkpoint — live observations

Implemented host_model_detail (identity-bound paged volumes/instances),
host_printer_read (upstream diagnostic snapshot), host_slicing_events and a separate
optional synchronous SlicingPipeline observer. Added ring overflow/cursor and live
identity tests. Source generator saved before native validation.
CI scripts now exercise stock Orca reopen/reslice of transformed four-channel paint,
and detailed GUI reads plus actual pipeline events. Native results are pending;
only prior 0.3.0 operations currently have completed native evidence.
Next: inspect CI; independent provider operations and calibration sweep semantics.

## Extension checkpoint — offline geometry, calibration and print hosts

Source saved: meshes.py (repair/split/cut/booleans/merge/hull/simplify/transform),
calibration.py (four types of resumable constant-setting coupon series), printers.py
(configured Moonraker/OctoPrint status/upload/job commands with durable dispatch IDs).
Documentation: EXTENDED_OPERATIONS.md and BUSINESS_LOGIC.md.
Optional geometry dependency group added; geometry tests use measured STL volumes,
including union=1500, difference=500, intersection=500 mm3 for overlapping cubes.
No physical device connected. New native evidence/0.4.0 release remains pending.
CI dependency installation is bounded so unrelated apt repositories cannot consume
an entire native-test run. Next: full checks, native CI, then release evidence.

Local full suite: 58 passed, evidence saved in extended-unit-0.4.0.txt.
Native test on 5dda5fd discovered Orca compares lexical XML core tag names:
ElementTree's namespace-equivalent ns0:model was interpreted as empty. Fixed
serialization to retain unprefixed core tags/original extension prefixes and added
an explicit lexical regression assertion. New native run must confirm this fix.

Native roundtrip succeeded on 17fad59 (semantics-0.4.0.json saved). All six
Windows/macOS/Linux matrix entries passed. GUI reads/details/printer diagnostics,
preset transactions and export succeeded; observer stage check found no events.
Inspection of its screenshot showed the modal Plugins manager was still open,
blocking the mainframe Slice action. Test now closes only that modal manager,
keeps the separate modeless bridge running, and saves selection/partial-report
and before/after screenshots. No application bridge code changed for this test fix.
