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

## Erweiterungen in 0.2.0

Objekt-/Teil-/Plattenänderungen adressieren gespeicherte IDs und lehnen fehlende
oder doppelte Ziele ab. Geometrie, Identität und G-Code-Referenzen werden nicht
als gewöhnliche Druckeinstellungen behandelt. Die neue Datei bleibt ein Projekt,
kein bereits fertiger Druckauftrag; alle bisherigen Slicing-Caches werden entfernt.
Das verhindert, dass ein Objektsetting versehentlich ein anderes Objekt verändert
oder noch der alte G-Code gedruckt wird.

Der Profilvergleich vergleicht serialisierte JSON-Werte inklusive verschachtelter
Typunterschiede. Eine flache Kopie erhält die Elternwerte, entfernt `inherits` und
die kopierte System-Setting-ID und wird als neues Benutzerprofil gespeichert.
Die Vorprüfung verwendet nur belegte Typ-/Enum-/Bereichshinweise des Source-Snapshots.
Unbekannte Schlüssel sind keine Fehler. Sie behauptet ausdrücklich keine Prüfung
gegen Orcas installierte Engine oder druckerspezifische Kombinationen.

Stapelaufträge speichern ihr Manifest vor der ersten Ausführung. Aus dem expliziten
Idempotenzschlüssel entstehen die Batch-ID und deterministische Job-IDs. Derselbe
Schlüssel mit denselben Parametern und Dateiinhalten liefert vorhandene Jobs zurück;
abweichende Parameter/Inhalte erzeugen einen Konflikt. Abgebrochene, fehlgeschlagene
oder nach einem Neustart unterbrochene Jobs werden dabei nicht automatisch wiederholt.
Ein absichtlicher neuer Versuch benötigt einen neuen Schlüssel. Fehlende, noch nie
angelegte Jobs eines unvollständig übermittelten Manifests können weiter angelegt
werden. Ein gespeicherter Abbruch verhindert auch das.

Jedes Eingabemodell bekommt einen eigenen Ausgabeordner unter der Batch-ID. Diese
Ordner werden rekursiv angelegt, weil Orcas CLI nicht alle Elternordner selbst
anlegt. Hashes der jeweils benötigten Modelle/Profile werden direkt vor dem Start
überprüft. Ändert ein Benutzer eine Datei während der Wartezeit, schlägt der Job
explizit fehl, statt still andere Einstellungen zu slicen. Bei einem Batch-Abbruch
bleiben bereits erfolgreiche Jobs und deren Dateien erhalten.

Die G-Code-Auswertung liest eine Textdatei im Stream. Sie gibt deklarierte Zeit-
und Materialwerte, Schichtmarker, ausgewählte Settings sowie explizite Temperatur-
kommandos aus. Kommentare mit hinterlegtem Startcode werden nicht als ausgeführte
Kommandos gezählt. Die Auswertung simuliert weder Firmware noch bedingte Makros
und ist kein Sicherheitsurteil über einen realen Druck.

Die Coverage-Ausgabe unterscheidet Funktionsfamilien statt eine erfundene
Vollständigkeitsquote auszugeben. Offizielle experimentelle Host-APIs gelten erst
nach echter Integration und Tests als unterstützt; ihre Existenz allein genügt nicht.

## Offizielle Host-Brücke

Die externe MCP-Anwendung bleibt eigenständig; ein optionales offizielles Script-
Plugin verbindet sie mit dem laufenden Orca. Das ist nötig, weil Dateibearbeitung
keine ungespeicherten Live-Presets oder In-Memory-Modelle erfasst und neue Orca-Builds
Systemprofile intern anders speichern können. Die Brücke nutzt die offiziellen
APIs, statt deren Cacheformat oder private C++-Details nachzubauen.

Modell-/Presetabfragen und Projektkopien laufen in GUI-Callbacks. Mutationen
laufen auf dem Script-Worker über `begin_update`/`set`/`commit`. Dadurch bleiben
Orcas Validierung und normale Dialoge zuständig. Ein Commit speichert das Preset
nicht automatisch. Filamentslots können dasselbe Preset teilen; das wird im
Ergebnis sichtbar gemacht. Native Handles werden nicht über Threads oder Requests
hinweg gespeichert.

Der lokale Dateitransport öffnet keinen Port und benötigt keine zusätzlichen
Python-Pakete im eingebetteten Interpreter. Er beschränkt sich auf benannte
Operationen. Sitzungs- und Request-ID, Token, Fingerprint, Ablaufzeit und dauerhafte
Quittungen verhindern unbeabsichtigte Wiederholung. Nach einem Timeout gilt der
Ausgang als unklar, bis Quittung oder Anwendung geprüft wurden. Ein Absturz zwischen
nativem Effekt und Quittung bleibt technisch unentscheidbar; dafür gibt es keine
falsche Exactly-once-Garantie. Gestartete native Dialogentscheidungen werden nicht
von einem Client-Timeout rückgängig gemacht.

Details, Betrieb, Wiederaufnahme und Threadregeln stehen in HOST_BRIDGE.md;
MAINTAINER_REVIEW.md beschreibt die geprüften Codegrenzen und verbleibenden Risiken
für die spätere sachliche Vorstellung beim OrcaSlicer-Team.

### Importierbare Benutzerprofile

`profile_export` benötigt einen nativen Profiltyp und gültige Versionsmetadaten.
Eine vorhandene Version wird übernommen; fehlt sie im Herstellerprofil, muss der
Aufrufer `profile_version` angeben. Der Server erfindet keine Hostversion. Ungültige
Metadaten erzeugen keine Datei. Dies behebt einen im echten GUI-Test gefundenen
Unterschied zwischen akzeptierten CLI-Einstellungen und importierbaren Profilen.

Datei-Recovery führt keine native Mutation erneut aus. Kurz blockierte atomare
Dateiwechsel unter Windows werden begrenzt wiederholt. Scheitert das Speichern der
Erfolgsquittung nach einer angewendeten Änderung, bleibt das Ergebnis unklar und
das gestartete Journal erhalten; es wird keine falsche Fehlerquittung erzeugt.

## Revision-bound project geometry and facet painting

3MF build/component transforms are explicit 12-number row-vector matrices in the
model's declared unit. Replace (do not silently compose) a transform after reading
its current value and the source SHA256. A component edit affects every instance
referencing it. Reflections are valid, singular/nonfinite transforms are rejected.
No topology or triangle order changes, so existing facet trees stay meaningful.

Painting targets a mesh by archive member + object ID + 0-based triangle index.
Support/seam/fuzzy states are the native enum (0 none, 1/2 per upstream enum);
material states are explicit filament slots, conservatively capped at 16 for older
readers. Subtriangle masks are parsed as reversed-nibble trees with validated node
arity and state bounds, rather than accepted as arbitrary hex. Clearing one channel
preserves every other channel and unknown triangle attribute. Shared meshes change
for every referring component. Slot existence is an engine/profile validation,
not proven by archive syntax checks.

Edits always produce a new .3mf. They check the source checksum before publication,
reject ambiguous ZIP members, retain opaque payloads, and remove cached slicing
outputs/references. New files must be reopened and resliced; they do not mutate the
running GUI or its undo stack. Native import validation is separate evidence.

## Live model details, printer state and slicing events

Detailed reads bind an index to the object ID previously returned by model.read;
reordered/replaced objects reject stale identities. Instance/volume poses are
copied on the GUI callback, rotations in radians and offsets in millimeters.
Selected-printer reads expose only upstream's redacted diagnostic snapshot.

The optional synchronous SlicingPipeline observer copies stage name, version,
cancellation state and object ID while ctx is valid. It never retains native
handles or accesses GUI/files/network from a slicing worker. A locked 512-event
ring bounds memory; sequence/epoch and a gap flag expose loss/reload. Observation
requires the capability to be enabled and selected in slicing_pipeline_plugin.
These stages are not percentages, successful exports or physical print evidence.

## Independent geometry, calibration and printer providers

See EXTENDED_OPERATIONS.md for input units and supported contracts. Topology edits
operate on explicit checksum-bound STL/PLY snapshots with optional trimesh/manifold
engines, checkpoint intent before computation and measure serialized outputs. These
new STLs intentionally do not inherit project settings/painting. No pointer writes
or unreviewed eval are used to bypass Orca's read-only native model binding.

Calibration is a recoverable controlled parameter sweep from a supplied test model,
not an automatic quality judgment. Baseline settings for all filament slots must
exist; only the chosen slot changes, and PA also enables its matching slot. A series
is bound to input checksum/parameters. Completed outputs are checked before reuse.

Printer commands use only administrator-configured URLs and named secret env vars.
An upload never starts a print. Print commands are separate explicit operations;
HTTP acknowledgements do not prove device execution. Durable exclusive request-ID
reservation prevents concurrent/restarted clients from dispatching the same ID
twice. Transport uncertainty is retained, not automatically retried. This trades
availability for avoiding duplicate physical actions. Cloud/AMS is an explicit gap.

## Typed native GUI workflows (0.5.0)

The inherited spiral prompt can resize/recenter after its first visible frame.
Observation retries reacquire its bounds and exact title before verifying both
body anchors; they never repeat input. A crop from the initial frame must not
authorize a click after the native window has moved.

See NATIVE_WORKFLOWS.md. The stock host bindings are read-only, so native actions
are driven through Orca's own visible controls, not undocumented native memory.
The adapter requires opt-in desktop control, foreground English Prepare UI,
current bridge session, an observed scene revision and a durable request ID.
Observed revisions cover copied identities, poses, bounds, facet counts and exposed
settings; they are explicitly not cryptographic full mesh hashes. Float noise is
normalized only for this revision, not the native model.

Transforms set one native gizmo axis and verify the corresponding native pose.
Move is relative millimeters, rotation relative degrees (other rotation axes must
be zero), scale is target percent with Orca's existing uniform-lock behavior.
The initial supported selection has one object/instance. Undo/Redo invokes Orca's
actual history and reports explicit steps, rather than restoring an exported file.
A workflow can create multiple native history entries.

Text uses the original emboss gizmo and verifies editable text, height and depth
in native-exported 3MF metadata. Calibration invokes native dialogs/generators;
backup and explicit scene replacement are required, and no print action occurs.
Scene-replacing operations first export the unsaved project. A missing control,
unexpected dialog/readback or partial native action remains indeterminate and is
never automatically replayed. The exclusive external journal precedes input and
retains screenshot/phase/result evidence. Platform/locale/layout acceptance must
be stated separately from pure Python tests.

### Selected native calibration values

GTK highlights focused values as white on blue. Numeric OCR must preserve glyph
holes and decimal points while removing field borders; connected highlight
components read the immutable screenshot, never a partly normalized image. Read
only the row identified by an exact field label, rather than accepting a tall OCR
word spanning two native fields. Exact numeric readback remains mandatory before
generation. Missing flow-ratio heading may use the single group above Settings
only with exact active title `Flow Ratio Calibration`, and still requires one
exact matching choice. These are observation fallbacks, never input retries.

Decimal values receive an additional cropped glyph read, retaining decimal points
that whole-row OCR can omit. Readback may observe up to three rendered frames;
these waits never re-click, retype or re-run a native operation. A mismatch still
fails the operation before generation. Full-height border removal cannot erase a
partially occupied column, which could otherwise remove a decimal point itself.

### Native calibration transitions

Max-volumetric-speed generation enables spiral mode in Orca's edited process.
Loading the flat flow-ratio coupon project while transferring those edits can open
Orca's spiral consistency prompt. For flow_ratio only, require its exact native
info-dialog title plus both spiral-mode and cancel-enabling explanation anchors,
then select No in the bottom button row. Upstream ConfigManipulation.cpp confirms
No clears only spiral_mode; Yes would also change wall/infill/support/timelapse
settings. The original project is already backed up. The receipt records this
specific adjustment. Other unknown dialogs still fail closed, and export requires
the actual Prepare MainFrame so a modal-blocked empty project cannot be accepted.
Grey secondary-button rectangles receive cropped black-text OCR; geometry/color
alone never authorizes a click. Thin grey separator lines cannot join buttons.
The isolated GUI fixture waits for Filament/Process/Quality before moving/clicking
the real MainFrame, avoiding interaction with a startup/splash frame.

Grey fallback is restricted to the exact spiral-info No route with its narrow
55-pixel button row. All primary calibration OK buttons retain teal-only fallback.
Two-dimensional connected components identify actual buttons; unrelated grey panels,
thin borders and separate radio marks above a button cannot merge into its bounds.
Six actual primary-dialog screenshots and the separate spiral No screenshot are
replayed without input; the synthetic regression includes a grey panel and a radio
mark directly above a primary button.
