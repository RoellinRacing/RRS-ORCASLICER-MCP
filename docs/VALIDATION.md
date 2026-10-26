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

## Noch kein Nachweis

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
