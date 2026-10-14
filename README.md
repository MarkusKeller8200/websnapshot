# WebSnapshot

Lokale Anwendung für manuell gestartete Website-Snapshots, Versionsvergleiche und HTML-Änderungsberichte.

## Was macht WebSnapshot?

WebSnapshot 0.2.0 ist eine lokal betriebene Python-Anwendung zur manuellen Erfassung, Archivierung und zum Vergleich von Webseiten. So lässt sich beispielsweise heute ein Snapshot einer Website erstellen und nach einem Monat feststellen, welche Textinhalte sich verändert haben.

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

**Beispiel:** Ändert eine Behörde die Anmeldefrist von «15. Oktober» auf «30. Oktober», zeigt der Textvergleich die alte und die neue Fassung. Eine fachliche KI-Zusammenfassung ist in Version 0.2.0 noch nicht enthalten.

### Funktionsumfang der ersten Version

| Funktion | Stand |
| --- | --- |
| Mehrere Websites verwalten | Implementiert |
| Interne Links rekursiv sowie Sitemaps durchsuchen | Implementiert, mit Sicherheitslimits |
| Snapshots manuell erstellen | Implementiert |
| Historische Text-Snapshots in SQLite speichern | Implementiert |
| Zwei Snapshots vergleichen | Implementiert |
| Neue, geänderte und fehlende URLs auflisten | Implementiert |
| HTML-Änderungsbericht herunterladen | Implementiert |
| PDF- und Word-Dokumentlinks inventarisieren | Implementiert; ohne Inhaltsdownload |\n| PDF- und Word-Dokumentinhalte auswerten | Geplant |\n| Dashboard mit Website-, Snapshot- und Speicherkennzahlen | Implementiert |\n| Websites hinzufügen und entfernen | Implementiert |\n| Warnung bei ältesten Snapshots über 30 Tagen | Implementiert |\n| GitHub-Update über die Anwendung | Implementiert (Neuladen; kein garantierter Prozessneustart) |
| Screenshots | Geplant |
| Dynamische JavaScript-Seiten mit Playwright erfassen | Geplant |
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
