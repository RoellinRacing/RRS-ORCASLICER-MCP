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

## Public tools and input units

`native_scene_read`, `native_ui_capabilities`, `native_request_status` are read
operations. `native_transform` accepts move (relative mm), rotate (relative degrees)
or scale (target percent under Orca's current uniform-lock behavior), axis x/y/z,
value, observed revision, bridge session and a fresh 32-hex request ID.
`native_history` takes direction undo/redo and an explicit number of native steps.
`native_text` takes text/height_mm/depth_mm, join/cut/modifier, backup and result
paths (new .3mf inside both client/host export roots), revision/session/request.
`native_calibration` takes kind, numeric values/options, backup/result, the same
identities and explicit replace_scene=true. No print action is invoked.

Generator routes: temperature (start/end; native 5 C step), pressure_advance
(start/end/step, method tower/line/pattern), max_volumetric_speed/retraction/vfa
(start/end/step), cornering (start/end), flow_ratio (test pass_1/pass_2/yolo/
yolo_perfectionist), input_shaping_frequency (x_start/x_end/y_start/y_end),
input_shaping_damping (freq_x/freq_y/start/end). A declared route is not acceptance
for every firmware/layout: refer to actual native evidence for tested families.

Setup: install `[desktop]`, system Tesseract OCR and a clipboard backend (xclip on
Linux X11). Set ORCA_MCP_DESKTOP=1. Keep the modeless bridge running but close the
modal Plugins manager, and foreground Prepare. The initial selector pack is English.
No existing install is switched to another locale automatically.

The selector pack uses Orca's shipped M/R/S/T and Ctrl/Cmd+A/Z/Y shortcuts;
custom shortcut remappings are outside this pack's acceptance scope. Pose
operations verify requested-axis native readback; generator numeric fields are
read back before clicking OK. Native calibration success also requires nonempty
exported geometry. Text operation type is verified as model part/negative/modifier.

Before native input the adapter parks the still-running modeless bridge compactly
at the bottom-left, leaving the native viewport/gizmos visible. This is a desktop
window placement change, not a model mutation. Mac window placement needs separate
acceptance; the initial driver fails before model input there.

Native Modifier text requires Orca Advanced/Expert mode; Orca hides this radio
button in Simple mode. The disposable acceptance fixture uses Expert. The adapter
does not change an existing user's mode automatically.
