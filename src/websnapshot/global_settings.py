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
        "visit_limit": 2000,
        "discovery_limit": 200000,
        "page_timeout": 3.0,
        "http_workers": 3,
        "links_per_page": 1000,
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
         visit_limit: int, sitemap_height: int, data: Path = DATA,
         discovery_limit: int = 200000, page_timeout: float = 3.0,
         http_workers: int = 3, links_per_page: int = 1000) -> dict:
    location = validate_download_directory(download_directory)
    if type(flat_downloads) is not bool:
        raise ValueError("Ungültige Auswahl für die Ordnerstruktur.")
    if type(visit_limit) is not int or not 10 <= visit_limit <= 100000:
        raise ValueError("URL-Besuchslimit muss zwischen 10 und 100'000 liegen.")
    if type(discovery_limit) is not int or not 1000 <= discovery_limit <= 1_000_000:
        raise ValueError("Discovery-Limit muss zwischen 1'000 und 1'000'000 liegen.")
    if type(page_timeout) not in (int,float) or not 1 <= page_timeout <= 60:
        raise ValueError("Seiten-Timeout muss zwischen 1 und 60 Sekunden liegen.")
    if type(http_workers) is not int or not 1 <= http_workers <= 10:
        raise ValueError("Parallelität muss zwischen 1 und 10 gleichzeitigen HTTP-Anfragen liegen.")
    if type(links_per_page) is not int or not 1 <= links_per_page <= 10000:
        raise ValueError("Links-pro-Seite-Limit muss zwischen 1 und 10'000 liegen.")
    if sitemap_height not in VALID_HEIGHTS:
        raise ValueError("Ungültige Höhe für die Sitemap-Tabelle.")
    values = {
        "download_directory": str(location),
        "flat_downloads": flat_downloads,
        "visit_limit": visit_limit,
        "discovery_limit": discovery_limit,
        "page_timeout": float(page_timeout),
        "http_workers": http_workers,
        "links_per_page": links_per_page,
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
