# Änderungsprotokoll – WebSnapshot

Die offiziellen GitHub-Releases werden aus den versionierten Release-Notizen unter `docs/releases/` erstellt. **Jede künftig veröffentlichte Version erhält vor dem Release einen eigenen Changelog-Eintrag**, und die Veröffentlichung erfolgt nach den Tests über GitHub Actions. Versionierte GitHub-Releases sind von normalen Entwicklungscommits zu unterscheiden.

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
