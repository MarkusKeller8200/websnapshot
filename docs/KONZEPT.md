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

## 9. Vollständigkeit der Website-Erfassung (geplant)

### 9.1 Problemstellung
Bei fremden Websites sind Anzahl und Verschachtelung der Unterseiten unbekannt. Eine feste Linktiefe oder maximale Seitenzahl kann daher unbemerkt Inhalte ausschliessen. Der aktuelle Crawler (0.1) verarbeitet ausschliesslich über HTML-Links erreichbare Seiten innerhalb vorgegebener Grenzen; **Vollständigkeit wird nicht zugesichert**.

### 9.2 Soll-Verfahren
1. **Discovery:** Start-URL, robots.txt mit dort genannten Sitemap-Adressen, `/sitemap.xml`, Sitemap-Indizes und zusätzliche benutzerdefinierte Sitemap-Adressen auswerten.
2. **Rekursive Linksuche:** Alle bekannten zulässigen HTML-Seiten untersuchen und interne Links nachverfolgen, bis die Warteschlange leer ist. Dabei eine automatische Tiefenbegrenzung vermeiden; Schutzlimits für Laufzeit, Datenmenge, Seitenzahl und Request-Rate bleiben nötig.
3. **Kanonisierung:** Fragmente entfernen, Redirects und Canonical-Links nachvollziehbar behandeln; Query-Parameter nicht unbesehen löschen, da sie eigene Inhalte kennzeichnen können. Subdomains nur nach expliziter Freigabe aufnehmen.
4. **Inhaltstypen:** HTML erfassen; Dokumente wie PDF/DOCX als separat zu behandelnde Assets inventarisieren (Extraktion spätere Version). JavaScript-gesteuerte Seiten später mit Playwright ergänzen.
5. **Persistente Warteschlange:** URLs und Status `gefunden`, `in Bearbeitung`, `erfolgreich`, `fehlgeschlagen`, `ausgeschlossen` oder `offen` protokollieren. Ein abgebrochener Lauf muss fortsetzbar sein.
6. **Abschlusskontrolle:** Anzahl gefundener, erfolgreich erfasster, fehlgeschlagener, ausgeschlossener und offener URLs sowie Herkunft jeder URL (Sitemap/Link/manuell) anzeigen. Bei Fehlern Wiederholversuche anbieten und Gründe dokumentieren.

### 9.3 Qualitätskennzahlen und Aussagekraft
`Erfassungsgrad = erfolgreich verarbeitete URLs / alle bekannten URLs` (sofern Nenner > 0). Der Wert sagt nur etwas über **bekannte** URLs aus; er ist kein objektiver Nachweis, dass sämtliche existierenden URLs entdeckt wurden.

Vorgesehene Zustände:
- **Abgeschlossen:** Alle bekannten und zulässigen URLs sind verarbeitet; keine Warteschlange mehr offen.
- **Unvollständig:** Bekannte URLs oder Dokumente sind noch offen, ausgeschlossen oder fehlgeschlagen.
- **Umfang unbekannt:** Nicht inventarisierbare Bereiche (z. B. Login, dynamische Navigation, fehlende Sitemap) verhindern eine belastbare Aussage.

Auch bei einem abgeschlossenen Crawl können unverlinkte, nicht in Sitemaps aufgeführte, zugriffsgeschützte oder dynamisch generierte Seiten fehlen. Das wird in UI und Export ausdrücklich kenntlich gemacht.

### 9.4 Versionsvergleich
Eine zuvor erfasste, bei der nächsten Inventarisierung aber fehlende URL bleibt zunächst **nicht nachgewiesen**. Erst zusätzliche URL-Prüfungen könnten eine tatsächliche Entfernung nahelegen; auch HTTP 404/410 und Weiterleitungen müssen mit Zeitstempel erfasst werden. Abruffehler niemals als Löschung melden.

### 9.5 Abnahmekriterien für einen künftigen Release
- Sitemap-Index und verschachtelte Sitemaps werden verarbeitet.
- Rekursion arbeitet bis zur leeren Warteschlange oder einem transparent ausgewiesenen Abbruchlimit.
- Jede bekannte URL hat Erfassungsstatus, Quelle und Fehlerprotokoll.
- Wiederaufnahme eines unterbrochenen Crawls ist möglich.
- Erfassungsgrad und Umfangseinschränkungen sind in Oberfläche und Änderungsbericht sichtbar.
- Nicht erfasste URLs werden nicht automatisch als gelöschte Seiten eingestuft.

## 10. Umsetzung Version 0.2.0 (14.10.2026)

- Streamlit-Dashboard mit Gesamt- und Website-Kennzahlen: Websites, letzter HTML-Seitenbestand, Dokumentlinks, Snapshot-Anzahl, ältestes/neuestes Datum, Speichermengen.
- Ältester Snapshot >30 Tage: roter Indikator. 30 Tage oder jünger: grün. Ohne Snapshot: neutral.
- Websites hinzufügen und entfernen; beim Entfernen optionale Löschung der Historie (ohne Auswahl bleiben verwaiste Datensätze erhalten).
- Sitemap-Discovery einschliesslich Sitemap-Indizes und rekursive HTML-Linksuche ohne feste Tiefe. Schutzlimit für maximal besuchte URLs sowie Grenzen für Sitemap-Anzahl und Antwortgrössen. Nur identischer Host, keine Weiterleitungen.
- PDF/Office-Dateien werden **nur als Links gezählt**, nicht heruntergeladen oder inhaltlich ausgewertet.
- Updatefunktion über git pull --ff-only und lokale pip-Installation mit Neuladen der Streamlit-Sitzung. Ein vollständiger Prozess-Neustart ist **noch nicht implementiert**.

**Einschränkungen:** Kein Beweis für die Vollständigkeit; Crawling ohne persistenten Wiederaufnahmestatus; keine dokumentenbezogenen Snapshots; fehlende URLs sind nicht als gelöscht nachgewiesen; Grundabsicherung gegen lokale Adressen ersetzt keine umfassende SSRF-Härtung für fremd erreichbare Server. Das Dashboard zeigt pro Website die gespeicherte Textmenge, während die tatsächliche SQLite-Dateigrösse nur insgesamt sinnvoll erfasst wird.

**Nächste Aufgaben:** Fortsetzbare URL-Queue und dauerhaftes Einzel-URL-Protokoll, separater Dokument-Inventarstand je Snapshot, vollständiger sicherer Neustart nach Updates, verbesserte Crawl-Abdeckung und Tests auf Windows/macOS.

## 11. Version 0.3.0 – Snapshot-Fortschritt und Dokumentdownloads

- Live-Fortschritt: Laufzeit in Sekunden, Crawl-Phase, entdeckte und besuchte URLs, erfolgreich gespeicherte HTML-Seiten und erkannte PDF-/Word-Links.
- Pro Snapshot eine Liste von Dokumenten (`documents`): URL, ETag, Last-Modified, Content-Length und daraus abgeleiteter Veränderungsstatus.
- Die Dokumente werden beim Snapshot **nicht heruntergeladen**, sondern nur via HTTP-HEAD auf Metadaten geprüft (soweit der Server dies unterstützt).
- Der Benutzer kann in der Oberfläche einzelne Dokumente auswählen und explizit herunterladen. Ablage in `.data/downloads/<host>/`, entweder mit URL-Unterordnern oder flach. Die heruntergeladenen Dateien werden mit SHA-256-Prüfsumme und Speicherort im lokalen Download-Protokoll registriert.
- Downloadgrenze 100 MB pro Datei; keine automatischen Redirects, keine privaten Netzwerke; Dateinamen werden bereinigt. Bestehende Ziele werden beim erneuten Download ersetzt.
- Statusdefinition: `Neu gefunden`, `Unverändert laut ETag`, `Unverändert laut Metadaten`, `Metadaten geändert`, `Nicht prüfbar`. **Keine Gleichsetzung von Metadatenänderung und sicher verifiziertem Inhaltswechsel.** Dokumente werden zunächst nicht inhaltlich verglichen.

**Offene Aufgaben:** Vollständiger SHA-256-Vergleich heruntergeladener Versionen, dauerhafte Dokumenthistorie unabhängig von Downloads, echter Crawlabbruch/Fortsetzung, Download-Fortschrittsanzeige pro Datei und die Absicherung gegen fortgeschrittene Server-/Netzwerkangriffe. Die in Version 0.3.0 hinzugefügten Funktionen benötigen weitere Praxistests.
