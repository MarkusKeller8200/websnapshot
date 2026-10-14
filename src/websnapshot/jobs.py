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
from .settings import require_available

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
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_site
        ON jobs(site_id) WHERE state IN ('queued','running')""")
    connection.commit()
    return connection


def launch(site_id: int, url: str, limit: int, data: Path = DATA) -> tuple[bool, int]:
    """Atomic database claim, safe against double-clicks and independent sessions."""
    require_available(site_id, data)
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
    _executor.submit(_work,job_id,site_id,url,limit,data)
    return True, job_id


def _work(job_id: int, site_id: int, url: str, limit: int, data: Path) -> None:
    def progress(**update):
        with _connect(data) as db:
            db.execute("UPDATE jobs SET progress=? WHERE id=?",
                       (json.dumps(update,ensure_ascii=False),job_id))
            db.commit()
    try:
        with _connect(data) as db:
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (job_id,))
            db.commit()
        run_id, result = discover_and_snapshot(site_id,url,limit,data,progress=progress)
        with _connect(data) as db:
            db.execute("""UPDATE jobs SET state='complete', ended_at=?,
                run_id=?, message=?, progress=? WHERE id=?""",
                (datetime.now(timezone.utc).isoformat(),run_id,
                 f"{result['pages']} Seiten, {result['documents']} Dokumente",
                 json.dumps({k:v for k,v in result.items() if k!='errors'}),job_id))
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
