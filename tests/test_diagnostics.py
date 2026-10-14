"""Regression tests: URL explosion limits and persisted crawl diagnostics."""
from websnapshot.diagnostics import (
    canonical, path_key, record, record_quality, summary, duplicate_groups,
)
from websnapshot.core import database
import sqlite3


def test_canonical_tracking_and_parameter_order():
    assert canonical("https://example.org/page?b=2&utm_source=test&a=1#top") == (
        "https://example.org/page?a=1&b=2")
    assert canonical("https://example.org/download.php?doc_id=123") == (
        "https://example.org/download.php?doc_id=123")


def test_path_limit_groups_query_variants():
    assert path_key("https://example.org/calendar?month=1") == (
        path_key("https://example.org/calendar?month=500"))


def test_quality_storage(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
        db.execute("INSERT INTO runs(id,site_id,created_at,status,errors) VALUES (5,1,'now','complete','[]')")
    record(5,{
        "https://example.org/":("start","archived",""),
        "https://example.org/calendar?month=1":("html-link","excluded","variant-limit"),
    },tmp_path)
    record_quality(5,dict(discovered=2,visited=1,archived=1,documents=0,
        pending=1,skipped=1,errors=0,duplicate_content=0,truncated=1,
        warning="Unvollständig"),tmp_path)
    info=summary(5,tmp_path)
    assert info["sources"]["html-link"] == 1
    assert info["quality"][9] == 1
    assert info["quality"][10] == "Unvollständig"


def test_duplicate_content_counter():
    assert duplicate_groups({"a":("A","same"),"b":("B","same"),
                             "c":("C","different")}) == 1
