> **Neu in 0.5.0: 61 MCP-Werkzeuge.** Gezielte Live-Transformationen mit nativer
> Undo-/Redo-Historie, editierbarer Text/Embossing und originale Kalibrierungsgeneratoren
> über Orcas sichtbare Bedienoberfläche. Der Server bleibt separat und Orca unverändert.
> [Paket](https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.5.0)
> · [Einrichtung, Umfang und Grenzen](docs/NATIVE_WORKFLOWS.md). Der erste Selector-Pack
> benötigt englische Oberfläche, Standardkürzel, Tesseract und den Desktop-Opt-in.

# RRS-ORCASLICER-MCP

Separate MCP-Schnittstelle für **OrcaSlicer**. OrcaSlicer bleibt unverändert installiert;
der Server läuft daneben auf demselben Computer. Windows, macOS und Linux werden
auf Python-Ebene unterstützt. Der echte Slicing-Nachweis dieser Veröffentlichung
wurde mit der offiziellen **Linux-Version 2.4.2** durchgeführt. Das optionale
Host-Plugin und die nativen Abläufe werden in der offiziellen Linux-Nightly geprüft;
den exakten Build und die Ergebnisse enthält `docs/evidence/host-0.5.0.json` im Paket.

## Neu in 0.3.0: Plugin für Orcas offiziellen Python-Host

39 MCP-Werkzeuge. Das optionale `rrs_orcaslicer_bridge.py` verbindet den externen
Server über Orcas offizielles Python-Plugin-System mit der laufenden Anwendung:
Live-Presets lesen/ändern, Modellinformationen lesen und ungespeicherte Projekte
als neue 3MF-Kopie exportieren. Presetänderungen gehen durch Orcas native
Transaktionen und bleiben bis zum normalen Speichern ungespeichert.

Das Plugin wird separat installiert und über **Plugins > Run** gestartet. Der
Server bleibt eigenständig; ältere Orca-Versionen können die bisherigen CLI-/Datei-
Werkzeuge weiter verwenden. Das eingebettete Plugin braucht eine kompatible
2.5-Entwicklungsversion. Die Anzeige `host_bridge_status` meldet die verfügbare API.
Eine vollständige Steuerung von Bemalung, Kalibrierung oder Geräten wird dadurch
nicht behauptet.

[Installation und Protokoll](docs/HOST_BRIDGE.md) ·
[Code-/Businesslogik-Prüfung für Maintainer](docs/MAINTAINER_REVIEW.md) ·
[Funktionsabdeckung](docs/FEATURE_COVERAGE.md)

## Neu in 0.2.0

30 MCP-Werkzeuge: direkte Objekt-/Teil-/Platteneinstellungen, Profilvergleich und
Vorprüfung, unabhängiger Profilexport, G-Code-Zusammenfassungen sowie Stapel-Slicing
mit Wiederholungsschutz und Abbruch. Die bestehende 0.1.1-Anbindung bleibt erhalten.

**Noch keine vollständige API für jede Orca-Funktion.** Die tatsächliche Abdeckung,
GUI-Funktionen und noch nicht integrierten Funktionen sind in
[FEATURE_COVERAGE.md](docs/FEATURE_COVERAGE.md) und per `feature_coverage` ausgewiesen.
Der vorbereitete [Kontakt zum OrcaSlicer-Team](docs/UPSTREAM_CONTACT.md) nennt die
passende offizielle Plugin-Diskussion. Dort wurde noch nichts gepostet.

## Was lässt sich steuern?

| Bereich | Unterstützung |
| --- | --- |
| Kommandozeile | Alle von der installierten Version in `--help` angebotenen langen Optionen über `cli_run`, in vorgegebener Reihenfolge |
| Slicing | Ein oder mehrere Modelle/Projekte, Plattenauswahl, Maschinen-/Prozess-/Filamentprofile, G-Code und 3MF |
| Modelloperationen | Alle verfügbaren CLI-Transformationen, z. B. Skalieren, Drehen, Anordnen, Kopien, Ausrichten und Export |
| Einstellungen | Beliebige JSON-Schlüssel und Werte; neue/unbekannte Schlüssel werden erhalten |
| Profile | Drucker, Filamente, Prozesse, Vererbung, Suche, gesicherte Änderungen |
| 3MF | Projektsettings sowie vorhandene JSON/XML-Metadaten für Objekte und Platten; Modelle, Bemalung und unbekannte Inhalte bleiben erhalten; alte Slicing-Caches werden entfernt |
| Live-Host | Optionales Script-Plugin: Presets lesen/ändern, Modell abfragen, Projektkopie exportieren |
| Native Abläufe (0.5.0) | Live-Verschieben/Drehen/Skalieren, Undo/Redo, editierbarer Text und neun Kalibrierungsgenerator-Familien; geprüfte Umgebung und Varianten im Paketnachweis |
| Oberfläche | Optional: Starten, Fokussieren, Screenshot, Maus, Tastatur und Unicode-Texteingabe |
| Aufträge | Warteschlange, Protokoll, Status, Zeitlimit, Prozessabbruch, Zustand nach Neustart |

**Grenze:** OrcaSlicer stellt keine vollständige externe API für sämtliche GUI-Funktionen
bereit. Die typisierten nativen Abläufe und ihre Ergebnisprüfung stehen in
[NATIVE_WORKFLOWS.md](docs/NATIVE_WORKFLOWS.md). Der optionale allgemeine Desktopzugriff
auf weitere Oberflächenfunktionen wie Live-Bemalung und manuelle Stützen hat keinen
vergleichbaren automatisierten Funktionsnachweis. Die nativen Tests gelten für die
aufgezeichnete Linux-X11-/Orca-Version und den englischen Selector-Pack.
Drucker-Anmeldung, Netzwerktreiber und Cloudfunktionen bleiben Sache von OrcaSlicer.
Erfolgreiches Slicing startet keinen physischen Druck.

Eine Garantie für jede vergangene oder zukünftige Orca-Version ist technisch nicht
möglich. Die Schnittstelle erkennt CLI-Fähigkeiten zur Laufzeit, erhält unbekannte
Daten und verweigert nicht angebotene Optionen. Die 966 Katalogdefinitionen stammen
aus einem dokumentierten Quellstand, nicht aus einer pauschalen Versionsgarantie.
Siehe [Kompatibilität](docs/COMPATIBILITY.md).

## Schnellinstallation

Voraussetzungen: Python **3.11 oder neuer** und eine separat installierte offizielle
OrcaSlicer-Version. Releasepaket entpacken oder Repository klonen.

### Windows

In PowerShell im entpackten Ordner:

```powershell
.\scripts\Install-Windows.ps1 -OrcaBin 'C:\Program Files\OrcaSlicer\orca-slicer.exe' -Workspace 'C:\OrcaMCP' -Desktop
```

Das Skript erstellt eine eigene Python-Umgebung und `mcp-config.json`. Ohne `-Desktop`
wird nur die CLI-/Dateianbindung installiert. Alternativ:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install '.[desktop]'
.\.venv\Scripts\python.exe scripts\make_config.py --binary 'C:\Program Files\OrcaSlicer\orca-slicer.exe' --root 'C:\OrcaMCP' --desktop
```

### macOS / Linux

```bash
bash scripts/install.sh
.venv/bin/python scripts/make_config.py \
  --binary /Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer \
  --root "$HOME/OrcaMCP"
```

Unter Linux als `--binary` den Pfad zur AppImage-Datei oder zum installierten
`orca-slicer` angeben. Für Desktopsteuerung zuerst `pip install '.[desktop]'`
innerhalb der Umgebung ausführen und `--desktop` ergänzen. Linux benötigt X11,
`xdotool`, ein Screenshot-Backend und eine Zwischenablage (z. B. `xclip`). Wayland
wird für Desktopaktionen nicht unterstützt. macOS benötigt Bedienungshilfen- und
Bildschirmaufnahmeberechtigungen; Windows einen entsperrten Benutzerdesktop.

### MCP-Client verbinden

Den Inhalt von `mcp-config.json` in einen MCP-Client mit **lokalem stdio-Support**
übernehmen, z. B. Claude Desktop, Claude Code oder einen passenden lokalen Agenten.
Ein Beispiel:

```json
{
  "mcpServers": {
    "rrs-orcaslicer": {
      "command": "C:\\OrcaMCP\\RRS-ORCASLICER-MCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "rrs_orcaslicer_mcp.server"],
      "env": {
        "ORCA_SLICER_BIN": "C:\\Program Files\\OrcaSlicer\\orca-slicer.exe",
        "ORCA_MCP_ROOTS": "C:\\OrcaMCP",
        "ORCA_MCP_STATE": "C:\\OrcaMCP\\state",
        "ORCA_MCP_DESKTOP": "0"
      }
    }
  }
}
```

Dies ist ein lokaler Server, kein direkt aus der ChatGPT-Weboberfläche erreichbarer
HTTPS-Connector. Ein solcher benötigt zusätzlich einen gesonderten, authentifizierten
Gateway; dieser ist nicht Teil dieses Pakets.

Weitere Ordner mit `make_config.py --root` ergänzen, z. B. Orcas Benutzerprofile und
`resources/profiles`. Ordnerlisten in `ORCA_MCP_ROOTS` sind unter Windows durch `;`,
unter macOS/Linux durch `:` getrennt. Der erste Ordner ist die Basis relativer
Dateipfade. `ORCA_MCP_STATE` muss pro gleichzeitigem Server verschieden sein.

## Erste Verwendung

1. `orca_capabilities` aufrufen: ausführbare Datei, verfügbare CLI-Optionen und Desktopstatus prüfen.
2. Mit `workspace_list`, `profiles_list` und `settings_read` Modelle/Profile auswählen.
3. Ein selbstständiges Orca-3MF verwenden oder vollständige, aufgelöste Profile bereitstellen.
4. `slice_project` starten und mit `job_status` bis zum Endstatus prüfen.
5. G-Code/Statistiken mit `artifact_read` prüfen. Für GUI-Aktionen vorher/nachher Screenshots auswerten.

Beispiel für `slice_project`:

```json
{
  "inputs": ["C:\\OrcaMCP\\teil.3mf"],
  "output_directory": "C:\\OrcaMCP\\output",
  "plate": 0,
  "export_3mf": "teil-gesliced.3mf"
}
```

`export_3mf` ist ein Dateiname innerhalb des Ausgabeordners. `plate: 0` bedeutet
alle Platten. CLI-Aufträge laufen in eigenen Jobordnern; rohe `cli_run`-Aufrufe
benötigen absolute Eingabe-/Profilpfade und müssen Orcas Exportregeln beachten.

Bei Einstellungen die Orca-Darstellung beibehalten: viele Zahlen sind als Strings
gespeichert, Filamentwerte häufig als Listen von Strings. Vor Änderungen lesen;
bestehende JSON-Dateien benötigen den aktuellen SHA256-Wert. Eine Sicherung wird
angelegt. Bei 3MF-Änderungen werden bestehender G-Code und zugehörige Slicing-Caches
entfernt; die neue Datei muss erneut geslicet werden. Laufende Orca-Instanzen können Profile überschreiben: Orca zum Bearbeiten
aktiver Profile schliessen oder eine neue Datei speichern und importieren.
`profile_resolve` löst Werte auf; beim Export eines flachen Profils `inherits`
entfernen. Gleiche Elternnamen in mehreren Suchordnern werden als Konflikt gemeldet.

## Diagnose und Entwicklung

```bash
python -m rrs_orcaslicer_mcp.server --doctor --output doctor.json
python -m pip install -e '.[test]'
python -m pytest -q
python -m ruff check src scripts tests
python scripts/package.py
```

`--doctor` benötigt dieselben Umgebungsvariablen wie der Client. Im stdio-Betrieb
bleibt stdout für MCP reserviert; Diagnose wird nur im separaten Doctor-Modus ausgegeben.

Der Quellkatalog lässt sich jederzeit aus einem separaten offiziellen Checkout
neu erzeugen; es werden keine Orca-Binärdateien in diesem Repository mitgeliefert:

```bash
git clone https://github.com/OrcaSlicer/OrcaSlicer.git ../OrcaSlicer
python scripts/sync_catalog.py ../OrcaSlicer
```

[Businesslogik und Architektur](docs/BUSINESS_LOGIC.md) ·
[Werkzeugreferenz](docs/TOOLS.md) · [Testnachweis](docs/VALIDATION.md) ·
[Arbeitsstand](WORK_STATE.md)

Lizenz: AGPL-3.0-or-later. Unabhängiges Projekt; keine offizielle OrcaSlicer-Erweiterung.
Herkunft des Katalogs und Lizenzhinweise stehen in [NOTICE](NOTICE).
