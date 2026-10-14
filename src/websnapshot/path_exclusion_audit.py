"""Compact persisted summary of explicit user-configured path exclusions."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sqlite3
from .core import DATA, database


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS crawl_path_exclusions(
            run_id INTEGER NOT NULL,
            rule TEXT NOT NULL,
            excluded_count INTEGER NOT NULL,
            examples_json TEXT NOT NULL,
            PRIMARY KEY(run_id,rule))""")


class ExclusionStats:
    def __init__(self, rules: list[str]):
        self.counts=Counter({rule:0 for rule in rules})
        self.examples={rule:[] for rule in rules}
        self._sampled={rule:set() for rule in rules}
        self.total=0

    def record(self,rule: str,url: str) -> None:
        self.counts[rule]+=1
        self.total+=1
        if len(self.examples[rule])<20 and url not in self._sampled[rule]:
            self._sampled[rule].add(url)
            self.examples[rule].append(url)

    def save(self,run_id: int,data: Path=DATA) -> None:
        init(data)
        with sqlite3.connect(database(data)) as db:
            db.executemany(
                """INSERT OR REPLACE INTO crawl_path_exclusions(
                    run_id,rule,excluded_count,examples_json) VALUES(?,?,?,?)""",
                ((run_id,rule,self.counts[rule],
                  json.dumps(self.examples[rule],ensure_ascii=False))
                 for rule in self.counts))


def summary(run_id: int,data: Path=DATA) -> list[dict]:
    init(data)
    with sqlite3.connect(database(data)) as db:
        rows=db.execute("""SELECT rule,excluded_count,examples_json
            FROM crawl_path_exclusions WHERE run_id=? ORDER BY rule""",
            (run_id,)).fetchall()
    return [{"Pfadregel":rule,"Ausgeschlossene URL-Kandidaten":count,
             "Beispiele":json.loads(examples)} for rule,count,examples in rows]
