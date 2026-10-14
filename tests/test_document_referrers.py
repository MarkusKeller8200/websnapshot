"""A document linked by two pages is one inventory item with two source pages."""
import sqlite3

from websnapshot.core import database
from websnapshot.inventory import discover_and_snapshot
from websnapshot.document_metadata import list_references


def test_same_document_from_multiple_pages_is_recorded_once(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    start="https://example.org/"
    second="https://example.org/zweiteseite"
    document="https://example.org/asset/bericht.csv"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(start,))
    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    html=("<html><body><a href='"+second+"'>Next</a>"
          "<a href='"+document+"'>CSV</a></body></html>").encode()
    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("/sitemap.xml"):
            return b"<urlset></urlset>","application/xml"
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    encountered=[]
    monkeypatch.setattr(inventory,"inventory_documents",
                        lambda rid,sid,docs,sess,data,progress=None:
                        encountered.extend(docs))
    run,result=discover_and_snapshot(1,start,limit=2,data=tmp_path,
        config={"crawl_scope":"host","discovery_limit":1000,
                "page_timeout":3.0,"http_workers":2})
    assert result["pages"]==2
    assert result["documents"]==1
    assert encountered==[document]
    refs=list_references(run,document,tmp_path)
    assert {r["url"] for r in refs}=={start,second}
    assert len(refs)==2
