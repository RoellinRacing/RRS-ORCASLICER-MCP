# RRS OrcaSlicer MCP 0.4.0

54 tools in an independent MCP server with optional official-host plugin.

- Revision-bound 3MF build/component transforms and support/seam/material/fuzzy
  facet painting, including validated subtriangle mask trees.
- Optional offline mesh repair, split, cut, merge, Boolean operations, convex hull,
  simplify and transform, with measured STL results.
- Resumable constant-setting calibration coupon series from a supplied 3MF.
- Copied live volume/instance details, selected-printer diagnostics and bounded
  synchronous native slicing observations with cursor/epoch/gap detection.
- Configured Moonraker/OctoPrint status, uploads and explicit print commands, with
  durable request IDs and conservative recovery after uncertain dispatch.

See EXTENDED_OPERATIONS.md and BUSINESS_LOGIC.md. Native source evidence is
bundled as docs/evidence/host-0.4.0.json when the release gates pass. CI includes
real stock-engine transform/painting reopen/reslice checks. Provider contracts
are tested against HTTP mocks; no physical printer acceptance was performed.

This is not a complete API for all Orca functions or versions. Live document
mutation/undo, embossing, native calibration generators, cloud/AMS/MMU and complete
GUI command coverage remain open. New STLs do not inherit 3MF annotations.

Install base: pip install ./rrs_orcaslicer_mcp-0.4.0-py3-none-any.whl
Install optional mesh tools: pip install 'rrs-orcaslicer-mcp[geometry]'
