"""Links-per-page limits: keep every dropped link and its exact source URL."""
from io import StringIO
import csv
import sqlite3

import pytest
from websnapshot.core import database
from websnapshot.global_settings import save as save_settings,get as get_settings
from websnapshot.inventory import discover_and_snapshot
from websnapshot.link_exclusions import (
    LinkExclusionJournal,stats,page,csv_page,
)


def test_global_limit_default_and_range(tmp_path):
    assert get_settings(tmp_path)["links_per_page"]==1000
    options=dict(download_directory=str(tmp_path/"downloads"),flat_downloads=False,
                 visit_limit=2000,sitemap_height=800,data=tmp_path)
    stored=save_settings(**options,links_per_page=1800)
    assert stored["links_per_page"]==1800
    assert get_settings(tmp_path)["links_per_page"]==1800
    with pytest.raises(ValueError):
        save_settings(**options,links_per_page=0)
    with pytest.raises(ValueError):
        save_settings(**options,links_per_page=10001)


def test_audit_persists_and_exports_source_urls(tmp_path):
    journal=LinkExclusionJournal()
    journal.add("https://example.org/s1",[
        "https://example.org/alpha","https://example.org/beta"])
    journal.add("https://example.org/s2",["https://example.org/third"])
    journal.persist(17,tmp_path)
    assert stats(17,tmp_path)=={"excluded_links":3,"affected_pages":2}
    count,items=page(17,source_search="s1",data=tmp_path)
    assert count==2
    assert {r["Ausgeschlossene URL"] for r in items}=={
        "https://example.org/alpha","https://example.org/beta"}
    content=csv_page(17,data=tmp_path).decode("utf-8-sig")
    rows=list(csv.reader(StringIO(content),delimiter=";"))
    assert len(rows)==4
    assert rows[0]==["Quellseite","Ausgeschlossene URL","Grund"]


def test_real_crawl_limits_and_audits_excluded_urls(tmp_path,monkeypatch):
    from websnapshot import inventory
    home="https://example.org/"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(home,))
    monkeypatch.setattr(inventory,"check_public",lambda url:None)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *a,**kw:None)
    links=[f"https://example.org/page-{n}" for n in range(5)]
    html=("<html><title>Start</title><body>"+ "".join(
        f'<a href="{url}">P{n}</a>' for n,url in enumerate(links)
        )+"</body></html>").encode()
    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("/sitemap.xml"):
            return b"<urlset></urlset>","application/xml"
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    run,result=discover_and_snapshot(1,home,limit=1,data=tmp_path,
        config={"discovery_limit":100,"page_timeout":3.0,
                "http_workers":2,"links_per_page":2})
    assert result["links_per_page"]==2
    assert result["excluded_limits"]["page_links"]==3
    assert any("Links-pro-Seite-Limit (2)" in msg for msg in result["limit_warnings"])
    assert result["excluded_link_pages"]==1
    assert stats(run,tmp_path)=={"excluded_links":3,"affected_pages":1}
    total,excluded=page(run,data=tmp_path)
    assert total==3
    assert all(item["Quellseite"]==home for item in excluded)
    assert {item["Ausgeschlossene URL"] for item in excluded}==set(links[2:])
    assert result["discovered"]==3
