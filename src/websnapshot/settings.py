"""Website-spezifische Erfassungsprofile für WebSnapshot 0.5.0.

Der Browsermodus ist für 0.6.0 reserviert und wird hier nicht ausgeführt.
"""
from pathlib import Path
import sqlite3
from .core import DATA, database

STATIC = "static"
BROWSER = "browser"
MODES = {STATIC: "Statisch (verfügbar)", BROWSER: "Browser / Playwright (ab 0.6.0)"}


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS site_settings (
            site_id INTEGER PRIMARY KEY, mode TEXT NOT NULL DEFAULT 'static'
            CHECK(mode IN ('static','browser')),
            wait_selector TEXT NOT NULL DEFAULT '',
            wait_ms INTEGER NOT NULL DEFAULT 1500
            CHECK(wait_ms BETWEEN 0 AND 30000),
            FOREIGN KEY(site_id) REFERENCES sites(id))""")


def get(site_id: int, data: Path = DATA) -> dict:
    init(data)
    with sqlite3.connect(database(data)) as db:
        row = db.execute("SELECT mode,wait_selector,wait_ms FROM site_settings WHERE site_id=?",
                         (site_id,)).fetchone()
    return {"mode": row[0], "wait_selector": row[1], "wait_ms": row[2]} if row else {
        "mode": STATIC, "wait_selector": "", "wait_ms": 1500}


def set_settings(site_id: int, mode: str, wait_selector: str = "",
                 wait_ms: int = 1500, data: Path = DATA) -> None:
    if mode not in MODES or not isinstance(wait_ms, int) or not 0 <= wait_ms <= 30000:
        raise ValueError("Ungültige Erfassungseinstellungen")
    if len(wait_selector) > 500:
        raise ValueError("CSS-Selektor ist zu lang")
    init(data)
    with sqlite3.connect(database(data)) as db:
        if not db.execute("SELECT id FROM sites WHERE id=?", (site_id,)).fetchone():
            raise ValueError("Website nicht gefunden")
        db.execute("""INSERT INTO site_settings(site_id,mode,wait_selector,wait_ms)
            VALUES(?,?,?,?) ON CONFLICT(site_id) DO UPDATE SET
            mode=excluded.mode, wait_selector=excluded.wait_selector,
            wait_ms=excluded.wait_ms""",(site_id,mode,wait_selector.strip(),wait_ms))


def require_available(site_id: int, data: Path = DATA) -> None:
    mode = get(site_id,data)["mode"]
    if mode != STATIC:
        raise ValueError("Browsermodus ist vorbereitet, aber erst ab Version 0.6.0 ausführbar. "
                         "Bitte den statischen Modus auswählen.")
