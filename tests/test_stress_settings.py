"""Upper stress-test settings and automatic table layout."""
from websnapshot.global_settings import save, get, defaults
from websnapshot.table_layout import streamlit_columns


def test_10_workers_and_100000_visited_pages_configurable(tmp_path):
    profile=save(
        download_directory=str(tmp_path/"downloads"),
        flat_downloads=False,visit_limit=100000,
        discovery_limit=1000000,page_timeout=3.0,
        http_workers=10,sitemap_height=800,data=tmp_path,
    )
    assert get(tmp_path)==profile
    assert profile["visit_limit"]==100000
    assert profile["discovery_limit"]==1000000
    assert profile["http_workers"]==10
    assert defaults(tmp_path)["visit_limit"]==2000
    assert defaults(tmp_path)["http_workers"]==3


def test_streamlit_columns_auto_size_including_final():
    rows=[{"Pfad":"/schule-hinterbirch","Titel":"Aktuelles",
           "Zeichen":101,"URL":"https://example.org/a"}]
    config=streamlit_columns(rows)
    assert "Pfad" in config
    assert "Titel" in config
    assert "Zeichen" in config
    assert "URL" in config
    assert config["URL"]["width"] >= 175
    assert config["URL"]["width"] <= 580
