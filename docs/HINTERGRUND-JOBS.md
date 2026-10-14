# Hintergrund-Jobs und Live-Dashboard (0.6.x)

## Darstellung

- Dashboard: alle aktiven Jobs aller Websites, Startzeit (UTC), Laufzeit, Fortschritt und Kennzahlen.
- Full-Snapshot: fortlaufende Anzahl erfasster HTML-Seiten, gefundener Dokumentlinks, entdeckter und bereits besuchter URLs; keine künstliche Prozentanzeige, da die Gesamtzahl unbekannt ist.
- Partial-Snapshot: Prozent = besuchte URLs / beim Start bekannte URLs. Ausserdem werden Textänderungen gegenüber dem unmittelbaren Vorgänger und der letzten Full-Baseline gezählt. Gezählt werden nur aktuell erfolgreich erfasste Seiten. Veränderte oder nicht erreichbare Dokumente sind davon ausgenommen.
- Alle zwei Sekunden werden Jobdaten aus der lokalen SQLite-Datenbank aktualisiert.
- Solange für eine Website ein Job den Status queued oder running besitzt, ist deren Starttaste deaktiviert. Eine SQLite-Unique-Sperre verhindert darüber hinaus doppelte Starts aus mehreren Browserfenstern. Andere Websites dürfen gleichzeitig verarbeitet werden.

## Grenzen

- Hintergrund-Threads benötigen einen laufenden Streamlit-Prozess. Der Job wird beim Schliessen der Anwendung nicht als eigenständiger Dienst fortgesetzt.
- Nach einem unvorhergesehenen Prozessabbruch müssen verwaiste Sperren kontrolliert und gegebenenfalls manuell freigegeben werden.
- Der Partial-Prozentwert bezieht sich auf besuchte URLs, nicht ausschliesslich erfolgreich geprüfte Seiten. Bei Crawl-Sicherheitslimits oder Fehlern ist 100 Prozent nicht gleichbedeutend mit einer fehlerfreien Erfassung.
- Zur Full-Baseline zählt die Anzeige aktuell geänderte, erfolgreich geprüfte Seiten; bei noch nicht geprüften Seiten oder früheren, inzwischen nicht erreichbaren Seiten ist kein abschliessender Gesamtänderungsstand ableitbar.

## Aktualisierung

Unter Windows im Projektordner:

```cmd
git pull
.venv313\Scripts\python.exe -m pip install -e ".[dev]"
```

WebSnapshot vollständig schliessen und über WebSnapshot.bat neu starten.
