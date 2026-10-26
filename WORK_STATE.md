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
65 local tests now passed. Follow-up source/coverage/docs are synchronized for
61 tools and explicit native UI limits. Native acceptance is expanded to three
text volume modes and nine generator families; it still must pass actual CI.

Native pilot 9793298 reached real controls and stopped before any model mutation:
Slice plate is disabled/poorly recognized in Preview after the baseline slice.
MainFrame detection now uses stable Prepare/Project view labels. The modeless bridge
is compacted/parked bottom-left (still running) so it cannot cover native gizmos.
No bridge/app binary modification is used. The failed native screenshot is retained
in CI 40335959668, artifact 12657167909. Next: rerun actual edit/history/text/generators.
The revised MainFrame detector passed a read-only replay of the actual failed
Preview screenshot. Proof and reusable script: native-ui-preflight-0.5.0.json and
scripts/replay_native_ocr.py. OCR is now cropped to the target region, bounded to
12 seconds and single-threaded per child; it cannot consume minutes on a dense
viewport composition. Desktop-window placement is journaled before native input.

Native pilot 8a7c479 passed MainFrame detection and reached window parking; no
model action executed. xdotool combines multiple search criteria with OR by default,
so PID+title returned more than the intended bridge window. Added explicit --all
(AND) and a regression test for the exact PID/title intersection before any move.

Continuation checkpoint b31cddf (2026-10-26): 66 local tests and all six
OS/Python CI unit entries passed. Native preflight and bridge parking worked;
the first move exposed a clipped mm label, then numeric input did not apply.
Numeric controls now use direct ASCII input, Tab and visible readback before
native pose verification. No successful native editing result is claimed yet.
The next pilot caught Openbox placing MainFrame partly outside the Xvfb screen.
The isolated fixture now sets a fully visible 1200x780 window at 100,80 and saves
per-operation preflight screenshots. Source is saved in b31cddf; active acceptance
run 40342059188. Stock project replacement dialogs are recognized with a completed
native backup; edited presets are kept. Next: inspect actual operation receipts,
fix any remaining native selector/commit behavior, then release only on full pass.

Native pilot c534598 passed move X+7 mm and rotate Z+15 degrees, each with actual
Undo, Redo, Undo and exact native revision restoration. Saved receipts are in run
40343988068 / artifact 12659199872. Scale did not reach the text editor reliably:
typing reached canvas shortcuts instead. Native ImGui mouse clicks now hold down
across a render frame; numeric focus/commit screenshots are saved per field.
No all-workflows success/release yet. Continue through scale, native editable text
and nine generators. Source before this follow-up: c53459878e331471397c2549bab5b092e649ce6e.

Current continuation 7c756f2 / run 40347148596: re-acquire numeric boxes after
hover to allow native gizmo width fitting to settle. Focus/commit images and
pointer/box JSON are retained. 72 full local tests passed; two further targeted
regressions now cover moving editor bounds and changed values before a click.
The GUI CI matrix independently exercises all/text/calibration in isolated stock
Orca sessions; only the all report with three text modes and nine generators may
be packaged. Product sources remain unchanged by these diagnostic sections.
Active jobs: all=121657780105, text=121657779965, calibration=121657779963.
Next: read the three native outcomes, fix selectors using their screenshots,
then require the combined run and all ordinary checks before publishing 0.5.0.

Native 7c756f2: all three transforms (move/rotate/scale) now passed with Undo,
Redo and exact scene restoration (12 native operations). Text stopped safely on
two matching default-name labels (editor and part notification); anchor its text
area above Style, independent of remembered text content. Temperature parameters
220/210 were set and read back, but sparse OCR missed white OK on teal. Fallback
now requires the exact native dialog title, isolates footer button rectangles and
reads their inset label; color alone never triggers a click. Read-only replay of
the actual text/temperature screenshots passed, saved in native-dialog-selectors-
0.5.0.json. Remaining: actual text modes and all nine generator successes, package
only after all combined acceptance checks. Further targeted regressions passed.

Native 12be2f3: all three text modes (Join/Cut/Modifier), editable text/height/depth
in real 3MF, correct native volume types and native Undo restoration passed in
the independent text session, run 40349995892 / artifact 12663777026. 76 full local
tests passed. Temperature reached the save prompt, whose actual native caption is
"Orca Slicer - Save" (with a space); the strict known-caption pack now recognizes
that official spelling too. Exact observed dialog titles are retained for diagnosis.
The combined successful native report is copied into release packages and prepends
a current package checkpoint so historical 0.4.0 notes are not mistaken for status.
Next: confirm native project replacement/Transfer and all nine generator families,
then full combined acceptance, immutable release and published-asset verification.

Repeat 1078957 correctly reached both Save and edited-preset dialogs. Transfer
matched the explanatory body rather than the primary button, so no model changed;
button locators now always constrain the footer. A repeat text run hit OCR of an
input border as "(1.00"; numeric parsing strips only the known border/caret marks,
with native metadata/pose verification still required. Frozen actual Transfer and
Depth screenshots now replay correctly without input (five-selector proof).
The earlier successful three-mode native text report is condensed in
native-text-0.5.0.json, alongside the 12-operation native-transforms proof.
Next: rerun native generators and the combined suite; release remains 0.4.0 until
all 0.5.0 acceptance gates pass.

Native 1a16350: the complete edit/Undo/Redo and all text modes passed together,
then the actual temperature generator passed (temperature_tower.drc, 8726 facets,
30 mm height for 220/215/210 C). PA dialog was visible but its radio label was not
recognized in the first observation. Radio choices are now scoped to their own
group with exact-word fallback; label observation waits for paint without repeating
input. OCR word segmentation alone is ignored, with exact letters still required.
Failed label observations are retained as JSON. A click failure can never enter a
locator fallback and dispatch a second click. Regression tests cover these rules.
CI now gives each of the nine generators its own disposable session, plus text
and the strict combined run. The package still requires every job and full combined
acceptance. An initial local 80-test run stalled on filesystem timing and rejected
expired fixture requests; both unchanged tests and the full rerun then passed.
Next: inspect all nine independent outcomes, fix remaining real selectors together,
then require the combined native result and publish/check the 0.5.0 assets.

Continuation 2026-10-26 (from 4aa5517): inspected the existing run 40358645271.
All six unit matrix entries and real slicing passed. Independent native text,
temperature, VFA and input-shaping frequency passed. Six generators exposed OCR
failures on selected GTK values, vertically merged numeric rows and a clipped
flow-ratio group heading. Saved correction normalizes blue selected text from
immutable pixels, reads numeric rows separately with border removal/3x OCR, and
uses an exact-title-bound flow radio group if its heading is clipped. Actual
failure screenshots are bound by SHA256 in native-calibration-ocr-manifest.json;
replay_calibration_ocr.py checks their exact values without desktop input.
Next: require all screenshot replays, ordinary tests and a new full native run;
release remains gated on successful combined native acceptance. No physical print.
All six saved screenshot cases passed the exact-value/choice replay, including
0.1/0.002/0.5 decimals and both 30 Hz fields. 87 local tests passed; static checks
and generated-plugin consistency passed. Actual results and reproduction manifest
are committed with source/business rules before the next native CI computation.

Native e09bfe1 / run 40361174972: all six OS/Python checks passed. Independent
text, temperature, PA, retraction, flow ratio, VFA, cornering and frequency generators
passed. Max flowrate and damping generated no result because immediate numeric
readback intermittently dropped decimal points; screenshots retain the correct
0.5/0.2 inputs. Added isolated decimal-glyph OCR and observation-only readback waits.
Ten saved before/committed/failure screenshots now require exact numeric values.
New regression verifies readback observation never dispatches a second input.
Next: finish exact screenshot replay + ordinary tests, push, require combined native
acceptance and both remaining generators, then verify the immutable public package.
Ten exact screenshot cases and 89 local tests passed; static checks and generated
bridge consistency passed. Source, business rules and actual replay/test results
are saved before the next native computation. The earlier local installed-wheel
87-test pass is retained explicitly bound to e09bfe1, including its first flaky
fixture result; the final published wheel still requires its own verification.

Native d4ed888 / run 40363467681: all six matrix checks and all nine independent
native generators passed. The combined session passed move/rotate/scale/history,
all three editable text modes and temperature/PA/retraction/max-flow (25 successful
operations), then caught a real cross-generator state: Max Flowrate leaves spiral
mode enabled, and transferring that into flat Flow Ratio coupons opens Orca's
spiral consistency dialog. Source inspection confirms No clears only spiral_mode;
Yes would alter additional wall/infill/support/timelapse settings. Added an exact
Flow Ratio-only prompt/No path with a recorded adjustment and MainFrame export gate.
Actual No-button replay is saved in native-spiral-prompt-0.5.0.json; reproduction:
scripts/replay_spiral_prompt.py (artifact 12669488298, dialog bounds 228 403 1172 614).
The independent text run stopped during fixture startup before model input: the
12-second sleep caught a partially loaded/splash MainFrame. The fixture now waits
for loaded Filament/Process/Quality controls before input. Regression tests cover
allowed/unknown/wrong-generator prompts and loading readiness. Next: complete local
checks, push, require the full combined native session and publish/verify 0.5.0.
The exact real spiral prompt replay and 94 local tests passed. Static checks and
bridge consistency passed. Source/business rules/actual partial native results and
prompt replay are saved before the next full native run. No physical print started.

82ecd65 native pilot exposed a selector regression before generator dispatch:
allowing grey secondary controls globally polluted primary OK rectangle detection.
Grey fallback is now allowed only for the exact spiral-info No route. Actual 2D
connected components replace overlapping-X grouping, which also prevents a radio
mark above Flow Ratio OK from stretching the click rectangle. Six real primary
button replays plus the real spiral No replay passed; scripts/replay_native_buttons.py
and native-primary-buttons-0.5.0.json retain the exact targets. A regression covers
unrelated grey panels and a radio mark above the button. Next: require new full
native acceptance after this isolated selector correction; do not release on the
older failed pilot or on screenshot-only results.

2dc6758 / run 40368784963 passed all nine independent native generators, all
three text modes and the six 95-test Python/OS checks. The combined session again
completed 25 operations, then stopped before responding to the inherited spiral
prompt: wx had recentered/resized the modal after the first bounds query, leaving
the first body line outside a stale crop. Observation retries now reacquire the
exact dialog title and bounds; both semantic anchors remain mandatory before the
single No input. Regression reproduces the real initial/settled bounds, and
replay_spiral_prompt.py accepts artifact/run provenance and initial bounds.
The actual image replay is retained in native-recentered-spiral-prompt-0.5.0.json.
Next: require fresh combined native acceptance before immutable publication.
The exact saved-dialog replay, 96 local tests, static checks and diff checks passed.
