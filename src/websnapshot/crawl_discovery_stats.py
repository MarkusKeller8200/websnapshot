"""Persistent compact discovery diagnostics for large website crawls."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from .core import DATA, database


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS crawl_discovery_stats (
            run_id INTEGER PRIMARY KEY,
            metrics_json TEXT NOT NULL)""")


def save(run_id: int, metrics: dict, data: Path = DATA) -> None:
    init(data)
    with sqlite3.connect(database(data)) as db:
        db.execute("""INSERT OR REPLACE INTO crawl_discovery_stats
            (run_id,metrics_json) VALUES(?,?)""",
            (run_id,json.dumps(metrics,ensure_ascii=False)))


def get(run_id: int, data: Path = DATA) -> dict | None:
    init(data)
    with sqlite3.connect(database(data)) as db:
        row=db.execute(
            "SELECT metrics_json FROM crawl_discovery_stats WHERE run_id=?",
            (run_id,)).fetchone()
    return json.loads(row[0]) if row else None
