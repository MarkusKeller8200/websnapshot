"""Every visible WebSnapshot table must fit ALL columns, including trailing URLs."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import ast

from websnapshot.table_layout import column_width, streamlit_columns, widths
from websnapshot.sitemap_view import export_xlsx


APP=Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py"


def test_all_columns_have_computed_widths_including_last():
    rows=[{"Pfad":"/schule-hinterbirch","Titel":"Aktuelles",
           "Zeichen":101,"URL":"https://example.org/a"}]
    settings=streamlit_columns(rows)
    assert list(settings)==list(rows[0])
    assert all(isinstance(settings[col]["width"],int) for col in rows[0])
    assert widths(rows)["URL"]==settings["URL"]["width"]


def test_content_changes_width_and_long_urls_are_bounded():
    small=[{"Meldung":"Kurz","URL":"https://e.ch/a"}]
    large=[{"Meldung":"Ein deutlich längerer Warnungstext zum Testen",
            "URL":"https://e.ch/"+("sehr-lang"*400)}]
    assert column_width(large,"Meldung")>column_width(small,"Meldung")
    assert column_width(large,"URL")<=580
    assert column_width(small,"URL")>=175
    assert column_width(large,"URL",cap=250)<=250


def test_sample_fits_middle_and_end_of_big_table():
    rows=[{"Titel":"Kurz","URL":"https://example.org/"} for _ in range(15000)]
    rows[14999]={"Titel":"Sehr langer Titel aus dem letzten Datensatz",
                  "URL":"https://example.org/letzter-datensatz-mit-vielen-zeichen"}
    assert column_width(rows,"Titel")>column_width(rows[:10],"Titel")
    assert column_width(rows,"URL")>column_width(rows[:10],"URL")


def test_all_dataframe_and_editor_widgets_provide_column_configs():
    tree=ast.parse(APP.read_text(encoding="utf-8"))
    widgets=[
        node for node in ast.walk(tree)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and node.func.attr in ("dataframe","data_editor")
    ]
    assert len(widgets)>=17
    for call in widgets:
        assert any(key.arg=="column_config" for key in call.keywords), (
            "Tabelle ohne Auto-Size column_config bei Zeile "
            +str(call.lineno))


def test_xlsx_export_column_widths_fit_content_not_fixed_constants():
    short=[{"Pfad":"/a","Titel":"X","Zeichen":1,"URL":"https://a.ch/a"}]
    long=[{"Pfad":"/schulverwaltung/aktuelle-richtlinien-und-prozesse",
           "Titel":"Richtlinien für Schulen und Lehrpersonen",
           "Zeichen":123,"URL":"https://example.org/schulverwaltung/aktuelle-richtlinien"}]
    ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    def measurements(data):
        with ZipFile(BytesIO(export_xlsx(data))) as file:
            root=ET.fromstring(file.read("xl/worksheets/sheet1.xml"))
            return [float(x.attrib["width"]) for x in root.findall(".//m:cols/m:col",ns)]
    short_w=measurements(short)
    long_w=measurements(long)
    assert len(short_w)==len(long_w)==4
    assert long_w[0]>short_w[0]
    assert long_w[1]>short_w[1]
    assert long_w[3]>short_w[3]
