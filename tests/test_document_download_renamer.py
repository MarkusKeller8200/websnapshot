"""End-to-end document naming/metadata/hash tests with fake HTTP responses."""
from hashlib import sha256
import sqlite3

from websnapshot.core import database
from websnapshot.documents import download_selected
from websnapshot.document_renamer import RENAMED


class Response:
    is_redirect = False
    headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="schul reglement.pdf"',
        "Last-Modified": "Tue, 02 Jun 2020 12:00:00 GMT",
    }
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        pass
    def iter_content(self, blocksize):
        yield self.payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


def test_dated_document_names_and_sha256_history(monkeypatch,tmp_path):
    url="https://example.org/download.php?doc_id=123"
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
        db.execute("INSERT INTO runs(id,site_id,created_at,status,errors) VALUES (1,1,'now','complete','[]')")
        db.execute("""CREATE TABLE IF NOT EXISTS documents(
            run_id INTEGER NOT NULL,url TEXT NOT NULL,etag TEXT,last_modified TEXT,
            length TEXT,status TEXT NOT NULL,PRIMARY KEY(run_id,url))""")
        db.execute("INSERT INTO documents VALUES (1,?,?,?,?,'Neu gefunden')",
                   (url,"abc",None,"5"))
    payloads=iter([b"%PDF-test-one",b"%PDF-test-one",b"%PDF-test-two"])
    monkeypatch.setattr("websnapshot.documents.check_public",lambda _url: None)
    monkeypatch.setattr("requests.Session.get",
        lambda self,_url,**kwargs: Response(next(payloads)))
    profile={"mode":RENAMED,"code":"DSB","case":"title"}
    for number,status in enumerate(("Neu","Unverändert (SHA-256)",
                                     "Inhalt geändert (SHA-256)"),1):
        outcome=download_selected(1,[url],data=tmp_path,
            destination_root=tmp_path/"custom",profile=profile)[0]
        assert "error" not in outcome
        assert outcome["content_status"]==status
        assert outcome["date_source"]=="HTTP Last-Modified (Download)"
        assert outcome["date"]=="2020-06-02"
        assert "2020_06_02_DSB_Schul_Reglement" in outcome["path"]
        if number>1:
            assert outcome["path"].endswith(f"_{number}.pdf")
        assert outcome["sha256"]==sha256(
            b"%PDF-test-two" if number==3 else b"%PDF-test-one").hexdigest()
    with sqlite3.connect(database(tmp_path)) as db:
        rows=db.execute("SELECT content_status,document_date,original_filename "
                        "FROM downloads ORDER BY id").fetchall()
    assert len(rows)==3
    assert rows[-1]==("Inhalt geändert (SHA-256)","2020-06-02",
                      "schul reglement.pdf")
