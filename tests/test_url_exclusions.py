"""Regression coverage for per-website URL path exclusions."""
import sqlite3

import pytest

from websnapshot.core import database
from websnapshot.settings import get as get_site_settings, set_settings
from websnapshot.url_exclusions import parse_excludes, excluded_by
from websnapshot.path_exclusion_audit import summary as exclusion_summary
from websnapshot.inventory import discover_and_snapshot


HOME="https://example.org/"
RULE="/schule-hinterbirch/aktuelles/agenda/p-2002"
BAD=HOME+RULE.lstrip("/")
CHILD=BAD+"/subpage.html"
SIBLING=HOME+"schule-hinterbirch/aktuelles/agenda/p-20020"
OK=HOME+"schule-hinterbirch/aktuelles/agenda/p-2003"
HTML=BAD+".html"


def test_exact_descendants_and_html_landing_not_prefix_neighbors():
    rules=parse_excludes(RULE+"\n# comment\n"+RULE+"/\n")
    assert rules==[RULE]
    assert excluded_by(BAD,rules)==RULE
    assert excluded_by(BAD+"/",rules)==RULE
    assert excluded_by(CHILD,rules)==RULE
    assert excluded_by(HTML,rules)==RULE
    assert excluded_by(BAD+"?page=2",rules)==RULE
    assert excluded_by(BAD.replace("2002","%32%30%30%32"),rules)==RULE
    assert excluded_by(SIBLING,rules) is None
    assert excluded_by(OK,rules) is None


def test_validation_and_site_setting_persistence(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(HOME,))
        db.execute("""CREATE TABLE site_settings(
            site_id INTEGER PRIMARY KEY,mode TEXT NOT NULL,
            wait_selector TEXT NOT NULL DEFAULT '',
            wait_ms INTEGER NOT NULL DEFAULT 1500)""")
        db.execute("INSERT INTO site_settings VALUES(1,'static','',1500)")
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[]
    set_settings(1,"static",data=tmp_path,exclude_paths=RULE+"\n"+RULE)
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[RULE]
    # Old method calls keep the already configured list.
    set_settings(1,"browser",data=tmp_path)
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[RULE]
    for value in ("https://example.org/forbidden","relative","/path*","/path?x=2"):
        with pytest.raises(ValueError):
            set_settings(1,"static",data=tmp_path,exclude_paths=value)
    with pytest.raises(ValueError,match="Startadresse"):
        set_settings(1,"static",data=tmp_path,exclude_paths="/")
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[RULE]
    set_settings(1,"static",data=tmp_path,exclude_paths="")
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[]


def test_exclude_from_sitemap_and_links_before_limit(tmp_path,monkeypatch):
    import websnapshot.inventory as inventory
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(HOME,))
    set_settings(1,"static",data=tmp_path,exclude_paths=RULE)
    monkeypatch.setattr(inventory,"check_public",lambda _url:None)
    monkeypatch.setattr(inventory,"inventory_documents",lambda *args,**kwargs:None)
    calls=[]
    links=[BAD,CHILD,HTML,SIBLING,OK]
    html=("<html><title>Home</title><body>"+
          "".join(f'<a href="{u}">page</a>' for u in links)+
          "</body></html>").encode()
    sitemap=("<urlset><url><loc>"+BAD+"</loc></url>"+
             "<url><loc>"+SIBLING+"</loc></url></urlset>").encode()
    def fake_fetch(session,url,max_bytes=2_000_000,timeout=3.0):
        calls.append(url)
        if url.endswith("robots.txt"):
            return b"User-agent: *\nAllow: /","text/plain"
        if url.endswith("sitemap.xml"):
            return sitemap,"application/xml"
        return html,"text/html"
    monkeypatch.setattr(inventory,"_fetch",fake_fetch)
    run_id,result=discover_and_snapshot(1,HOME,limit=3,data=tmp_path,
        config={"crawl_scope":"host","discovery_limit":1000,
                "page_timeout":3,"http_workers":1,"links_per_page":2})
    assert BAD not in calls
    assert CHILD not in calls
    assert HTML not in calls
    assert result["path_excluded"]>=4
    assert result["discovered"]==3
    assert result["excluded_limits"]["page_links"]==0
    assert SIBLING in calls
    assert OK in calls
    audit=exclusion_summary(run_id,tmp_path)
    assert len(audit)==1 and audit[0]["Pfadregel"]==RULE
    assert audit[0]["Ausgeschlossene URL-Kandidaten"]>=4
    assert BAD in audit[0]["Beispiele"]


def test_partial_crawl_rejects_new_rules_to_avoid_inherited_pages(tmp_path,monkeypatch):
    from websnapshot.core import save
    from websnapshot.versions import mark_full
    from websnapshot import inventory
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,?,'now')",(HOME,))
    earlier=save(1,{HOME:("Home","Okay"),BAD:("Old","Should disappear")},[],tmp_path)
    mark_full(earlier,tmp_path)
    monkeypatch.setattr(inventory,"check_public",lambda url:None)
    monkeypatch.setattr(inventory,"_fetch",lambda *args,**kwargs:(b"","text/plain"))
    with pytest.raises(ValueError,match="Full-Snapshot"):
        discover_and_snapshot(1,HOME,limit=5,data=tmp_path,
            snapshot_kind="partial",
            config={"crawl_scope":"host","exclude_paths":[RULE],
                    "discovery_limit":1000,"page_timeout":3,"http_workers":1})



def test_dedicated_save_roundtrips_and_preserves_capture_settings(tmp_path):
    """Reproduce the reported bug: save a textarea and reload from SQLite."""
    from websnapshot.settings import set_exclusions
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES (1,?,'now')",(HOME,))
    set_settings(1,"browser",wait_selector="#main",wait_ms=2500,
                 scope="host",data=tmp_path)
    saved=set_exclusions(1,RULE+"\n"+OK+"\n"+RULE,tmp_path)
    assert saved==[RULE,"/schule-hinterbirch/aktuelles/agenda/p-2003"]
    loaded=get_site_settings(1,tmp_path)
    assert loaded["exclude_paths"]==saved
    assert loaded["mode"]=="browser"
    assert loaded["wait_selector"]=="#main"
    assert loaded["wait_ms"]==2500
    assert loaded["crawl_scope"]=="host"
    # The update survives a completely new SQLite connection.
    with sqlite3.connect(database(tmp_path)) as db:
        row=db.execute("SELECT exclude_paths FROM site_settings WHERE site_id=1").fetchone()
    assert row is not None and __import__("json").loads(row[0])==saved
    with pytest.raises(ValueError,match="Startadresse"):
        set_exclusions(1,"/",tmp_path)
    assert get_site_settings(1,tmp_path)["exclude_paths"]==saved
    assert set_exclusions(1,"",tmp_path)==[]
    assert get_site_settings(1,tmp_path)["exclude_paths"]==[]


def test_ui_has_direct_exclusion_save_and_visible_database_readback():
    from pathlib import Path
    code=(Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py").read_text(
        encoding="utf-8")
    direct=code.index('st.button("💾 Ausschlussliste speichern"')
    advanced=code.index('with st.expander("Erweiterte Browser-Einstellungen")')
    assert direct<advanced
    assert "on_click=save_site_exclusion_list" in code
    assert 'st.session_state[f"exclude_paths_{site_id}"]' in code
    assert "saved=set_exclusions(" in code
    assert "Tatsächlich gespeicherte Ausschlussregeln:" in code
    assert "noch nicht gespeicherte Änderungen" in code
