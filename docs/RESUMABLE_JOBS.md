# Fortsetzbare CLI-Aufträge — 0.5.1

`slice_project` startet einen Hintergrundauftrag und liefert seine ID. Mit
`idempotency_key: "halter-001"` liefert derselbe Aufruf nach einem verlorenen
Antwortpaket denselben gespeicherten Auftrag. Modell-/Profilinhalt, Parameter und
Zeitlimit müssen identisch sein. Für einen absichtlichen neuen Versuch eine neue
Kennung wählen. Ohne Kennung erzeugt jeder Aufruf weiterhin einen neuen Auftrag.

1. `slice_project(inputs=["/druck/halter.3mf"], output_directory="/druck/out",
   idempotency_key="halter-001", export_3mf="sliced.3mf")` aufrufen.
2. `job_wait(job_id="…", timeout_seconds=10)` liefert spätestens nach 10 Sekunden
   den aktuellen Zustand. `queued`/`running`: erneut abfragen. Der Ablauf läuft
   weiter, wenn die Wartefrist verstreicht oder nur die Abfrage abgebrochen wird.
3. `job_log(job_id="…", offset=0, limit_bytes=8000)` lesen und beim nächsten Mal
   `next_offset` übernehmen. Der Cursor zählt Bytes. `at_end` bedeutet, dass die
   bisher gespeicherten Bytes gelesen sind; den Abschluss über `status` prüfen.
4. `job_cancel(job_id="…")` beendet einen laufenden oder wartenden Auftrag.

Wartefrist: 0–30 Sekunden. Logbereich: 1–100000 Bytes, höchstens 10 MiB gespeichert.
Kleine Logbereiche müssen Platz für ein UTF-8-Zeichen bieten (bis zu vier Bytes).
Ein einzelnes Auftragsverzeichnis darf nur von einer Serverinstanz benutzt werden.
Ein getrenntes MCP-Serverende beendet seine Kindprozesse; ein harter Abbruch wird
beim Neustart als `interrupted` erkannt. Die Wiederaufnahme liest Ergebnisse und
Quittungen, sie startet unterbrochene Berechnungen nicht automatisch erneut.

Modelle und explizite Profile werden beim Einreihen und vor der Ausführung geprüft.
Während der Ausführung müssen sie unverändert bleiben. Ausgabepfade sollten für
unterschiedliche Aufträge getrennt sein. Vorhandene Dateien werden nicht als Beweis
für einen erfolgreichen neuen Lauf gewertet. `cli_run` bleibt ein bewusst allgemeiner
CLI-Zugang; dessen beliebige Argumente werden nicht als Modellpfade interpretiert.
Diese Funktionen steuern den separaten CLI-Prozess. Sie steuern keinen GUI-Slicejob
und starten keinen Drucker.
