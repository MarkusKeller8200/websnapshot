"""Safe, browser-readable comparison of the text extracted from HTML pages.

Snapshots contain extracted text rather than original HTML/DOM. The comparison
therefore renders *text differences*, not a pixel-perfect reconstruction.
"""
from difflib import HtmlDiff
from html import escape


def comparison_html(before: str, after: str, title: str = "") -> str:
    # HtmlDiff escapes line content and receives only constant descriptions.
    # Title is escaped explicitly: never execute markup from a remote website.
    table = HtmlDiff(tabsize=4, wrapcolumn=85).make_table(
        before.splitlines(), after.splitlines(),
        fromdesc="Vorher", todesc="Nachher", context=True, numlines=4,
    )
    return ("""<!doctype html><html lang="de"><meta charset="utf-8">
<style>
html{color-scheme:light}body{font:14px system-ui,sans-serif;padding:12px;margin:0;color:#1f2937}
h2{font-size:16px}p{color:#586174}
table.diff{width:100%;border-collapse:collapse;table-layout:fixed}
table.diff td,table.diff th{border:1px solid #e5e7eb;padding:5px 7px;
vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}
table.diff th{background:#f3f4f6;text-align:left}
.diff_header{background:#f3f4f6;width:32px}
.diff_add{background:#dbfce7}.diff_chg{background:#fff0a9}.diff_sub{background:#fbd5d5}
.diff_next{width:20px}
</style><h2>""" + escape(title) + """</h2>
<p>Direkter Vergleich des gespeicherten HTML-Textinhalts. Formatierung und
Layout der Originalseite sind nicht im Snapshot enthalten.</p>""" +
            table + "</html>")
