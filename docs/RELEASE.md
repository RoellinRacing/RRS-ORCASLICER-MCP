# RRS OrcaSlicer MCP 0.5.0

61 tools in the independent MCP server, including seven typed native workflows.
The stock Orca binary remains unchanged; the optional official bridge supplies
copied native state while the desktop adapter drives Orca's own visible controls.

New operations:
- Observed scene revisions and durable no-repeat GUI receipts with screenshots.
- Native move/rotate/scale gizmos with actual pose readback and actual Undo/Redo.
- Native editable text/emboss/engrave, verified in exported 3MF text/shape metadata.
- Original calibration dialogs/generators, with unsaved-project backups and explicit
  scene replacement, distinct from independent 0.4.0 coupon parameter sweeps.

Install [desktop], system Tesseract and a working clipboard backend (e.g. xclip on
X11), set ORCA_MCP_DESKTOP=1 and keep the official bridge running. Initial native
acceptance is Linux X11 / English UI. Transforms/text currently require one object
and one instance. Native operation evidence and exact tested generator families
are bundled in docs/evidence/host-0.5.0.json and the native GUI CI artifact.
Native Undo/Redo uses explicit steps; a compound workflow can create several steps.
A scene revision covers exposed identities/poses/bounds/settings, not all mesh bytes.

Other layouts/locales/platforms and firmware-specific generator dialogs require
acceptance. Missing or ambiguous controls fail closed. No physical print was started.
No claim of every Orca function, all-version compatibility, cloud or AMS/MMU control.

Code and business rules: docs/NATIVE_WORKFLOWS.md and docs/BUSINESS_LOGIC.md.
