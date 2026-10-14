"""Erfassungsprofile: Migration und bewusst blockierter Browsermodus."""
import sqlite3
import pytest
from websnapshot.core import database
from websnapshot.settings import get, set_settings, require_available


def test_site_modes(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    assert get(1,tmp_path)["mode"] == "static"
    require_available(1,tmp_path)
    set_settings(1,"browser","#main",2500,tmp_path)
    assert get(1,tmp_path) == {
        "mode":"browser","wait_selector":"#main","wait_ms":2500,
        "crawl_scope":"auto"}
    require_available(1,tmp_path)
    set_settings(1,"static","",1500,tmp_path)
    require_available(1,tmp_path)


def test_validation(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    with pytest.raises(ValueError):
        set_settings(1,"automatic","",100,tmp_path)
    with pytest.raises(ValueError):
        set_settings(1,"browser","",40000,tmp_path)
    with pytest.raises(ValueError):
        set_settings(999,"static","",100,tmp_path)
