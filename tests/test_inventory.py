"""Regression tests for local dashboard and recursive discovery."""
from pathlib import Path
import sqlite3
from websnapshot.core import database, save
from websnapshot.inventory import dashboard, remove_site, storage_bytes


def test_dashboard_and_retention(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','2026-01-01')")
    run = save(1, {"https://example.org/": ("A", "One"),
                   "https://example.org/page": ("B", "Two")}, [], tmp_path)
    rows = dashboard(tmp_path)
    assert rows[0]["snapshots"] == 1
    assert rows[0]["pages"] == 2
    assert rows[0]["documents"] == 0
    assert storage_bytes(tmp_path) > 0
    remove_site(1, False, tmp_path)
    assert dashboard(tmp_path) == []
    with sqlite3.connect(database(tmp_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM pages WHERE run_id=?", (run,)).fetchone()[0] == 2


def test_remove_site_with_snapshots(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','2026-01-01')")
    run = save(1, {"https://example.org/": ("Title", "Text")}, [], tmp_path)
    remove_site(1, True, tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
