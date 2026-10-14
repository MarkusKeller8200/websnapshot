"""Low-overhead timing summaries persisted after snapshot completion.

Measurements use monotonic clocks. Values in milliseconds are aggregated
without keeping an unbounded list of individual 200k URL samples.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from time import perf_counter
import json
import sqlite3

from .core import DATA, database

class Timings:
    def __init__(self):
        self._groups={}

    def observe(self, phase: str, duration_seconds: float, url: str = "") -> None:
        ms=max(0.,duration_seconds*1000.)
        entry=self._groups.setdefault(phase,dict(count=0,sum_ms=0.0,
            min_ms=None,max_ms=None,slowest_url=""))
        entry["count"]+=1
        entry["sum_ms"]+=ms
        entry["min_ms"]=ms if entry["min_ms"] is None else min(entry["min_ms"],ms)
        if entry["max_ms"] is None or ms>entry["max_ms"]:
            entry["max_ms"]=ms
            entry["slowest_url"]=url[:2048]

    def summary(self) -> dict:
        result={}
        for name,stats in self._groups.items():
            result[name]=dict(
                count=stats["count"],min_ms=round(stats["min_ms"],1),
                max_ms=round(stats["max_ms"],1),
                avg_ms=round(stats["sum_ms"]/stats["count"],1),
                total_ms=round(stats["sum_ms"],1),
                slowest_url=stats["slowest_url"])
        return result


def init(data: Path = DATA):
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS crawl_performance (
            run_id INTEGER PRIMARY KEY,
            metrics_json TEXT NOT NULL,
            static_pages INTEGER NOT NULL DEFAULT 0,
            browser_static_pages INTEGER NOT NULL DEFAULT 0,
            browser_dynamic_pages INTEGER NOT NULL DEFAULT 0,
            browser_unknown_pages INTEGER NOT NULL DEFAULT 0,
            timeouts INTEGER NOT NULL DEFAULT 0
        )""")


def save(run_id: int, timings: Timings, *, static_pages: int,
         browser_static_pages: int, browser_dynamic_pages: int,
         browser_unknown_pages: int = 0, timeouts: int = 0, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        db.execute("""INSERT OR REPLACE INTO crawl_performance
          (run_id,metrics_json,static_pages,browser_static_pages,
           browser_dynamic_pages,browser_unknown_pages,timeouts) VALUES (?,?,?,?,?,?,?)""",
          (run_id,json.dumps(timings.summary(),ensure_ascii=False),
           static_pages,browser_static_pages,browser_dynamic_pages,
           browser_unknown_pages,timeouts))


def get(run_id: int, data: Path = DATA) -> dict | None:
    init(data)
    with sqlite3.connect(database(data)) as db:
        row=db.execute("""SELECT metrics_json,static_pages,browser_static_pages,
          browser_dynamic_pages,browser_unknown_pages,timeouts FROM crawl_performance WHERE run_id=?""",
          (run_id,)).fetchone()
    return None if row is None else dict(
        timings=json.loads(row[0]),static_pages=row[1],
        browser_static_pages=row[2],browser_dynamic_pages=row[3],
        browser_unknown_pages=row[4],timeouts=row[5])
