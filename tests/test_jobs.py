"""Job database locking and failure-status tests."""
import sqlite3
from pathlib import Path
from unittest.mock import patch
from websnapshot.core import database
from websnapshot.jobs import launch, latest, recover_interrupted

def test_only_one_job_per_site(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    with patch("websnapshot.jobs._executor.submit"):
        started, first = launch(1, "https://example.org/", 10, tmp_path)
        duplicate, same = launch(1, "https://example.org/", 10, tmp_path)
    assert started and not duplicate and first == same
    assert latest(1,tmp_path)["state"] == "queued"
    assert recover_interrupted(tmp_path) == 1
    with patch("websnapshot.jobs._executor.submit"):
        again, second = launch(1,"https://example.org/",10,tmp_path)
    assert again and second != first
