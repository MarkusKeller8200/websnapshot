import sqlite3
import pytest
from websnapshot.core import database, compare
from websnapshot.versions import mark_full, save_partial, effective_pages, remove_snapshot
from websnapshot.core import save

def test_delta_and_baseline_delete_protection(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    first=save(1,{"https://example.org/":("Titel","Version 1"),
                  "https://example.org/a":("A","Gleich")},[],tmp_path)
    mark_full(first,tmp_path)
    second,count=save_partial(1,{"https://example.org/":("Titel","Version 2"),
                 "https://example.org/a":("A","Gleich")},[],first,tmp_path)
    assert count==1
    assert len(effective_pages(second,tmp_path))==2
    assert len(compare(first,second,tmp_path))==1
    with pytest.raises(ValueError,match="Grundlage"):
        remove_snapshot(1,first,tmp_path)
    with pytest.raises(ValueError,match="Delta"):
        remove_snapshot(1,second,tmp_path)

def test_unreferenced_full_can_be_removed(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    run=save(1,{"https://example.org/":("Titel","Text")},[],tmp_path)
    mark_full(run,tmp_path)
    remove_snapshot(1,run,tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]==0
