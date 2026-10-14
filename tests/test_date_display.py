"""All user-visible timestamps use YYYY.MM.DD HH:MM:SS (24-hour clock)."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re

from websnapshot.date_format import format_datetime, format_property
from websnapshot.document_properties import display_properties
from websnapshot.job_logging import write, read, log_path


def test_iso_timestamp_and_utc_offset():
    assert format_datetime("2026-10-14T21:24:59+00:00")=="2026.10.14 21:24:59"
    assert format_datetime("2026-10-14T23:24:59+02:00")=="2026.10.14 21:24:59"
    assert format_datetime("2026-10-14T21:24:59Z")=="2026.10.14 21:24:59"
    assert format_datetime("2026-10-14 21:24:59.123456")=="2026.10.14 21:24:59"
    assert format_datetime(datetime(2026,10,14,23,24,59,tzinfo=
        timezone(timedelta(hours=2))))=="2026.10.14 21:24:59"


def test_http_office_and_pdf_date_formats():
    assert format_datetime("Wed, 14 Oct 2026 21:24:59 GMT")=="2026.10.14 21:24:59"
    assert format_datetime("2026.10.14 21:24:59")=="2026.10.14 21:24:59"
    assert format_datetime("D:20261014212459")=="2026.10.14 21:24:59"
    assert format_property("created","2026-10-14T21:24:59Z")=="2026.10.14 21:24:59"
    assert format_property("modified","Wed, 14 Oct 2026 21:24:59 GMT")=="2026.10.14 21:24:59"
    assert format_property("last_printed","2026-10-14T21:24:59Z")=="2026.10.14 21:24:59"


def test_missing_time_or_unparseable_data_are_not_fabricated():
    assert format_datetime("2026-10-14")=="2026.10.14"
    assert format_datetime(date(2026,10,14))=="2026.10.14"
    assert format_datetime(None)=="–"
    assert format_datetime(None,fallback="")==""
    assert format_datetime("nicht bekannt")=="nicht bekannt"
    assert format_property("creator","Dr. Muster")=="Dr. Muster"
    assert format_datetime("2026-13-99")=="2026-13-99"


def test_document_property_labels_use_standard_datetime():
    rows=display_properties({
        "title":"Beispiel",
        "created":"2026-10-14T20:10:11+00:00",
        "modified":"Wed, 14 Oct 2026 21:24:59 GMT",
        "custom_properties":{"Projekt":"WebSnapshot"},
    })
    vals={row["Eigenschaft"]:row["Wert"] for row in rows}
    assert vals["Inhalt erstellt"]=="2026.10.14 20:10:11"
    assert vals["Letzte Speicherung"]=="2026.10.14 21:24:59"
    assert vals["Titel"]=="Beispiel"
    assert vals["Benutzerdefiniert: Projekt"]=="WebSnapshot"


def test_log_display_and_old_iso_timestamps(tmp_path: Path):
    write(1,"INFO","Crawl gestartet",tmp_path)
    message=read(1,tmp_path)
    assert re.match(r"^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2} \[INFO\]",message)
    with log_path(1,tmp_path).open("a",encoding="utf-8") as stream:
        stream.write("2026-10-14T21:24:59+00:00 [INFO] Alter Logeintrag\n")
    assert "2026.10.14 21:24:59 [INFO] Alter Logeintrag" in read(1,tmp_path)


def test_ui_displays_not_raw_iso_dates():
    code=(Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py"
          ).read_text(encoding="utf-8")
    assert '"Zeit (UTC)":format_datetime(row[1])' in code
    assert '"Erstellt":format_datetime(d.get("created"),fallback="")' in code
    assert 'format_datetime(details.get("last_modified"))' in code
    assert 'format_datetime(start_time)' in code
    assert 'format_datetime(last_activity)' in code
    assert 'row[1].replace("T"," ")[:19]' not in code
    assert 'strftime("%d.%m.' not in code
