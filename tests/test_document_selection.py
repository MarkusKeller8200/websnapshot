"""Document selection must stay stable when the filter changes."""
from websnapshot.document_selection import filter_documents, bulk_selection, merge_visible

DOCS = [
    {"url":"https://example.org/a.pdf","status":"Neu gefunden","length":"100"},
    {"url":"https://example.org/b.docx","status":"Unverändert","length":"200"},
    {"url":"https://example.org/c.pdf","status":"Nicht prüfbar","length":None},
]

def test_filter_case_insensitive_url_and_status():
    assert [r["url"] for r in filter_documents(DOCS,"PDF")] == [
        "https://example.org/a.pdf","https://example.org/c.pdf"]
    assert [r["url"] for r in filter_documents(DOCS,"NEU")] == ["https://example.org/a.pdf"]
    assert filter_documents(DOCS,"") == DOCS
    assert filter_documents(DOCS,"kein-treffer") == []

def test_bulk_all_and_filtered_clear():
    urls=[r["url"] for r in DOCS]
    assert bulk_selection(set(),urls,urls[:1],"all_select") == set(urls)
    assert bulk_selection(set(urls),urls,urls[:1],"filtered_clear") == set(urls[1:])
    assert bulk_selection(set(urls),urls,urls[:1],"all_clear") == set()
    assert bulk_selection(set(),urls,urls[:1],"filtered_select") == {urls[0]}

def test_editor_merges_visible_without_clearing_hidden():
    urls=[r["url"] for r in DOCS]
    after=merge_visible({urls[0],urls[1]},urls,[urls[0],urls[2]],[urls[2]])
    assert after == {urls[1],urls[2]}
