"""Partial snapshots must recheck document URLs, not only HTML pages.

Network requests are fully mocked. A Partial run should HEAD-check inherited
PDF/Office/CSV URLs, compare ETags and Last-Modified, retain failed URLs, and
discover newly linked document URLs without downloading file bodies.
"""
import sqlite3

import requests

from websnapshot.core import database
from websnapshot.documents import list_documents
from websnapshot.inventory import discover_and_snapshot
from websnapshot.versions import kind


ROOT="https://example.org/"
PDF=ROOT+"docs/bericht.pdf"
XLSX=ROOT+"docs/liste.xlsx"
CSV=ROOT+"docs/neu.csv"


class HeadResponse:
    def __init__(self, status_code, headers=None):
        self.status_code=status_code
        self.headers=headers or {}
        self.is_redirect=300<=status_code<400
        self.ok=200<=status_code<400

    def __enter__(self):
        return self

    def __exit__(self,*args):
        return False


def test_full_and_partial_recheck_all_documents_and_discover_new_links(
        tmp_path,monkeypatch):
    from websnapshot import inventory,documents
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(ROOT,))
    monkeypatch.setattr(inventory,"check_public",lambda u:None)
    monkeypatch.setattr(documents,"check_public",lambda u:None)
    state={"version":"v1","new_link":False,"xls_status":200,"robots":"Allow: /"}
    fetched=[]
    checked=[]

    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        fetched.append(url)
        if url.endswith("robots.txt"):
            return ("User-agent: *\n"+state["robots"]).encode(),"text/plain"
        if url.endswith("sitemap.xml"):
            return b"<urlset/>","application/xml"
        html=(f'<html><title>Start</title><body><a href="{PDF}">PDF</a>'
              f'<a href="{XLSX}">Excel</a>'
              +(f'<a href="{CSV}">CSV</a>' if state["new_link"] else "")
              +"</body></html>")
        return html.encode(),"text/html"

    def fake_head(self,url,**kwargs):
        assert kwargs.get("allow_redirects") is False
        checked.append(url)
        if url==XLSX and state["xls_status"]!=200:
            return HeadResponse(state["xls_status"])
        return HeadResponse(200,{
            "ETag": state["version"] if url==PDF else "excel-v1" if url==XLSX else "csv-v1",
            "Last-Modified":"Wed, 14 Oct 2026 10:00:00 GMT",
            "Content-Length":"1234",
        })

    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    monkeypatch.setattr(requests.Session,"head",fake_head)
    options={"crawl_scope":"host","discovery_limit":100,
             "page_timeout":3,"http_workers":1}

    full_id,full_result=discover_and_snapshot(
        1,ROOT,limit=3,data=tmp_path,snapshot_kind="full",config=options)
    assert kind(full_id,tmp_path)==("full",None)
    assert set(checked)=={PDF,XLSX}
    assert set(d["url"] for d in list_documents(full_id,tmp_path))=={PDF,XLSX}
    assert full_result["documents_checked"]==2
    assert full_result["document_statuses"]=={"Neu gefunden":2}
    # Download bodies must not be fetched during full or partial snapshots.
    assert PDF not in fetched and XLSX not in fetched

    checked.clear()
    state.update(version="v2",new_link=True,xls_status=404)
    partial_id,result=discover_and_snapshot(
        1,ROOT,limit=3,data=tmp_path,snapshot_kind="partial",config=options)
    assert kind(partial_id,tmp_path)==("partial",full_id)
    assert set(checked)=={PDF,XLSX,CSV}
    assert result["documents"]==3
    assert result["documents_checked"]==3
    statuses={item["url"]:item["status"]
              for item in list_documents(partial_id,tmp_path)}
    assert statuses=={
        PDF:"Metadaten geändert",
        XLSX:"Nicht erreichbar (HTTP 404)",
        CSV:"Neu gefunden",
    }
    assert result["document_statuses"]=={
        "Metadaten geändert":1,
        "Nicht erreichbar (HTTP 404)":1,
        "Neu gefunden":1,
    }
    assert not any(url in fetched for url in (PDF,XLSX,CSV))

    # Simulate pre-fix partial snapshots which did not inventory documents:
    # the next partial must fall back to the Full ancestor.
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("DELETE FROM documents WHERE run_id=?",(partial_id,))
    checked.clear()
    state.update(version="v1",new_link=False,xls_status=200)
    third_id,third=discover_and_snapshot(
        1,ROOT,limit=3,data=tmp_path,snapshot_kind="partial",config=options)
    assert kind(third_id,tmp_path)==("partial",partial_id)
    assert set(checked)=={PDF,XLSX}
    assert third["documents"]==2
    assert {d["status"] for d in list_documents(third_id,tmp_path)}=={
        "Unverändert laut ETag"}


def test_partial_does_not_head_robots_blocked_document(tmp_path,monkeypatch):
    from websnapshot import inventory,documents
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(ROOT,))
    monkeypatch.setattr(inventory,"check_public",lambda u:None)
    monkeypatch.setattr(documents,"check_public",lambda u:None)
    state={"deny":False}
    checked=[]
    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        if url.endswith("robots.txt"):
            rules="Disallow: /docs/" if state["deny"] else "Allow: /"
            return ("User-agent: *\n"+rules).encode(),"text/plain"
        if url.endswith("sitemap.xml"):return b"<urlset/>","application/xml"
        return (f"<html><a href='{PDF}'>PDF</a></html>").encode(),"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    def fake_head(self,url,**kw):
        checked.append(url)
        return HeadResponse(200,{"ETag":"one"})
    monkeypatch.setattr(requests.Session,"head",fake_head)
    opts={"crawl_scope":"host","discovery_limit":100,
          "page_timeout":3,"http_workers":1}
    full,_=discover_and_snapshot(1,ROOT,3,tmp_path,snapshot_kind="full",config=opts)
    assert checked==[PDF]
    checked.clear()
    state["deny"]=True
    partial,_=discover_and_snapshot(1,ROOT,3,tmp_path,snapshot_kind="partial",config=opts)
    assert checked==[]
    docs=list_documents(partial,tmp_path)
    assert docs[0]["url"]==PDF
    assert docs[0]["status"]=="Nicht geprüft (robots.txt)"



def test_inherited_documents_work_for_legacy_full_without_snapshot_meta(tmp_path):
    from websnapshot.core import save
    from websnapshot.documents import init, previous_document_metadata
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(ROOT,))
    full=save(1,{ROOT:("Test","Seiteninhalt")},[],tmp_path)
    init(tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("""INSERT INTO documents
            (run_id,url,etag,last_modified,length,status)
            VALUES(?,?,?,?,?,?)""",
            (full,PDF,"alt","Wed, 14 Oct 2026 10:00:00 GMT","123","Neu gefunden"))
    previous=previous_document_metadata(full,tmp_path)
    assert previous=={PDF:("alt","Wed, 14 Oct 2026 10:00:00 GMT","123")}
