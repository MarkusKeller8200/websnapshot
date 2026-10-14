"""Disk-backed audit of links omitted by per-page crawl protection.

The journal spills to a temporary file and never keeps all dropped URLs in
RAM. Entries become persistent only after a snapshot has been saved.
"""
from __future__ import annotations

from collections import Counter
import csv
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import SpooledTemporaryFile

from .core import DATA, database


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS crawl_link_exclusions (
            run_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            excluded_url TEXT NOT NULL,
            reason TEXT NOT NULL,
            PRIMARY KEY(run_id, source_url, excluded_url, reason)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS crawl_link_exclusions_run
            ON crawl_link_exclusions(run_id, source_url)""")


class LinkExclusionJournal:
    """Append-only spool: cheap on large crawls, deterministic on reruns."""

    def __init__(self) -> None:
        self._stream = SpooledTemporaryFile(
            max_size=1024 * 1024, mode="w+t", encoding="utf-8")
        self.total = 0
        self.per_source: Counter[str] = Counter()

    def add(self, source_url: str, excluded_urls: list[str]) -> None:
        for url in excluded_urls:
            self._stream.write(json.dumps([source_url, url],ensure_ascii=False)+"\n")
            self.total += 1
            self.per_source[source_url] += 1

    def persist(self, run_id: int, data: Path = DATA) -> None:
        init(data)
        self._stream.seek(0)
        with sqlite3.connect(database(data)) as db:
            batch=[]
            for line in self._stream:
                source,url=json.loads(line)
                batch.append((run_id,source,url,"links_per_page"))
                if len(batch)>=500:
                    db.executemany("""INSERT OR IGNORE INTO crawl_link_exclusions
                        (run_id,source_url,excluded_url,reason) VALUES(?,?,?,?)""",batch)
                    batch.clear()
            if batch:
                db.executemany("""INSERT OR IGNORE INTO crawl_link_exclusions
                    (run_id,source_url,excluded_url,reason) VALUES(?,?,?,?)""",batch)
        self.close()

    def close(self) -> None:
        self._stream.close()


def stats(run_id: int, data: Path = DATA) -> dict:
    init(data)
    with sqlite3.connect(database(data)) as db:
        count=db.execute("""SELECT COUNT(*) FROM crawl_link_exclusions
                            WHERE run_id=?""",(run_id,)).fetchone()[0]
        sources=db.execute("""SELECT COUNT(DISTINCT source_url)
                              FROM crawl_link_exclusions WHERE run_id=?""",
                           (run_id,)).fetchone()[0]
    return {"excluded_links":count,"affected_pages":sources}


def page(run_id: int, *, offset: int = 0, limit: int = 200,
         source_search: str = "", data: Path = DATA) -> tuple[int,list[dict]]:
    """Read selected rows without loading an arbitrarily large audit log."""
    init(data)
    limit=max(1,min(1000,int(limit)))
    offset=max(0,int(offset))
    sql="FROM crawl_link_exclusions WHERE run_id=?"
    args=[run_id]
    if source_search:
        # Match literal text rather than interpreting SQL LIKE wildcards.
        pattern=source_search.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
        sql+=" AND (source_url LIKE ? ESCAPE '\\' OR excluded_url LIKE ? ESCAPE '\\')"
        args.extend(["%"+pattern+"%"]*2)
    with sqlite3.connect(database(data)) as db:
        count=db.execute("SELECT COUNT(*) "+sql,args).fetchone()[0]
        records=db.execute("""SELECT source_url,excluded_url,reason """
            +sql+" ORDER BY source_url,excluded_url LIMIT ? OFFSET ?",
            (*args,limit,offset)).fetchall()
    return count,[{"Quellseite":src,"Ausgeschlossene URL":url,
                   "Grund":"Links-pro-Seite-Limit"} for src,url,_ in records]


def csv_page(run_id: int, *, offset: int = 0, limit: int = 10000,
             source_search: str = "", data: Path = DATA) -> bytes:
    limit=max(1,min(10000,int(limit)))
    _,rows=page(run_id,offset=offset,limit=min(1000,limit),
                source_search=source_search,data=data)
    stream=StringIO(newline="")
    writer=csv.writer(stream,delimiter=";",lineterminator="\r\n")
    writer.writerow(["Quellseite","Ausgeschlossene URL","Grund"])
    cursor=offset
    while rows and cursor<offset+limit:
        for row in rows:
            if cursor>=offset+limit: break
            def safe(value):
                text=str(value)
                return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text
            writer.writerow([safe(row[name]) for name in
                ("Quellseite","Ausgeschlossene URL","Grund")])
            cursor+=1
        if len(rows)<1000 or cursor>=offset+limit: break
        _,rows=page(run_id,offset=cursor,limit=min(1000,offset+limit-cursor),
                    source_search=source_search,data=data)
    return ("\ufeff"+stream.getvalue()).encode("utf-8")
