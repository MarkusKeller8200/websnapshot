"""Crawl discovery should not waste time or quotas on robots-blocked URLs."""
import sqlite3

from websnapshot.core import database
from websnapshot.inventory import discover_and_snapshot
from websnapshot.crawl_discovery_stats import get as get_discovery_stats


def test_robots_are_applied_before_discovery_and_urls_not_queued(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    home="https://example.org/"
    blocked="https://example.org/inc/hidden"
    variant="https://example.org/events?page=1"
    another="https://example.org/events?page=2"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(home,))
    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *a,**kw:None)
    seen=[]
    html=("<html><body><a href='/inc/hidden'>blocked</a>"
          "<a href='/events?page=1'>one</a>"
          "<a href='/events?page=2'>two</a></body></html>").encode()
    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        seen.append(url)
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nDisallow: /inc/\n","text/plain"
        if url.endswith("/sitemap.xml"):
            xml=("<urlset><url><loc>"+blocked+"</loc></url>"
                 "<url><loc>"+variant.replace("&","&amp;")+"</loc></url></urlset>")
            return xml.encode(),"application/xml"
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    run,result=discover_and_snapshot(1,home,limit=3,data=tmp_path,
        config={"discovery_limit":100,"page_timeout":3,"http_workers":2,
                "links_per_page":5})
    assert blocked not in seen
    assert result["discovered"]==3
    assert result["robots_excluded"]>=1
    assert result["query_variants"]==2
    assert result["unique_paths"]==2  # / and /events
    stored=get_discovery_stats(run,tmp_path)
    assert stored["robots_loaded"] is True
    assert stored["query_variants"]==2
    assert stored["top_query_parameters"][0]==["page",2]
    assert blocked in stored["robots_examples"]
    assert stored["discovered_sources"]["sitemap"]==1
    assert stored["discovered_sources"]["html-link"]==1


def test_sitemap_does_not_materialise_unbounded_list(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    home="https://example.org/"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(home,))
    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *a,**kw:None)
    fetched=[]
    sitemap="<urlset>"+"".join(
        f"<url><loc>https://example.org/p{i}</loc></url>" for i in range(150)
        )+"</urlset>"
    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        fetched.append(url)
        if url.endswith("robots.txt"):return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("sitemap.xml"):return sitemap.encode(),"application/xml"
        return b"<html><body>Ok</body></html>","text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    run,result=discover_and_snapshot(1,home,limit=3,data=tmp_path,
        config={"discovery_limit":20,"page_timeout":3,"http_workers":2})
    assert result["discovered"]==20
    assert result["visited"]==3
    assert get_discovery_stats(run,tmp_path)["discovered_sources"]["sitemap"]==19
    assert len(fetched)==5  # robots, sitemap and only 3 page requests
