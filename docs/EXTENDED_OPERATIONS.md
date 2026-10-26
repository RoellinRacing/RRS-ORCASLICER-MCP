# Extended operations (0.4.0)

## Project transforms and facet painting

`project_geometry_read` pages model resources and build items. Inspect the archive
member list first for multi-part projects: meshes may be in `3D/Objects/*.model`.
`project_transform_write` replaces a build/component transform using a source hash;
3MF uses the 3x3 linear part then XYZ translation (row vectors, declared model unit).
For a scale 2 and shift 10 on X: `[2,0,0, 0,1,0, 0,0,1, 10,0,0]`.

`project_painting_read` identifies triangle indices and native mask strings.
`project_painting_write` changes one channel per call using `{triangle:0,state:1}`
or `{triangle:0,mask:"841"}` (a subdivided support triangle). `mask:null` clears
that channel. Enforcer = 1, blocker = 2, none = 0; material 1..16 is a filament slot.
Changing a shared component mesh changes all its instances. Other channels,
triangle order and unknown archive members survive. Always reopen and reslice.

## Offline mesh topology

Install `pip install 'rrs-orcaslicer-mcp[geometry]'`.
`mesh_inspect` measures STL/PLY inputs bound to SHA256. `mesh_operation` supports:
repair (normals/duplicates/small holes), split connected components, capped plane
cut into both halves, concatenate/merge, manifold union/difference/intersection,
convex_hull, simplify and affine transform. Inputs use `{path,sha256}`.

Cut parameters: `origin:[0,0,5]`, `normal:[0,0,1]`, `cap:true`.
Mesh transforms use conventional column-vector 4x4 matrices; the last column holds
translation. This is deliberately distinct from 3MF's serialized 12-number matrix.
Outputs are measured after STL reload with watertightness, volume and bounds.
STL units are assumed millimeters; no project settings/facet paint are transferred.
Repair reports actual watertightness; it cannot promise to repair every bad model.
Each operation saves intent before computation and outputs after each result.

## Calibration coupons

`calibration_series_create` accepts a supplied 3MF test coupon, source SHA256,
new directory, filament_slot (1-based), kind and values. Types: temperature,
flow_ratio, pressure_advance, max_volumetric_speed. Each output is a separate
constant-setting coupon; all other slots are retained. PA explicitly enables its
slot. `calibration.json` records completed hashes; repeating identical input resumes
and validates prior outputs. `batch_slice` accepts those output paths.

These are parameter sweeps, not replicas of Orca's built-in tower/line generators.
Use suitable test geometry, printer limits and measured inspection to choose a
winner. Applying a result is an explicit profile/settings edit, never inferred from
successful slicing.

## Live observations

`host_model_detail` requires index and object_id from `host_model_read`. It returns
bounded copied poses, volume types, extrusion slots, diagnostics and instances.
`host_printer_read` exposes only Orca's official redacted selected-printer snapshot.
`host_slicing_events` reads a 512-item ring with epoch, sequence and gap detection.
Enable and select **RRS MCP slicing observer** in process `slicing_pipeline_plugin`.
The callback is synchronous; native context references never leave it. No GUI or
filesystem work is done in that callback. Stages are observations, not percentages.

## Independent Moonraker / OctoPrint adapter

Set `ORCA_MCP_PRINTERS` to an administrator-controlled JSON configuration path:

```json
{
  "centauri": {
    "provider": "moonraker",
    "url": "http://YOUR-PRINTER:7125",
    "api_key_env": "CENTAURI_API_KEY"
  },
  "octo": {
    "provider": "octoprint",
    "url": "http://YOUR-OCTOPRINT",
    "api_key_env": "OCTOPRINT_API_KEY"
  }
}
```

Provide secrets in environment variables, never tool arguments or tracked files.
URLs are fixed by configuration, redirects/proxy inheritance disabled and TLS
verification enabled. `printer_capabilities` lists configured targets.
`printer_status` queries job state. `printer_upload` sends checksum-bound text
G-code; uploading never starts it and may replace the remote filename.
`printer_command` explicitly starts a named uploaded file or pauses/resumes/cancels.

Every mutation needs a 32-hex request_id. A durable exclusive dispatch receipt is
saved before the network request. Reuse of that ID returns the receipt across
restarts, not a second command. A timeout, uncertain error or interrupted dispatch
requires state inspection; a fresh ID is not an automatic retry. `acknowledged`
means only HTTP/provider acknowledgement. Query state afterward. No real device
was commanded during development. Bambu cloud and AMS/MMU control are not covered.

Protocol references:
- https://docs.octoprint.org/en/main/api/job.html
- https://docs.octoprint.org/en/main/api/files.html
- https://moonraker.readthedocs.io/en/latest/external_api/printer/
- https://moonraker.readthedocs.io/en/latest/external_api/file_manager/

## Remaining upstream gaps

Stock PluginHostModel bindings remain read-only at upstream commit
1433316b550bac676136f618e215ece8c884bb8c. Live topology/painting with undo, native
calibration generator invocation, GUI slice/cancel/export commands and cloud/AMS
commands do not have integrated supported entry points. File/HTTP operations above
are explicit independent workflows, not a claim of full native GUI coverage.
