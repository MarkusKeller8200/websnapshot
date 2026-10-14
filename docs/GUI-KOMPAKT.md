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
