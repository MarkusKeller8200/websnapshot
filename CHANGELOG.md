# Änderungsprotokoll – WebSnapshot

Die offiziellen GitHub-Releases werden aus den versionierten Release-Notizen unter `docs/releases/` erstellt. **Jede künftig veröffentlichte Version erhält vor dem Release einen eigenen Changelog-Eintrag**, und die Veröffentlichung erfolgt nach den Tests über GitHub Actions. Versionierte GitHub-Releases sind von normalen Entwicklungscommits zu unterscheiden.

## v0.6.14 – Einheitliches Datum und Uhrzeit (14.10.2026)
- Datums- und Zeitstempel in der Oberfläche auf **YYYY.MM.DD HH:MM:SS** im 24-Stunden-Format vereinheitlicht.
- Job- und Snapshot-Zeitpunkte inklusive Sekunden; Dashboard, Job-Protokolle und historische Ansichten angepasst.
- HTTP-Dokumentdaten und eingebettete Word-/PDF-/Excel-Zeitstempel in Dokumentenlisten und Eigenschaften einheitlich formatiert.
- Bei bekannten Zeitzonen erfolgt die Anzeige in UTC; reine Datumswerte bleiben ohne erfundene Uhrzeit.
- Bestehende Datenbank- und JSON-Rohwerte sowie das Dateinamen-Schema bleiben unverändert.
- Automatisierte Regressionstests für ISO, HTTP-Datum, Zeitzonen und alte Logeinträge.

[Vollständige Release-Notizen](docs/releases/v0.6.14.md)

## v0.6.13 – Discovery beschleunigen und URL-Flut erklären (14.10.2026)
- robots.txt-Ausschlüsse bei erfolgreich geladenen Regeln **vor** der Aufnahme in die Crawl-Warteschlange berücksichtigen.
- XML-Sitemap-Einträge unmittelbar filtern und einreihen, ohne eine potenziell riesige Zwischenliste aufzubauen.
- Live- und Archivstatistik für unterschiedliche Pfade, URLs mit Query-Parametern, robots.txt-Ausschlüsse und Entdeckungsquellen.
- Diagnose mit häufigsten Query-Parametern und den Pfaden mit den meisten URL-Varianten, um Auffälligkeiten wie Kalender-/Filter-Varianten zu erkennen.
- Schutzlimits und benutzerdefinierte Ausschlusslisten unverändert respektieren; bereits laufende Jobs übernehmen neue Filter nicht rückwirkend.
- Regressionstests für frühe robots-Filterung, Sitemap-Limits und dauerhafte Discovery-Diagnose.

[Vollständige Release-Notizen](docs/releases/v0.6.13.md)

## v0.6.12 – Crawl-Ausschlussliste speichern (14.10.2026)
- Eigener **«Ausschlussliste speichern»**-Button direkt unter dem mehrzeiligen Eingabefeld.
- Aktuelle Eingabe über Streamlit-Callback übernehmen und Pfade unabhängig von Browser- und Erfassungsmodus speichern.
- Nach dem Schreiben per **neuer SQLite-Verbindung zurücklesen und prüfen**, bevor eine Erfolgsmeldung erscheint.
- Tatsächlich gespeicherte Regeln samt Anzahl anzeigen; ungespeicherte Änderungen und Eingabefehler klar kennzeichnen.
- Allgemeiner Einstellungsbutton bestätigt Änderungen ohne sofortiges Verschwinden der Erfolgsmeldung.
- Regressionstest für Speicherung, erneutes Laden, Integrität anderer Website-Einstellungen und Fehlerfälle.

[Vollständige Release-Notizen](docs/releases/v0.6.12.md)

## v0.6.11 – Ausschlussliste für URL-Bereiche (14.10.2026)
- Pro Website eine mehrzeilige **Crawl-Ausschlussliste** hinterlegen, beispielsweise /schule-hinterbirch/aktuelles/agenda/p-2002.
- Die Regel schliesst den exakten Pfad, Unterseiten und passende .html-Landingpages aus, ohne ähnlich benannte Nachbarpfade zu blockieren.
- Ausschlüsse bereits bei Sitemap-Discovery sowie statischen und gerenderten Links beachten, **vor** dem Discovery- und Links-pro-Seite-Limit.
- Pfadregeln pro Job festhalten; Zahl ausgelassener URL-Kandidaten live und je Regel in der Snapshot-Diagnose anzeigen, inklusive bis zu 20 Beispiel-URLs.
- Bei einer geänderten Ausschlussliste vor weiteren Delta-Snapshots einen neuen Full-Snapshot verlangen.
- Automatisierte Tests für Bereichsabgrenzung, Konfiguration, Migration, URL-Filterung und Delta-Vererbung.

[Vollständige Release-Notizen](docs/releases/v0.6.11.md)

## v0.6.10 – Link-Limit und Navigation (14.10.2026)
- **Links pro Seite** global einstellbar von 1 bis 10'000, Standard **1'000** (zuvor fest 300).
- Bei Schutzlimit-Ausschlüssen werden die nicht weiterverfolgten URLs zusammen mit ihren HTML-Quellseiten in SQLite protokolliert.
- In der Snapshot-Verwaltung unter Crawl-Diagnose nach ausgeschlossenen URLs suchen und sie als CSV (maximal 10'000 Zeilen je Block) exportieren.
- Die Sidebar kann in eine **schmale, weiterhin bedienbare Icon-Navigation** umgeschaltet werden; die Hauptansicht erhält dabei mehr Breite.
- Die Webseiten-Auswahl steht wieder als Dropdown unter «Übersicht»; im Icon-Modus über das 🌐-Symbol.
- **Tooltipps nur bei eingeklapptem Menü**, rechts neben dem betreffenden Icon; im ausgeklappten Menü keine Tooltips.
- Ergänzende Tests für Crawl-Limits, persistierte Ausschlusslisten und Navigation.

[Vollständige Release-Notizen](docs/releases/v0.6.10.md)

## v0.6.9 – Dokumenteigenschaften und Fundstellen
- PDF, DOC/DOCX, XLS/XLSX, TXT und CSV in Inventar, Metadatenprüfung und Download.
- Office-Tags wie Titel, Autor, Revision, Firma und Erstellungs-/Änderungsdatum sowie PDF-Metadaten.
- TXT-/CSV-Eigenschaften: Kodierung, Zeilen, CSV-Trennzeichen und Spalten.
- SHA-256 und Dateieigenschaften auf ausdrücklichen Wunsch temporär vor dem eigentlichen Download prüfen; HTTP-Daten bleiben separat.
- Mehrere Seiten können auf dasselbe Dokument verweisen; alle Fundstellen werden ohne Dokument-Duplikate protokolliert.
- Suchbare Dokumententabelle und Detailansicht, inklusive Datenbankmigration, Tests und robots.txt-Berücksichtigung.

[Vollständige Release-Notizen](docs/releases/v0.6.9.md)

## v0.6.8 – Unterseiten gezielt crawlen (14.10.2026)
- Automatische Begrenzung auf die Startseite und ihre Unterpfade bei Unterseiten-URLs; die Root-Domain bleibt standardmässig domainweit.
- Neue websitebezogene Einstellung **«Erfassungsbereich»** mit Automatik, Unterbereich und gesamter Domain.
- Unterstützung von Einstiegsseiten mit `.html`-Endung, beispielsweise `/de/bildung.html` einschliesslich `/de/bildung/...`.
- Domainweite Sitemap-Einträge sowie HTML-/Browserlinks ausserhalb des Bereichs aussortieren, bevor sie in die Crawl-Warteschlange gelangen.
- Direkt von erlaubten Seiten verlinkte PDF- und Word-Dateien aus gemeinsamen Dokumentverzeichnissen weiterhin inventarisieren.
- Anzahl wegen der Bereichsgrenze übersprungener URLs im Jobverlauf anzeigen und archivieren.
- Full-Snapshot verpflichtend beim Wechsel von domainweiter Baseline auf einen Unterbereich.
- Regressionstests für Präfixgrenzen, HTML-Unterseiten, Dokumentlinks, Altbestand und Migration.

[Vollständige Release-Notizen](docs/releases/v0.6.8.md)

## v0.6.7 – 10 Worker, grosse Crawls und Sitemap-Baum (14.10.2026)
- Parallelität im statischen Crawler auf **1–10 HTTP-Worker** einstellbar (Standard weiterhin 3).
- Besuchslimit auf maximal **100'000 URLs** erhöht; Discovery-Limit erlaubt weiterhin bis zu **1'000'000 URLs**. Standardwerte bleiben bei 2'000 / 200'000.
- Sitemap mit umschaltbarer **aufklappbarer Pfad-Baumtabelle** und **flacher, sortierbarer Tabelle**.
- Sitemap-Suche mit automatischem Öffnen gefilterter Ordner; auf 2'500 gleichzeitig sichtbare Baumzeilen begrenzt.
- Grosse Sitemap-Listen laden nur Pfad, Titel und Länge, nicht mehr den vollständigen HTML-Text.
- CSV-Export (UTF-8-BOM, Semikolon, Formelschutz) und vollwertiger XLSX-Export mit Filterzeile und eingefrorener Kopfzeile.
- Für alle Tabellen: Inhaltsabhängige Breiten für alle Spalten **ausser der letzten**, die ihren Platz flexibel erhält.
- Belastungswarnung im GUI bei sehr hohen Besuchslimits oder acht bis zehn Workern sowie Regressionstests.

[Vollständige Release-Notizen](docs/releases/v0.6.7.md)

## v0.6.6 – Discovery, Timeout und Performance-Messung (14.10.2026)
- Discovery-Limit global einstellbar, Standard **200'000 URLs** (bisher 10'000); Besuchslimit **2'000 URLs** (bisher 1'000).
- Seiten-Timeout konfigurierbar, standardmässig **3 Sekunden** für Verbindungsaufbau und ausbleibende HTTP-Daten; Browsernavigation erhält dieselbe Wartezeitgrenze.
- Sichere statische HTTP-Parallelität (Standard 3, maximal 4), mit eigener wiederverwendbarer Session pro Worker; Playwright bleibt sequentiell.
- Dauerstatistiken nach `perf_counter`: Anzahl, Minimum, Mittelwert, Maximum und Gesamtdauer für robots.txt, Sitemaps, Discovery, Links, Seitenabrufe und Persistierung.
- Live-Performance während des Jobs und dauerhaft in SQLite beim Snapshot; Timeout-Zähler und langsamste URL pro Phase.
- Separate Erfassung von statischen HTTP-Seiten sowie im Browser erkannten statischen, dynamischen und nicht klassifizierbaren Seiten. Dynamik ist eine **Heuristik**, kein Nachweis.
- Geringerer SQLite-Fortschrittsaufwand (zeitlich gebündelt) und keine quadratische wiederholte Delta-Hashberechnung.
- Ergänzende Tests für Limits, Timeout, Zeitstatistik, echte begrenzte Parallelität und Seitenarten.

[Vollständige Release-Notizen](docs/releases/v0.6.6.md)

## v0.6.5 – Vereinheitlichte Oberfläche, Dokument-Renamer und Einstellungen (14.10.2026)
- Abgeschnittenen WebSnapshot-Titel korrigiert und Navigation vollständig in den linken, einklappbaren Menübaum überführt; Schaltflächen, Symbole und Beschriftungen linksbündig.
- Snapshot starten, Snapshot-Verwaltung, Änderungsvergleich, Dokumentdownload und Job-Protokolle als eigenständige Ansichten aufgeteilt.
- HTML-Textänderungen farbig im Browser als Vorher-/Nachher-Vergleich ansehen, mit optionalem HTML-Export.
- Intelligente Spaltenbreiten für Dashboard-, Archiv-, Diagnose-, Dokument- und Sitemap-Tabellen.
- Dokument-Renamer mit pro Website einstellbarem Herkunftskürzel (z. B. DSB / SEKB), Datum aus PDF-/DOCX-/HTTP-Metadaten und unterschiedlichen Grossschreibungsmodi; Originalnamen weiterhin möglich.
- Neue Dateien mit `YYYY_MM_DD_HERKUNFT_Dokumentenname` ohne URL-Hash benennen, Leerzeichen durch Unterstriche ersetzen; Konflikte durch `_2`, `_3` usw. lösen.
- Prüfsummen (SHA-256) und Datumsherkunft intern speichern; Dokumentänderungen bei erneutem Download anhand des Hashwerts erkennen.
- Neuer globaler Menüpunkt «Einstellungen» für Download-Pfad, Standard-Ordnerstruktur, Besuchslimit und Sitemap-Höhe.
- Neue Regressionstests für Renamer, Einstellungen, GUI-Struktur und Tabellenbreiten.

[Vollständige Release-Notizen](docs/releases/v0.6.5.md)

## v0.6.4 – Navigation, Auswahl und Oberfläche
- Einklappbare linke Webseiten-Navigation mit Symbolen und Suchfilter; die Auswahl gilt über alle Funktionsbereiche.
- Entfernte Website-Dropdowns in der Snapshot-Zentrale und Sitemap.
- Website-Verwaltung auf die ausgewählte Website begrenzt, das Formular zum Hinzufügen ist einklappbar.
- Durchsuchbares Dokumentinventar mit Platzhalter-Suche nach URL, Dateiname und Status.
- Direkte Auswahl über Checkboxen in der Dokumenttabelle statt langer Mehrfachauswahl.
- Aktionen «Alle auswählen/abwählen» und «Gefilterte auswählen/abwählen».
- Verdeckte Dokumentauswahl bleibt auch beim Filterwechsel erhalten.
- Historische Snapshot-Details ausklappbar statt dauerhaft angezeigt.
- Regressionstests für Filter- und Auswahlverhalten.

[Vollständige Release-Notizen](docs/releases/v0.6.4.md)

## v0.6.3 – Konsolidierter Entwicklungsstand
- Crawl-Schutz, URL-Normalisierung, diagnostizierte Limits.
- Erkennung verlinkter Dokumente und opt-in Download, auch über PHP-URLs und zugehörige Dokument-Subdomains.
- Volle und inkrementelle Snapshots; Änderungen gegenüber Vorgänger und Baseline.
- Website- und Snapshot-Qualitätsberichte, Warnungen und Laufzeitdaten.
- Job-Protokolle inklusive Tracebacks und Inaktivitätswarnungen.
- Kompaktes Dashboard und grössenverstellbare Sitemap.

Die Einzeländerungen der internen Entwicklungsstände **0.6.1** und **0.6.2** sind in den [0.6.x-Release-Notizen](docs/RELEASE_0.6.1-0.6.3.md) dokumentiert. **v0.6.3 ist eine nachträgliche Zusammenfassung** der damals sukzessive implementierten Änderungen, kein bestätigter vollständiger Integrationstest.

[Vollständige Release-Notizen](docs/releases/v0.6.3.md)

## Regeln für zukünftige Versionen
1. Alle Änderungen in `CHANGELOG.md` und einer neuen Datei `docs/releases/vX.Y.Z.md` dokumentieren.
2. Versionsnummer in `pyproject.toml` und in der App-Anzeige aktualisieren.
3. Quellcode und Tests auf `main` einchecken. Ein Versions-Commit startet die Veröffentlichung über `.github/workflows/publish-release.yml`.
4. Der Workflow prüft Syntax und Tests und erstellt anschliessend das zugehörige **GitHub Release mit Tag `vX.Y.Z`**, sofern es noch nicht existiert. Bestehende Releases werden bewusst nicht stillschweigend überschrieben.
5. Falls GitHub Actions gesperrt sind oder der Workflow scheitert, wird **kein erfolgreiches Release behauptet**. Status und Fehlermeldungen unter GitHub → Actions kontrollieren.

Ein Release ist erst dann veröffentlicht, wenn es unter [GitHub Releases](https://github.com/MarkusKeller8200/websnapshot/releases) sichtbar ist.
