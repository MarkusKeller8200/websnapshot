"""Mocked crawl tests: timing persistence, concurrency, discovery cap and timeouts."""
from pathlib import Path
import sqlite3

import requests

from websnapshot.core import database
from websnapshot.inventory import discover_and_snapshot
from websnapshot.performance import get as get_performance


def test_static_crawl_timings_timeout_and_limits(tmp_path,monkeypatch):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    monkeypatch.setattr("websnapshot.inventory.check_public",lambda _url: None)
    from websnapshot import inventory

    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        assert timeout==3.0
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("/sitemap.xml"):
            return (b"<urlset><url><loc>https://example.org/okay</loc></url>"
                    b"<url><loc>https://example.org/slow</loc></url></urlset>","application/xml")
        if url.endswith("/slow"):
            raise requests.ReadTimeout("Read timed out (3 seconds)")
        return (b"<html><title>ok</title><body>Valid content</body></html>","text/html")

    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    progress=[]
    run_id,result=discover_and_snapshot(1,"https://example.org/",limit=10,
        data=tmp_path,progress=lambda **kw:progress.append(kw),
        config={"discovery_limit":1000,"page_timeout":3.0,"http_workers":3})
    assert result["static_pages"]==2
    assert result["browser_dynamic_pages"]==0
    assert result["timeouts"]==1
    assert result["http_workers"]==3
    perf=get_performance(run_id,tmp_path)
    assert perf["timeouts"]==1
    assert perf["static_pages"]==2
    assert perf["timings"]["page_fetch"]["count"]==3
    assert perf["timings"]["page_fetch"]["min_ms"]<=perf["timings"]["page_fetch"]["avg_ms"]<=perf["timings"]["page_fetch"]["max_ms"]
    assert "snapshot_save" in perf["timings"]
    assert "diagnostic_save" in perf["timings"]
    assert "discovery_initial" in perf["timings"]
    assert progress[-1]["phase"]=="Fertig"
    assert "performance" in progress[-1]


def test_browser_heuristic_counts(tmp_path,monkeypatch):
    from websnapshot import inventory
    from websnapshot.settings import set_settings
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    set_settings(1,"browser",data=tmp_path)
    monkeypatch.setattr(inventory,"check_public",lambda _url: None)
    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        if url.endswith("robots.txt"): return b"","text/plain"
        return b"<urlset></urlset>","application/xml"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)

    class FakeBrowser:
        def __init__(self,start,settings):
            self.last_page_kind="browser_dynamic"
            assert settings["page_timeout"]==3.0
        def fetch(self,url):
            return "Dynamic","Text from browser renderer",[]
        def close(self):
            pass

    import websnapshot.browser
    monkeypatch.setattr(websnapshot.browser,"BrowserRenderer",FakeBrowser)
    run_id,result=discover_and_snapshot(1,"https://example.org/",limit=1,
        data=tmp_path,config={"discovery_limit":1000,"page_timeout":3.0,"http_workers":3})
    assert result["static_pages"]==0
    assert result["browser_dynamic_pages"]==1
    assert get_performance(run_id,tmp_path)["browser_dynamic_pages"]==1


def test_static_page_requests_really_run_in_parallel(tmp_path,monkeypatch):
    from threading import Lock
    from time import sleep
    from websnapshot import inventory
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    lock=Lock()
    active=0
    peak=0
    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        nonlocal active,peak
        if url.endswith("robots.txt"):
            return b"","text/plain"
        if url.endswith("sitemap.xml"):
            return b"<urlset><url><loc>https://example.org/page2</loc></url></urlset>","application/xml"
        with lock:
            active+=1
            peak=max(peak,active)
        try:
            sleep(0.045)
            return b"<html><body>Hello</body></html>","text/html"
        finally:
            with lock:
                active-=1
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    run,result=discover_and_snapshot(1,"https://example.org/",limit=2,
        data=tmp_path,
        config={"discovery_limit":1000,"page_timeout":3.0,"http_workers":2})
    assert result["static_pages"]==2
    assert peak==2
    assert get_performance(run,tmp_path)["timings"]["page_fetch"]["count"]==2
