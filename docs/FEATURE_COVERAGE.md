## Stand 0.5.0 — gezielte native Bedienabläufe

`native_transform` bearbeitet Live-Position/Drehung/Skalierung und liest die echte
Pose zurück. `native_history` nutzt Orcas eigene Undo-/Redo-Historie.
`native_text` prüft editierbaren Text, Höhe/Tiefe und Volumentyp in der nativen
Projektkopie. `native_calibration` ruft die Originaldialoge und Generatoren auf.
Die neun Familien und die konkreten getesteten Varianten stehen in
[NATIVE_WORKFLOWS.md](NATIVE_WORKFLOWS.md) bzw. den nativen CI-Nachweisen.

Das ist ein gezielter Desktop-Adapter mit nativer Ergebnisprüfung, keine neue
öffentliche C++-Dokument-API. Englisches Prepare-Layout, Standardkürzel und expliziter
Desktop-Opt-in sind erforderlich. Transformation/Text: zunächst ein Objekt/eine
Instanz; relative Drehung bei sonst ungedrehten Achsen. Kein vollständiger Mesh-Hash,
keine generelle Plattform-/Versions-/Firmwaregarantie. Die älteren Tabellen unten
sind versionsbezogene Ausgangsstände und werden dadurch nicht rückwirkend umgedeutet.

## Stand 0.4.0 — native Nachweise bestanden

Neue semantische Wege: `project_geometry_read/project_transform_write`,
`project_painting_read/write` (vier Kanäle samt Unterdreiecken), `mesh_operation`
(Reparieren, Teilen, Schneiden, Booleans, Verbinden, Hülle, Vereinfachen, Transformieren),
`calibration_series_create` (vier Parameterreihen), `host_model_detail`,
`host_printer_read`, `host_slicing_events` und konfigurierte Moonraker-/OctoPrint-
Adapter. Details und Grenzen: [EXTENDED_OPERATIONS.md](EXTENDED_OPERATIONS.md).
Die frühere Tabelle unten beschreibt den Ausgangsstand 0.3.0; aktuelle
maschinenlesbare Wege stehen in `data/coverage.json`.

Live-Modelländerungen mit Undo, Text/Embossing, die nativen Kalibrierungsdialoge,
Cloud/AMS/MMU und vollständige native GUI-Steuerung bleiben offen. Ein generischer
Maus-/Tastaturzugriff ist kein Ersatz für deren semantische Implementierung.

# Vollständigkeit: was unterstützt wird und was noch fehlt

**Die Schnittstelle ist keine vollständige semantische API für alle Orca-Funktionen.**
Ein allgemeiner Maus-/Tastaturzugriff beweist keine solche Vollständigkeit. Ebenso
sind 966 Katalogdefinitionen nicht gleichbedeutend mit 966 getesteten Funktionen.

`feature_coverage` gibt die Abdeckung maschinenlesbar zusammen mit den tatsächlich
erkannten CLI-Optionen aus. Die Tabelle in `data/coverage.json` unterscheidet direkte
Implementierung, versionsabhängige CLI-Funktionen und GUI-/Upstream-Lücken.

| Funktionsfamilie | Aktueller Weg | Offene Arbeit für eine vollständige semantische API |
| --- | --- | --- |
| Printer-/Prozess-/Filamentsettings | JSON lesen, bearbeiten, auflösen, vergleichen, exportieren | Live-Lesen/-Transaktionen sind über das optionale offizielle Plugin angebunden; normales Speichern bleibt Orcas Aufgabe |
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

In 0.3.0 sind Live-Preset-Abfragen, native Preset-Transaktionen, Modellabfragen
und die Live-Projektkopie über das optionale offizielle Script-Plugin angebunden.
Die externe Grundarchitektur bleibt bestehen. `host_bridge_status` handelt die
vorhandenen Operationen aus; Details stehen in HOST_BRIDGE.md. Die konkreten
abgeschlossenen Host-Tests stehen in VALIDATION.md, nicht in einer pauschalen
Alle-Funktionen-Behauptung. Geometrie-/Bemalungsänderungen, Kalibrierung, Live-Slicing-
Hooks und Geräteoperationen sind damit weiterhin nicht implementiert.

## Reihenfolge für die restliche Arbeit

1. Die vorhandenen Host-Operationen bei API-/Versionswechseln gegen den Referenzsatz prüfen.
2. Live-Geometrieänderungen und Slicing-Ereignisse einzeln anbinden und abnehmen.
3. Bemalung, Kalibrierung und Printer-Provider nach tatsächlicher API-Verfügbarkeit ergänzen.
4. Für jede Operation einen Nachweis und die getesteten Versionen dokumentieren.

Keine der offenen Zeilen wird allein durch einen erfolgreichen CLI-Slicing-Test
als erledigt markiert. Es gibt derzeit keine ehrliche 100-%- oder Alle-Versionen-Garantie.
