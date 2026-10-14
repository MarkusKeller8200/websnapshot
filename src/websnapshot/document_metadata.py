"""Per-snapshot document metadata, change checks and all referencing pages."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests

from .core import DATA, AGENT, database, check_public
from .document_properties import extract_properties
from .document_renamer import filename_from_headers, resolve_extension

MAX_METADATA_BYTES = 20*1024*1024
MAX_PROBE_SELECTION = 20


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS document_referrers (
            run_id INTEGER NOT NULL,
            document_url TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            PRIMARY KEY (run_id,document_url,source_url,source_type));
        CREATE INDEX IF NOT EXISTS idx_doc_refs_url
            ON document_referrers(run_id,document_url);
        CREATE TABLE IF NOT EXISTS document_properties (
            run_id INTEGER NOT NULL, url TEXT NOT NULL,
            properties_json TEXT NOT NULL DEFAULT '{}',
            sha256 TEXT, examined_at TEXT NOT NULL,
            status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(run_id,url));
        """)


def save_references(run_id: int, references: dict[str,set[tuple[str,str]]],
                    data: Path = DATA) -> None:
    init(data)
    with sqlite3.connect(database(data)) as db:
        for document_url,sources in references.items():
            db.executemany("""INSERT OR IGNORE INTO document_referrers
                (run_id,document_url,source_url,source_type) VALUES(?,?,?,?)""",
                ((run_id,document_url,source,type_name)
                 for source,type_name in sources))


def list_references(run_id: int, url: str, data: Path = DATA) -> list[dict]:
    init(data)
    with sqlite3.connect(database(data)) as db:
        entries=db.execute("""SELECT source_url,source_type
            FROM document_referrers WHERE run_id=? AND document_url=?
            ORDER BY source_type,source_url""",(run_id,url)).fetchall()
    return [{"url":link,"type":source} for link,source in entries]


def info_by_url(run_id: int, data: Path = DATA) -> dict[str,dict]:
    init(data)
    with sqlite3.connect(database(data)) as db:
        info={url:dict(properties=json.loads(properties or "{}"),
                       sha256=digest,examined_at=checked,
                       property_status=status,property_error=err)
              for url,properties,digest,checked,status,err in db.execute(
                """SELECT url,properties_json,sha256,examined_at,status,error
                   FROM document_properties WHERE run_id=?""",(run_id,))}
        counts={url:(n,s) for url,n,s in db.execute(
            """SELECT document_url,COUNT(*),MIN(source_url)
               FROM document_referrers WHERE run_id=? GROUP BY document_url""",
            (run_id,))}
    for url,data_entry in info.items():
        data_entry["references"]=counts.get(url,(0,None))[0]
        data_entry["found_on"]=counts.get(url,(0,None))[1]
    for url,(count,source) in counts.items():
        info.setdefault(url,dict(references=count,found_on=source))
    return info


def _previous_hash(run_id: int,url: str,data: Path) -> str | None:
    with sqlite3.connect(database(data)) as db:
        row=db.execute("""SELECT p.sha256 FROM document_properties p
            JOIN runs r ON r.id=p.run_id
            WHERE p.url=? AND p.run_id<? AND r.site_id=(
                SELECT site_id FROM runs WHERE id=?)
            AND p.sha256 IS NOT NULL ORDER BY p.run_id DESC LIMIT 1""",
            (url,run_id,run_id)).fetchone()
        if row:
            return row[0]
        row=db.execute("""SELECT d.digest FROM downloads d
            JOIN runs r ON r.id=d.run_id
            WHERE d.url=? AND r.site_id=(SELECT site_id FROM runs WHERE id=?)
            ORDER BY d.id DESC LIMIT 1""",(url,run_id)).fetchone()
    return row[0] if row else None


def store_properties(run_id: int,url: str,props: dict,digest: str | None,
                     *,data: Path=DATA,error: str="") -> str:
    init(data)
    before=_previous_hash(run_id,url,data) if digest else None
    if error:
        status="Fehler beim Auslesen"
    elif not digest:
        status="Ohne Dateiprüfsumme"
    elif before is None:
        status="Erstmals anhand Datei geprüft"
    elif before==digest:
        status="Unverändert (SHA-256)"
    else:
        status="Inhalt geändert (SHA-256)"
    with sqlite3.connect(database(data)) as db:
        db.execute("""INSERT INTO document_properties
            (run_id,url,properties_json,sha256,examined_at,status,error)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(run_id,url) DO UPDATE SET
            properties_json=excluded.properties_json,sha256=excluded.sha256,
            examined_at=excluded.examined_at,status=excluded.status,error=excluded.error""",
            (run_id,url,json.dumps(props,ensure_ascii=False),digest,
             datetime.now(timezone.utc).isoformat(),status,error))
    return status


def _robots_allowed(session: requests.Session,url: str, cache: dict) -> bool:
    origin=urlsplit(url).scheme+"://"+urlsplit(url).netloc
    if origin not in cache:
        check_public(origin)
        rules=RobotFileParser()
        robots_url=origin+"/robots.txt"
        with session.get(robots_url,timeout=(3,5),
                         allow_redirects=False,stream=True) as response:
            if response.status_code==404:
                cache[origin]=None
            else:
                response.raise_for_status()
                if response.is_redirect:
                    raise ValueError("robots.txt leitet weiter; Abruf nicht geprüft")
                text=bytearray()
                for chunk in response.iter_content(8192):
                    text.extend(chunk)
                    if len(text)>200_000:
                        raise ValueError("robots.txt zu gross")
                rules.parse(text.decode("utf-8","replace").splitlines())
                cache[origin]=rules
    return cache[origin] is None or cache[origin].can_fetch(AGENT,url)


def probe_selected(run_id: int, urls: list[str], *,
                   data: Path=DATA,max_bytes: int=MAX_METADATA_BYTES) -> list[dict]:
    """Opt-in temporary full GET to read embedded Office metadata *before saving*.

    This transfers the bytes but never stores the file in the download folder.
    Every network request is bounded; no redirects or embedded content executes.
    """
    from .documents import init as init_documents
    init_documents(data)
    init(data)
    urls=list(dict.fromkeys(urls))
    if len(urls)>MAX_PROBE_SELECTION:
        raise ValueError(f"Pro Abfrage höchstens {MAX_PROBE_SELECTION} Dokumente auswählen.")
    with sqlite3.connect(database(data)) as db:
        permitted={url for (url,) in db.execute(
            "SELECT url FROM documents WHERE run_id=?",(run_id,))}
    outcomes=[]
    session=requests.Session()
    session.headers["User-Agent"]=AGENT
    robots_cache={}
    tmp_dir=data/"metadata_tmp"
    tmp_dir.mkdir(parents=True,exist_ok=True)
    for url in urls:
        if url not in permitted:
            outcomes.append({"url":url,"error":"Nicht im Dokumentinventar"})
            continue
        path=None
        try:
            check_public(url)
            if not _robots_allowed(session,url,robots_cache):
                raise ValueError("robots.txt untersagt das Abrufen dieses Dokuments")
            with session.get(url,stream=True,timeout=(5,15),
                             allow_redirects=False) as res:
                if res.is_redirect:
                    raise ValueError("Dokument-Weiterleitung wird nicht verfolgt")
                res.raise_for_status()
                content_type=res.headers.get("Content-Type","").lower()
                source=filename_from_headers(url,res.headers.get("Content-Disposition"))
                ext=resolve_extension(source,content_type)
                length=res.headers.get("Content-Length")
                if length and length.isdecimal() and int(length)>max_bytes:
                    raise ValueError("Dokument überschreitet Metadaten-Abfragelimit (20 MB)")
                digest=sha256()
                size=0
                with NamedTemporaryFile(mode="wb",suffix=ext,dir=tmp_dir,
                                        prefix="properties_",delete=False) as handle:
                    path=Path(handle.name)
                    for chunk in res.iter_content(65536):
                        size+=len(chunk)
                        if size>max_bytes:
                            raise ValueError("Dokument überschreitet Metadaten-Abfragelimit (20 MB)")
                        handle.write(chunk)
                        digest.update(chunk)
            props=extract_properties(path,ext)
            status=store_properties(run_id,url,props,digest.hexdigest(),data=data)
            outcomes.append({"url":url,"status":status,
                             "properties":props,"bytes":size})
        except (requests.RequestException,ValueError,OSError) as exc:
            store_properties(run_id,url,{},None,data=data,error=str(exc))
            outcomes.append({"url":url,"error":str(exc)})
        finally:
            if path:
                path.unlink(missing_ok=True)
    return outcomes
