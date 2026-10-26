# Official Orca host bridge

This is an optional **official Python Script plugin**, installed through Orca's
Plugins dialog. The MCP server remains a separate process. Neither component
patches Orca or loads private C++ symbols. The plugin has no third-party Python
dependencies, socket listener, arbitrary expression evaluator or printer endpoint.

The plugin requires a compatible 2.5 development build with asynchronous Script
execution and `orca.host.ui.create_window`. Older Orca versions can keep using the
CLI/file MCP tools. Do not install the plugin in 2.4.2 and expect an embedded host.

## Install and connect

1. Download `rrs_orcaslicer_bridge.py` from the release, or call MCP
   `host_plugin_export` with a new `.py` destination.
2. In a compatible Orca build open **File > Plugins > Install local plugin** and
   select the file. Select **RRS MCP local bridge** and press **Run**.
3. Keep the bridge's non-modal panel open. It shows the private mailbox directory.
4. Add `ORCA_MCP_BRIDGE` with that directory to the external MCP configuration,
   then restart the MCP client. The config helper accepts `--bridge-dir`:

```bash
python scripts/make_config.py --binary /path/to/OrcaSlicer \
  --root /path/to/models --bridge-dir /path/shown/in/the/plugin/panel
```

5. Check `host_bridge_status`. `online` must be true. Use its `session_id` for
   mutating requests and generate a fresh UUID hex request ID for each intended
   operation. Keep that ID when retrieving or repeating the same request.

By default, live project exports are allowed only inside the plugin's private
`rrs-mcp-bridge/exports` folder. Additional absolute directories can be listed in
the plugin's `export_roots` configuration. MCP also checks `ORCA_MCP_ROOTS`.
Orca's native audit/permission mechanisms still apply; the plugin does not disable
or pre-approve them. Do not configure a network/shared multi-user mailbox.

## Implemented host operations

| MCP tool | Official host access | Execution context |
| --- | --- | --- |
| `host_bridge_status` | Session and advertised capability receipt | External process; no native call |
| `host_snapshot` | `app_info`, Plater dirty states, selected presets, object count | GUI callback |
| `host_model_read` | Live model objects, IDs, counts, painting flags and object settings | GUI callback; paged |
| `host_presets_list` | Loaded preset collection names and selected name | GUI callback; paged |
| `host_preset_read` | Loaded/edited preset serialized values, including unsaved values | GUI callback; paged; secret keys redacted |
| `host_preset_update` | `begin_update`, `set`, `commit` on process/printer/filament | Background Script worker |
| `host_project_export` | `plater.export_3mf_copy` | GUI callback; new `.3mf` only |
| `host_request_status` | Durable execution journal/response | External process; also for older sessions |
| `host_plugin_export` | Copy packaged generated plugin to a new file | External process; no native call |

The host's available methods determine advertised operations. Missing APIs produce
an explicit unsupported/rejected receipt, never a substitute success. This is not
an arbitrary proxy to every attribute of `orca.host`. Read-only model access does
not imply model mutation, painting, calibration or device-control support.

## Thread and object lifetime rules

The Script invocation owns an asyncio loop on Orca's Script worker. It opens a
host-managed HTML window and stays alive until that panel closes or Orca cancels
the capability. The window sends small tick messages; its `on_message` callback
runs on the GUI thread. This callback performs native model/preset reads and the
3MF copy export, converts native values immediately to JSON data, and drops the
native handles before returning.

Preset mutations are queued as plain JSON. The Script worker takes one request,
calls the official staged preset API and waits for its native GUI handoff. It
never enumerates the live model from the worker. No native model/preset pointers
are retained in queues, journals or across coroutine suspension points.

Native target-selection and unsaved-edit dialogs remain authoritative. The
bridge does not choose a response or save a dirty preset. A successful commit
returns `saved_to_disk: false`, along with the actual target, dirty state, changed
keys, selection changes and shared filament-slot information exposed by Orca.
For filaments, callers must supply a 1-based slot. Editing a shared preset can
affect every slot using it.

## Protocol and recovery

Protocol version **1** uses the plugin's own storage folder:

```text
session.json
<session-id>/requests/<request-id>.json
<session-id>/journal/<request-id>.json
<session-id>/responses/<request-id>.json
```

Session/request IDs are 32 lowercase hexadecimal characters. A new plugin run
creates a fresh session and random token. The external client reads the token
from a local private file; it is not returned by `host_bridge_status` or printed
in the panel. New protocol files use mode 0600, new private directories 0700 on
POSIX. Windows security remains the user's file ACLs. This is a same-user trust
boundary, not a sandbox against another process running as that user.

Requests are immutable, bounded to 128 KiB and authenticated by the current token.
They carry an operation/parameter fingerprint and a finite expiry. Responses are
bounded to 2 MiB; callers can request smaller pages. Path/ID checks reject traversal
and symbolic links. Only named operations are dispatched. Existing request IDs with
different parameters conflict. The plugin never replays old sessions.

Before a native effect, a `started` journal is atomically written and fsynced.
The terminal response is cached with the same fingerprint. Repeating the same ID
in the same session retrieves that response and does not commit again. A host
crash between native mutation and final receipt is **indeterminate**; a filesystem
journal cannot make a C++ transaction and a JSON write one atomic transaction.
This is duplicate suppression with conservative recovery, not a global exactly-once
guarantee across crashes or deliberately submitted fresh IDs.

A client timeout returns `outcome_unknown` with both IDs. It does not undo or
repeat a request. Call `host_request_status` and inspect Orca if necessary. A dialog
may remain open and an already started transaction may still finish. A changed
session invalidates mutation submission with the previous session ID. An expired
request that has not started is rejected. Closing the panel rejects queued work;
it does not reverse accepted native selection decisions or an in-flight commit.

The host transaction's guarantees remain those of Orca: staged setting validation
and application, not rollback of every dialog decision, preset selection, dependent
callback or external effect. See the upstream preset API design for that boundary.

## Source and build discipline

Reviewed implementation references at upstream revision
`5817a76da6a783a992009c8f3aa6cd6b88efc9b8`:

- `src/slic3r/plugin/host/PluginHostApp.cpp` — GUI-thread checks and 3MF copy export.
- `PluginHostModel.cpp` / `PluginHostPresets.cpp` — native data and transaction APIs.
- `PluginHostUi.cpp` — window callbacks and GUI marshalling.
- `docs/HLSD/python-plugin-async-bridge.md` and `preset-plugin-api.md` — worker and transaction semantics.

The source modules are in `host_bridge/`. `scripts/build_host_plugin.py` combines
them with the official plugin entry template into one standalone Python file.
`--check` verifies that the committed artifact matches the reviewed modules.
CI compiles, lints, tests the generated artifact and separately exercises the native
host. A documentation example or mocked unit test is not reported as native proof.

Public upstream documentation may lag current source (notably the Script-thread
description); the test evidence must identify the actual Orca build used.
