# Extended semantic automation

Baseline: published 0.3.0, repository checkpoint 8bec1947.
Upstream inspected: OrcaSlicer main 1433316b550bac676136f618e215ece8c884bb8c.

Goal: expose operations with explicit inputs, actual results and version-specific
limits. Preserve the independent external server and optional stock-host plugin.
Never equate a generic input channel with complete semantic coverage.

Implementation sections:
1. Project geometry: inspect actual 3MF object/component/build transforms; write
   instance transforms to new archives with source revision checks and invalidated
   slicing artifacts. Preserve all unmodified payloads and painting.
2. Triangle painting: inspect and edit stored support/seam/material/fuzzy masks,
   using upstream serialization and explicit mesh/triangle identities.
3. Host expansion: copied detailed model/instance/volume data and selected-printer
   state where official bindings expose them. No retained native handles.
4. Slicing event observations through the official synchronous pipeline capability.
   Do not invoke GUI code from a slicing callback.
5. Reconcile calibration and device commands against actual supported upstream
   entry points; implement independent operations where a verifiable path exists.

Business rationale: file-level operations work on releases that lack live mutation
bindings. A new recoverable project is preferable to unsafe edits through borrowed
native pointers. Existing 0.3.0 native evidence remains authoritative only for its
original operations and versions. New behavior gets separate evidence.

Checkpoint after each completed section: implementation, tests, business rules,
remaining gaps and next step; commit and push before costly native validation.
