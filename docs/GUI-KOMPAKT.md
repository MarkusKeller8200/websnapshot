# Kompaktes GUI und skalierbare Sitemap-Tabelle

Die Oberfläche von WebSnapshot 0.6.3 wurde platzsparender gestaltet. Die Inhalte nutzen die volle Breite des Browserfensters; Titel, vertikale Abstände, Registerkarten und Kennzahlen sind kompakter. Das Dashboard zeigt die Websites jetzt in einer einzigen tabellarischen Übersicht statt mit mehreren grossen Kennzahlenblöcken pro Website.

Im Tab «Sitemap» ist die Tabellenhöhe über einen Regler mit **350, 550, 800, 1'100 oder 1'500 Pixeln** einstellbar. Die Tabelle nutzt die ganze verfügbare Breite und zeigt je Seite Pfad, Titel, Zeichenzahl, Original-Link und URL in einer Zeile. Zusätzlich kann die integrierte Vollbildansicht der Streamlit-Tabelle über deren Werkzeugleiste verwendet werden.

Die Bedienung ist bereits im Quellcode angepasst. Für die Überprüfung auf Windows und mit unterschiedlichen Bildschirmgrössen ist ein manueller Test nötig. Die Änderungen betreffen keine vorhandenen Snapshots oder Datenbankinhalte.

## Snapshot-Zentrale – übersichtlicher Aufbau

Im Bereich «Snapshots & Vergleich» sind die Einstellungen zum Starten eines Jobs und die Live-Anzeige direkt oben angeordnet. Darunter folgt das kompakte Snapshot-Archiv. Die weiteren Funktionen befinden sich in vier Unterregistern: «Änderungen vergleichen», «Dokumente», «Crawl-Diagnose» und «Verwaltung». Dadurch bleiben grosse Diagnoseauswertungen und Dokumentlisten verborgen, solange sie nicht benötigt werden. Die bestehende Full-/Partial-Auswahl, exklusive Job-Sperre, Dokumentdownloads, Vergleichsexporte und Löschschutzregeln bleiben erhalten.

## Dauerhafte Job-Zusammenfassung und Fehlerprotokoll

Im «Snapshot-Archiv» wird die Gesamtlaufzeit im Format `hh:mm:ss` aus den in SQLite gespeicherten UTC-Zeitstempeln berechnet. Der Auswahlbereich «Zusammenfassung und Fehlerprotokoll» zeigt für jeden Snapshot dessen Job-ID, Start, Ende, Laufzeit, Status, Erfassungsmodus, Besuchslimit, URL, zuletzt protokollierte Phase, entdeckte und besuchte URLs, archivierte HTML-Seiten, gefundene Dokumente, offene URLs, übersprungene URLs, Sitemaps sowie – bei Delta-Läufen – geänderte Seiten und Vergleich zur Full-Baseline.

Fehler werden bereits in `runs.errors` als JSON gespeichert; darunter sind URL-Fehler, Sitemap-Probleme und überschrittene Sicherheitslimits. Der neue Bereich stellt alle Meldungen einzeln in einer Tabelle dar und ermöglicht ihren Export als JSON. Daneben lässt sich eine vollständige Job-Zusammenfassung inklusive Original-Fortschrittsdaten, Fehlermeldungen und Zeitstempeln exportieren.

Die Tabelle `jobs` enthält weiterhin die Start- und Endzeit sowie den letzten Fortschrittsstand. Neu bleiben auch sämtliche zuvor aufgezeichneten Fortschrittsfelder beim Abschluss erhalten und die Konfiguration bei Start des Jobs wird gespeichert. Die Einzelupdates jedes Fortschrittsschritts sind **keine** Zeitreihe; es wird nur der letzte Zustand persistent vorgehalten. Bereits existierende Jobs können anhand der gespeicherten Zeitstempel rückwirkend Laufzeitinformationen anzeigen, soweit diese vorhanden sind; fehlende frühere Erfassungsfelder lassen sich nicht zuverlässig ergänzen.

## Schutzlimits während des Crawls

Im laufenden Full-Snapshot werden zwei Fortschrittsbalken angezeigt: **entdeckte URLs / Discovery-Limit (10'000)** und **besuchte URLs / eingestelltes Besuchslimit**. Die Werte sind bewusst getrennt; ein Besuchslimit ist keine Vollständigkeitsquote der Website. Sobald die Discovery-Grenze erreicht ist oder Pfad- beziehungsweise Links-pro-Seite-Limits URL-Kandidaten ausschliessen, wird eine gelbe Warnung mit der Ursache und Anzahl der ausgeschlossenen Kandidaten eingeblendet. Beim Erreichen des Besuchslimits wird die Warnung mit den offenen URLs ergänzt.

Die finalen Schutzlimit-Meldungen werden in `runs.errors` hinterlegt; Zähler und Warnungen stehen auch in der letzten Job-Zusammenfassung als JSON zur Verfügung. Die UI zeigt sie im Detailbereich des Snapshot-Archivs an. Die neuen Live-Zähler sind nur für Jobs verfügbar, die nach diesem Update gestartet werden. Ein Programmneustart während eines laufenden Jobs beendet dessen Hintergrund-Thread und sollte vermieden werden.


## Technische Job-Protokolle

Ab diesem Update wird für jeden neu gestarteten Hintergrund-Job automatisch eine UTF-8-Logdatei in `.data/logs/job_<ID>.log` angelegt. Sie enthält Zeitstempel in UTC, Ereignisse zu Start/Ende/Phasen, regelmässige Fortschrittsstände, erstmals aufgetretene Warnungen und **vollständige Python-Tracebacks** bei abgefangenen Worker-Fehlern. Die Logdatei ist über «Snapshots & Vergleich» direkt beim aktuellen Job («Technisches Job-Protokoll») einsehbar; für abgeschlossene Snapshots steht zusätzlich das Unterregister «Job-Protokolle» zur Verfügung. Beide Ansichten erlauben den Download als Text.

Jede Fortschrittsmeldung schreibt `last_activity_at` und `last_progress_at` in SQLite. Wenn bei einem laufenden Job mindestens 60 Sekunden lang keine neue Meldung eingegangen ist, zeigt die Oberfläche eine Warnung. Das ist **kein Beweis für einen Absturz**: Eine einzelne langsame Anfrage oder eine blockierte Website kann denselben Effekt haben. Technische Logs, die im Prozess selbst einen harten Absturz (z. B. Stromverlust) verhindern, können nicht nachträglich geschrieben werden; in diesem Fall ist der letzte vorhandene Logeintrag ausschlaggebend.

Für ältere Jobs werden keine Logdateien rückwirkend erstellt. Die Protokollansicht liest höchstens die letzten 500 KB ein, um Streamlit nicht mit riesigen Dateien zu blockieren. Bestehende Datenbanken erhalten die neuen Spalten automatisch beim ersten Öffnen. Die Anwendung darf während eines laufenden Crawls nicht aktualisiert oder neu gestartet werden, da die Hintergrundthreads im selben Prozess laufen.


## Neue Seitenleiste und Dokumentenauswahl ab v0.6.4

Die Website wird nun links in der ausklappbaren Streamlit-Seitenleiste ausgewählt. Jeder Eintrag besitzt ein 🌐-Symbol und eine eindeutige Website-Adresse; die gewählte Website bleibt beim Wechsel zwischen Snapshot-Zentrale, Sitemap und Website-Einstellungen erhalten. Das Sidebar-Suchfeld erlaubt ein schnelles Filtern zahlreicher registrierter Websites. Die zentrale Dashboard-Tabelle bleibt eine Gesamtübersicht über alle Websites.

Die Website-Verwaltung zeigt die Einstellungen für die links ausgewählte Website. Das Formular «Neue Website hinzufügen» und die Löschbestätigung sind ausklappbar. Im Snapshot-Archiv sind Zusammenfassung und Fehlerprotokoll ebenfalls standardmässig eingeklappt.

### Dokumentauswahl

Unter «Snapshots & Vergleich → Dokumente» werden Dokumente direkt in einer Tabelle mit Checkboxen ausgewählt. Der Suchfilter enthält einen Platzhalter «Dateiname, PDF-Link oder Änderungsstatus suchen …»; er filtert case-insensitiv nach URL, Status und HTTP-Dateigrösse. Die Schaltflächen «Alle auswählen», «Alle abwählen», «Gefilterte auswählen» und «Gefilterte abwählen» wirken wie beschriftet. Insbesondere löschen Filterwechsel und «Gefilterte abwählen» keine Auswahl ausserhalb der momentan sichtbaren Zeilen. Der Download umfasst die gesamte Auswahl des aktuellen Snapshots, nicht bloss die Treffer des Filters. Die Auswahl ist eine Streamlit-Sitzungseinstellung, kein dauerhaftes Datenbankfeld.

### Veröffentlichungen auf GitHub

Jede neue Version erhält einen Eintrag in `CHANGELOG.md` und ausführliche Release-Notizen unter `docs/releases/vX.Y.Z.md`. Die GitHub-Actions-Datei `.github/workflows/publish-release.yml` prüft bei einer Versionsänderung Tests und erstellt anschliessend GitHub-Releases, soweit Actions und Schreibberechtigungen aktiviert sind. Die tatsächliche Veröffentlichung ist erst nach dem erfolgreichen Workflow bestätigt.
