# WebSnapshot

Local, manually triggered website snapshots, content comparison and HTML change reports.

## Was macht WebSnapshot?

WebSnapshot 0.1.0 ist eine lokal betriebene Python-Anwendung zur manuellen Erfassung, Archivierung und zum Vergleich von Webseiten. So lässt sich beispielsweise heute ein Snapshot einer Website erstellen und nach einem Monat feststellen, welche Textinhalte sich verändert haben.

### Arbeitsablauf

1. **Website hinzufügen:** Eine öffentliche HTTP(S)-Adresse eingeben. Mehrere Websites können verwaltet werden.
2. **Umfang bestimmen:** Maximale Seitenzahl und Linktiefe konfigurieren.
3. **Snapshot starten:** Die Anwendung besucht die Startseite und gefundene Unterseiten innerhalb desselben Hosts und erfasst den HTML-Text und Seitentitel.
4. **Archivieren:** URL, Text, Zeitstempel und SHA-256-Prüfsumme werden lokal in SQLite gespeichert.
5. **Vergleichen:** Zwei beliebige gespeicherte Snapshots einer Website auswählen.
6. **Bericht erstellen:** Die Unterschiede in der Oberfläche ansehen und als HTML-Änderungsbericht exportieren.

### Erkannte Änderungen

| Status | Bedeutung |
| --- | --- |
| `added` | Die URL wurde im neueren Snapshot erstmals erfasst. |
| `changed` | Der gespeicherte Textinhalt unterscheidet sich. |
| `missing` | Die zuvor erfasste URL fehlt im neueren Snapshot. **Das beweist keine Löschung**; auch Abruffehler oder Crawling-Grenzen können die Ursache sein. |

**Beispiel:** Ändert eine Behörde die Anmeldefrist von «15. Oktober» auf «30. Oktober», zeigt der Textvergleich die alte und die neue Fassung. Eine fachliche KI-Zusammenfassung ist in Version 0.1.0 noch nicht enthalten.

### Funktionsumfang der ersten Version

| Funktion | Stand |
| --- | --- |
| Mehrere Websites verwalten | Implementiert |
| Unterseiten anhand von Links erfassen | Implementiert, begrenzte Tiefe und Seitenzahl |
| Snapshots manuell erstellen | Implementiert |
| Historische Text-Snapshots in SQLite speichern | Implementiert |
| Zwei Snapshots vergleichen | Implementiert |
| Neue, geänderte und fehlende URLs auflisten | Implementiert |
| HTML-Änderungsbericht herunterladen | Implementiert |
| PDF- und Word-Dokumente auswerten | Geplant |
| Screenshots | Geplant |
| Dynamische JavaScript-Seiten mit Playwright erfassen | Geplant |
| KI-Zusammenfassungen und Relevanzbewertung | Geplant |
| Automatisch nach Zeitplan scannen | Optional später |

### Datenspeicherung und Grenzen

Snapshots werden im Verzeichnis `.data/` in der Datei `websnapshot.sqlite3` gespeichert (sofern kein anderer Datenordner konfiguriert ist). Dieses Verzeichnis ist von Git ausgeschlossen. WebSnapshot archiviert **Textinhalte**, keine vollständigen Offline-Kopien inklusive Layout, Bilder und Downloads. Die Erfassung ist auf öffentliche HTML-Seiten ausgelegt und folgt nur Links innerhalb desselben Hosts. Eine Seite, die nicht mehr im Snapshot auftaucht, darf nicht automatisch als gelöscht interpretiert werden.

### Geplante Weiterentwicklung

Priorität haben die Sitemap-Auswertung und ein transparenter Crawl-Status, anschliessend die Erkennung geänderter PDF-Dokumente und KI-gestützte Änderungsberichte. Weitere Ideen sind PDF-Export und Integrationen in Confluence, Jira sowie Microsoft 365. Siehe [technisches Konzept](docs/KONZEPT.md).

## Local installation (Windows/macOS)

Requires Python 3.11+.

```bash
git clone https://github.com/MarkusKeller8200/websnapshot.git
cd websnapshot
python -m venv .venv
```

Activate the environment: Windows PowerShell: `.venv\Scripts\Activate.ps1`; macOS: `source .venv/bin/activate`.

```bash
pip install -e '.[dev]'
streamlit run src/websnapshot/app.py
```

Open http://localhost:8501. Add a public URL, adjust crawl depth and page count, run a manual snapshot, then select two snapshots to generate a report.

Snapshots are stored locally in `.data/` and must not be committed.

**V0.1 limitations:** Static HTML only; no PDF extraction, dynamic JS rendering, AI or scheduling. Missing pages are NOT confirmed deletions. Respect robots.txt, copyright and website usage terms. This is for trusted local use only.

See [Konzept](docs/KONZEPT.md).
