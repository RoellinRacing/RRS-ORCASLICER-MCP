# Kontakt zum OrcaSlicer-Team

Bestehender Entwicklerthread:
https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878

Vor einem Beitrag den aktuellen CONTRIBUTING.md des Upstreams lesen. Dani will
selbst Kontakt aufnehmen; kein Beitrag, Issue oder PR wurde gesendet.

## Sachlicher englischer Entwurf

We develop RRS-ORCASLICER-MCP, a separate local MCP server:
https://github.com/RoellinRacing/RRS-ORCASLICER-MCP

Version 0.4.0 exposes 54 tools. The optional dependency-free official Script plugin
uses GUI callbacks for copied reads and a Script worker for begin_update/set/commit.
It preserves native validation, unsaved-edit dialogs and dirty state. The external
process uses a bounded local mailbox with session/request identities and durable
receipts; uncertain native outcomes are never retried automatically.

The expansion adds identity-bound live volume/instance diagnostics, selected-printer
reads and an optional synchronous SlicingPipeline observer. The observer copies
only stage/version/object IDs into a bounded cursor/epoch ring and never retains
borrowed native references or calls the GUI/filesystem from a slicing callback.

Independent workflows cover revision-bound 3MF transforms and four-channel facet
painting, including validated subdivision trees, optional measured STL topology
operations, calibration coupon series and configured Moonraker/OctoPrint adapters.
The last two are explicitly separate workflows, not claims of native calibration
API coverage or Orca cloud/AMS control. Printer dispatch uses durable request IDs
and separates upload from explicit physical job commands; no real printer was
commanded during development.

The stock OrcaSlicer 2.4.2 Linux CLI successfully reopened/resliced transformed and
painted projects and preserved all four masks. This caught an actual compatibility
issue: namespace-equivalent ns0:model XML is treated as empty by the lexical Expat
handlers, so we retain unprefixed core tags and original extension prefixes.
The repository includes exact version/build/checksum/CI evidence and distinguishes
native integration results from HTTP mocks and pure Python tests. See VALIDATION.md,
MAINTAINER_REVIEW.md and docs/evidence for completed results.

We inspected host bindings at upstream commit
1433316b550bac676136f618e215ece8c884bb8c. ModelObject/Volume/Instance bindings are
read-only; we do not use private pointers, arbitrary eval or binary patches to
pretend that this is complete control of Orca. We would appreciate guidance on:

1. A supported document transaction API for model/instance changes with stable IDs,
   validation, undo and correct slicing invalidation.
2. Native facet-paint edits with triangle/subtriangle identity and roundtrip rules.
3. Asynchronous slice/cancel/export jobs with structured lifecycle/result events.
4. Parameterized native calibration model generation and result/application flows.
5. Capability-negotiated printer/provider/AMS actions without credential exposure.
6. A versioned scheduling/transport contract so external automation can remain
   separate and compatible across supported host versions.

Would these fit the planned extension architecture? We can contribute focused
operation-level test cases and compatibility results rather than a broad unsafe
method-dispatch endpoint.
