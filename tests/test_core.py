from pathlib import Path
import sqlite3

from websnapshot.core import normalize_url, extract, database, save, compare, report


def test_extract():
    assert normalize_url("https://EXAMPLE.org/a#fragment") == "https://example.org/a"
    title, text, links = extract(
        '<title>A</title><main>Text <b>here</b></main><a href="/x">next</a><script>bad()</script>',
        "https://example.org/",
    )
    assert title == "A"
    assert "Text" in text and "bad()" not in text
    assert links == ["https://example.org/x"]


def test_report(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,'https://example.org/','now')")
    old = save(1, {"https://example.org/": ("Page", "previous")}, [], tmp_path)
    new = save(1, {"https://example.org/": ("Page", "new <script>")}, [], tmp_path)
    changes = compare(old, new, tmp_path)
    assert len(changes) == 1 and changes[0]["kind"] == "changed"
    assert "&lt;script&gt;" in report(changes, old, new)
