"""Regression tests for the consolidated side navigation and inline HTML diff."""
import ast
from pathlib import Path

from websnapshot.ui_diff import comparison_html

APP = Path(__file__).resolve().parents[1] / "src" / "websnapshot" / "app.py"


def test_app_syntax_and_nine_independent_views():
    code = APP.read_text(encoding="utf-8")
    ast.parse(code)
    assert "st.tabs(" not in code
    for page in ("Dashboard","Websites verwalten","Snapshot starten",
                 "Snapshot-Verwaltung","Änderungsvergleich","Dokumente",
                 "Sitemap","Job-Protokolle","Updates"):
        assert f'if current_page == "{page}":' in code
    assert "padding-top: 3.7rem !important" in code


def test_inline_html_diff_is_escaped():
    markup = comparison_html("<script>alert('x')</script>\nalt",
                             "<b>Neu</b>\naktuell", "<svg onload='bad'>")
    assert "<script>alert" not in markup
    assert "<b>Neu</b>" not in markup
    assert "<svg onload" not in markup
    assert "&lt;script&gt;" in markup
    assert "Vorher" in markup
    assert "Nachher" in markup
    assert 'table class="diff"' in markup or 'class="diff"' in markup
