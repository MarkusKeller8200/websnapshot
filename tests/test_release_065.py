"""Global settings, filename convention and auto width regression tests."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from websnapshot.core import database
from websnapshot.global_settings import defaults, get, save
from websnapshot.document_renamer import (
    build_filename, choose_date, filename_from_headers, file_metadata_dates,
    get_profile, set_profile, RENAMED, ORIGINAL,
)
from websnapshot.table_layout import column_width, streamlit_columns


def test_global_settings_roundtrip(tmp_path):
    dest=tmp_path/"custom documents"
    result=save(download_directory=str(dest), flat_downloads=True,
                visit_limit=2500,sitemap_height=1100,data=tmp_path)
    assert get(tmp_path)==result
    assert dest.is_dir()
    with pytest.raises(ValueError):
        save(download_directory="relative/folder",flat_downloads=False,
             visit_limit=1000,sitemap_height=800,data=tmp_path)


def test_renamer_dated_and_original():
    when=datetime(2025,3,5,tzinfo=timezone.utc)
    name=build_filename("schul regelung 2025.pdf",".pdf",mode=RENAMED,
                        code="sekb",case="title",date=when)
    assert name=="2025_03_05_SEKB_Schul_Regelung_2025.pdf"
    assert build_filename("eins zwei.pdf",".pdf",mode=ORIGINAL,
                          code="DSB",case="first",date=when)=="eins_zwei.pdf"
    with pytest.raises(ValueError):
        build_filename("x.pdf",".pdf",mode=RENAMED,code="../invalid",
                       case="title",date=when)


def test_date_precedence_and_fallback():
    date,source=choose_date(("Embedded","2024-01-03T09:30:00Z"),
                            ("HTTP","Wed, 04 Oct 2023 10:00:00 GMT"))
    assert date.strftime("%Y_%m_%d")=="2024_01_03"
    assert source=="Embedded"
    date,source=choose_date(("HTTP",None),
        now=datetime(2026,10,14,tzinfo=timezone.utc))
    assert date.year==2026 and source.startswith("Download-Datum")


def test_filename_http_content_disposition():
    assert filename_from_headers("https://example.org/download.php?doc_id=10",
        "attachment; filename*=UTF-8''Pr%C3%BCfung%202024.pdf")=="Prüfung 2024.pdf"


def test_site_profiles(tmp_path):
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("INSERT INTO sites(id,url,created_at) VALUES(1,'https://example.org/','now')")
    assert get_profile(1,tmp_path)["code"]=="WEB"
    set_profile(1,mode=RENAMED,code="dsb",case="upper",data=tmp_path)
    assert get_profile(1,tmp_path)["code"]=="DSB"


def test_table_widths_reasonable():
    rows=[{"ID":1,"Website":"https://example.org",
           "Meldung":"A very long message "+("x"*1000)}]
    assert column_width(rows,"ID")<=155
    assert 175 <= column_width(rows,"Website") <= 580
    assert column_width(rows,"Meldung")<=580
    assert "Website" in streamlit_columns(rows)


def test_pdf_metadata_optional(tmp_path):
    assert file_metadata_dates(tmp_path/"missing.pdf",".pdf")==[]
