# 0.3.0 — official-host plugin bridge

39-tool external MCP server with an optional dependency-free official Orca Script plugin.

- Live app/model/preset snapshots and paged serialized preset reads.
- Process/printer/filament updates through official staged host transactions.
- Explicit session/request identity, durable receipts and duplicate suppression.
- Conservative timeout recovery: an unknown outcome is never retried automatically.
- New-file export of the live project, including unsaved settings.
- Reviewed GUI/Script-worker separation; native dialogs and dirty-state behavior preserved.
- Standalone plugin asset, reproducible generation, protocol/business-logic documentation
  and maintainer review notes.

The plugin requires a compatible 2.5 development host. The existing CLI/file bridge
continues to work independently. Painting, live geometry mutation, calibration and
physical printer/cloud operations are not implemented by this adapter. See the
published validation report for the exact tested host/build and platforms.
