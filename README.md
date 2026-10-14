# WebSnapshot

Lokale Anwendung für manuell gestartete Website-Snapshots, Versionsvergleiche und HTML-Änderungsberichte.

## Was macht WebSnapshot?

WebSnapshot 0.4.0 ist eine lokal betriebene Python-Anwendung zur manuellen Erfassung, Archivierung und zum Vergleich von Webseiten. So lässt sich beispielsweise heute ein Snapshot einer Website erstellen und nach einem Monat feststellen, welche Textinhalte sich verändert haben.

### Arbeitsablauf

1. **Website hinzufügen:** Eine öffentliche HTTP(S)-Adresse eingeben. Mehrere Websites können verwaltet werden.
2. **Erfassungsumfang bestimmen:** Sicherheitslimit für die Anzahl besuchter URLs festlegen. Die Anwendung sucht Sitemaps und folgt internen Links rekursiv ohne feste Linktiefe.
3. **Snapshot starten:** Die Anwendung durchsucht Sitemaps und interne Links, archiviert HTML-Texte und inventarisiert Dokumentlinks innerhalb desselben Hosts.
4. **Archivieren:** URL, Text, Zeitstempel und SHA-256-Prüfsumme werden lokal in SQLite gespeichert.
5. **Vergleichen:** Zwei beliebige gespeicherte Snapshots einer Website auswählen.
6. **Bericht erstellen:** Die Unterschiede in der Oberfläche ansehen und als HTML-Änderungsbericht exportieren.

### Erkannte Änderungen

| Status | Bedeutung |
| --- | --- |
| `added` | Die URL wurde im neueren Snapshot erstmals erfasst. |
| `changed` | Der gespeicherte Textinhalt unterscheidet sich. |
| `missing` | Die zuvor erfasste URL fehlt im neueren Snapshot. **Das beweist keine Löschung**; auch Abruffehler oder Crawling-Grenzen können die Ursache sein. |

**Beispiel:** Ändert eine Behörde die Anmeldefrist von «15. Oktober» auf «30. Oktober», zeigt der Textvergleich die alte und die neue Fassung. Eine fachliche KI-Zusammenfassung ist in Version 0.3.0 noch nicht enthalten.

### Funktionsumfang der ersten Version

| Funktion | Stand |
| --- | --- |
| Mehrere Websites verwalten | Implementiert |
| Full- und Partial-/Delta-Snapshots | Implementiert |
| Einzelne Full-Snapshots ohne abhängige Deltas löschen | Implementiert |
| Sitemap als kompakte Tabelle mit Originalseiten-Links | Implementiert |
| Interne Links rekursiv sowie Sitemaps durchsuchen | Implementiert, mit Sicherheitslimits |
| Snapshots manuell erstellen | Implementiert |
| Historische Text-Snapshots in SQLite speichern | Implementiert |
| Zwei Snapshots vergleichen | Implementiert |
| Neue, geänderte und fehlende URLs auflisten | Implementiert |
| HTML-Änderungsbericht herunterladen | Implementiert |
| PDF- und Word-Dokumentlinks inventarisieren | Implementiert; ohne Inhaltsdownload |\n| PDF- und Word-Dokumentinhalte auswerten | Geplant |\n| Dashboard mit Website-, Snapshot- und Speicherkennzahlen | Implementiert |\n| Websites hinzufügen und entfernen | Implementiert |\n| Warnung bei ältesten Snapshots über 30 Tagen | Implementiert |\n| GitHub-Update über die Anwendung | Implementiert (Neuladen; kein garantierter Prozessneustart) |\n| Live-Status mit Laufzeit, Seiten- und Dokumentzählern | Implementiert |\n| Hintergrund-Snapshot mit exklusiver Job-Sperre je Website | Implementiert |\n| Navigierbare Sitemap mit Links zu Originalseiten | Implementiert (URL-Pfadgruppen) |\n| Dokumentliste mit selektivem Download | Implementiert für PDF, DOC und DOCX |\n| Dokumentänderungen erkennen | ETag / Last-Modified / Dateigrösse; kein Inhaltsvergleich ohne Download |
| Screenshots | Geplant |
| Dynamische JavaScript-Seiten mit Playwright erfassen | Verfügbar (Browsermodus, Prototyp) |
| KI-Zusammenfassungen und Relevanzbewertung | Geplant |
| Automatisch nach Zeitplan scannen | Optional später |

### Datenspeicherung und Grenzen

Snapshots werden im Verzeichnis `.data/` in der Datei `websnapshot.sqlite3` gespeichert (sofern kein anderer Datenordner konfiguriert ist). Dieses Verzeichnis ist von Git ausgeschlossen. WebSnapshot archiviert **Textinhalte**, keine vollständigen Offline-Kopien inklusive Layout, Bilder und Downloads. Die Erfassung ist auf öffentliche HTML-Seiten ausgelegt und folgt nur Links innerhalb desselben Hosts. Eine Seite, die nicht mehr im Snapshot auftaucht, darf nicht automatisch als gelöscht interpretiert werden.

### Geplante Weiterentwicklung

Die erste automatische Inventarisierung über Sitemap und rekursive Linksuche ist integriert. Geplant sind ausführlicher Crawl-Status, Wiederaufnahme abgebrochener Scans und anschliessend die Erkennung geänderter PDF-Dokumente und KI-gestützte Änderungsberichte. Weitere Ideen sind PDF-Export und Integrationen in Confluence, Jira sowie Microsoft 365. Siehe [technisches Konzept](docs/KONZEPT.md).

## Installation und Start

### Voraussetzungen

- Windows 10/11 oder macOS
- **Python 3.13 empfohlen** (Python 3.15 kann wegen der Streamlit-/PyArrow-Abhängigkeiten zu Installationsfehlern führen)
- Git zum Herunterladen des Projekts
- Internetverbindung zum Installieren der Python-Pakete und späteren Abrufen der Websites
- Für die übliche Installation mit passenden vorkompilierten Paketen sind keine C++-Build-Tools vorgesehen. Wenn `pip` Pakete aus Quellcode baut, zuerst Python-Version und Paketkompatibilität prüfen.

### Windows (Eingabeaufforderung / CMD)

Python 3.13 gegebenenfalls installieren:

```cmd
winget install --id Python.Python.3.13 -e
```

Eine neue Eingabeaufforderung öffnen, dann das Projekt herunterladen und die virtuelle Python-Umgebung anlegen:

```cmd
git clone https://github.com/MarkusKeller8200/websnapshot.git
cd websnapshot
py -3.13 -m venv .venv313
.venv313\Scripts\activate.bat
python --version
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Die Versionskontrolle muss `Python 3.13.x` anzeigen. Die Installation erfolgt nur einmalig. **Start per Doppelklick:** Anschliessend `WebSnapshot.bat` im Projektordner ausführen. Das Skript verwendet direkt `.venv313`, auch wenn systemweit Python 3.15 eingestellt ist.

Alternativ in CMD:

```cmd
.venv313\Scripts\python.exe -m streamlit run src\websnapshot\app.py
```

Für PowerShell lautet der Aktivierungsbefehl `.\.venv313\Scripts\Activate.ps1`. Eine Aktivierung ist für den Doppelklick-Start nicht notwendig.

### macOS

Python 3.13 sowie Git installieren, falls sie noch nicht vorhanden sind. Die folgenden Befehle im Terminal ausführen:

```bash
git clone https://github.com/MarkusKeller8200/websnapshot.git
cd websnapshot
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m streamlit run src/websnapshot/app.py
```

Falls der Befehl `python3.13` nicht verfügbar ist, muss zuerst die Python-3.13-Installation beziehungsweise deren PATH geprüft werden.

### WebSnapshot verwenden

Die Anwendung öffnet normalerweise automatisch den Browser und ist lokal unter **http://localhost:8501** erreichbar. Eine öffentliche Website unter «Websites verwalten» hinzufügen, im Bereich «Snapshots & Vergleich» das Sicherheitslimit einstellen und auf «Neuen Snapshot erstellen» klicken. Ab dem zweiten Snapshot lassen sich zwei Versionen vergleichen und die Unterschiede als HTML-Bericht herunterladen.

**Hinweis zur Vollständigkeit:** Version 0.2 durchsucht Sitemaps und verfolgt Links ohne feste Verschachtelungstiefe. Grenzen bei Laufzeit, URL-Zahl, Sitemap-Anzahl und dynamischen/geschützten Bereichen bleiben bestehen. Die Inventarisierung ist **kein Nachweis einer vollständig erfassten Website**. Weitere Informationen stehen im [Konzept](docs/KONZEPT.md).

Die Snapshots werden lokal in `.data/` gespeichert. Dieser Ordner gehört nicht ins Git-Repository. Version 0.2 zählt PDF-/Office-Dokumentlinks, speichert aber keine Dokumentinhalte. Dynamische JavaScript-Seiten und KI-Auswertung fehlen noch. Die Website-Regeln (insbesondere robots.txt und Nutzungsbedingungen) sind zu respektieren.

### Aktualisieren

Im Projektordner ausführen:

```cmd
git pull
.venv313\Scripts\python.exe -m pip install -e ".[dev]"
```

Auf macOS stattdessen `.venv/bin/python -m pip install -e ".[dev]"` ausführen. Die lokalen Snapshot-Daten bleiben durch `git pull` unangetastet.

### Dashboard und Verwaltung (Version 0.2)

Das Dashboard zeigt pro Website die Anzahl der zuletzt archivierten HTML-Seiten, gefundene Dokumentlinks, Anzahl Snapshots, letztes und ältestes Snapshot-Datum und die geschätzte Grösse der gespeicherten Texte. Ein **ältester Snapshot über 30 Tage** wird mit einem roten Symbol gekennzeichnet; ohne Snapshot erscheint ein neutraler Marker. Zusätzlich wird der Speicherplatz des Datenordners einschliesslich SQLite-Dateien angezeigt. **Die Summe der Textmengen pro Website ist eine Schätzung und kein exklusiv zuordenbarer Festplattenverbrauch.**

Websites können unter «Websites verwalten» hinzugefügt und entfernt werden. Optional lassen sich die gespeicherten Snapshots beim Entfernen löschen. Ohne diese Option bleibt die Historie in SQLite erhalten, erscheint jedoch nicht mehr in der Website-Auswahl.

### Update-Knopf

Im Tab «Updates» führt die Anwendung lokal `git pull --ff-only` und `pip install -e` aus und lädt die Streamlit-Sitzung neu. Der Update-Vorgang bricht bei lokalen Git-Änderungen oder Fehlern ab. **Das aktuelle Verfahren startet nicht garantiert den gesamten Python-Prozess neu**; bei Änderungen an Abhängigkeiten oder am Streamlit-Server die BAT-Datei schliessen und erneut starten. Eine sichere automatische Prozess-Neustartlogik ist für eine spätere Version vorgesehen.

**Wichtig:** Die Updatefunktion ist nur für eine vertrauenswürdige lokale Einzelplatzinstallation gedacht. Fremden Code aus GitHub zu übernehmen und auszuführen ist ein sicherheitsrelevanter Vorgang. Vor Updates `.data/` sichern.

## Neuerungen in Version 0.3.0

### Live-Status beim Snapshot
Während der Erfassung werden die verstrichenen Sekunden, entdeckte URLs, besuchte URLs, archivierte HTML-Seiten und gefundene Dokumentlinks laufend angezeigt. Auch die Prüfung der Sitemaps und Dokument-Metadaten erscheint als Phase. Der Lauf ist nicht automatisch abbrechbar oder fortsetzbar.

### Dokumentinventar und manuelle Downloads
Für jeden **neuen** Snapshot werden erkannte PDF-, DOC- und DOCX-Adressen in der Datenbank gespeichert. In «Snapshots & Vergleich» kann der jeweilige Snapshot ausgewählt werden. Eine Tabelle zeigt Dokument-URL, Metadatenstatus, gemeldete Dateigrösse und Download-Status. Erst nach expliziter Auswahl und Klick auf den Download-Button werden Dateien tatsächlich heruntergeladen (maximal 100 MB je Datei). Das Verzeichnis lautet `.data/downloads/`; Dateien werden nach Website-Host gruppiert. Der Benutzer kann zwischen einer Unterordnerstruktur entsprechend dem URL-Pfad und flacher Ablage wählen. Vorhandene Dateien mit gleichem Zielpfad werden ersetzt; bei flacher Ablage erhält der Name einen URL-Hash zum Schutz vor Namenskonflikten.

**Vergleich mit dem letzten Snapshot:** Die Anwendung prüft über HTTP-HEAD die Metadaten `ETag`, `Last-Modified` und `Content-Length`. Sie unterscheidet «Neu gefunden», «Unverändert laut ETag», «Unverändert laut Metadaten», «Metadaten geändert» und «Nicht prüfbar». Metadatenänderungen sind **kein sicherer Beweis einer Inhaltsänderung**; umgekehrt sind gleiche Metadaten kein kryptografischer Integritätsnachweis. Ein echter Dokumentinhaltsvergleich anhand gespeicherter SHA-256-Prüfsummen bleibt eine künftige Funktion. Bei bestehenden Snapshots aus 0.2 sind keine Einzel-Dokumentlisten vorhanden.

### Wichtige Einschränkungen
Die Erfassung selbst lädt **keine Dokumentinhalte** herunter, fordert aber zur Statusprüfung leichte HEAD-Antworten an. URLs ausserhalb des ursprünglichen Hosts werden nicht verfolgt; Redirects werden nicht automatisch aufgelöst. Die Zahl gefundener Dokumente entspricht den während des Crawls erreichten Links und ist kein Vollständigkeitsnachweis. Robuste Prüfung von DNS-Rebinding, Download-Dateisignaturen, Unterbrechung und Wiederaufnahme bleiben für eine gehärtete Version vorgesehen.

## Version 0.4.0 – Hintergrund-Jobs und Sitemap

Ein Snapshot wird nun als lokaler Hintergrund-Thread gestartet. Das Dashboard und andere Webseiten bleiben währenddessen bedienbar. Laufende Jobs werden in der SQLite-Tabelle `jobs` erfasst; eine eindeutige partielle Datenbank-Indexsperre erlaubt **pro Website nur einen aktiven oder wartenden Job gleichzeitig**, auch bei mehrfachen Klicks oder mehreren Browser-Tabs. Andere Websites dürfen parallel verarbeitet werden (maximal drei Worker). Fortschrittsdaten werden alle zwei Sekunden aus der Datenbank gelesen.

**Wichtig:** Hintergrund bedeutet hier **innerhalb des laufenden lokalen Streamlit-Prozesses**, nicht als unabhängiger Windows-Dienst. Die Anwendung muss während des Crawls geöffnet bleiben. Nach einem unerwarteten Prozessende können Job-Sperren bestehen bleiben; im Tab «Updates» können solche Sperren nach Kontrolle manuell als unterbrochen markiert werden. Einen Job-Abbruch oder automatischen Wiederanlauf gibt es noch nicht. Updates sind während aktiver Jobs gesperrt.

### Sitemap-Navigation
Ein neuer Tab «Sitemap» zeigt die **im ausgewählten Snapshot tatsächlich archivierten HTML-Seiten**, nach erstem URL-Pfadsegment gruppiert, durchsuchbar und mit einem Link «Öffnen» zur Original-URL im Browser. Dies ist eine Navigationsübersicht, keine Zusicherung über alle existierenden Seiten. Eine verschachtelte Baumdarstellung inklusive Dokumente ist als weiterer Ausbau geplant.

### Dynamische Websites
Viele moderne Websites rendern Inhalte erst im Browser über JavaScript. Die bisherige `requests`-Erfassung erfasst nur ausgeliefertes HTML; nachgeladene Inhalte können fehlen. Vorgesehen ist ein **optionaler Playwright-Modus pro Website**: echtes Chromium mit JavaScript, gezielte Wartebedingungen auf relevante Seitenelemente, Begrenzungen für Laufzeit/Seitenzahl, Wiederverwendung einer Browser-Sitzung und getrennte Erkennung dynamisch verlinkter URLs. Er bleibt vorerst **geplant und ist in 0.4.0 noch nicht implementiert**. Login- und geschützte Bereiche erfordern zusätzliche Sicherheits- und Berechtigungskonzepte.

### Reihenfolge der nächsten Versionen

- **0.5.0 – Browsermodus vorbereiten:** Website-spezifische Wahl des Erfassungsmodus (statisch / Browser / später automatisch), Benutzeroberfläche und Konfiguration. Der Browsermodus ist bis zur Integration einer Browser-Engine noch nicht ausführbar; es erfolgt **kein stillschweigender Rückfall** auf statische Erfassung.
- **0.6.0 – Playwright integrieren:** Browsermodus mit Chromium tatsächlich ausführen, JavaScript-Inhalte und dynamisch erzeugte Links erfassen, Fortschritt/Fehlerstatus in bestehende Hintergrund-Jobs integrieren. Erst danach automatisches Umschalten prüfen.

## Version 0.6.0

Neu sind Playwright-/Chromium-Erfassung für dynamische Webseiten, Full-Baselines und Partial-/Delta-Snapshots mit Wiederverwendung der URL-Liste, sicheres Löschen nicht benötigter Full-Snapshots sowie eine tabellarische Sitemap mit Browser-Links. Partial-Snapshots speichern nur Änderungen an bekannten Seiten und benötigen ihre Baseline. Die Löschfunktion verhindert das Entfernen von Baselines mit abhängigen Deltas und das einzelne Löschen von Delta-Snapshots. Details und Grenzen stehen in [Version 0.6.0](docs/VERSION_0.6.0.md).

**Chromium einmalig installieren:** Nach `git pull` und `pip install -e ".[dev]"` in der Projektumgebung zusätzlich `python -m playwright install chromium` ausführen. Unter Windows mit `.venv313\\Scripts\\python.exe -m playwright install chromium`.

## Versionen 0.6.1–0.6.3

Die neueste 0.6.x-Fassung enthält einen Schutz gegen URL-Explosionen (normalisierte Query-Parameter, Grenzwerte für Discovery, Pfadvarianten und Links je Seite), eine Crawl-Diagnose mit URL-Herkunft und Qualitätskennzahlen sowie die Erkennung von PDF-/Word-Dokumenten anhand des HTTP-Inhaltstyps auch hinter PHP-Download-URLs. Dokumente werden weiterhin nur nach ausdrücklicher Auswahl heruntergeladen. Der kontrollierte Abbruch von Hintergrund-Jobs ist nun über die Oberfläche möglich. Hinweise zu Grenzen und Funktionsumfang: [Release 0.6.1–0.6.3](docs/RELEASE_0.6.1-0.6.3.md).

**Wichtig:** Die Grenzwerte schützen vor URL-Explosionen, können aber auch legitime URLs begrenzen. Eine als vollständig gemeldete Erfassung bezieht sich ausschliesslich auf die bekannten und zulässigen URLs. Neue Features sind eingecheckt, jedoch noch nicht durch einen vollständigen Windows-Integrationstest bestätigt.

### Dokumente auf zugehörigen Subdomains

Ein von `www.datenschutz.ch` verlinktes PDF auf `docs.datenschutz.ch` wird auch dann inventarisiert, wenn der HTML-Crawler aus Sicherheitsgründen auf `www.datenschutz.ch` beschränkt bleibt. Derzeit werden direkte PDF-, DOC- und DOCX-Links auf der ausdrücklich zugehörigen Subdomain `docs.<Domain>` erfasst; fremde Domains bleiben ausgeschlossen. Dokumentdateien werden beim Snapshot nicht heruntergeladen. Ein separater, ausdrücklich ausgelöster Download ist weiterhin erforderlich. Dies ist keine generelle automatische Erkennung beliebiger CDN-Hosts.

## Websnapshot v0.6.4 – Seitenleiste und Dokumentfilter

Die Website-Auswahl erfolgt zentral in einer ein- und ausblendbaren linken Seitenleiste (🌐) mit Suchfeld. Snapshot-Zentrale, Sitemap und Website-Einstellungen übernehmen die gewählte Website automatisch. Im Dokumentinventar stehen eine Suche nach Dateiname, URL und Status, Checkboxen direkt in der Liste und Aktionen zum Auswählen/Abwählen aller beziehungsweise ausschliesslich der gefilterten Dokumente bereit. Auch bei Filterwechseln bleibt die Auswahl von nicht sichtbaren Dokumenten bestehen.

**Versionsgeschichte:** [CHANGELOG.md](CHANGELOG.md) · [GitHub Releases](https://github.com/MarkusKeller8200/websnapshot/releases) · [Hinweise zu v0.6.4](docs/releases/v0.6.4.md). Releases werden durch einen GitHub-Actions-Workflow nach Testprüfung veröffentlicht. Wenn der Workflow nicht erfolgreich war, ist die Veröffentlichung noch nicht abgeschlossen.

## WebSnapshot v0.6.5 – Neues Navigationskonzept und Dokument-Renamer

**Aktueller Stand:** Die Oberfläche verwendet einen linksbündigen, ausklappbaren Menübaum mit getrennten Seiten für Snapshot-Steuerung, -Verwaltung, Änderungsvergleich, Dokumentdownloads, Job-Protokolle, globale Einstellungen und Updates. Änderungen am gespeicherten **HTML-Text** lassen sich direkt im Browser farbig vergleichen. Die Tabellen nutzen inhaltsabhängige, begrenzte Spaltenbreiten.

Für Downloads stehen ein Original-Dateinamensmodus und ein Renamer nach dem Schema `YYYY_MM_DD_HERKUNFT_Dokumentenname.pdf` zur Wahl. Die Herkunft (z. B. `DSB`/`SEKB`) wird pro Website gespeichert. Dokumentdaten stammen vorrangig aus PDF- und DOCX-Metadaten, dann HTTP-`Last-Modified`, ersatzweise aus dem Downloadzeitpunkt. Das genaue Datum und die Quelle werden mit dem Download protokolliert. Namenskonflikte werden ohne URL-Hash durch eine laufende Nummer gelöst; bereits vorhandene Dateien werden nicht ersetzt. Ein SHA-256-Vergleich neu heruntergeladener Inhalte mit früheren Downloads bleibt intern erhalten.

Unter «Einstellungen» lassen sich das globale Download-Verzeichnis (absoluter Pfad), die Standard-Ordnerstruktur, das Besuchslimit und die Sitemap-Tabellenhöhe zentral festlegen. Website-Einstellungen betreffen weiterhin nur die gerade ausgewählte Website.

**Versionsgeschichte:** [CHANGELOG](CHANGELOG.md) · [Release-Notizen v0.6.5](docs/releases/v0.6.5.md) · [alle GitHub Releases](https://github.com/MarkusKeller8200/websnapshot/releases).

**Hinweis:** Ältere Abschnitte dieses README beschreiben den historischen Entwicklungsstand und können abweichende Menübezeichnungen oder frühere Download-Namensregeln enthalten. Massgeblich für die aktuelle Version sind die v0.6.5-Release-Notizen. Die optische Darstellung muss noch auf dem lokalen Windows-System überprüft werden.

## WebSnapshot v0.6.6 – Konfigurierbare Crawl-Performance

Die neuen Standardwerte sind **200'000 entdeckte URLs**, **2'000 besuchte Seiten**, **3 Sekunden Timeout** und **3 parallele statische HTTP-Aufrufe**. Einstellbar unter «Einstellungen → Crawl-Grenzen und Geschwindigkeit». Gespeicherte frühere Einstellungen werden nicht stillschweigend überschrieben.

WebSnapshot misst beim Crawlen die Zeiten von robots.txt, Sitemaps, Link-Discovery, Seitenabrufen und Datenbankspeicherung. Live und im Snapshot-Archiv erscheinen Anzahl, Minimum, Mittelwert, Maximum und Summe der Messungen in Millisekunden sowie die langsamste URL pro Phase. Für Browserseiten wird zusätzlich heuristisch zwischen serverseitig vorhandenem Inhalt und durch JavaScript nachgeladenen Inhalten unterschieden; dies ist keine exakte Klassifikation.

Statische Seiten werden mit bis zu vier HTTP-Workern gleichzeitig abgerufen. Browserseiten bleiben sequentiell. Der HTTP-Timeout bezeichnet eine Wartezeit ohne Datenempfang und ist **keine harte Grenze für die gesamte Seitendauer**. Grosse Discovery-Limits erhöhen Datenbank- und Speicherbedarf. Weitere Details: [Release v0.6.6](docs/releases/v0.6.6.md) und [CHANGELOG](CHANGELOG.md).
