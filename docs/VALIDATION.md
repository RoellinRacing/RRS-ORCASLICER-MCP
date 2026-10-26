# Abnahme für 0.5.0

Das 0.5.0-Paket wird erst nach sechs erfolgreichen OS-/Python-Prüfungen, echtem
Slicing und vollständiger kombinierter Linux-X11-Abnahme veröffentlicht. Der
paketeigene `evidence/host-0.5.0.json` bindet den offiziellen Orca-Build, Pluginhash,
Source-Commit und CI-Lauf. `evidence/native-workflows-0.5.0.json` enthält die echten
Operationsquittungen für Transformation/Undo/Redo, Join/Cut/Modifier-Text und neun
native Generatorfamilien. Die unabhängigen Diagnoseläufe allein geben kein Paket frei.

95 lokale Tests bestanden im Fortsetzungsstand. Zehn tatsächliche Fehler-/Commitbilder
wurden zusätzlich ohne Eingaben gegen exakte Zahlen/Radioziele geprüft:
[evidence/native-calibration-ocr-0.5.0.json](evidence/native-calibration-ocr-0.5.0.json).
Das ist ein Selector-Nachweis; die native Gesamtabnahme bleibt zusätzlich erforderlich.
Geschäftsregeln und Grenzen: [NATIVE_WORKFLOWS.md](NATIVE_WORKFLOWS.md).

# Historischer Nachweis — 0.4.0

[CI 40323305158](https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40323305158)
ist vollständig erfolgreich, Release-Commit `ad2227e2acd48a32e7e1a912d3bf2461ae49625d`.
58 Tests je Matrixeintrag auf Windows/macOS/Linux, Python 3.11/3.13; lokale
Suite und separat installiertes Wheel ebenfalls 58 bestanden.

**Stock Orca 2.4.2 Linux:** Das über öffentliche MCP-Werkzeuge transformierte und
in allen vier Kanälen bemalte 3MF wurde geöffnet und neu geslict. Der Faktor 1.1
und Support-/Naht-/Material-/Fuzzy-Masken blieben im Orca-Export erhalten. G-Code wurde
erzeugt; [tatsächlicher Roundtrip](evidence/semantics-0.4.0.json).

**Offizieller Linux-Nightly 2.5.0-dev, Build 2dfcba39:** Detaillierte Volumen-/Instanz-
Abfragen mit Objektidentität, redigierte Geräteabfrage (kein Gerät verbunden),
Preset-Transaktionen aller drei Kategorien, Fehler-/Duplikatbehandlung, ungespeicherte
Projektkopie und MCP-stdio bestanden. Nach Auswahl des Observers und normalem GUI-
Slicen wurden zehn echte Pipeline-Schritte gemeldet, darunter posSlice, posPerimeters,
posInfill und psSkirtBrim. [Build-/Plugin-/CI-Nachweis](evidence/host-0.4.0.json).

**Mesh-Tests:** Booleans werden am exportierten und neu geladenen STL gemessen:
Union 1500, Differenz 500, Schnittmenge 500 mm3 für die dokumentierten Testwürfel.
Zwei geschlossene Schnitthälften je 500 mm3, Reparatur, Teilen, Transformation,
Hülle und Vereinfachung geprüft. Keine Zusicherung für beliebige defekte Netze.

**Kalibrierung und Geräte:** Wiederaufnahme/Parameterbindung und Erhalt fremder
Filamentslots getestet. Moonraker-/OctoPrint-HTTP-Verträge, explizite Pause/Resume,
Upload ohne Druckstart, Request-ID-Konflikte und unsichere Transportresultate nach
Neustart getestet. Das sind HTTP-Mocks, keine Geräteabnahme. Kein physischer Druck.

Öffentliche Downloads wurden gegen SHA256SUMS, ZIP-Integrität, enthaltene native
Nachweise und Wheel-Quellinhalt geprüft:
[Releaseprüfung](evidence/github-release-0.4.0.json). Die vollständigen früheren
Nachweise folgen als historische, versionsbezogene Ergebnisse.

# Testnachweis für 0.1.1

Prüfung am 26. Oktober 2026, Linux x86_64, Python 3.12.14, MCP SDK 1.30.0.

## Automatisierte Prüfungen

14 Tests bestanden. Abgedeckt sind JSON-Erhalt unbekannter Werte, Revisionskonflikte,
Backups, Pfad-/Symlinkgrenzen, Profilvererbung und Zyklen, 3MF-Inhaltserhalt,
Objektmetadaten, Entfernung veralteter Druckdaten, Prozessfehler, Warteschlange,
Abbruch, Timeout, Wiederaufnahmestatus und echter MCP-stdio-Handshake mit Toolaufrufen und Abbruch laufender Arbeit beim
Trennen des MCP-Clients.
`ruff check src scripts tests` ist fehlerfrei. Auch nach separater Installation des
gebauten Wheels bestanden dieselben 14 Tests; siehe `evidence/wheel-tests.txt`.

## Echte OrcaSlicer-Engine

Offizielle OrcaSlicer Linux AppImage **v2.4.2** von
https://github.com/OrcaSlicer/OrcaSlicer/releases/tag/v2.4.2.
55 CLI-Optionen wurden aus der installierten Hilfe erkannt. Fehlende Hostbibliotheken
wurden für den Test separat bereitgestellt; Orca selbst wurde nicht verändert.

`scripts/smoke_orca.py` erzeugte einen 10-mm-Würfel und löste die mitgelieferten
A1-mini-/PLA-/0.20-mm-Profile derselben Engine auf. Orca erzeugte:

| Artefakt | Grösse | SHA256 |
| --- | ---: | --- |
| `plate_1.gcode` | 193126 Bytes | `5a95544b851afac7147230401cd36c87ce392898ecde65b468f8d36e4865dd3c` |
| `cube-sliced.3mf` | 39262 Bytes | `f2c18cfde89a086529deda1ec9551c292dcb1499f10718fc0cd46e86b0382353` |

Das 3MF enthält den erzeugten G-Code zusätzlich als eingebettetes Archivmitglied.
Der Maschinen-/Filamentdatensatz dient ausschliesslich dem Engine-Test und ist
kein Profilvorschlag für einen anderen Drucker.

## Vollständiger MCP-Roundtrip

`scripts/verify_roundtrip.py` startete den Server als separaten stdio-Prozess und
verwendete den offiziellen MCP-Client. Es las das erzeugte 3MF, änderte die globale
Schichthöhe auf `0.25`, prüfte den unveränderten Hash der Originaldatei und stellte
sicher, dass die neue 3MF-Datei den alten G-Code nicht mehr enthält. Danach wurde
`slice_project` über MCP aufgerufen und bis zum erfolgreichen Jobende kontrolliert.

Ergebnis: neuer G-Code mit **169258 Bytes**, SHA256
`32be01bd5e76744b48bcb0f69eff2acefd4a1d98a2b1b31a6d452d0a4be86a82`.
Das neue, von Orca exportierte 3MF enthält die geänderte Schichthöhe `0.25` und einen
neu eingebetteten G-Code. Sein SHA256 lautet
`5c8041269ec469065f2b5c5a9c167b53a69254649a8f40ed68cc3b4e53e5b4a8`.

Maschinenlesbare Ergebnisse: [Slicing](evidence/real-slicing.json) und
[MCP-Roundtrip](evidence/mcp-roundtrip.json). Die Erzeugungsskripte sind beigefügt.
G-Code-Hashes können wegen Versions-/Zeitmetadaten bei einem neuen Lauf abweichen.

## Noch kein Nachweis im damaligen Stand 0.1.1

Die lokale Prüfung umfasst keinen physischen Druck, keine Druckerverbindung,
keine GUI-Aktionen und keinen praktischen Windows-/macOS-Lauf. Die CI-Matrix prüft
Python-/Protokollfunktionen auf allen drei Betriebssystemen, sobald GitHub Actions
läuft. Für GUI-only-Funktionen und zukünftige Orca-Versionen bestehen die im
README dokumentierten Grenzen.

## Abschliessender GitHub-Nachweis

[Workflow 40276480510](https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40276480510)
ist vollständig erfolgreich: **14 Tests je Matrixeintrag**, Windows/macOS/Linux mit
Python 3.11 und 3.13, echter OrcaSlicer-Slicing-/MCP-Roundtrip sowie Paketbau.
Release **v0.1.1** wurde auf Commit `b801692e51f5bfba880466941eac258e0781dcc3`
veröffentlicht. Das öffentliche ZIP wurde wieder heruntergeladen und gegen die
veröffentlichten SHA256SUMS sowie auf ZIP-Integrität geprüft.
[Maschinenlesbare Releaseprüfung](evidence/github-release.json).

## Erweiterungsnachweis für 0.2.0

25 lokale Tests bestanden, einschliesslich der neuen semantischen 3MF-Änderungen,
Vererbungsexporte, serialisierten Profilunterschiede, advisory Vorprüfungen,
G-Code-Auswertung, persistierter Batch-Identität, Abbruch und geänderten Warteschlangen-
Eingaben. Die bisherigen 0.1.1-Prüfungen bleiben enthalten.

`scripts/verify_extensions.py` verwendet das schon vorhandene reale Referenzprojekt
und den offiziellen MCP-Client. Getestet wurden Objekt-Wände auf `4`, eine neue
Plattenbezeichnung, flacher Profilexport und ein Zweier-Stapel mit Original und
geändertem Projekt. Der zweite identische Aufruf verwendete dieselben Job-IDs und
erzeugte keine weiteren Slicing-Prozesse.

OrcaSlicer 2.4.2 erzeugte für das Original 193189 Bytes G-Code mit deklarierten
739 Sekunden/0.72 g und für das Vier-Wände-Objekt 205164 Bytes mit 743 Sekunden/0.94 g.
Die objektbezogene Einstellung `wall_loops=4` blieb im neu exportierten 3MF erhalten.
Das sind Slicer-Schätzungen, keine gemessenen Druckzeiten oder Materialverbräuche.
Maschinenlesbares Ergebnis: [extensions-0.2.0.json](evidence/extensions-0.2.0.json).

Die hier recherchierte experimentelle offizielle Plugin-API wurde nicht in einer
Nightly ausgeführt und ist keine implementierte Funktion dieser Veröffentlichung.

Auch das separat installierte 0.2.0-Wheel bestand dieselben 25 Tests:
[evidence/wheel-tests-0.2.0.txt](evidence/wheel-tests-0.2.0.txt).

## Öffentliche Freigabe von 0.2.0

[GitHub-Lauf 40278472600](https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40278472600)
ist vollständig erfolgreich: 25 Tests je OS-/Python-Matrixeintrag, bestehende echte
Engine-Prüfungen sowie der neue semantische Objekt-/Platten-/Profil-/Stapel-Test.
Release-Commit: `735a5f0e4d18beeda71e86ffacb13431a09b5da7`.
Das veröffentlichte ZIP wurde heruntergeladen und gegen die öffentlichen
SHA256SUMS sowie auf Archivintegrität geprüft.
[Release-Prüfung](evidence/github-release-0.2.0.json).

## Prüfungen für 0.3.0

43 Tests bestanden lokal und mit separat installiertem Wheel, einschliesslich
Protokollidentitäten, Wiederholungsschutz, Timeout-Recovery, GUI-/Worker-Zuordnung,
Filamentslots, Exportpfaden, nativen Benutzerprofil-Metadaten, Windows-Dateisperren
und dem Quittungsausfall nach einer angewendeten Änderung.
[Wheel-Prüfung](evidence/wheel-tests-0.3.0.txt).

Die Releasepipeline verlangt zusätzlich einen erfolgreichen Lauf des unveränderten
offiziellen Nightly-AppImage in X11. Sie prüft die echte Pluginregistrierung,
Live-Modell-/Presetzugriffe, native Änderungen aller drei Presetkategorien,
Zurückweisung ungültiger Änderungen sowie ungespeicherte Einstellungen im
exportierten 3MF. Auch der öffentliche MCP-stdio-Weg wird dabei ausgeführt.
Vor dem Paketbau wird der Ergebnisbericht mit Pluginhash, Nightly-Prüfsumme,
Quellcommit und CI-Link in `docs/evidence/host-0.3.0.json` aufgenommen; ein fremder
Pluginhash oder fehlender Erfolgsnachweis verhindert den Paketbau.

Ein erfolgreicher nativer Linuxlauf beweist keine native Windows-/macOS-GUI-Prüfung
und keine vollständige Orca-Funktionsabdeckung. Der aktuelle Hostnachweis ist erst
mit diesem Bericht und dem erfolgreichen CI-Lauf abgeschlossen.

## Abgeschlossener nativer Host- und Release-Nachweis 0.3.0

[CI-Lauf 40288598146](https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40288598146)
ist vollständig erfolgreich: **43 Tests je Matrixeintrag** unter Windows, macOS und
Linux mit Python 3.11/3.13, echtes Slicing mit 2.4.2, eingebetteter Host und Paketbau.
Der native Test lief im offiziellen Linux-Nightly **2.5.0-dev, Build 2dfcba39**,
mit aktiviertem Audit und ohne Drucker-/Kontoanmeldung.

Nachgewiesene Ergebnisse:

- Ein geladenes Modell; Prozess-Wände von `2` auf `5`, über MCP danach auf `6`.
- Druckerwert `machine_max_speed_z=13`, Filamentwert `filament_flow_ratio=0.98`.
- Dieselbe Request-ID liefert dieselbe Quittung; eine ungültige native Änderungsgruppe
  erhält den vorherigen Wandwert.
- Neue 3MF-Kopie mit ungespeichertem `wall_loops=5` (26432 Bytes); Projektpfad und
  Dirty-Zustände bleiben vor/nach dem Kopieren gleich. Die Datei enthält keinen
  behaupteten Drucknachweis.

[Originaler Hostbericht mit Hashes](evidence/host-0.3.0.json). Die nativen
Resultatflags werden unverändert weitergegeben, einschliesslich des vom Host
gelieferten Filament-`dirty=false`; daraus wird kein automatisches Speichern
abgeleitet. Das Plugin verwendet den offiziellen einfachen Script-Worker, keinen
eigenen asyncio-Loop und keine vorab genehmigten Audit-Berechtigungen.

Release **v0.3.0** stammt aus `de282ab59b013dd80806de4be59e2aebe61186a0`.
Alle vier veröffentlichten Dateien wurden erneut heruntergeladen und mit den
öffentlichen SHA256SUMS sowie den GitHub-Asset-Digests verglichen. ZIP und Wheel
sind integer; Plugin und native Evidenz stimmen mit der Veröffentlichung überein.
[Release-Prüfung](evidence/github-release-0.3.0.json). Das veröffentlichte Wheel
wurde zusätzlich separat installiert und bestand ebenfalls alle 43 Tests.
