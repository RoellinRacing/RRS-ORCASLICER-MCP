# Kontakt zum OrcaSlicer-Team

Passender vorhandener Entwicklerthread:
**https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878**

Alternativ: https://github.com/OrcaSlicer/OrcaSlicer/discussions/categories/dev.
Vor dem Posten den aktuellen CONTRIBUTING.md des offiziellen Repositories lesen.
Dieser Entwurf wurde noch nicht veröffentlicht. Aktuelle Testergebnisse und Grenzen
stehen in VALIDATION.md und MAINTAINER_REVIEW.md.

## Vorbereiteter englischer Beitrag

We are developing RRS-ORCASLICER-MCP, a separate local MCP server for OrcaSlicer:
https://github.com/RoellinRacing/RRS-ORCASLICER-MCP

It supports CLI/file workflows and now includes an optional, dependency-free
Script plugin using the official Python host. The plugin reads live preset/model
snapshots in GUI callbacks, queues preset changes onto the Script worker and uses
begin_update/set/commit. It preserves native selection/unsaved-edit dialogs and
leaves edited presets unsaved. It also exposes the supported 3MF copy export.

The external process communicates through a bounded local mailbox in plugin
storage. Operations are allowlisted. Session/request identities and durable receipts
prevent accidental repeats; timeouts are explicitly indeterminate. We do not expose
an eval endpoint, private C++ symbols, a network listener or printer credentials.

The repository includes reproducible tests, business-logic/protocol notes and a
maintainer review summary. The validation report identifies exactly which native
host build/platform was tested; mocked protocol tests are labelled separately.
We do not claim full GUI/geometry/painting/calibration/device control or compatibility
with every host version.

Would this approach fit the supported extension architecture? In particular, we
would appreciate guidance on UI/worker dispatch, API compatibility negotiation and
future semantic model/slicing operations. The bridge currently uses the documented
window on_message callback as its GUI-thread entry point. If a preferred host-owned
scheduling or local transport capability is planned, we would be happy to align
with it and contribute focused test results.
