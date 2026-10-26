# Maintainer review notes

Purpose: make the implementation and its limits easy to assess before discussing
the integration with OrcaSlicer's maintainers. No upstream message or PR is sent
automatically by this project.

## Code boundaries

| Component | Responsibility | Intentionally excluded |
| --- | --- | --- |
| `host_bridge/protocol.py` | Bounded JSON, identities, fingerprints and durable atomic writes | Native host calls |
| `host_bridge/client.py` | External request submission, timeout and receipt retrieval | Automatic mutation retries or host internals |
| `host_bridge/service.py` | Allowlisted operations and GUI/worker separation | `eval`, arbitrary imports/method dispatch, raw native handles in replies |
| `entry_template.py` | Official Script registration and window/invocation lifecycle | Starting threads, subprocesses or network listeners |
| `build_host_plugin.py` | Reproducible dependency-free single-file packaging | Downloading code or changing the Orca binary |

## Business rules checked in review

- The user's installed Orca owns setting validation, dirty state, target selection
  and dialogs. The bridge does not implement a competing preset setter.
- Mutations use an explicit preset name and a session/request pair. Filament edits
  include a slot and report shared usage rather than implying per-slot isolation.
- Model reads happen in a GUI callback and are converted immediately. The worker
  queue contains JSON, not native object pointers.
- Native exports are copies to new paths inside allowed roots. A repeated request
  retrieves its prior receipt even though the destination now exists.
- Secret-like preset keys are redacted or rejected; app-config/credential files
  are not read by the embedded plugin.
- Invalid data, unknown operations, expired requests, stale sessions and receipt
  mismatches do not get silently converted to success.
- Mailbox processing is bounded per GUI tick. Bad/processed files cannot keep later
  valid requests stuck behind the first page of the directory.
- Transient Windows sharing locks retry only atomic file replacement. A failed
  final receipt write after a native effect retains its indeterminate started
  journal; it never relabels an applied commit as a native failure.
- A timeout is indeterminate. The journal is written before a native call and a
  missing final receipt never authorizes an automatic repeat under a new ID.
- The generated plugin is checked against its source modules. It imports only the
  standard library and Orca's own `orca` module.

## Validation evidence

Unit/protocol tests verify thread assignment, duplicate suppression, conflicting
requests, native-error propagation, timeout recovery, redaction, bounds, export
paths, queue shutdown and standalone registration. Their host is explicitly a test
double. The separate X11 test launches the official nightly binary with disposable
profiles and no account/device connection, invokes the real plugin and records
the actual app build. Its screenshots/logs are CI diagnostics, not user data.

Consult `VALIDATION.md` and `docs/evidence/` for completed results. A pending or
failed native job is not treated as a passing integration test.

## Known limits to present honestly upstream

The host API is experimental. Painting/geometry mutation, calibration and physical
printer control remain outside this adapter. Native modal interaction can outlive
an MCP timeout. Native side effects and receipt persistence cannot form one atomic
cross-process transaction. The mailbox assumes a trusted local account; it is not
an authenticated remote ChatGPT gateway or an OS security sandbox. Retained session
journals require user-managed cleanup after they are no longer needed.

The intended discussion is whether these integration points and compatibility
boundaries fit the supported host architecture, and which missing capabilities
should be proposed separately. The integration should not be described as full
control of every Orca feature or every past/future version.

## 0.4.0 extension review

The independent server now has 54 tools. Offline geometry/painting targets explicit
file revisions and never treats a modified archive as a live GUI edit. Unknown ZIP
payloads and unrelated paint channels are retained; stale slicing outputs removed.
Stock 2.4.2 has successfully reimported/resliced all four changed paint channels and
an affine instance transform. Namespace lexical compatibility has a regression test.

Optional mesh topology results are measured after STL reload, not inferred from a
successful library call. Calibration series preserve non-target filament slots and
checkpoint individual outputs. Native tower/line generators remain unbound.
Printer adapters are configured external HTTP providers, not Orca credential/cloud
bridges; protocol mocks prove request formation and conservative duplicate recovery,
not physical-device acceptance. Selected native printer state is still read-only.

The earlier limits refer to the original embedded-host adapter. Independent offline
painting/geometry and provider actions now exist, while live scene undo/mutation,
native calibration, cloud/AMS/MMU and complete GUI command coverage remain open.


## 0.5.0 native workflow acceptance

The separate server now has 61 tools. Typed live transforms, native history,
editable text and calibration generation use observed stock-Orca controls with
bridge readback. Every request binds the bridge session, scene revision and durable
request ID. Backup/new export paths precede text/calibration work; repeated IDs
return receipts without repeating input.

The accepted Linux X11/English/light selector pack passed 30 operations together:
three transforms with native Undo/Redo, Join/Cut/Modifier text, and nine generator
families. Native 3MF text metadata, volume type, pose/history and nonempty geometry
are checked. Max Flowrate's inherited spiral mode is declined for flat Flow Ratio
coupons only after the exact info title, both explanation anchors and a unique
footer target match. Client bounds are reacquired without another title-bar inset.
Unknown/ambiguous dialogs retain an indeterminate receipt and screenshots.

Source 1101d5f, CI 40373662076 and public v0.5.0 are immutable reference points.
Six OS/Python jobs each passed 95 tests with two optional Pillow skips; all 97
passed locally and with the separately installed public wheel. All 19 CI jobs
passed; public assets match SHA256SUMS and GitHub digests. Full native evidence is
bundled and saved under docs/evidence. Other GUI platforms/locales, multiple-object
workflows and firmware-specific variants require additional acceptance.

The host bridge keeps its public allowlist and GUI/worker ownership rules.
Supported native document transactions, paint mutations, job lifecycle and
provider APIs would reduce the desktop selector dependency; these are the
concrete questions in UPSTREAM_CONTACT.md.
