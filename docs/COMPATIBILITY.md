# Kompatibilität

Der Server patcht und ersetzt OrcaSlicer nicht. `ORCA_SLICER_BIN` kann nach einem
Update auf dieselbe Installationsdatei zeigen. Vor jedem CLI-Auftrag wird `--help`
erneut geprüft. Nach einem Update `orca_capabilities(refresh=true)` ausführen und
ein kleines vorhandenes Referenzprojekt slicen.

| Schicht | Strategie | Verbleibendes Risiko |
| --- | --- | --- |
| CLI | Optionen des tatsächlich installierten Programms | Gleicher Optionsname kann seine Bedeutung ändern; Hilfe kann unvollständig sein |
| JSON | Alle Schlüssel erhalten, Werte nicht ungefragt umformen | Orca kann Werte migrieren oder ablehnen |
| 3MF | Unbekannte ZIP-Mitglieder erhalten, Slicing-Caches verwerfen, neue Ausgabedatei | Ein internes Format kann sich ändern; JSON/XML-Syntax ist keine Semantikprüfung |
| Katalog | Aus offiziellem Source regenerierbare Metadaten mit Revision | Parser ist kein C++-Compiler; Makros/dynamische Definitionen können fehlen |
| Host-Plugin | Protokollversion und verfügbare offizielle Methoden prüfen | Experimentelle API; erfordert kompatiblen Hintergrund-Script-Host |
| Desktop | Beobachten und interagieren, keine festen Klickrezepte | Sprache, Layout, Dialoge und OS-Berechtigungen ändern Abläufe |

Nachgewiesene Engine: Linux AppImage **v2.4.2**, offizielles Upstream-Release.
Der beigefügte Katalog stammt aus **2.5.0-dev**, Commit
`5817a76da6a783a992009c8f3aa6cd6b88efc9b8`. Seine 966 Einträge enthalten auch
CLI-Definitionen. Funktionen aus dem Entwicklungsstand werden nicht auf einer
älteren Engine vorgetäuscht. Fehlende Definitionen verhindern keine JSON-Änderung.

Die GitHub-Actions-Prüfung führt Unit-/Protokolltests auf Windows, macOS und Linux
aus. Ein separater Linux-Test lädt beim regulären Build das festgelegte Release
2.4.2; beim wöchentlichen und manuellen Lauf stattdessen das aktuellste offizielle
stabile Release. Die Resultate sind Testnachweise, keine Garantie für beliebige
Versionen. Ein zusätzlicher isolierter Linux-X11-Test bedient die offizielle
Nightly tatsächlich: Live-Transformationen mit Undo/Redo, native Textmodi und neun
Generatorfamilien. Jede Veröffentlichung (zuletzt 0.5.1) erfordert den vollständigen
kombinierten Nachweis; Einzelprüfungen ersetzen ihn nicht. Die genauen Build- und
Plugin-Prüfsummen stehen im jeweiligen Paketnachweis. Windows/macOS-GUI und andere
Sprachen/Layouts sind durch diese Linux-Prüfung nicht abgenommen.

Manuelle Prüfung einer neuen Version:

```bash
ORCA_SLICER_BIN=/path/to/OrcaSlicer python -m rrs_orcaslicer_mcp.server --doctor --output doctor.json
ORCA_SLICER_BIN=/path/to/AppRun ORCA_TEST_RESOURCES=/path/to/resources \
  ORCA_TEST_OUTPUT=/path/to/new-smoke python scripts/smoke_orca.py
```

Den Smoke-Ausgabeordner für verschiedene Versionen getrennt halten. Die erzeugten
Profile müssen zur getesteten Engine gehören. Danach das eigene Druckerprojekt
öffnen, slicen und G-Code/Startcode mit der bisherigen Ausgabe vergleichen.

## Nativer Hostnachweis 0.3.0

Offizielles Linux-Nightly **2.5.0-dev, Build 2dfcba39** erfolgreich getestet.
Die AppImage-Prüfsumme, der Pluginhash und der tatsächliche Live-/MCP-Bericht stehen
in [host-0.3.0.json](evidence/host-0.3.0.json). Dieser Nachweis gilt für den
aufgezeichneten Build; die Plugin-API bleibt experimentell. Der separate Server
bestand 43 Tests in allen sechs OS-/Python-Konfigurationen.
