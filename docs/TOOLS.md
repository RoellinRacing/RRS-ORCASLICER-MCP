# MCP-Werkzeuge

| Werkzeug | Zweck |
| --- | --- |
| `orca_capabilities(refresh)` | Engine, vollständiger Hilfetext, CLI-Flags, Version aus Hilfetext, Desktopstatus |
| `workspace_list(directory, offset, limit)` | Dateien und Ordner finden |
| `artifact_read(path, offset_bytes, limit_bytes)` | G-Code, Statistik und Protokolle stückweise lesen |
| `settings_catalog(query, offset, limit)` | Definitionen des dokumentierten Source-Snapshots suchen |
| `settings_read(path)` | JSON und SHA256 lesen |
| `settings_write(path, changes, expected_sha256, remove)` | Beliebige Werte setzen/entfernen; Sicherung und Revisionsschutz |
| `profiles_list(directory, query, offset, limit)` | Profilordner rekursiv durchsuchen |
| `profile_resolve(path, search_directories)` | Elternprofile zusammenführen |
| `project_inspect(path, metadata_member)` | 3MF-Inhalt und ausgewählte JSON/XML-Metadaten lesen |
| `project_settings_write(source, destination, changes, expected_source_sha256, remove)` | Globale Settings in neuer 3MF |
| `project_metadata_write(source, destination, metadata_member, text, expected_source_sha256)` | Vorhandene Objekt-/Platten- oder andere JSON/XML-Metadaten in neuer 3MF ersetzen |
| `cli_run(arguments, timeout_seconds)` | Alle angebotenen langen CLI-Optionen; eigene Reihenfolge bleibt erhalten |
| `slice_project(inputs, output_directory, plate, settings, filaments, export_3mf, timeout_seconds)` | Komfortaufruf für Slicing |
| `job_status(job_id, log_tail_bytes)` | Persistierter Status, Exitcode, Log und Dateien im Jobordner |
| `jobs_list(limit)` | Letzte Aufträge einschliesslich unterbrochener Arbeiten |
| `job_cancel(job_id)` | Wartenden/aktiven Auftrag samt Prozessbaum beenden |
| `desktop_launch(project)` | Lokale Oberfläche starten |
| `desktop_focus()` | Ein vorhandenes Orca-Fenster fokussieren |
| `desktop_screenshot()` | PNG des aktuellen Desktops bei aktivem Orca-Fenster |
| `desktop_action(action, x, y, text, keys, amount)` | Sichtbare Oberfläche bedienen |

CLI-Argumente müssen als einzelne Elemente einer JSON-Liste übergeben werden;
keine Shell-Anführungszeichen um Pfade setzen. Keine Shellkommandos anhängen.
Werte negativer Zahlen sind erlaubt. Kurze Optionsaliasnamen werden bewusst
abgewiesen; die lange Schreibweise steht in `orca_capabilities.cli.help`.

Beispiel einer Modelltransformation (nur wenn alle Flags angeboten werden):

```json
{
  "arguments": [
    "--scale", "1.2", "--rotate", "90",
    "--outputdir", "/home/user/OrcaMCP/output",
    "--export-3mf", "transformed.3mf",
    "/home/user/OrcaMCP/input.stl"
  ]
}
```

Bei Orca 2.4.2 heisst die Z-Drehung **`--rotate`**. Immer die Laufzeithilfe lesen.

Desktopaktionen: `click`, `double_click`, `right_click`, `move`, `drag`, `scroll`,
`keys`, `text`. Für Drag zuerst `move` zum Startpunkt, dann `drag` zum Ziel.
`keys` enthält PyAutoGUI-Namen wie `["ctrl", "o"]`, `text` wird per Zwischenablage
mit Unicode eingefügt. `amount` ist die Scrollanzahl von -100 bis 100.
Maus in die obere linke Ecke bewegen löst PyAutoGUIs Notabbruch aus.

## Ergänzungen in 0.2.0

| Werkzeug | Zweck |
| --- | --- |
| `feature_coverage()` | Tatsächliche Funktionsfamilien und offene GUI-/API-Lücken |
| `settings_compare(left_path, right_path)` | Zusätzliche, entfernte und geänderte JSON-Werte |
| `settings_validate(values)` | Unverbindliche Quellkatalog-Vorprüfung; kein Engine-Nachweis |
| `profile_export(source, destination, name, search_directories)` | Neues, vollständig aufgelöstes Benutzerprofil |
| `project_objects_read(path)` | Objekte, Teile, Platten, IDs und Instanzzuweisungen |
| `project_target_settings_write(source, destination, target, target_id, changes, expected_source_sha256, remove, part_id)` | Objekt-, Teil- oder Plattensettings gezielt ändern |
| `gcode_analyze(path)` | Deklarierte Zeit/Materialwerte, Schichten und Temperaturkommandos |
| `batch_slice(inputs, output_directory, idempotency_key, plate, settings, filaments, timeout_seconds)` | Bis zu 64 Eingaben unabhängig slicen |
| `batch_status(batch_id)` | Gesamtzustand und Einzeljobs lesen |
| `batch_cancel(batch_id)` | Offene Batch-Jobs beenden, Erfolge erhalten |

Objekt-/Plattensettings verwenden `target: "object"` oder `"plate"` und die IDs aus
`project_objects_read`. Werte werden als Orcas serialisierte Strings übergeben,
z. B. `{"wall_loops":"4"}`. Für eine Teileinstellung zusätzlich `part_id` angeben.
Der Zielpfad muss neu sein; das Ergebnis muss erneut geslicet werden.

Beispiel für einen wiederholbar beauftragbaren Stapel:

```json
{
  "inputs": ["C:\\OrcaMCP\\teil-a.3mf", "C:\\OrcaMCP\\teil-b.3mf"],
  "output_directory": "C:\\OrcaMCP\\batch-output",
  "idempotency_key": "auftrag-2026-10-26-erster-versuch"
}
```

Derselbe Schlüssel ist für denselben Auftrag zu behalten, auch nach einem
Verbindungsabbruch. Ein bewusst neuer Versuch nach einem fehlgeschlagenen oder
abgebrochenen Job braucht einen neuen Schlüssel. Der Status eines abgeschlossenen
Jobs ist kein Nachweis dafür, dass jemand seine Ausgabedatei nicht später gelöscht
hat; die Dateien können über `workspace_list` und `gcode_analyze` überprüft werden.

## Offizielle Host-Brücke (0.3.0)

Die zusätzlichen neun Werkzeuge sind in [HOST_BRIDGE.md](HOST_BRIDGE.md) beschrieben:
`host_bridge_status`, `host_plugin_export`, `host_snapshot`, `host_model_read`,
`host_presets_list`, `host_preset_read`, `host_preset_update`, `host_project_export`
und `host_request_status`.

Vor Mutationen `host_bridge_status` lesen. Mit der zurückgegebenen `session_id`
und einer eigenen UUID-Hex-ID (`request_id`, 32 kleine Hex-Zeichen) beauftragen.
Bei `outcome_unknown` dieselben IDs über `host_request_status` prüfen; keinen
neuen Änderungsauftrag als vermeintlich sicheren Retry erfinden. Erfolg liegt
nur bei `status: succeeded` vor. Native Dialoge können eine lokale Antwort benötigen.
