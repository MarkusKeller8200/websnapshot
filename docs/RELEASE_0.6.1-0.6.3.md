# WebSnapshot – Änderungen 0.6.1 bis 0.6.3

## 0.6.1 – Crawl-Schutz und Diagnose
- URL-Normalisierung inklusive Entfernung bekannter Tracking-Parameter; fachlich relevante Query-Parameter wie `doc_id` bleiben erhalten.
- Schutzlimits: maximal 10'000 entdeckte eindeutige URLs, 200 Varianten desselben URL-Pfades und 300 weiterverfolgte Links je HTML-Seite. Das bisherige konfigurierbare Besuchslimit bleibt bestehen.
- Pro Snapshot werden URL-Herkunft, Verarbeitungsstatus und Gründe bei Fehlern oder Ausschlüssen protokolliert.
- Bei Erreichen von Grenzen erhält der Lauf eine Warnung und bleibt unvollständig; keine automatische Erhöhung des Limits.
- Hintergrund-Job kann kooperativ abgebrochen werden. Der Abbruch stoppt beim nächsten Fortschrittsereignis. Eine bereits laufende HTTP-Anfrage muss zuerst ihren Timeout erreichen.
- Laufende Jobs bleiben pro Website exklusiv, andere Websites können parallel verarbeitet werden.

## 0.6.2 – Dokumente und Inhaltsduplikate
- Dokumentantworten werden anhand von HTTP-`Content-Type` auch hinter Downloadadressen wie `download.php?doc_id=...` erkannt, ohne sie beim Crawling automatisch als Datei zu speichern.
- Der ausdrücklich durch den Benutzer ausgelöste Download unterstützt solche URLs mit sicher erzeugtem Dateinamen und validiert den PDF-/Word-Inhaltstyp.
- Anzahl gleicher, gespeicherter HTML-Textinhalte mit verschiedenen URLs wird ermittelt. Es werden dabei keine Seiten gelöscht oder automatisch zusammengelegt.
- Dokumente werden nicht auf Dateiinhaltsgleichheit geprüft; ETag, Last-Modified und Content-Length bleiben Indikatoren.

## 0.6.3 – Qualitätsdashboard
- Im Tab «Snapshots & Vergleich» sind Quellen, Zustände, Fehlergründe, häufige URL-Pfade, Query-Parameter und Qualitätskennzahlen des gewählten Snapshots abrufbar.
- Kennzahlen: bekannt, besucht, archiviert, Dokumente, offen, übersprungen, Fehler, Inhaltsduplikate und erreichte Limits.
- Eine Erfassung gilt nur für die **bekannten URLs** als abgeschlossen. Weder eine vollständige Site-Inventarisierung noch die Abwesenheit geschützter oder dynamischer Seiten wird garantiert.
- Das neue Dashboard enthält einen kontrollierten Job-Abbruch; abgebrochene Läufe werden nicht als vollständige Snapshots deklariert.
- Bei der Löschung von Snapshots und Website-Historien werden die zugehörigen Diagnoseeinträge entfernt.

## Bekannte Grenzen
Die URL-Begrenzungen sind zunächst global konfiguriert, nicht über die Benutzeroberfläche einstellbar. Bei URL-Explosionen können auch legitime Seiten vorübergehend ausgeschlossen werden; die Warnung zeigt diesen Sachverhalt an. Fehlerhaftes oder unvollständiges robots.txt, URL-Weiterleitungen, Browser-SSRF-Härtung, JavaScript-Zustand und Retry-Strategien bedürfen zusätzlicher Tests. Bei einem kontrollierten Abbruch werden keine halbfertigen Snapshots gespeichert; während eines Browser-Crawls kann eine offene Browserressource bis zum Prozessende bestehen bleiben.

## Update
Vor dem Update aktive Jobs beenden, Datenordner `.data/` sichern, WebSnapshot beenden. Unter Windows:
```cmd
cd /d S:\_ChatGTP\WebSnapshot\websnapshot
git pull
.venv313\Scripts\python.exe -m pip install -e ".[dev]"
```
Browsermodus benötigt zusätzlich (einmalig) `.venv313\Scripts\python.exe -m playwright install chromium`. Anwendung anschliessend neu starten.

**Status:** Implementierung und Tests sind eingecheckt. Ein erfolgreicher vollständiger Integrations- und Windows-Test kann ohne Zugriff auf die lokale Installation nicht bestätigt werden.
