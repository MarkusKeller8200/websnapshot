"""Shared application preferences for this local WebSnapshot installation."""
from pathlib import Path
from tempfile import NamedTemporaryFile
import json
import sqlite3

from .core import DATA, database

DEFAULT_SITEMAP_HEIGHT = 800
VALID_HEIGHTS = (350, 550, 800, 1100, 1500)


def defaults(data: Path = DATA) -> dict:
    return {
        "download_directory": str((data / "downloads").resolve()),
        "flat_downloads": False,
        "visit_limit": 1000,
        "sitemap_height": DEFAULT_SITEMAP_HEIGHT,
    }


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS app_preferences (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")


def get(data: Path = DATA) -> dict:
    result = defaults(data)
    init(data)
    with sqlite3.connect(database(data)) as db:
        rows = db.execute("SELECT key,value FROM app_preferences").fetchall()
    for key, value in rows:
        if key in result:
            try:
                result[key] = json.loads(value)
            except (ValueError, TypeError):
                pass
    return result


def validate_download_directory(value: str) -> Path:
    raw = Path(value.strip()).expanduser()
    if not raw.is_absolute():
        raise ValueError("Bitte einen absoluten Verzeichnispfad eingeben.")
    location = raw.resolve()
    if location.exists() and not location.is_dir():
        raise ValueError("Der Download-Pfad ist eine Datei, kein Verzeichnis.")
    try:
        location.mkdir(parents=True, exist_ok=True)
        # Check access early to avoid losing a long multi-file download.
        with NamedTemporaryFile(prefix=".websnapshot-test-",dir=location) as probe:
            probe.write(b"ok")
            probe.flush()
    except OSError as exc:
        raise ValueError(f"Download-Verzeichnis nicht beschreibbar: {exc}") from exc
    return location


def save(*, download_directory: str, flat_downloads: bool,
         visit_limit: int, sitemap_height: int, data: Path = DATA) -> dict:
    location = validate_download_directory(download_directory)
    if type(flat_downloads) is not bool:
        raise ValueError("Ungültige Auswahl für die Ordnerstruktur.")
    if type(visit_limit) is not int or not 10 <= visit_limit <= 20000:
        raise ValueError("URL-Besuchslimit muss zwischen 10 und 20'000 liegen.")
    if sitemap_height not in VALID_HEIGHTS:
        raise ValueError("Ungültige Höhe für die Sitemap-Tabelle.")
    values = {
        "download_directory": str(location),
        "flat_downloads": flat_downloads,
        "visit_limit": visit_limit,
        "sitemap_height": sitemap_height,
    }
    init(data)
    with sqlite3.connect(database(data)) as db:
        db.executemany(
            "INSERT INTO app_preferences(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(key,json.dumps(value,ensure_ascii=False)) for key,value in values.items()],
        )
    return values
