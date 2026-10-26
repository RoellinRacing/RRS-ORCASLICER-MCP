# Vollständigkeit: was unterstützt wird und was noch fehlt

**Die Schnittstelle ist keine vollständige semantische API für alle Orca-Funktionen.**
Ein allgemeiner Maus-/Tastaturzugriff beweist keine solche Vollständigkeit. Ebenso
sind 966 Katalogdefinitionen nicht gleichbedeutend mit 966 getesteten Funktionen.

`feature_coverage` gibt die Abdeckung maschinenlesbar zusammen mit den tatsächlich
erkannten CLI-Optionen aus. Die Tabelle in `data/coverage.json` unterscheidet direkte
Implementierung, versionsabhängige CLI-Funktionen und GUI-/Upstream-Lücken.

| Funktionsfamilie | Aktueller Weg | Offene Arbeit für eine vollständige semantische API |
| --- | --- | --- |
| Printer-/Prozess-/Filamentsettings | JSON lesen, bearbeiten, auflösen, vergleichen, exportieren | Offizielles Live-Preset-API integrieren, GUI-Validierung und Speicherabläufe prüfen |
| Globale und objektbezogene Drucksettings | 3MF-JSON/XML, gezielte Objekt-/Teil-/Plattenänderungen | Live-Objektidentität und Undo im laufenden Orca |
| Slicing, Stapel und Exporte | Installierte CLI, permanente Jobzustände, G-Code-Auswertung | Strukturierte Live-Fortschritts-/Resultatereignisse |
| Skalieren, Drehen, Anordnen, Kopien | Sämtliche angebotenen CLI-Flags | Vollständige Manipulation des geladenen Szenenmodells |
| Reparieren, Teilen, Schneiden, Verbinden, Text | CLI soweit angeboten, sonst sichtbare GUI | Typisierte Operationen mit überprüfbaren Geometrieergebnissen |
| Stütz-, Naht- und Farbbemalung | Sichtbare GUI; vorhandene Archivinhalte bleiben erhalten | Semantische Flächen-/Maskenänderungen samt Roundtrip-Tests |
| Kalibrierungswerkzeuge | Sichtbare GUI | Generatorparameter, Resultate und Druckerbezug als API |
| Drucker, AMS/MMU und Cloud | Orcas eigene Oberfläche/Provider | Providerfähigkeiten, normalisierte Zustände und explizite Druckaktionen |

## Neue offizielle Erweiterungspunkte

Beim Nachprüfen des Upstreams wurde das **experimentelle Python-Plugin-System**
gefunden. Der Projektaufruf unter
https://github.com/OrcaSlicer/OrcaSlicer/discussions/14878 fragt ausdrücklich nach
Anforderungen für externe Automatisierung und fehlende APIs. Die dort genannten
Schnittstellen sind im Wandel und kein Vertrag für ältere stabile Orca-Versionen.

Im untersuchten Quellstand gibt es unter anderem:

- `docs/HLSD/preset-plugin-api.md`: Live-Preset-Transaktionen über
  `begin_update()`, `set()` und `commit()`, unter Einbezug normaler GUI-Validierung.
- `docs/HLSD/python-plugin-async-bridge.md`: Hintergrundausführung von Script-
  Fähigkeiten und die Lebensdauer-/Threadregeln für API-Aufrufe.
- `src/slic3r/plugin/host/`: Host-Bindings für Presets, Modelle, Geometrie, Slicing und UI.
- `sandboxes/orca_inspector_plugin_any.py`: offizielles Beispiel zur API-Inspektion.

Diese Punkte sind **noch nicht an den externen MCP-Server angeschlossen**. Sie
ohne Lauf in einer passenden Nightly-Version als funktionierend auszugeben wäre
falsch. Die externe Grundarchitektur kann bestehen bleiben; eine optionale kleine
offizielle Host-Erweiterung wäre ein möglicher Weg für den Live-Zugriff. Welche
Funktionen der Host tatsächlich freigibt und welche ergänzt werden müssen, ist
mit den Maintainern und anhand realer Tests zu klären.

## Reihenfolge für die restliche Arbeit

1. Unterstützte Nightly und offizielle Host-API gegen einen kleinen Referenzsatz prüfen.
2. Capability-Aushandlung und einen lokalen, begrenzten Transport implementieren.
3. Live-Presets, Modelloperationen und Slicing-Ereignisse einzeln anbinden und abnehmen.
4. Bemalung, Kalibrierung und Printer-Provider nach tatsächlicher API-Verfügbarkeit ergänzen.
5. Für jede Operation einen Nachweis und die getesteten Versionen dokumentieren.

Keine der offenen Zeilen wird allein durch einen erfolgreichen CLI-Slicing-Test
als erledigt markiert. Es gibt derzeit keine ehrliche 100-%- oder Alle-Versionen-Garantie.
