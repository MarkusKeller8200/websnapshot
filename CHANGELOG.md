# Änderungsprotokoll – WebSnapshot

Die offiziellen GitHub-Releases werden aus den versionierten Release-Notizen unter `docs/releases/` erstellt. **Jede künftig veröffentlichte Version erhält vor dem Release einen eigenen Changelog-Eintrag**, und die Veröffentlichung erfolgt nach den Tests über GitHub Actions. Versionierte GitHub-Releases sind von normalen Entwicklungscommits zu unterscheiden.

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
