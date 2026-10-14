"""Background snapshot jobs with a persistent, per-website SQLite lock."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import threading
from .core import DATA, database
from .inventory import discover_and_snapshot
from .settings import get as get_capture

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
    get_capture(site_id,data)
    with _lock, _connect(data) as db:
        existing = db.execute("""SELECT id FROM jobs WHERE site_id=?
            AND state IN ('queued','running') ORDER BY id DESC LIMIT 1""", (site_id,)).fetchone()
        if existing:
            return False, existing[0]
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = db.execute("""INSERT INTO jobs(site_id,url,state,started_at,progress)
                VALUES(?,?,?,?,?)""",(site_id,url,"queued",now,"{}"))
            job_id = cur.lastrowid
            db.commit()
        except sqlite3.IntegrityError:
            existing = db.execute("""SELECT id FROM jobs WHERE site_id=?
                AND state IN ('queued','running')""",(site_id,)).fetchone()
            return False, existing[0]
    _executor.submit(_work,job_id,site_id,url,limit,data,snapshot_kind)
    return True, job_id


def _work(job_id: int, site_id: int, url: str, limit: int, data: Path, snapshot_kind: str) -> None:
    def progress(**update):
        with _connect(data) as db:
            cancelled=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(job_id,)).fetchone()
            if cancelled and cancelled[0]:
                raise JobCancelled("Vom Benutzer abgebrochen")
            db.execute("UPDATE jobs SET progress=? WHERE id=?",
                       (json.dumps(update,ensure_ascii=False),job_id))
            db.commit()
    try:
        with _connect(data) as db:
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (job_id,))
            db.commit()
        run_id, result = discover_and_snapshot(site_id,url,limit,data,progress=progress,snapshot_kind=snapshot_kind)
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
    except JobCancelled as exc:
        with _connect(data) as db:
            db.execute("UPDATE jobs SET state='cancelled',ended_at=?,message=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(),str(exc),job_id))
            db.commit()
    except Exception as exc:
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
        return cur.rowcount>0


def snapshot_job(run_id: int, data: Path = DATA) -> dict | None:
    """Return historical job metadata, including exact recorded start/end times."""
    with _connect(data) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT * FROM jobs WHERE run_id=? ORDER BY id DESC LIMIT 1",
                       (run_id,)).fetchone()
        return dict(row) if row else None
