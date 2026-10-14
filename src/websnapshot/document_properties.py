"""Read Office/PDF document properties without executing active document content.

DOCX properties come from docProps/core.xml, app.xml and custom.xml.
Legacy .doc uses OLE compound files, which are intentionally not parsed yet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

PROPERTY_LABELS = {
    "title": "Titel",
    "subject": "Betreff",
    "keywords": "Markierungen",
    "category": "Kategorien",
    "comments": "Kommentare",
    "creator": "Autoren",
    "last_modified_by": "Zuletzt gespeichert von",
    "revision": "Revisionsnummer",
    "version": "Versionsnummer",
    "application": "Programmname",
    "company": "Firma",
    "manager": "Dokumentenverwalter",
    "created": "Inhalt erstellt",
    "modified": "Letzte Speicherung",
    "last_printed": "Zuletzt gedruckt",
    "total_editing_time": "Gesamtbearbeitungszeit (Minuten)",
    "template": "Vorlage",
}
MAX_XML = 128_000


def _local(tag: str) -> str:
    return tag.rsplit("}",1)[-1]


def _xml_properties(archive: ZipFile, filename: str) -> dict[str,str]:
    try:
        member=archive.getinfo(filename)
    except KeyError:
        return {}
    if member.file_size > MAX_XML:
        raise ValueError(f"Eigenschaften-XML zu gross: {filename}")
    root=ET.fromstring(archive.read(member))
    return {_local(node.tag):node.text.strip()
            for node in root.iter() if node.text and node.text.strip()}


def docx_properties(path: Path) -> dict:
    fields={}
    with ZipFile(path) as archive:
        core=_xml_properties(archive,"docProps/core.xml")
        app=_xml_properties(archive,"docProps/app.xml")
        custom={}
        try:
            info=archive.getinfo("docProps/custom.xml")
            if info.file_size > MAX_XML:
                raise ValueError("Benutzerdefinierte Eigenschaften zu gross")
            root=ET.fromstring(archive.read(info))
            for property_node in root:
                name=property_node.attrib.get("name","").strip()
                if name:
                    custom[name]=next((element.text or ""
                        for element in property_node.iter()
                        if element is not property_node and element.text), "")
        except KeyError:
            pass
    core_map={
        "title":"title","subject":"subject","keywords":"keywords",
        "category":"category","description":"comments","creator":"creator",
        "lastModifiedBy":"last_modified_by","revision":"revision",
        "version":"version","created":"created","modified":"modified",
        "lastPrinted":"last_printed"}
    app_map={
        "Application":"application","Company":"company","Manager":"manager",
        "TotalTime":"total_editing_time","AppVersion":"version",
        "Template":"template"}
    for tag,key in core_map.items():
        if core.get(tag):
            fields[key]=core[tag]
    for tag,key in app_map.items():
        if app.get(tag) and (key not in fields or not fields[key]):
            fields[key]=app[tag]
    if custom:
        fields["custom_properties"]=custom
    return fields


def pdf_properties(path: Path) -> dict:
    from pypdf import PdfReader
    reader=PdfReader(str(path),strict=False)
    meta=reader.metadata
    if not meta:
        return {}
    raw={
        "title":meta.get("/Title"),
        "subject":meta.get("/Subject"),
        "keywords":meta.get("/Keywords"),
        "creator":meta.get("/Author"),
        "application":meta.get("/Creator"),
        "company":meta.get("/Producer"),
        "created":meta.creation_date,
        "modified":meta.modification_date,
    }
    return {key:(value.astimezone(timezone.utc).isoformat() if isinstance(value,datetime)
                  and value.tzinfo else str(value))
            for key,value in raw.items() if value is not None and str(value).strip()}


def extract_properties(path: Path, extension: str) -> dict:
    extension=extension.lower()
    try:
        if extension==".docx":
            return docx_properties(path)
        if extension==".pdf":
            return pdf_properties(path)
        if extension==".doc":
            return {}  # OLE SummaryInformation needs a separate legacy decoder.
    except (BadZipFile,ET.ParseError,ValueError,TypeError,OSError) as exc:
        raise ValueError(f"Dokumenteigenschaften nicht lesbar: {exc}") from exc
    raise ValueError("Nicht unterstütztes Dokumentformat")


def display_properties(props: dict) -> list[dict]:
    rows=[]
    for key,label in PROPERTY_LABELS.items():
        if key in props and props[key] not in ("",None):
            rows.append({"Eigenschaft":label,"Wert":str(props[key])})
    for key,val in (props.get("custom_properties") or {}).items():
        rows.append({"Eigenschaft":"Benutzerdefiniert: "+key,"Wert":str(val)})
    return rows
