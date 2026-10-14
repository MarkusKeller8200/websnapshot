"""Background snapshot jobs with a persistent, per-website SQLite lock."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import threading
import traceback
from .job_logging import write as log_write
from .core import DATA, database
from .inventory import discover_and_snapshot
from .settings import get as get_capture
from .global_settings import get as get_global

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="websnapshot")
_lock = threading.Lock()


def _connect(data: Path):
    connection = sqlite3.connect(database(data), timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY,
        site_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        state TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        progress TEXT NOT NULL DEFAULT '{}',
        message TEXT NOT NULL DEFAULT '',
        run_id INTEGER
    )""")
    columns={r[1] for r in connection.execute("PRAGMA table_info(jobs)")}
    if "last_activity_at" not in columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN last_activity_at TEXT")
    if "last_progress_at" not in columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN last_progress_at TEXT")
    if "cancel_requested" not in columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_site
        ON jobs(site_id) WHERE state IN ('queued','running')""")
    connection.commit()
    return connection


def launch(site_id: int, url: str, limit: int, data: Path = DATA, snapshot_kind: str = 'full') -> tuple[bool, int]:
    """Atomic database claim, safe against double-clicks and independent sessions."""
    if snapshot_kind not in ('full','partial'):
        raise ValueError('Unbekannter Snapshottyp')
    capture=get_capture(site_id,data)
    crawl_config=get_global(data)
    setup={"site_url":url,"visit_limit":limit,"capture_mode":capture["mode"],
           "wait_selector":capture.get("wait_selector",""),
           "wait_ms":capture.get("wait_ms",0),"snapshot_kind":snapshot_kind,
           "discovery_limit":crawl_config["discovery_limit"],
           "page_timeout":crawl_config["page_timeout"],
           "http_workers":crawl_config["http_workers"],
           "links_per_page":crawl_config["links_per_page"],
           "crawl_scope":capture["crawl_scope"]}
    with _lock, _connect(data) as db:
        existing = db.execute("""SELECT id FROM jobs WHERE site_id=?
            AND state IN ('queued','running') ORDER BY id DESC LIMIT 1""", (site_id,)).fetchone()
        if existing:
            return False, existing[0]
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = db.execute("""INSERT INTO jobs(site_id,url,state,started_at,progress)
                VALUES(?,?,?,?,?)""",(site_id,url,"queued",now,json.dumps(setup,ensure_ascii=False)))
            job_id = cur.lastrowid
            db.commit()
        except sqlite3.IntegrityError:
            existing = db.execute("""SELECT id FROM jobs WHERE site_id=?
                AND state IN ('queued','running')""",(site_id,)).fetchone()
            return False, existing[0]
    log_write(job_id,"INFO",f"Job eingereiht: {url}; Typ={snapshot_kind}; Limit={limit}",data)
    _executor.submit(_work,job_id,site_id,url,limit,data,snapshot_kind)
    return True, job_id


def _work(job_id: int, site_id: int, url: str, limit: int, data: Path, snapshot_kind: str) -> None:
    last_logged={"visited":-1,"phase":None}
    def progress(**update):
        stamp=datetime.now(timezone.utc).isoformat()
        with _connect(data) as db:
            cancelled=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(job_id,)).fetchone()
            if cancelled and cancelled[0]:
                raise JobCancelled("Vom Benutzer abgebrochen")
            old=db.execute("SELECT progress FROM jobs WHERE id=?",(job_id,)).fetchone()
            combined={**json.loads(old[0] or "{}"),**update}
            db.execute("UPDATE jobs SET progress=?,last_activity_at=?,last_progress_at=? WHERE id=?",
                       (json.dumps(combined,ensure_ascii=False),stamp,stamp,job_id))
            db.commit()
        phase=update.get("phase")
        visited=update.get("visited",-1)
        if phase!=last_logged["phase"] or (isinstance(visited,int) and visited-last_logged["visited"]>=25):
            log_write(job_id,"INFO",f"Phase={phase}; besucht={visited}; entdeckt={update.get('discovered')}; Seiten={update.get('pages')}; Dokumente={update.get('documents')}",data)
            last_logged.update(phase=phase,visited=visited)
        for warning in update.get("limit_warnings",[]):
            warning_type=warning.split(":")[0].split(" erreicht")[0]
            if warning_type not in reported_warnings:
                reported_warnings.add(warning_type)
                log_write(job_id,"WARNING",warning,data)
    reported_warnings=set()
    try:
        log_write(job_id,"INFO","Worker gestartet",data)
        with _connect(data) as db:
            db.execute("UPDATE jobs SET state='running',last_activity_at=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(),job_id))
            db.commit()
        with _connect(data) as db:
            row=db.execute("SELECT progress FROM jobs WHERE id=?",(job_id,)).fetchone()
            submitted=json.loads(row[0] or "{}")
        config={k:submitted[k] for k in ("discovery_limit","page_timeout","http_workers","links_per_page","crawl_scope")
                if k in submitted}
        run_id, result = discover_and_snapshot(
            site_id,url,limit,data,progress=progress,snapshot_kind=snapshot_kind,
            config=config)
        with _connect(data) as db:
            previous=db.execute("SELECT progress,started_at FROM jobs WHERE id=?",(job_id,)).fetchone()
            progress_before=json.loads(previous[0] or "{}")
            ended=datetime.now(timezone.utc)
            started=datetime.fromisoformat(previous[1])
            final={**progress_before,**{k:v for k,v in result.items() if k!='errors'},
                   "snapshot_kind":snapshot_kind,"phase":"Fertig",
                   "duration_seconds":round((ended-started).total_seconds(),2),
                   "errors_count":len(result["errors"]),
                   "percent":100 if snapshot_kind=="partial" and not result["pending"] else None}
            db.execute("""UPDATE jobs SET state='complete', ended_at=?,
                run_id=?, message=?, progress=? WHERE id=?""",
                (ended.isoformat(),run_id,
                 f"{result['pages']} Seiten, {result['documents']} Dokumente",
                 json.dumps(final,ensure_ascii=False),job_id))
            db.commit()
        for issue in result.get("errors",[]):
            log_write(job_id,"WARNING",issue,data)
        log_write(job_id,"INFO",f"Abgeschlossen: Snapshot #{run_id}, {result['pages']} Seiten, {result['documents']} Dokumente",data)
    except JobCancelled as exc:
        log_write(job_id,"WARNING",str(exc),data)
        with _connect(data) as db:
            db.execute("UPDATE jobs SET state='cancelled',ended_at=?,message=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(),str(exc),job_id))
            db.commit()
    except Exception as exc:
        log_write(job_id,"ERROR",traceback.format_exc(),data)
        with _connect(data) as db:
            db.execute("""UPDATE jobs SET state='failed', ended_at=?,
                message=? WHERE id=?""",
                (datetime.now(timezone.utc).isoformat(),str(exc)[:2000],job_id))
            db.commit()


def latest(site_id: int, data: Path = DATA) -> dict | None:
    with _connect(data) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM jobs WHERE site_id=? ORDER BY id DESC LIMIT 1",
                         (site_id,)).fetchone()
        return dict(row) if row else None


def running(data: Path = DATA) -> int:
    with _connect(data) as db:
        return db.execute("""SELECT COUNT(*) FROM jobs
            WHERE state IN ('queued','running')""").fetchone()[0]


def recover_interrupted(data: Path = DATA) -> int:
    """Explicit recovery action for after a process restart, never silently unlock."""
    with _connect(data) as db:
        cur = db.execute("""UPDATE jobs SET state='interrupted',ended_at=?,
            message='Prozess beendet; Snapshot muss neu gestartet werden.'
            WHERE state IN ('queued','running')""",
            (datetime.now(timezone.utc).isoformat(),))
        db.commit()
        return cur.rowcount


class JobCancelled(Exception):
    pass

def request_cancel(site_id: int, data: Path = DATA) -> bool:
    """Request cooperative stop; worker releases unique job lock after next callback."""
    with _connect(data) as db:
        cur=db.execute("""UPDATE jobs SET cancel_requested=1 WHERE site_id=?
            AND state IN ('queued','running')""",(site_id,))
        db.commit()
        requested=cur.rowcount>0
    if requested:
        job=latest(site_id,data)
        if job:
            log_write(job["id"],"WARNING","Abbruch angefordert",data)
    return requested


def snapshot_job(run_id: int, data: Path = DATA) -> dict | None:
    """Return historical job metadata, including exact recorded start/end times."""
    with _connect(data) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT * FROM jobs WHERE run_id=? ORDER BY id DESC LIMIT 1",
                       (run_id,)).fetchone()
        return dict(row) if row else None
