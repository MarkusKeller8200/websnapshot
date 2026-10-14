"""URL discovery protection and persistent crawl diagnostics."""
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re
import sqlite3
from .core import DATA, database, normalize_url

TRACKING = {"utm_source","utm_medium","utm_campaign","utm_content","utm_term",
            "gclid","fbclid","msclkid","_ga"}
MAX_DISCOVERED = 10000
MAX_PER_PATH = 200
MAX_PER_PAGE = 300

def canonical(url: str) -> str:
    url=normalize_url(url)
    p=urlsplit(url)
    params=sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                  if k.lower() not in TRACKING and not k.lower().startswith("utm_"))
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(params,doseq=True),""))

def path_key(url: str) -> str:
    p=urlsplit(url)
    # Preserve paths: bound combinatorial query variants per path, not entire directories.
    return p.path

def init(data: Path = DATA):
    with sqlite3.connect(database(data)) as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS crawl_urls (
          run_id INTEGER NOT NULL, url TEXT NOT NULL,
          source TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(run_id,url));
        CREATE TABLE IF NOT EXISTS crawl_quality (
          run_id INTEGER PRIMARY KEY, discovered INTEGER, visited INTEGER,
          archived INTEGER, documents INTEGER, pending INTEGER, skipped INTEGER,
          errors INTEGER, duplicate_content INTEGER, truncated INTEGER,
          warning TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS document_links (
          run_id INTEGER NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
          PRIMARY KEY(run_id,url));
        """)

def record(run_id: int, entries: dict, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        db.executemany("INSERT OR REPLACE INTO crawl_urls(run_id,url,source,status,reason) VALUES(?,?,?,?,?)",
            [(run_id,u,*record) for u,record in entries.items()])

def record_quality(run_id: int, stats: dict, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        columns=("discovered","visited","archived","documents","pending","skipped",
                 "errors","duplicate_content","truncated","warning")
        db.execute("INSERT OR REPLACE INTO crawl_quality VALUES("+",".join("?" for _ in range(11))+")",
                   (run_id,*[stats.get(k,0 if k!="warning" else "") for k in columns]))

def summary(run_id: int, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        rows=db.execute("SELECT source,status,reason,url FROM crawl_urls WHERE run_id=?",(run_id,)).fetchall()
        record=db.execute("SELECT * FROM crawl_quality WHERE run_id=?",(run_id,)).fetchone()
    return {"sources":dict(Counter(r[0] for r in rows)),
            "statuses":dict(Counter(r[1] for r in rows)),
            "reasons":dict(Counter(r[2] for r in rows if r[2])),
            "paths":Counter(urlsplit(r[3]).path for r in rows).most_common(20),
            "parameters":Counter(k for r in rows for k,v in parse_qsl(urlsplit(r[3]).query)).most_common(20),
            "quality":record}

def duplicate_groups(pages: dict) -> int:
    from hashlib import sha256
    return len(pages)-len({sha256(content.encode()).digest() for _,content in pages.values()})
