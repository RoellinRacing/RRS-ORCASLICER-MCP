# Kontakt zum OrcaSlicer-Team

Der passendste konkrete Ort ist die vorhandene offizielle Entwicklungsdiskussion:

**https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878**

Titel: Help Shape OrcaSlicer's Plugin System: Capabilities, Use Cases, and Developer Needs.
Alternativ: https://github.com/OrcaSlicer/OrcaSlicer/discussions/categories/dev.
Ein neuer Bugreport ist für die Vorstellung dieser Integration nicht passend.

Vor dem Posten den aktuellen Stand von `CONTRIBUTING.md` im offiziellen Repository
lesen. Das Team verlangt, dass ein Mensch den Beitrag vor dem Posten liest und die
angegebenen Tests versteht. Dieser Entwurf ist noch nicht veröffentlicht.

## Vorbereiteter englischer Beitrag

We are developing RRS-ORCASLICER-MCP, a separate local MCP server for external
automation without maintaining an OrcaSlicer fork:
https://github.com/RoellinRacing/RRS-ORCASLICER-MCP

The current bridge uses the installed CLI, JSON presets and Orca 3MF metadata. It
provides profile inheritance/diffs, object and plate settings, persistent slicing
jobs, batch cancellation and declared G-code statistics. We have tested actual
slicing and a read/edit/reslice roundtrip with the official Linux 2.4.2 release;
the Python/MCP layer is also tested on Windows and macOS. This does not validate
all GUI functions, printer operations or nightly plugin integration.

Our goal is semantic access to workflows that still require GUI interaction:
live preset validation, model/instance transformations, painting masks, calibration
generators and structured slice results. The Python host and staged preset API
look like a promising direction. We have not yet tested an embedded bridge in a
nightly build, and do not claim those operations are implemented.

Which host capabilities and compatibility/version-negotiation approach would you
recommend for this use case? Would a small optional local bridge plugin fit the
intended architecture? We would appreciate guidance on the appropriate extension
points and can contribute focused tests and feedback. The MCP server would remain
external, with explicit host-advertised capabilities rather than assuming that
every GUI operation is available or stable across versions.
