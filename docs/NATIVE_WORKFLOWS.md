# Native live editing, text and calibration workflows

Baseline: 0.4.0 / ea7e738. The inspected stock host model bindings are read-only.
The separate MCP server therefore drives Orca's own visible controls, then reads
back native state/3MF results through the official plugin. It does not claim a new
native C++ document API or replace native generators with coupon approximations.

Business rules:
- Require explicit desktop opt-in, the bridge session, an observed scene revision
  and a durable request ID. Reject stale scenes before GUI input.
- Check foreground Orca process and visible expected control labels. Never accept
  arbitrary coordinates from a semantic operation. Stop on missing/ambiguous UI.
- Native undo/redo uses Orca's own history. Multi-step history is explicit, with
  before/after state; no file-level pseudo-undo is called native undo.
- Back up the unsaved project before scene-replacing calibration generation.
  Never start a physical print. Unknown dialogs/results remain indeterminate.
- Native text must retain editable text metadata in an exported 3MF, rather than
  merely producing a faceted lookalike STL.
- Persist intent before the first side effect, screenshots/phases after actions
  and the actual native result. Repeated request IDs never repeat input.

Initial acceptance environment: official Linux nightly 2.5.0-dev, English UI,
X11 isolated CI. Other platforms/locales/layouts need explicit acceptance evidence.
A version/layout mismatch fails closed, not a universal-version guarantee.

Implementation order: copied scene revision; native control locator; live move and
Undo/Redo; native editable text; native temperature/PA/retraction/flowrate generators;
unit and real GUI acceptance; immutable release and saved continuation state.
