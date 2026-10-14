"""Sitemap tree model and portable CSV/XLSX export (standard-library OOXML).

The tree is constructed from metadata only: it does not need to load the
archived HTML bodies, even for snapshots containing many thousands of pages.
"""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

EXPORT_COLUMNS = ("Pfad", "Titel", "Zeichen", "URL")
TREE_COLUMNS = ("Aufklappen", "Ebene / Pfad", "Seiten", "Titel", "Zeichen", "Öffnen", "URL")


def tree_from_pages(pages: list[dict]) -> dict:
    """A path can simultaneously be a page and a parent directory."""
    root = {"id": "/", "label": "/", "children": {},
            "url": "", "title": "", "chars": 0, "count": 0, "parent": None}
    nodes = {"/": root}
    for page in pages:
        url = page["URL"]
        path = urlsplit(url).path or "/"
        segments = [unquote(x) for x in path.split("/") if x]
        parent = root
        parent["count"] += 1
        current_path = ""
        if not segments:
            segments = ["/"]
        for segment in segments:
            current_path += "/" + segment if segment != "/" else "/"
            key = current_path
            if key not in nodes:
                node = {"id": key, "label": segment, "children": {},
                        "url": "", "title": "", "chars": 0,
                        "count": 0, "parent": parent["id"]}
                nodes[key] = node
                parent["children"][key] = node
            node = nodes[key]
            node["count"] += 1
            parent = node
        if parent["url"] and parent["url"] != url:
            # Separate query-string variants of the same URL path.
            key = "url:" + url
            parent["children"][key] = {
                "id": key, "label": "?" + (urlsplit(url).query or "Variante"),
                "children": {}, "url": url, "title": page["Titel"],
                "chars": page["Zeichen"], "count": 1, "parent": parent["id"],
            }
        else:
            parent["url"] = url
            parent["title"] = page["Titel"]
            parent["chars"] = page["Zeichen"]
    return root


def visible_tree_rows(root: dict, expanded: set[str], *,
                      limit: int = 2500) -> tuple[list[dict], list[str], bool]:
    """Only render visible nodes, not every entry in a million-URL tree."""
    rows = []
    ids = []
    stack = [(node,0) for node in sorted(root["children"].values(),
                          key=lambda n:n["label"].casefold(),reverse=True)]
    while stack and len(rows) < limit:
        node,depth = stack.pop()
        children = bool(node["children"])
        open_now = children and node["id"] in expanded
        icon = "📂" if open_now else "📁" if children else "📄"
        indent = "\u00a0"*min(24,depth*3)
        rows.append({
            "Aufklappen": open_now if children else False,
            "Ebene / Pfad": indent+icon+" "+node["label"],
            "Seiten":node["count"] if children else 1,
            "Titel":node["title"],
            "Zeichen":node["chars"] if node["url"] else None,
            "Öffnen":node["url"],
            "URL":node["url"],
        })
        ids.append(node["id"])
        if open_now:
            for child in sorted(node["children"].values(),
                                key=lambda n:n["label"].casefold(),reverse=True):
                stack.append((child,depth+1))
    return rows,ids,bool(stack)


def all_parent_ids(root: dict) -> set[str]:
    """Useful for showing all ancestors when the user has filtered the tree."""
    result=set()
    stack=list(root["children"].values())
    while stack:
        node=stack.pop()
        if node["children"]:
            result.add(node["id"])
            stack.extend(node["children"].values())
    return result


def filtered_page_rows(pages: list[dict], query: str) -> list[dict]:
    term=query.casefold().strip()
    if not term:
        return pages
    return [row for row in pages if term in
            (str(row.get("Pfad",""))+" "+str(row.get("Titel",""))+
             " "+str(row.get("URL",""))).casefold()]


def _safe_csv_cell(value) -> str:
    text=str(value if value is not None else "")
    # Guard spreadsheets which may interpret CSV cells as formulas on import.
    if text.lstrip().startswith(("=","+","-","@")):
        return "'"+text
    return text


def export_csv(pages: list[dict]) -> bytes:
    writer_buffer=StringIO(newline="")
    writer=csv.writer(writer_buffer,delimiter=";",lineterminator="\r\n")
    writer.writerow(EXPORT_COLUMNS)
    for row in pages:
        writer.writerow([_safe_csv_cell(row.get(key,"")) for key in EXPORT_COLUMNS])
    return ("\ufeff"+writer_buffer.getvalue()).encode("utf-8")


def _xml(value) -> str:
    # XLSX inline strings are literal cells, not executable Excel formulae.
    text=str(value if value is not None else "")[:32767]
    text="".join(c for c in text if ord(c) >= 32 or c in "\t\n\r")
    return escape(text,{"\"":"&quot;","'":"&apos;"})


def export_xlsx(pages: list[dict]) -> bytes:
    """Stream a real, sortable XLSX workbook with frozen heading row.

    Uses only the standard library and writes individual rows to the zip
    archive rather than constructing a huge XML document in memory.
    """
    output=BytesIO()
    last=len(pages)+1
    with ZipFile(output,"w",compression=ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>')
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        z.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sitemap" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
        z.writestr("xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Aptos"/></font>'
            '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Aptos"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF1E3A5F"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFill="1" applyFont="1"/></cellXfs>'
            '</styleSheet>')
        with z.open("xl/worksheets/sheet1.xml","w") as sheet:
            def put(value: str):
                sheet.write(value.encode("utf-8"))
            put('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                '<cols><col min="1" max="1" width="45" customWidth="1"/>'
                '<col min="2" max="2" width="48" customWidth="1"/>'
                '<col min="3" max="3" width="15" customWidth="1"/>'
                '<col min="4" max="4" width="73" customWidth="1"/></cols><sheetData>')
            columns="ABCD"
            put('<row r="1" ht="26" customHeight="1">')
            for idx,label in enumerate(EXPORT_COLUMNS):
                put(f'<c r="{columns[idx]}1" s="1" t="inlineStr"><is><t>{_xml(label)}</t></is></c>')
            put("</row>")
            for index,row in enumerate(pages,2):
                put(f'<row r="{index}">')
                for i,key in enumerate(EXPORT_COLUMNS):
                    value=row.get(key,"")
                    addr=f"{columns[i]}{index}"
                    if key=="Zeichen" and isinstance(value,(int,float)):
                        put(f'<c r="{addr}"><v>{int(value)}</v></c>')
                    else:
                        put(f'<c r="{addr}" t="inlineStr"><is><t>{_xml(value)}</t></is></c>')
                put("</row>")
            put(f'</sheetData><autoFilter ref="A1:D{last}"/></worksheet>')
    return output.getvalue()
