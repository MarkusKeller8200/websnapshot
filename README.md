# WebSnapshot

Lokale Anwendung für manuell gestartete Website-Snapshots, Versionsvergleiche und HTML-Änderungsberichte.

## Was macht WebSnapshot?

WebSnapshot 0.1.0 ist eine lokal betriebene Python-Anwendung zur manuellen Erfassung, Archivierung und zum Vergleich von Webseiten. So lässt sich beispielsweise heute ein Snapshot einer Website erstellen und nach einem Monat feststellen, welche Textinhalte sich verändert haben.

### Arbeitsablauf

1. **Website hinzufügen:** Eine öffentliche HTTP(S)-Adresse eingeben. Mehrere Websites können verwaltet werden.
2. **Umfang bestimmen:** Maximale Seitenzahl und Linktiefe konfigurieren.
3. **Snapshot starten:** Die Anwendung besucht die Startseite und gefundene Unterseiten innerhalb desselben Hosts und erfasst den HTML-Text und Seitentitel.
4. **Archivieren:** URL, Text, Zeitstempel und SHA-256-Prüfsumme werden lokal in SQLite gespeichert.
5. **Vergleichen:** Zwei beliebige gespeicherte Snapshots einer Website auswählen.
6. **Bericht erstellen:** Die Unterschiede in der Oberfläche ansehen und als HTML-Änderungsbericht exportieren.

### Erkannte Änderungen

| Status | Bedeutung |
| --- | --- |
| `added` | Die URL wurde im neueren Snapshot erstmals erfasst. |
| `changed` | Der gespeicherte Textinhalt unterscheidet sich. |
| `missing` | Die zuvor erfasste URL fehlt im neueren Snapshot. **Das beweist keine Löschung**; auch Abruffehler oder Crawling-Grenzen können die Ursache sein. |

**Beispiel:** Ändert eine Behörde die Anmeldefrist von «15. Oktober» auf «30. Oktober», zeigt der Textvergleich die alte und die neue Fassung. Eine fachliche KI-Zusammenfassung ist in Version 0.1.0 noch nicht enthalten.

### Funktionsumfang der ersten Version

| Funktion | Stand |
| --- | --- |
| Mehrere Websites verwalten | Implementiert |
| Unterseiten anhand von Links erfassen | Implementiert, begrenzte Tiefe und Seitenzahl |
| Snapshots manuell erstellen | Implementiert |
| Historische Text-Snapshots in SQLite speichern | Implementiert |
| Zwei Snapshots vergleichen | Implementiert |
| Neue, geänderte und fehlende URLs auflisten | Implementiert |
| HTML-Änderungsbericht herunterladen | Implementiert |
| PDF- und Word-Dokumente auswerten | Geplant |
| Screenshots | Geplant |
| Dynamische JavaScript-Seiten mit Playwright erfassen | Geplant |
| KI-Zusammenfassungen und Relevanzbewertung | Geplant |
| Automatisch nach Zeitplan scannen | Optional später |

### Datenspeicherung und Grenzen

Snapshots werden im Verzeichnis `.data/` in der Datei `websnapshot.sqlite3` gespeichert (sofern kein anderer Datenordner konfiguriert ist). Dieses Verzeichnis ist von Git ausgeschlossen. WebSnapshot archiviert **Textinhalte**, keine vollständigen Offline-Kopien inklusive Layout, Bilder und Downloads. Die Erfassung ist auf öffentliche HTML-Seiten ausgelegt und folgt nur Links innerhalb desselben Hosts. Eine Seite, die nicht mehr im Snapshot auftaucht, darf nicht automatisch als gelöscht interpretiert werden.

### Geplante Weiterentwicklung

Priorität haben eine möglichst vollständige Inventarisierung per Sitemap, rekursiver Linksuche und transparentem Crawl-Status, anschliessend die Erkennung geänderter PDF-Dokumente und KI-gestützte Änderungsberichte. Weitere Ideen sind PDF-Export und Integrationen in Confluence, Jira sowie Microsoft 365. Siehe [technisches Konzept](docs/KONZEPT.md).

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

Die Anwendung öffnet normalerweise automatisch den Browser und ist lokal unter **http://localhost:8501** erreichbar. Eine öffentliche Website hinzufügen, Seitenzahl und Linktiefe konfigurieren und auf «Neuen Snapshot erstellen» klicken. Ab dem zweiten Snapshot lassen sich zwei Versionen vergleichen und die Unterschiede als HTML-Bericht herunterladen.

**Hinweis zur Vollständigkeit:** In Version 0.1 werden nur verlinkte HTML-Seiten innerhalb desselben Hosts und der eingestellten Grenzen erfasst. Es wird noch keine Sitemap eingelesen. Die aktuelle Erfassung ist **kein Nachweis einer vollständig erfassten Website**. Weitere Informationen stehen im [Konzept](docs/KONZEPT.md).

Die Snapshots werden lokal in `.data/` gespeichert. Dieser Ordner gehört nicht ins Git-Repository. Version 0.1 verarbeitet noch keine PDF-Dokumente, keine dynamischen JavaScript-Seiten und keine KI-Auswertung. Die Website-Regeln (insbesondere robots.txt und Nutzungsbedingungen) sind zu respektieren.

### Aktualisieren

Im Projektordner ausführen:

```cmd
git pull
.venv313\Scripts\python.exe -m pip install -e ".[dev]"
```

Auf macOS stattdessen `.venv/bin/python -m pip install -e ".[dev]"` ausführen. Die lokalen Snapshot-Daten bleiben durch `git pull` unangetastet.
