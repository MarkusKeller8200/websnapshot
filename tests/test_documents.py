from websnapshot.documents import destination, document_status
from pathlib import Path

def test_document_status():
    assert document_status(None, ("e1",None,None)) == "Neu gefunden"
    assert document_status(("e1",None,None),("e1",None,None)) == "Unverändert laut ETag"
    assert document_status(("e1",None,None),("e2",None,None)) == "Metadaten geändert"
    assert document_status((None,None,None),(None,None,None)) == "Nicht prüfbar"

def test_download_paths(tmp_path: Path):
    url = "https://example.org/docs/sub/report.pdf"
    structured = destination(url,tmp_path,False)
    flat = destination(url,tmp_path,True)
    assert structured.parent == tmp_path / "example.org" / "docs" / "sub"
    assert flat.parent == tmp_path / "example.org"
    assert flat.name.endswith(".pdf")
    assert flat.name != structured.name
