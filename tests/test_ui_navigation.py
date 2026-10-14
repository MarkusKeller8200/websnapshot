"""UI structure tests: sidebar navigation and filtered document controls."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "websnapshot" / "app.py"

def test_ui_is_valid_python():
    ast.parse(SOURCE.read_text(encoding="utf-8"))

def test_sidebar_navigation_present():
    code = SOURCE.read_text(encoding="utf-8")
    assert "with st.sidebar:" in code
    assert '"active_site_id"' in code
    assert 'st.selectbox("Website auswählen"' in code
    assert 'ws_compact_nav' in code
    assert 'with st.popover("🌐"' in code
    assert 'ws_nav_toggle' in code
    assert '[data-testid="stSidebar"] {width: 20rem' not in code
    assert "st.selectbox(\"Website\", list(options)" not in code

def test_documents_have_bulk_controls_and_direct_selection():
    code = SOURCE.read_text(encoding="utf-8")
    assert 'filter_documents(docs,search)' in code
    for token in ("all_select","all_clear","filtered_select","filtered_clear"):
        assert token in code
    assert 'st.data_editor(' in code
    assert 'merge_visible(' in code
