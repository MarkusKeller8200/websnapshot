"""Document inventory and explicitly requested downloads."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import sqlite3
from urllib.parse import unquote, urlsplit
import requests
from .core import DATA, AGENT, check_public, database, normalize_url

EXTS = (".pdf", ".doc", ".docx")
MAX_DOWNLOAD = 100 * 1024 * 1024


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS documents(
            run_id INTEGER NOT NULL,url TEXT NOT NULL,etag TEXT,last_modified TEXT,
            length TEXT, status TEXT NOT NULL, PRIMARY KEY(run_id,url));
        CREATE TABLE IF NOT EXISTS downloads(
            id INTEGER PRIMARY KEY,run_id INTEGER,url TEXT NOT NULL,path TEXT NOT NULL,
            bytes INTEGER NOT NULL,digest TEXT NOT NULL,downloaded_at TEXT NOT NULL);
        """)


def document_status(previous: tuple | None, current: tuple) -> str:
    if previous is None:
        return "Neu gefunden"
    a, b, size = previous
    x, y, n = current
    if a and x and a == x:
        return "Unverändert laut ETag"
    if a and x and a != x:
        return "Metadaten geändert"
    if b and y and size and n:
        if b == y and size == n:
            return "Unverändert laut Metadaten"
        if b != y or size != n:
            return "Metadaten geändert"
    return "Nicht prüfbar"


def inventory_documents(run_id: int, site_id: int, urls: set[str],
                        session: requests.Session, data: Path = DATA,
                        progress=None) -> None:
    """Only HEAD requests, never download document bodies during snapshots."""
    init(data)
    with sqlite3.connect(database(data)) as db:
        prev_run = db.execute("""SELECT d.run_id FROM documents d
          JOIN runs r ON r.id=d.run_id WHERE r.site_id=? AND d.run_id<?
          ORDER BY d.run_id DESC LIMIT 1""", (site_id, run_id)).fetchone()
        prev = {}
        if prev_run:
            prev = {u:(e,m,l) for u,e,m,l in db.execute(
                "SELECT url,etag,last_modified,length FROM documents WHERE run_id=?",
                prev_run)}
    rows = []
    for index, url in enumerate(sorted(urls), 1):
        etag = modified = length = None
        try:
            url = normalize_url(url)
            check_public(url)
            with session.head(url, timeout=(5,10), allow_redirects=False) as res:
                if res.is_redirect:
                    raise ValueError("Weiterleitung nicht verfolgt")
                if res.ok:
                    etag = res.headers.get("ETag")
                    modified = res.headers.get("Last-Modified")
                    length = res.headers.get("Content-Length")
        except (requests.RequestException, ValueError, OSError):
            pass
        current = (etag, modified, length)
        rows.append((run_id,url,etag,modified,length,document_status(prev.get(url),current)))
        if progress:
            progress(doc_checked=index)
    with sqlite3.connect(database(data)) as db:
        db.executemany("""INSERT OR REPLACE INTO documents
          (run_id,url,etag,last_modified,length,status) VALUES(?,?,?,?,?,?)""", rows)


def list_documents(run_id: int, data: Path = DATA) -> list[dict]:
    init(data)
    with sqlite3.connect(database(data)) as db:
        entries = db.execute("""SELECT url,status,etag,last_modified,length
           FROM documents WHERE run_id=? ORDER BY url""",(run_id,)).fetchall()
        downloaded = {url:(path,size) for url,path,size in db.execute(
            "SELECT url,path,bytes FROM downloads WHERE run_id=? ORDER BY id", (run_id,))}
    return [dict(url=u,status=s,etag=e,last_modified=m,length=l,
                 downloaded=downloaded.get(u)) for u,s,e,m,l in entries]


def _clean(value: str) -> str:
    value = re.sub(r'[^\w.\- ]+', "_", value, flags=re.UNICODE).strip(" .")
    return value[:100] or "unbenannt"


def destination(url: str, root: Path, flat: bool, content_type: str = "") -> Path:
    p = urlsplit(url)
    segments = [_clean(unquote(x)) for x in PurePosixPath(p.path).parts if x != "/"]
    if not segments:
        raise ValueError("Kein Dokumentname in URL")
    filename = segments[-1]
    if not filename.lower().endswith(EXTS):
        kind=content_type.lower()
        suffix=".pdf" if "application/pdf" in kind else (
            ".docx" if "wordprocessingml.document" in kind else (
            ".doc" if "msword" in kind else None))
        if not suffix:
            raise ValueError("Antwort ist kein unterstütztes PDF/Word-Dokument")
        filename=_clean(filename.rsplit(".",1)[0])+"_"+sha256(url.encode()).hexdigest()[:10]+suffix
    host = _clean(p.netloc.replace(":", "_"))
    parent = root / host if flat else root.joinpath(host, *segments[:-1])
    if p.query or flat:
        stem, suffix = filename.rsplit(".",1)
        filename = stem[:70] + "_" + sha256(url.encode()).hexdigest()[:10] + "." + suffix
    return parent / filename


def download_selected(run_id: int, urls: list[str], flat: bool = False,
                      data: Path = DATA, progress=None) -> list[dict]:
    """Save only documents explicitly selected from this run."""
    init(data)
    root = data / "downloads"
    with sqlite3.connect(database(data)) as db:
        allowed = {u for (u,) in db.execute("SELECT url FROM documents WHERE run_id=?", (run_id,))}
    outcomes = []
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    for i, url in enumerate(dict.fromkeys(urls), 1):
        if url not in allowed:
            outcomes.append({"url":url,"error":"Dokument gehört nicht zum gewählten Snapshot"})
            continue
        try:
            check_public(url)
            target = None
            temp = None
            size = 0
            digest = sha256()
            try:
                with session.get(url,stream=True,timeout=(5,30),allow_redirects=False) as res:
                    if res.is_redirect:
                        raise ValueError("Weiterleitung nicht verfolgt")
                    res.raise_for_status()
                    kind=res.headers.get("Content-Type","").lower()
                    target = destination(url,root,flat,kind)
                    if not any(x in kind for x in ("pdf","msword","wordprocessingml")):
                        raise ValueError("Antwort hat keinen PDF/Word-Inhaltstyp")
                    target.parent.mkdir(parents=True,exist_ok=True)
                    temp = target.with_name(target.name+".part")
                    with temp.open("wb") as file:
                        for chunk in res.iter_content(65536):
                            size += len(chunk)
                            if size > MAX_DOWNLOAD:
                                raise ValueError("Datei überschreitet 100 MB")
                            file.write(chunk)
                            digest.update(chunk)
                temp.replace(target)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
            with sqlite3.connect(database(data)) as db:
                db.execute("""INSERT INTO downloads
                    (run_id,url,path,bytes,digest,downloaded_at) VALUES (?,?,?,?,?,?)""",
                    (run_id,url,str(target),size,digest.hexdigest(),
                     datetime.now(timezone.utc).isoformat()))
            outcomes.append({"url":url,"path":str(target),"bytes":size})
        except (requests.RequestException,ValueError,OSError) as exc:
            outcomes.append({"url":url,"error":str(exc)})
        if progress:
            progress(done=i,total=len(urls))
    return outcomes
