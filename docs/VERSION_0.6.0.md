# WebSnapshot 0.6.0 – Browser und Snapshot-Versionierung

## Neue Funktionen

- **Browsermodus:** Playwright startet ein lokales Chromium und rendert HTML inklusive JavaScript. CSS-Selektor und Wartezeit können je Website festgelegt werden. Der Modus ist nur für öffentliche Seiten vorgesehen; dynamische APIs, Login und unendliches Scrollen werden nicht automatisch vollständig erfasst.
- **Full-Snapshot:** Startseite, Sitemaps und interne Links werden neu inventarisiert und als Vollversion archiviert.
- **Partial-/Delta-Snapshot:** Bereits bekannte URLs aus dem letzten Snapshot werden erneut abgerufen. Nur geänderte oder neu gespeicherte Seitentexte werden in der Datenbank als Delta abgelegt; unveränderte Inhalte bleiben über den Vorgänger referenziert. Es werden **keine neuen URLs gesucht**. Fehlgeschlagene Seiten gelten nicht als gelöscht.
- **Snapshot-Löschung:** Einzelne Full-Snapshots können nach Bestätigung entfernt werden, solange keine Partial-Snapshots davon abhängen. Einzelne Partial-/Delta-Snapshots sind von der Löschfunktion ausgenommen.
- **Sitemap-Tabelle:** Eine kompakte Tabellenansicht mit Pfad, Titel, URL, Zeichenzahl und Link zur Originalseite ersetzt die einzelnen Kacheln. Filter-/Sortierausbau ist für später geplant.

## Installation unter Windows (Python 3.13)

Vor dem Update WebSnapshot schliessen; Sicherheitskopie des Ordners `.data` anlegen. In CMD:

```cmd
cd /d S:\_ChatGTP\WebSnapshot\websnapshot
git pull
.venv313\Scripts\python.exe -m pip install -e ".[dev]"
.venv313\Scripts\python.exe -m playwright install chromium
```

Anschliessend `WebSnapshot.bat` per Doppelklick starten.

Für macOS analog `python -m pip install -e ".[dev]"` und `python -m playwright install chromium` in der aktivierten virtuellen Umgebung ausführen.

## Grenzen und Datensicherheit

Ein Full-Snapshot beweist keine vollständige Abdeckung aller Website-Inhalte. Partial-Snapshots sind schneller, weil sie die Sitemap-Erkennung und die rekursive Suche überspringen; alle bekannten Seiten werden allerdings erneut abgerufen, sodass die Dauer von Netzwerklatenz und Seitenzahl abhängt. Delta-Snapshots müssen zusammen mit ihren Vorgängern aufbewahrt werden. Das Löschen einer Full-Baseline mit abhängigen Deltas ist gesperrt.

Der Browsermodus ist ein erster Prototyp. Auf fremden Seiten können weitergeleitete Ressourcen, komplexe JavaScript-App-Navigation oder Zugriffsregeln das Ergebnis einschränken. Keine Zugangsdaten für fremde Websites hinterlegen. Browsermode-Tests mit verschiedenen realen Websites und umfassende Netzwerksicherheitsprüfungen stehen noch aus.
