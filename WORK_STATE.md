# Published checkpoint — 0.4.0

Last successful step: official native integration and all six Windows/macOS/Linux
Python 3.11/3.13 matrix entries passed (58 tests each). Stock OrcaSlicer 2.4.2
reopened/resliced an affine-transformed project and preserved all four edited facet
paint channels. Official Linux nightly 2.5.0-dev build 2dfcba39 delivered ten native
pipeline events and passed detailed model/printer reads, preset transactions,
invalid-setting handling, duplicate suppression, unsaved export and MCP stdio checks.

Source/release commit: ad2227e2acd48a32e7e1a912d3bf2461ae49625d.
Release: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.4.0
CI: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40323305158
ZIP SHA256: e8c070e18497354c39465309fef1bf9c996ad980df3a3603819f1f9d4dab6d2d
Plugin SHA256: 1de73dc4b8cf21c3580d6226b21250200ce54bf4f900769c3c36311f214a95eb

## Saved implementation and actual results

54 MCP tools (15 additions to 0.3.0):
- project_geometry.py: paged 3MF identities, build/component affine transforms,
  four-channel facet/subtriangle paint read/write with revision-bound new archives.
- meshes.py: optional measured STL/PLY repair, split, cut, merge, Booleans, hull,
  simplify and transform, checkpointed before computation and after each output.
- calibration.py: resumable temperature/flow/PA/volumetric-speed coupon series from
  a supplied 3MF, preserving other filament slots; no automatic quality selection.
- printers.py: configured Moonraker/OctoPrint status, upload and explicit job commands;
  durable exclusive dispatch IDs, no automatic retry of uncertain physical actions.
- host_bridge/: copied identity-bound volume/instance diagnostics, redacted printer
  snapshot and a synchronous bounded stage observer without retained native handles.
- docs/evidence/: extended-unit-0.4.0.txt, wheel-tests-0.4.0.txt,
  semantics-0.4.0.json, host-0.4.0.json, github-release-0.4.0.json and package checks.
- Actual public ZIP/wheel/source/plugin were downloaded and checked against
  SHA256SUMS. ZIP integrity and wheel source contents verified. Native evidence is
  included in the published ZIP. Public wheel acceptance results are saved separately.

Business rules/operation contracts: BUSINESS_LOGIC.md, EXTENDED_OPERATIONS.md,
MAINTAINER_REVIEW.md. Reproducible verification: verify_semantics.py,
verify_host_gui.py, record_host_evidence.py, package.py and saved pytest tests.

Native validation caught and fixed lexical XML namespace compatibility. GUI tests
now close the modal Plugins manager, retain the modeless bridge and use validated
cropped/upscaled OCR with explicit MainFrame activation. Those fixes are saved;
do not repeat already successful investigations/reference generation.

## Remaining requirements / exact next step

Full semantic coverage of every Orca function is NOT achieved. Live model/painting
mutation with undo, embossing, native calibration tower/line generator invocation,
GUI slice/cancel/export job APIs, cloud/AMS/MMU control remain explicit gaps.
At inspected upstream 1433316b550bac676136f618e215ece8c884bb8c the document-model
bindings are read-only. Do not invent supported mutators or bypass native ownership.

Next: re-check upstream for supported document transactions/native calibration and
job/provider APIs; integrate one supported operation with operation-level proof.
The factual proposal/questions are saved in UPSTREAM_CONTACT.md for Dani's own
contact: https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878.
No upstream message/issue/PR was sent.

Physical printer/provider acceptance requires an explicitly configured compatible
device; only HTTP contract tests were performed. No physical print was started.
Windows/macOS native GUI operations are not accepted yet. No every-version or
future-version guarantee. Existing immutable 0.3.0 evidence remains in docs/evidence.

## 0.5.0 native workflow implementation checkpoint

Saved source: native_ui.py, native_workflows.py, scene.read bridge extension,
seven public MCP tools, verify_native_workflows.py and GUI harness integration.
64 local tests passed; source/evidence in docs/evidence/unit-0.5.0.txt.
Business rationale and limits: docs/NATIVE_WORKFLOWS.md, BUSINESS_LOGIC.md.
Next: run stock native acceptance for move/rotate/scale + real Undo/Redo, editable
native text and five native generator families. New GUI behavior is not accepted
until those actual operation checks pass. Existing 0.4.0 native results stand.

First CI checkpoint 541b7bf: Linux/Windows suites passed; macOS test double used
Ctrl instead of Command and was corrected without changing product key mapping.
Native GUI job never started the app: Azure Ubuntu mirror stalled downloading a
font package and hit the bounded installer timeout. CI now uses the official Ubuntu
HTTPS archive rather than the slow Azure mirror.

Saved follow-up: namespace-unaware parsing of Orca's native unbound slic3rpe:text/
shape tags, exact numeric-field readback for generator parameters, nonempty native
model/type checks, and nine generator families plus all three text modes in the
acceptance script. 65-test suite is being rechecked before the next native run.
