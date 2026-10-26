# Businesslogik und technische Entscheidungen

## Zweck

Ein lokaler Agent soll dieselbe installierte OrcaSlicer-Version verwenden, die der
Benutzer auch manuell nutzt. Einstellungen, Modellaufbereitung und Druckdateien
sollen nicht von einem eingebetteten, veralteten Slicer oder einem gepflegten Fork
abhängen. Die Schnittstelle ist deshalb ein eigenständiger Python-Prozess.

## Regeln und Gründe

| Regel | Grund | Umsetzung |
| --- | --- | --- |
| Installierte Fähigkeiten bestimmen die CLI | Versionen haben verschiedene Funktionen; erfundene Flags sind kein Ersatz | `engine.py`: echtes `--help`, Prüfung langer Flags vor jedem Auftrag |
| Unbekannte Einstellungsfelder bleiben erhalten | Neue Orca-Versionen und Hersteller erweitern Profile | `storage.py`: JSON-Zusammenführung ohne Schlüssel-Allowlist |
| Katalog ist Hilfe, nicht abschliessende Validierung | C++-Bedingungen, Migrationen und dynamische Enum-Tabellen lassen sich nicht vollständig statisch spiegeln | `catalog.py`, `sync_catalog.py`; Herkunft mit Commit-ID |
| Keine automatischen Standardwerte für einen unbekannten Drucker | Unpassende Startcodes/Temperaturen oder Bettmasse können reale Schäden verursachen | Selbstständiges 3MF oder explizite vollständige Profile erforderlich |
| Vorhandene Dateien nur mit passender Revision ändern | Agenten oder Benutzer können zwischen Lesen und Schreiben Änderungen vornehmen | SHA256-Vergleich, atomarer JSON-Austausch, inhaltsbezogene `.bak`-Datei |
| 3MF immer in eine neue Datei schreiben | Originalmodelle, Supportbemalung und Herstellerdaten sind wertvoll | `projects.py`: Geometrie/Bemalung und unbekannte Mitglieder erhalten; alte Slicing-Caches und deren Verweise entfernen; neues Archiv |
| XML/JSON-Metadaten dürfen direkt ersetzt werden | Objekt-/Platteneinstellungen sind nicht alle globale JSON-Felder | Syntaxprüfung; semantische Prüfung durch Orca beim Öffnen |
| Ein Slicing-Auftrag gleichzeitig | Slicing benötigt viel RAM; parallele Prozesse können den Rechner überlasten | Semaphore und explizite Warteschlange |
| Aufträge überleben als Statusdaten | Ein Agent darf nach einer Unterbrechung nicht behaupten, die Arbeit sei erledigt | Dauerhafte `job.json`, Log, Endstatus `interrupted`; keine automatische Wiederholung |
| Ein Prozess schreibt in einen Jobordner | Zwei Server dürfen laufende Aufträge nicht gegenseitig als unterbrochen markieren | Betriebssystem-Dateisperre pro State-Verzeichnis |
| CLI läuft ohne Shell | Pfade, G-Code-Ausdrücke und Modellnamen dürfen keine Shellkommandos werden | argv-Liste, Prozessgruppe, Timeout und Abbruch des Prozessbaums |
| GUI benötigt gesonderte Aktivierung | Der Adapter bewegt Maus/Tastatur auf dem lokalen Desktop | `ORCA_MCP_DESKTOP=1`, Vordergrundfensterprüfung, Screenshot vor/nach Aktionen |
| Keine GUI-Positionen hart codieren | Theme, Sprache, DPI und Orca-Version ändern das Layout | Visuelle Werkzeuge statt fragiler fester Menü-Makros |
| Kein physischer Druck beim Slicing | Die Erstellung einer Datei ist keine Druckfreigabe | Keine versteckten Netzwerk-/Druckaufrufe; explizite Desktopinteraktion nötig |

## Datenfluss

Ein MCP-Client startet den Server über stdio. `orca_capabilities` prüft die externe
Installation. `slice_project` baut überprüfbare Argumente; `cli_run` erlaubt sämtliche
angebotenen langen Optionen in der Reihenfolge des Aufrufers. `Engine` speichert den
Auftrag vor der Ausführung. Ein Worker startet Orca, liest das kombinierte Protokoll
und speichert Endstatus und Exitcode. Die Logdatei ist auf rund 10 MiB begrenzt; der
Prozessausgang wird weiter geleert, damit Orca nicht wegen einer vollen Pipe blockiert.

`slice_project` sendet für 3MF-Exporte nur den Dateinamen: Orca 2.4.2 setzt
`outputdir` und `export-3mf` selbst zusammen und behandelt einen absoluten Exportpfad
dabei nicht korrekt. Profile werden mit Orcas Semikolon-Syntax übergeben; solche
Dateinamen mit Semikolon lehnt der Wrapper ab. Rohe CLI-Aufrufe bleiben unverändert.

Die Dateiwerkzeuge prüfen aufgelöste Pfade inklusive symbolischer Links gegen die
konfigurierten Wurzeln. Diese Prüfung ist **keine Betriebssystem-Sandbox**: Orca
selbst läuft mit den Rechten des Benutzers, kann G-Code-Dateien schreiben und über
eigene Optionen weitere Pfade verwenden. Der stdio-Client und seine Agenten müssen
vertrauenswürdig sein. Es wird kein öffentlicher Netzwerkport geöffnet.

## Wiederaufnahme und Grenzen

Bei regulärem Serverende werden aktive und wartende Jobs abgebrochen. Nach einem
harten Prozessabbruch wird ein unvollständiger Zustand beim nächsten Start als
`interrupted` markiert. Ein vom Betriebssystem nicht mitbeendeter Orca-Prozess kann
weiterlaufen; deshalb vor erneutem Start dessen PID und die vorhandenen Ergebnisse
prüfen. Wiederholung erzeugt einen neuen Auftrag und geschieht nicht automatisch.

JSON-Einstellungen werden nur auf Dokumentebene zusammengeführt; verschachtelte
Objekte/Listen ersetzt der Aufrufer vollständig. Profilvererbung folgt dem
`inherits`-Namen und lehnt fehlende, doppelte oder zyklische Eltern ab. Hersteller-
und Versionsmigrationen bleiben Orcas Aufgabe. XML-Metadaten werden nicht in eine
angeblich versionsunabhängige Objektstruktur umgeschrieben.

Desktopaktionen beweisen nur, dass die Eingabe ausgeführt wurde. Ob ein Werkzeug
seinen Zweck erfüllt hat, muss am neuen Screenshot oder an der erzeugten Datei
überprüft werden. GUI, Cloudanmeldung, physische Drucker und alle alten Orca-Versionen
sind nicht durch den Linux-Slicing-Test abgenommen.
