# 0.2.0

30-tool standalone OrcaSlicer MCP bridge with new semantic project and batch workflows.

- Read objects, parts, plate IDs and instance assignments; change print settings by ID.
- Compare serialized profiles, run advisory source-based checks, export flattened profiles.
- Read declared G-code time, filament, layer and temperature data without executing it.
- Durable batch slicing, content-sensitive idempotency, aggregate status and cancellation.
- Verify queued input/profile hashes before engine execution; keep prior successful jobs.
- Real MCP verification of object settings, two-input batch slicing, output analysis and retry identity.
- Explicit feature coverage and a prepared upstream plugin-discussion contact proposal.

Not a complete semantic API for all GUI, painting, calibration, printer/cloud or
live-plugin functions. The experimental official host API has been researched but
is not yet integrated. See docs/FEATURE_COVERAGE.md. No message has been sent upstream.
