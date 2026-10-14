"""Scope rules for entire domains vs a single educational site section."""
import sqlite3
from websnapshot.core import database
from websnapshot.crawl_scope import (
    SCOPE_AUTO,SCOPE_PATH,SCOPE_HOST,logical_root,effective_scope,
    within_scope,eligible_link,is_document,
)
from websnapshot.settings import get,set_settings


BASE = "https://www.zh.ch/de/bildung.html"


def test_html_landing_and_nested_section():
    assert logical_root(BASE)=="/de/bildung"
    assert effective_scope(BASE)==SCOPE_PATH
    assert within_scope(BASE,BASE)
    assert within_scope("https://www.zh.ch/de/bildung",BASE)
    assert within_scope("https://www.zh.ch/de/bildung/",BASE)
    assert within_scope("https://www.zh.ch/de/bildung/schulen.html",BASE)
    assert within_scope("https://www.zh.ch/de/bildung/schulen/volksschule.html",BASE)
    assert not within_scope("https://www.zh.ch/de/bildungspolitik.html",BASE)
    assert not within_scope("https://www.zh.ch/de/gesundheit.html",BASE)
    assert not within_scope("https://www.zh.ch/de/bildung-alt.html",BASE)
    assert not within_scope("https://other.zh.ch/de/bildung/test.html",BASE)


def test_domain_scope_and_root_path():
    assert effective_scope("https://example.org/")==SCOPE_HOST
    assert within_scope("https://example.org/anderes",BASE.replace("www.zh.ch/de/bildung.html","example.org/"),
                        SCOPE_HOST)
    assert within_scope("https://example.org/sonstiges","https://example.org/")
    assert not within_scope("https://example.com/sonstiges","https://example.org/")


def test_document_in_shared_storage_only_if_linked_directly():
    pdf="https://www.zh.ch/content/dam/zhweb/bilder-dokumente/themen/bildung/merkblatt.pdf"
    assert is_document(pdf)
    assert eligible_link(pdf,BASE,directly_linked=True)
    assert not eligible_link(pdf,BASE,directly_linked=False)
    assert not eligible_link("https://www.zh.ch/de/gesundheit.html",BASE)
    assert not eligible_link("https://evil.com/file.pdf",BASE)


def test_site_scope_database_migration_and_save(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,?,'now')",(BASE,))
        db.execute("""CREATE TABLE site_settings(
            site_id INTEGER PRIMARY KEY,mode TEXT NOT NULL,
            wait_selector TEXT NOT NULL DEFAULT '',
            wait_ms INTEGER NOT NULL DEFAULT 1500)""")
        db.execute("INSERT INTO site_settings VALUES(1,'static','',1500)")
    current=get(1,tmp_path)
    assert current["crawl_scope"]==SCOPE_AUTO
    set_settings(1,"static",scope=SCOPE_PATH,data=tmp_path)
    assert get(1,tmp_path)["crawl_scope"]==SCOPE_PATH
    set_settings(1,"static",scope=SCOPE_HOST,data=tmp_path)
    assert get(1,tmp_path)["crawl_scope"]==SCOPE_HOST
