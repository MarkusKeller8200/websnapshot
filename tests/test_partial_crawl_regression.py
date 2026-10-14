"""Regression: HTTP Content-Type must never shadow the snapshot-kind resolver.

Before v0.6.17 the local 'kind' variable in discover_and_snapshot
overrode the imported versions.kind function. Partial snapshots then raised:
UnboundLocalError: cannot access local variable 'kind' ...
"""
import sqlite3
from pathlib import Path

from websnapshot.core import database
from websnapshot.inventory import discover_and_snapshot
from websnapshot.versions import effective_pages, kind


ROOT="https://example.org/"
SUBPAGE=ROOT+"aktuelles/"


def test_full_then_partial_then_second_partial_crawls(tmp_path: Path, monkeypatch):
    import websnapshot.inventory as inventory

    with sqlite3.connect(database(tmp_path)) as db:
        db.execute(
            "INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",
            (ROOT,),
        )

    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *args,**kwargs:None)

    revision={"page":"Ursprünglicher Inhalt","start":"Startseite"}
    requested=[]

    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        requested.append(url)
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nAllow: /\n","text/plain"
        if url.endswith("/sitemap.xml"):
            return b"<urlset></urlset>","application/xml"
        if url==ROOT:
            return (
                f"<html><title>Start</title><body>{revision['start']}"
                f'<a href="{SUBPAGE}">Aktuelles</a></body></html>'
            ).encode(),"text/html; charset=utf-8"
        if url==SUBPAGE:
            return (
                f"<html><title>Aktuelles</title><body>{revision['page']}</body></html>"
            ).encode(),"text/html; charset=utf-8"
        raise AssertionError(f"Unbekannte Test-URL: {url}")

    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    config={
        "discovery_limit":100,
        "page_timeout":3.0,
        "http_workers":1,
        "links_per_page":1000,
        "crawl_scope":"host",
    }

    first,full_result=discover_and_snapshot(
        1,ROOT,limit=5,data=tmp_path,snapshot_kind="full",config=config)
    assert kind(first,tmp_path)==("full",None)
    assert full_result["snapshot_kind"]=="full"
    assert set(effective_pages(first,tmp_path))=={ROOT,SUBPAGE}

    revision["page"]="Neuer Inhalt im Partial"
    second,partial_result=discover_and_snapshot(
        1,ROOT,limit=5,data=tmp_path,snapshot_kind="partial",config=config)
    assert kind(second,tmp_path)==("partial",first)
    assert partial_result["snapshot_kind"]=="partial"
    assert partial_result["full_baseline_id"]==first
    assert partial_result["changed"]==1
    assert effective_pages(second,tmp_path)[SUBPAGE][1]=="Neuer Inhalt im Partial"
    assert len(effective_pages(second,tmp_path))==2

    # Also cover the parent-chain walk on a subsequent partial snapshot.
    revision["start"]="Änderung der Startseite"
    third,result=discover_and_snapshot(
        1,ROOT,limit=5,data=tmp_path,snapshot_kind="partial",config=config)
    assert kind(third,tmp_path)==("partial",second)
    assert result["full_baseline_id"]==first
    assert result["changed"]==1
    assert result["changed_since_full"]==2
    assert effective_pages(third,tmp_path)[ROOT][1].startswith("Änderung")
    assert effective_pages(third,tmp_path)[SUBPAGE][1]=="Neuer Inhalt im Partial"
    assert SUBPAGE in requested
