# Konzept WebSnapshot

**Version:** 0.1 · **Stand:** 14.10.2026 · **Status:** Prototyp

## 1. Ziel
WebSnapshot archiviert den textlichen Zustand öffentlich zugänglicher Websites zu manuell gewählten Zeitpunkten. Änderungen zwischen zwei Snapshots werden transparent protokolliert und als HTML-Bericht exportiert. In der Startphase läuft die Anwendung ausschliesslich lokal unter Windows und macOS, ohne automatischen Hintergrunddienst.

## 2. Arbeitsablauf
1. Website als Start-URL speichern.
2. Maximale Unterseitenzahl und Linktiefe festlegen.
3. Auf «Neuen Snapshot erstellen» klicken.
4. Website innerhalb desselben Hosts crawlen, Titel, Text und SHA-256-Hash pro Seite archivieren.
5. Zwei beliebige Snapshots wählen.
6. Neue, geänderte und fehlende URLs samt Text-Diff prüfen.
7. HTML-Änderungsbericht herunterladen.

## 3. Funktionsanforderungen

| ID | Funktion | V0.1 |
| --- | --- | --- |
| F01 | Mehrere Websites verwalten | Ja |
| F02 | Snapshot manuell starten | Ja |
| F03 | Unterseiten begrenzt crawlen | Ja |
| F04 | Historische Snapshots lokal speichern | Ja |
| F05 | Zwei Versionen vergleichen | Ja |
| F06 | Hinzugefügte, geänderte, fehlende Seiten unterscheiden | Ja |
| F07 | HTML-Bericht erstellen | Ja |
| F08 | Abruffehler anzeigen | Ja |
| F09 | PDFs/Dokumente vergleichen | Geplant |
| F10 | JavaScript-Seiten mit Playwright | Geplant |
| F11 | KI-Bewertung, Relevanz und Zusammenfassungen | Geplant |
| F12 | PDF-Export, Jira-/Confluence-Integration | Geplant |
| F13 | Zeitgesteuerte Überwachung | Optional später |

## 4. Technische Architektur
Streamlit-Benutzeroberfläche → Python-Crawler mit requests / BeautifulSoup → SQLite-Datenbank → difflib-basierter Versionsvergleich → HTML-Export.

SQLite-Tabellen: `sites` (Quellen), `runs` (Zeitstempel, Fehler, Status), `pages` (URL, Titel, Text, Hash, Snapshot-ID). Daten verbleiben in `.data/`. Der Snapshot stellt **keine vollständige Offline-Kopie** der Webseite dar, sondern ein Textarchiv.

## 5. Qualitäts- und Sicherheitsregeln
- Nur http(s), keine eingebetteten URL-Zugangsdaten, keine lokalen oder privaten Netzwerkziele.
- Ausschliesslich URLs desselben Hosts; keine Weiterleitungen zu anderen Netzwerken.
- robots.txt nach Möglichkeit respektieren; begrenzte Seitengrösse, Seitenzahl und Linktiefe; HTTP-Timeout.
- Fehler offen anzeigen. Eine im neuen Crawl fehlende URL kann auf eine temporäre Störung oder Crawl-Grenzen zurückgehen; niemals automatisch als gelöscht deklarieren.
- Fremde Inhalte in HTML-Berichten escapen.
- Laufzeitdaten, fremde Webinhalte und Anmeldedaten nicht in Git committen.
- Kein öffentlich zugänglicher Mehrbenutzerbetrieb: zusätzliche Netzwerkisolation und SSRF-Härtung wären erforderlich.

## 6. Nichtziele für 0.1
Keine automatische Überwachung, keine KI, keine Browser-Emulation, keine PDFs, keine Screenshots, keine Authentifizierung, keine beweissichere Langzeitarchivierung.

## 7. Abnahmekriterien
- Zwei Snapshots derselben Site sind mit eigenständigen Zeitstempeln gespeichert.
- Textänderungen sind als Unified Diff sichtbar.
- Neu entdeckte und im Vergleich fehlende URLs sind gesondert markiert.
- HTML-Berichte sind lokal herunterladbar.
- Ein vollständig fehlgeschlagener Crawl erzeugt keinen irreführenden Snapshot.
- Alle lokalen Laufzeitdaten bleiben ausserhalb von Git.

## 8. Roadmap
0.1 Lokaler Prototyp; 0.2 robustere Fehlerbehandlung und Tests; 0.3 PDF-Dokumente; 0.4 Playwright; 0.5 optionale lokale KI-Analyse; 1.0 produktionsreifer Desktop- und Serverbetrieb.
