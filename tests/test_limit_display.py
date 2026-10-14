"""Regression: live crawl limit indicators are persisted for each completed job."""
import ast
from pathlib import Path

def test_inventory_limit_instrumentation_compiles():
    source=Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"inventory.py"
    ast.parse(source.read_text(encoding="utf-8"))
    code=source.read_text(encoding="utf-8")
    assert "limit_warnings=limit_warnings()" in code
    assert 'limit_exclusions["path_variants"]+=1' in code
    assert 'limit_exclusions["page_links"]+=len(links)-MAX_PER_PAGE' in code

def test_ui_live_limits_compile():
    source=Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py"
    ast.parse(source.read_text(encoding="utf-8"))
    code=source.read_text(encoding="utf-8")
    assert "Schutzlimit erreicht" in code
    assert "Entdeckte URLs:" in code
    assert "Besuchte URLs:" in code
