"""Historische Jobs: Startkonfiguration und permanent gespeicherte Laufzeit."""
import sqlite3
from unittest.mock import patch
from websnapshot.core import database
from websnapshot.jobs import launch, snapshot_job


def test_snapshot_job_history_and_settings(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
        db.execute("""INSERT INTO runs(id,site_id,created_at,status,errors)
                      VALUES (42,1,'now','partial','["Schutzlimit erreicht"]')""")
    with patch("websnapshot.jobs._executor.submit"):
        created, jid=launch(1,"https://example.org/",1000,tmp_path,"full")
    assert created
    with sqlite3.connect(database(tmp_path)) as db:
        import json
        start_info=json.loads(db.execute("SELECT progress FROM jobs WHERE id=?",(jid,)).fetchone()[0])
        assert start_info["visit_limit"]==1000
        assert start_info["snapshot_kind"]=="full"
        db.execute("UPDATE jobs SET run_id=?,state='complete',ended_at='2026-10-14T16:30:00+00:00' WHERE id=?",(42,jid))
    job=snapshot_job(42,tmp_path)
    assert job is not None
    assert job["id"]==jid
    assert job["ended_at"]=="2026-10-14T16:30:00+00:00"
    assert snapshot_job(999,tmp_path) is None
