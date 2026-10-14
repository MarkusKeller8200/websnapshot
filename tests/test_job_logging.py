"""Persistent job log and heartbeat regression tests."""
from pathlib import Path
from unittest.mock import patch
import sqlite3
from websnapshot.core import database
from websnapshot.job_logging import write, read, log_path
from websnapshot.jobs import launch, latest


def test_persistent_log(tmp_path: Path):
    write(3,"INFO","Start",tmp_path)
    write(3,"ERROR","Traceback: example",tmp_path)
    text=read(3,tmp_path)
    assert "[INFO] Start" in text
    assert "[ERROR] Traceback: example" in text
    assert log_path(3,tmp_path).exists()


def test_missing_log(tmp_path: Path):
    assert "keine Logdatei" in read(99,tmp_path)


def test_job_launch_creates_log_and_fields(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    with patch("websnapshot.jobs._executor.submit"):
        created,job_id=launch(1,"https://example.org/",10,tmp_path)
    assert created
    assert "eingereiht" in read(job_id,tmp_path)
    assert "last_activity_at" in latest(1,tmp_path)
    assert "last_progress_at" in latest(1,tmp_path)
