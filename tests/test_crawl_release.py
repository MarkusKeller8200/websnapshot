from pathlib import Path
import sqlite3
from unittest.mock import patch

from websnapshot.core import database
from websnapshot.jobs import launch, latest, request_cancel
from websnapshot.documents import destination


def test_cancel_requested_for_one_site(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    with patch("websnapshot.jobs._executor.submit"):
        ok, job_id = launch(1,"https://example.org/",20,tmp_path)
    assert ok
    assert request_cancel(1,tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        assert db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(job_id,)).fetchone()[0]==1
    assert not request_cancel(2,tmp_path)


def test_php_document_filename(tmp_path: Path):
    url="https://example.org/download.php?action=download&doc_id=123"
    target=destination(url,tmp_path,False,"application/pdf")
    assert target.suffix==".pdf"
    assert target.parent==tmp_path/"example.org"
    assert target.name.startswith("download_")
