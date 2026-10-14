"""Integration: a subtree crawl never archives unrelated same-host pages."""
import sqlite3
from websnapshot.core import database
from websnapshot.inventory import discover_and_snapshot
from websnapshot.settings import set_settings


ROOT="https://www.zh.ch/de/bildung.html"
SUB="https://www.zh.ch/de/bildung/schulen/volksschule.html"
FOREIGN="https://www.zh.ch/de/gesundheit.html"
PDF="https://www.zh.ch/content/dam/zhweb/bildung/merkblatt.pdf"


def test_subtree_does_not_follow_external_department_but_records_linked_doc(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(ROOT,))
    set_settings(1,"static",scope="path",data=tmp_path)
    monkeypatch.setattr(inventory,"check_public",lambda _url: None)
    xml=(f"<urlset><url><loc>{SUB}</loc></url>"
         f"<url><loc>{FOREIGN}</loc></url>"
         f"<url><loc>{PDF}</loc></url></urlset>")
    html=(f"<html><title>Bildung</title><body>"
          f"<a href='{SUB}'>Volksschule</a>"
          f"<a href='{FOREIGN}'>Gesundheit</a>"
          f"<a href='{PDF}'>PDF</a></body></html>").encode()
    called=[]
    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        called.append(url)
        if url.endswith("robots.txt"):
            return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("sitemap.xml"):
            return xml.encode(),"application/xml"
        if url==FOREIGN or url==PDF:
            raise AssertionError("Unrelated pages and PDF documents must not be crawled as HTML")
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    recorded={}
    def collect(run_id,site_id,docs,session,data,progress=None):
        recorded["docs"]=set(docs)
    monkeypatch.setattr(inventory,"inventory_documents",collect)
    run_id,result=discover_and_snapshot(1,ROOT,limit=5,data=tmp_path,
        config={"discovery_limit":100,"page_timeout":3.0,"http_workers":2,
                "crawl_scope":"path"})
    assert ROOT in called and SUB in called
    assert FOREIGN not in called
    assert PDF not in called
    assert result["pages"]==2
    assert result["documents"]==1
    assert result["crawl_scope"]=="path"
    assert result["scope_excluded"]>=1
    assert recorded["docs"]=={PDF}


def test_domain_mode_can_discover_other_section(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(ROOT,))
    monkeypatch.setattr(inventory,"check_public",lambda _url: None)
    html=(f"<html><body><a href='{FOREIGN}'>Other</a></body></html>").encode()
    def fake_fetch(client,url,max_bytes=2_000_000,timeout=3.0):
        if url.endswith("robots.txt"):return b"","text/plain"
        if url.endswith("sitemap.xml"):return b"<urlset/>","application/xml"
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *a,**kw:None)
    run_id,result=discover_and_snapshot(1,ROOT,limit=2,data=tmp_path,
        config={"discovery_limit":100,"page_timeout":3.0,"http_workers":1,
                "crawl_scope":"host"})
    assert result["pages"]==2
    assert result["crawl_scope"]=="host"
