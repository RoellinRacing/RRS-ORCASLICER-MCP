# RRS OrcaSlicer MCP 0.5.1

63 tools. Reconnect-safe individual CLI slicing adds an optional idempotency key
bound to arguments, timeout and model/profile SHA256. Concurrent identical keys
produce one saved job. Queued inputs are checked before Orca starts.

New job_log returns bounded log ranges with reusable byte cursors; job_wait waits
up to 30 seconds without cancelling computation on observation timeout. Saved logs
are capped at exactly 10 MiB while the child output continues to be drained.

The existing native 0.5.0 workflows remain: move/rotate/scale with Undo/Redo,
editable text and nine original calibration generator families. Native acceptance
is Linux X11 / English UI / documented layout, one object and one instance for
transforms/text. Additional GUI platforms, locales and firmware variants need
separate acceptance. No cloud/AMS/MMU API or every-version guarantee is claimed.

Installation is described in README.md. Business rules and usage are in
RESUMABLE_JOBS.md, NATIVE_WORKFLOWS.md and BUSINESS_LOGIC.md. No physical print
was started during development.
