"""Metadata coverage for Word, PDF, Excel, TXT, CSV and multiple citations."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import sqlite3

from pypdf import PdfWriter

from websnapshot.core import database
from websnapshot.documents import init as init_documents, list_documents
from websnapshot.document_metadata import (
    save_references,list_references,info_by_url,probe_selected,store_properties,
)
from websnapshot.document_properties import extract_properties
from websnapshot.document_renamer import resolve_extension


CORE = """<?xml version="1.0"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/">
<dc:title>Leitlinie Informationssicherheit</dc:title><dc:subject>Vorlage</dc:subject>
<dc:creator>Datenschutzbeauftragte</dc:creator><cp:lastModifiedBy>Adrian</cp:lastModifiedBy>
<cp:revision>2</cp:revision><dcterms:created>2025-02-18T16:42:00Z</dcterms:created>
<dcterms:modified>2025-02-19T16:42:00Z</dcterms:modified></cp:coreProperties>"""
APP = """<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>Microsoft Office</Application><Company>Datenschutzbeauftragte</Company>
<Manager>Dokumentenverwaltung</Manager><TotalTime>14</TotalTime></Properties>"""
CUSTOM = """<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<property name="Freigabe"><vt:lpwstr>geprüft</vt:lpwstr></property></Properties>"""


def office_file(path: Path):
    with ZipFile(path,"w") as archive:
        archive.writestr("docProps/core.xml",CORE)
        archive.writestr("docProps/app.xml",APP)
        archive.writestr("docProps/custom.xml",CUSTOM)


def test_docx_and_xlsx_office_tags(tmp_path):
    for extension in (".docx",".xlsx"):
        path=tmp_path/("details"+extension)
        office_file(path)
        p=extract_properties(path,extension)
        assert p["title"]=="Leitlinie Informationssicherheit"
        assert p["subject"]=="Vorlage"
        assert p["creator"]=="Datenschutzbeauftragte"
        assert p["last_modified_by"]=="Adrian"
        assert p["revision"]=="2"
        assert p["company"]=="Datenschutzbeauftragte"
        assert p["manager"]=="Dokumentenverwaltung"
        assert p["created"]=="2025-02-18T16:42:00Z"
        assert p["custom_properties"]["Freigabe"]=="geprüft"


def test_pdf_properties(tmp_path):
    path=tmp_path/"sample.pdf"
    writer=PdfWriter()
    writer.add_blank_page(width=100,height=100)
    writer.add_metadata({"/Title":"Richtlinie","/Author":"Abteilung",
                         "/Subject":"Vorgabe","/Keywords":"Sicherheit"})
    with path.open("wb") as handle:
        writer.write(handle)
    props=extract_properties(path,".pdf")
    assert props["title"]=="Richtlinie"
    assert props["creator"]=="Abteilung"
    assert props["subject"]=="Vorgabe"


def test_csv_txt_and_legacy_xls(tmp_path,monkeypatch):
    for suffix in (".csv",".txt"):
        path=tmp_path/("data"+suffix)
        path.write_text("Name;Wert\nÄnderung;2\n",encoding="utf-8")
        props=extract_properties(path,suffix)
        assert props["encoding"]=="UTF-8"
        assert props["line_count"]==2
        assert "title" not in props and "created" not in props
        if suffix==".csv":
            assert props["delimiter"]==";"
            assert props["columns"]==2
    import olefile
    class FakeOle:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self):return self
        def __exit__(self,*args): pass
        def exists(self,name):return True
        def getproperties(self,name):
            return {2:"Excel Report",4:"Office User"} if "DocumentSummary" not in name else {
                14:"Manager",15:"Organisation"}
    monkeypatch.setattr(olefile,"OleFileIO",FakeOle)
    assert extract_properties(tmp_path/"legacy.xls",".xls")["title"]=="Excel Report"
    assert extract_properties(tmp_path/"legacy.xls",".xls")["company"]=="Organisation"
    assert resolve_extension("report.csv","text/plain; charset=utf-8")==".csv"
    assert resolve_extension("report.xlsx","application/octet-stream")==".xlsx"


def test_multiple_referrers_and_inventory_fields(tmp_path):
    init_documents(tmp_path)
    url="https://example.org/berichte/report.xlsx"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,'https://example.org/','now')")
        db.execute("INSERT INTO runs(id,site_id,created_at,status,errors) VALUES(1,1,'now','complete','[]')")
        db.execute("INSERT INTO documents VALUES(1,?,?,?,?,?)",
                   (url,"etag","today","100","Neu gefunden"))
    save_references(1,{url:{("https://example.org/a","html-link"),
                            ("https://example.org/b","html-link")}},tmp_path)
    save_references(1,{url:{("https://example.org/a","html-link")}},tmp_path)
    assert len(list_references(1,url,tmp_path))==2
    assert info_by_url(1,tmp_path)[url]["references"]==2
    store_properties(1,url,{"title":"Excel Bericht"},"a"*64,data=tmp_path)
    item=list_documents(1,tmp_path)[0]
    assert item["title"]=="Excel Bericht"
    assert item["references"]==2
    assert item["found_on"]=="https://example.org/a"


def test_metadata_precheck_fetches_temporarily_without_download(tmp_path,monkeypatch):
    import websnapshot.document_metadata as dm
    url="https://example.org/data/report.xlsx"
    init_documents(tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,'https://example.org/','now')")
        db.execute("INSERT INTO runs(id,site_id,created_at,status,errors) VALUES(1,1,'now','complete','[]')")
        db.execute("INSERT INTO documents VALUES(1,?,?,?,?,?)",
                   (url,None,None,None,"Neu gefunden"))
    zipfile=tmp_path/"report.xlsx"
    office_file(zipfile)
    data=zipfile.read_bytes()
    class Response:
        is_redirect=False
        headers={"Content-Type":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 "Content-Length":str(len(data))}
        def raise_for_status(self):pass
        def iter_content(self,size):yield data
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(dm,"check_public",lambda url:None)
    monkeypatch.setattr(dm,"_robots_allowed",lambda *args:True)
    monkeypatch.setattr("requests.Session.get",
                        lambda self,url,**kwargs:Response())
    outcome=probe_selected(1,[url],data=tmp_path)[0]
    assert outcome["properties"]["title"]=="Leitlinie Informationssicherheit"
    assert outcome["status"]=="Erstmals anhand Datei geprüft"
    assert not list((tmp_path/"metadata_tmp").iterdir())
    assert not (tmp_path/"downloads").exists()
