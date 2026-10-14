"""Sitemap hierarchy and spreadsheet export regression tests."""
import csv
from io import BytesIO, StringIO
from pathlib import Path
import sqlite3
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from websnapshot.sitemap_view import (
    tree_from_pages, visible_tree_rows, all_parent_ids,
    filtered_page_rows, export_csv, export_xlsx,
)
from websnapshot.core import database, save
from websnapshot.versions import mark_full, effective_page_metadata, save_partial


def samples():
    base="https://example.org"
    paths=[
        "/schule-hinterbirch/",
        "/schule-hinterbirch/aktuelles/",
        "/schule-hinterbirch/aktuelles/offene-stellen/",
        "/schule-hinterbirch/aktuelles/offene-stellen/p-130/",
        "/schule-hinterbirch/aktuelles/offene-stellen/p-130/schulverwaltung/",
        "/schule-hinterbirch/aktuelles/offene-stellen/p-130/schulverwaltung/systematische-rechtssammlung/",
        "/schule-hinterbirch/aktuelles/offene-stellen/p-130/schulverwaltung/systematische-rechtssammlung/p-5984/",
    ]
    return [{"URL":base+path,"Pfad":path,"Titel":path.split("/")[-2],
             "Zeichen":number*11,"Öffnen":base+path}
            for number,path in enumerate(paths,1)]


def test_nested_user_example_can_expand_stepwise():
    rows=samples()
    tree=tree_from_pages(rows)
    first,ids,truncated=visible_tree_rows(tree,set())
    assert len(first)==1
    assert "schule-hinterbirch" in first[0]["Ebene / Pfad"]
    assert first[0]["Seiten"]==len(rows)
    key=ids[0]
    second,ids2,_=visible_tree_rows(tree,{key})
    assert len(second)==2
    assert "aktuelles" in second[1]["Ebene / Pfad"]
    opened=all_parent_ids(tree)
    full,identifiers,truncated=visible_tree_rows(tree,opened)
    assert len(full)==len(rows)
    assert "p-5984" in full[-1]["Ebene / Pfad"]
    assert not truncated
    assert filtered_page_rows(rows,"rechtssammlung")


def test_tree_only_renders_first_n_rows():
    tree=tree_from_pages(samples())
    shown,_,truncated=visible_tree_rows(tree,all_parent_ids(tree),limit=3)
    assert len(shown)==3
    assert truncated


def test_csv_has_utf8_bom_semicolon_and_formula_protection():
    rows=samples()
    rows[0]["Titel"]="=HYPERLINK(\"danger\")"
    content=export_csv(rows)
    assert content.startswith(b"\xef\xbb\xbf")
    parsed=list(csv.reader(StringIO(content.decode("utf-8-sig")),delimiter=";"))
    assert len(parsed)==8
    assert parsed[1][1].startswith("'=HYPERLINK")


def test_xlsx_is_real_workbook_with_autofilter_and_frozen_header():
    data=export_xlsx(samples())
    with ZipFile(BytesIO(data)) as file:
        assert file.testzip() is None
        for name in ("xl/workbook.xml","xl/styles.xml",
                     "xl/worksheets/sheet1.xml","[Content_Types].xml"):
            ET.fromstring(file.read(name))
        sheet=file.read("xl/worksheets/sheet1.xml")
        root=ET.fromstring(sheet)
        ns="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        assert root.find(".//"+ns+"autoFilter").attrib["ref"]=="A1:D8"
        assert root.find(".//"+ns+"pane").attrib["ySplit"]=="1"
        assert len(root.findall(".//"+ns+"sheetData/"+ns+"row"))==8
        assert b"schule-hinterbirch" in sheet


def test_effective_metadata_inherits_full_pages(tmp_path: Path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,'https://example.org/','now')")
    old=save(1,{"https://example.org/a":("Old","One"),"https://example.org/b":("B","Two")},
             [],tmp_path)
    mark_full(old,tmp_path)
    new,changed=save_partial(1,{"https://example.org/a":("New","Three")},[],old,tmp_path)
    assert changed==1
    items=effective_page_metadata(new,tmp_path)
    assert [x["URL"] for x in items]==["https://example.org/a","https://example.org/b"]
    assert items[0]["Titel"]=="New"
    assert items[1]["Zeichen"]==3



def test_all_levels_button_expands_every_folder_without_exceeding_visible_limit():
    """The Sitemap toolbar must offer a fast all-levels action alongside collapse."""
    app=(Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py").read_text(
        encoding="utf-8")
    assert 'st.button("🗂️ Alle Ebenen"' in app
    assert 'key=f"tree_all_{site_id}_{selected_run}"' in app
    assert 'expanded=all_parent_ids(tree)' in app
    assert 'rows,node_ids,truncated=visible_tree_rows(tree,expanded,limit=2500)' in app
    tree=tree_from_pages(samples())
    expanded=all_parent_ids(tree)
    assert len(expanded)>=5
    rows,ids,limited=visible_tree_rows(tree,expanded,limit=2500)
    assert len(rows)==len(samples()) and not limited
    assert ids[-1].endswith("p-5984")
    few,_,limited=visible_tree_rows(tree,expanded,limit=2)
    assert len(few)==2 and limited
