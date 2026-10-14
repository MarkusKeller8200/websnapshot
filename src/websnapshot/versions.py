"""Full/partial snapshot metadata, delta resolution and safe removal."""
from pathlib import Path
import sqlite3
from .core import DATA, database, save
from hashlib import sha256

def init(data: Path = DATA):
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS snapshot_meta(
           run_id INTEGER PRIMARY KEY, kind TEXT NOT NULL, parent_id INTEGER,
           FOREIGN KEY(run_id) REFERENCES runs(id))""")

def kind(run_id: int, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        result=db.execute("SELECT kind,parent_id FROM snapshot_meta WHERE run_id=?",(run_id,)).fetchone()
    return result or ("full",None)  # existing 0.1-0.5 snapshots

def effective_pages(run_id: int, data: Path = DATA) -> dict:
    init(data)
    with sqlite3.connect(database(data)) as db:
        seen=set()
        chain=[]
        cursor=run_id
        while cursor is not None:
            if cursor in seen:
                raise ValueError("Snapshot-Abhängigkeitszyklus")
            seen.add(cursor)
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(cursor,)).fetchone():
                raise ValueError("Basis-Snapshot fehlt")
            chain.append(cursor)
            cursor=kind(cursor,data)[1]
        pages={}
        for ident in reversed(chain):
            pages.update({u:(t,c,h) for u,t,c,h in db.execute(
                "SELECT url,title,content,digest FROM pages WHERE run_id=?",(ident,))})
        return pages

def latest_run(site_id: int, data: Path = DATA):
    with sqlite3.connect(database(data)) as db:
        row=db.execute("SELECT id FROM runs WHERE site_id=? ORDER BY id DESC LIMIT 1",(site_id,)).fetchone()
        return row[0] if row else None

def mark_full(run_id: int, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        db.execute("INSERT OR REPLACE INTO snapshot_meta VALUES(?,'full',NULL)",(run_id,))

def save_partial(site_id: int, observed: dict, errors: list, parent_id: int, data: Path = DATA):
    existing=effective_pages(parent_id,data)
    if not observed:
        raise ValueError("Keine Seiten erfolgreich geprüft; kein Delta gespeichert")
    # Only changed/new pages; unchanged content is inherited from parent.
    delta={u: (title,content) for u,(title,content) in observed.items()
           if u not in existing or sha256(content.encode()).hexdigest()!=existing[u][2]}
    # save() refuses empty snapshots; handle the unchanged case transactionally.
    from datetime import datetime,timezone
    import json
    with sqlite3.connect(database(data)) as db:
        if db.execute("SELECT site_id FROM runs WHERE id=?",(parent_id,)).fetchone()!=(site_id,):
            raise ValueError("Basis-Snapshot gehört zu einer anderen Website")
        run_id=db.execute("INSERT INTO runs(site_id,created_at,status,errors) VALUES(?,?,?,?)",
          (site_id,datetime.now(timezone.utc).isoformat(),
           "partial" if errors else "complete",json.dumps(errors))).lastrowid
        db.executemany("INSERT INTO pages VALUES(?,?,?,?,?)",
          [(run_id,u,t,c,sha256(c.encode()).hexdigest()) for u,(t,c) in delta.items()])
        db.execute("INSERT INTO snapshot_meta VALUES(?,'partial',?)",(run_id,parent_id))
    return run_id, len(delta)

def remove_snapshot(site_id: int, run_id: int, data: Path = DATA):
    init(data)
    with sqlite3.connect(database(data)) as db:
        row=db.execute("SELECT site_id FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row or row[0]!=site_id:
            raise ValueError("Snapshot nicht gefunden")
        if db.execute("SELECT 1 FROM snapshot_meta WHERE parent_id=? LIMIT 1",(run_id,)).fetchone():
            raise ValueError("Snapshot ist Grundlage eines weiteren Snapshots")
        if kind(run_id,data)[0]=="partial":
            raise ValueError("Delta-Snapshots können nicht einzeln gelöscht werden")
        db.execute("BEGIN")
        for table in ("downloads","documents","inventory","crawl_urls","crawl_quality","crawl_performance","document_links","pages","snapshot_meta"):
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
            if exists:
                db.execute(f"DELETE FROM {table} WHERE {'run_id' if table!='inventory' else 'run_id'}=?",(run_id,))
        db.execute("DELETE FROM runs WHERE id=?",(run_id,))
