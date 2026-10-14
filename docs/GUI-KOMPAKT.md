# Kompaktes GUI und skalierbare Sitemap-Tabelle

Die Oberfläche von WebSnapshot 0.6.3 wurde platzsparender gestaltet. Die Inhalte nutzen die volle Breite des Browserfensters; Titel, vertikale Abstände, Registerkarten und Kennzahlen sind kompakter. Das Dashboard zeigt die Websites jetzt in einer einzigen tabellarischen Übersicht statt mit mehreren grossen Kennzahlenblöcken pro Website.

Im Tab «Sitemap» ist die Tabellenhöhe über einen Regler mit **350, 550, 800, 1'100 oder 1'500 Pixeln** einstellbar. Die Tabelle nutzt die ganze verfügbare Breite und zeigt je Seite Pfad, Titel, Zeichenzahl, Original-Link und URL in einer Zeile. Zusätzlich kann die integrierte Vollbildansicht der Streamlit-Tabelle über deren Werkzeugleiste verwendet werden.

Die Bedienung ist bereits im Quellcode angepasst. Für die Überprüfung auf Windows und mit unterschiedlichen Bildschirmgrössen ist ein manueller Test nötig. Die Änderungen betreffen keine vorhandenen Snapshots oder Datenbankinhalte.
