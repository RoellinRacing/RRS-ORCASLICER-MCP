> **Abgeschlossen (2026-10-26):** v0.5.1 veröffentlicht — https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/releases/tag/v0.5.1
> Quellcommit `6c85555`, CI https://github.com/RoellinRacing/RRS-ORCASLICER-MCP/actions/runs/40397479271 (19/19). Ergebnis und Nachweise: WORK_STATE.md,
> docs/VALIDATION.md, docs/evidence/*-0.5.1.*. Dieser Auftrag ist erledigt.

# Claude: OrcaSlicer MCP 0.5.1 abschliessen und abnehmen

## Auftrag und Ausgangspunkt

Dani übergibt dir den Abschluss und die Abnahme. Repository:
https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
Branch: `feat/resumable-slice-jobs`. Den aktuellen öffentlichen Branch klonen und
dessen HEAD verwenden. Dani hat den öffentlichen Upload ausdrücklich genehmigt.
Die Veröffentlichung erfolgt über die GitHub-API, weil der lokale Git-CLI-Zugang
keine Anmeldedaten hat. Der öffentliche Sicherungscommit kann deshalb von den
lokalen Commit-IDs abweichen; der vollständige Dateibaum wird auf Gleichheit geprüft.
Das frühere lokale ZIP mit Bundle ist optional; für die Abnahme genügt dieser
Branch. Keine alte Bundle-Upload-Sperre als aktuellen Blocker behandeln.
Lokale Provenienz: Implementierung `53335cd`; Paket-/Wheelnachweise `8ad1859`.
Basis auf main: `31b95c8`; veröffentlichtes stabiles Release: `v0.5.0`.

Lies zuerst WORK_STATE.md, dieses Dokument, docs/RESUMABLE_JOBS.md,
docs/BUSINESS_LOGIC.md und docs/VALIDATION.md. Prüfe den tatsächlichen aktuellen
Repository-/CI-Stand; ältere gescheiterte GUI-Piloten sind historische Nachweise.
Keine bereits erfolgreiche Untersuchung ohne durch Änderungen begründeten Bedarf
wiederholen. Du sollst die offenen Arbeiten ausführen, nicht nur einen Plan liefern.

## Was implementiert und lokal geprüft ist

0.5.1 bietet 63 MCP-Werkzeuge. slice_project erhält einen optionalen
idempotency_key, gebunden an Argumente, Timeout und SHA256 aller Modelle und
expliziten Profile. Wiederholungen liefern denselben gespeicherten Auftrag;
geänderte Daten verursachen einen Konflikt. Ohne Key bleibt jeder Aufruf neu.
Queued-Eingaben werden vor Prozessstart erneut geprüft. Die Engine serialisiert
Lookup/Capability-Probe/Quittungserzeugung, damit konkurrierende identische
Einreichungen nicht doppelt rechnen.

job_log liest begrenzte Logbereiche mit fortsetzbarem Byte-Cursor und UTF-8-
Grenzbehandlung. job_wait beobachtet bis 30 Sekunden; Timeout oder Abbruch nur
dieser Abfrage cancelt nicht die Berechnung. Ein tatsächliches Serverende beendet
seine Prozesse weiterhin. Nach hartem Neustart werden offene Jobs interrupted;
keine automatische Wiederholung. Logs sind exakt auf 10 MiB begrenzt, während die
Kindprozessausgabe weiter geleert wird.

103 Tests bestehen lokal und separat gegen das installierte Wheel; dessen
Importpfad wurde geprüft. Ruff, Plugin-Generierungsvergleich und Diff-Prüfung
bestehen. Alle vier lokalen Paketchecksummen stimmen; alle 26 Modul-/Datendateien
im Wheel stimmen mit Source überein. 63 Tools sind im Wheel registriert. Nachweise:
- docs/evidence/unit-0.5.1.txt
- docs/evidence/resumable-jobs-0.5.1.txt
- docs/evidence/wheel-local-0.5.1.txt
- docs/evidence/package-local-0.5.1.json
- docs/evidence/tool-inventory-local-0.5.1.json

Das sind lokale Kandidatennachweise, keine öffentliche 0.5.1-Abnahme.
Die lokale ZIP ist reproduzierbar mit scripts/package.py; dist/ ist kein
versionierter Release. Prüfsummen in package-local-0.5.1.json beziehen sich genau
auf diesen damaligen lokalen Build und müssen nicht einem späteren Build gleichen.

## Deine Abschlussarbeiten

1. Prüfe den tatsächlichen Diff gegen main, Geschäftsregeln und Fehlermodi.
   Insbesondere: parallele gleiche/abweichende Keys, Modell-/Profiländerung,
   queued/running/terminal und Neustart, UTF-8 und Log-Cursor, Timeout/Abbruch der
   Beobachtung versus tatsächlicher Jobabbruch. Behebe reale Befunde mit geeigneten
   Regressionstests. Keine Behauptung einer vollständigen Orca-API hinzufügen.
2. Erstelle einen PR vom Übergabebranch nach main. Pushes nur auf diesem Branch
   lösen in der aktuellen CI keinen normalen Push-Lauf aus; der PR startet die
   vorhandene Pipeline. Prüfe alle tatsächlichen CI-Ergebnisse.
3. Verifiziere das neue scripts/verify_resumable_jobs.py im Smoke-Job mit dem
   echten offiziellen Orca-CLI: zwei gleiche Aufrufe erzeugen genau einen Job,
   echtes G-Code/3MF entsteht, Logs und job_wait funktionieren über MCP-stdio,
   ein neuer Serverprozess liefert denselben fertigen Job ohne Neuberechnung,
   geänderte Parameter werden zurückgewiesen. Berichte werden vor/nach Abschnitten
   gespeichert. Das Skript ist bereits in .github/workflows/ci.yml eingebunden.
4. Bestehe die sechs OS-/Python-Konfigurationen, echtes Slicing und alle nativen
   Abschnitte samt gemeinsamem Durchlauf. Die bisherige native 0.5.0-Abnahme ist
   abgeschlossen: 30 reale Operationen mit Transform/Undo/Redo, drei editierbaren
   Textmodi und neun Generatorfamilien inklusive Max-Flow→Flow-Ratio-Übergang.
   Für 0.5.1 stehen erneute CI/native Abnahme und öffentliche Paketprüfung aus.
   Fehler anhand tatsächlicher Artefakte beheben; Gates nicht abschwächen.
5. Nach erfolgreicher Prüfung zusammenführen. Der main-Push durchläuft dieselben
   Gates; erst danach veröffentlicht die vorhandene Pipeline v0.5.1 automatisch.
   Vorher Versionsdateien/Releasebeschreibung prüfen. Kein bestehendes Release
   überschreiben. Die Übergabe selbst darf kein vorzeitiges Release auslösen.
6. Tatsächlich veröffentlichte ZIP, Wheel, Source und Plugin herunterladen.
   SHA256SUMS und GitHub-Digests prüfen, Paketmodule mit Releasecommit vergleichen,
   Wheel separat installieren, einschlägige Tests und alle 63 Tools über echtes
   stdio prüfen. Aktuelle Abnahme-/Build-/CI-/Paketnachweise versioniert speichern;
   lokale Kandidatennachweise nicht als öffentliche Downloads ausgeben.
7. WORK_STATE.md, VALIDATION.md, Release-/Kompatibilitätsdokumentation und
   Maintainer-Übergabe auf die tatsächlichen Ergebnisse bringen. Abschluss an Dani:
   Release-/Downloadlink, finaler Commit, CI-Link, bestandene Prüfungen und reale
   Grenzen. Bei einem echten externen Blocker exakten Stand und nächsten Schritt
   sichern und offen berichten; nicht mit einer Erfolgsmeldung kaschieren.

## Arbeitsweise und Grenzen

Arbeite in kleinen, wiederaufnehmbaren Abschnitten. Skripte vor aufwendigen Läufen,
tatsächliche Resultate danach sichern. Nach jedem Abschnitt letzten Erfolg,
Dateien und nächsten Schritt dokumentieren; GitHub-Sicherungen mit Commit-ID
bestätigen. Sourcecode immer zusammen mit der fachlichen Businesslogik speichern.

Die Serveranwendung bleibt separat; Orca-Binaries werden nicht verändert. Diese
Erweiterung betrifft CLI-Aufträge und fügt keine native GUI-Slicejob-API hinzu.
Native GUI-Abnahme gilt für Linux X11, Englisch/helles geprüftes Layout und ein
Objekt/eine Instanz bei Transformation/Text. Windows/macOS-GUI, andere Sprachen,
Cloud/AMS/MMU und sämtliche zukünftigen Orca-Versionen sind nicht pauschal geprüft.
Keine physischen Druckaufträge starten und keine Nachricht an Orca-Entwickler
senden. Dani übernimmt den Kontakt; Entwurf: docs/UPSTREAM_CONTACT.md.
