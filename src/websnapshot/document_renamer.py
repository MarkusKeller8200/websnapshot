"""Configure safe, human-readable filenames for downloaded documents.

Document dates are best-effort metadata, not independently verified creation dates.
Original filenames are preserved when available, subject to Windows-safe sanitation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.parse import parse_qs
import re
import sqlite3
from .core import DATA, database

RENAMED = "dated"
ORIGINAL = "original"
CASE_MODES = {
    "first": "Nur ersten Buchstaben gross",
    "title": "Jedes Wort mit Grossbuchstaben",
    "upper": "GANZER NAME GROSS",
}
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
EXTS = (".pdf", ".doc", ".docx")
RESERVED = {"CON","PRN","AUX","NUL"} | {f"COM{i}" for i in range(1,10)} | {f"LPT{i}" for i in range(1,10)}


def clean_stem(value: str) -> str:
    value = unquote(value).rsplit("/",1)[-1]
    value = INVALID.sub("_", value).strip(" ._")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    if value.upper().split(".",1)[0] in RESERVED:
        value = "_" + value
    return value[:105].strip(" ._") or "Dokument"


def origin_code(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,16}",value):
        raise ValueError("Herkunft muss 1 bis 16 Buchstaben oder Ziffern enthalten (z. B. DSB, SEKB).")
    return value


def parse_document_date(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    try:
        date = value if isinstance(value,datetime) else parsedate_to_datetime(value)
        if date.tzinfo is None:
            date=date.replace(tzinfo=timezone.utc)
        date=date.astimezone(timezone.utc)
        return date if 1900 <= date.year <= 2100 else None
    except (ValueError,TypeError,OverflowError,IndexError):
        return None


def choose_date(*sources: tuple[str, str | datetime | None],
                now: datetime | None = None) -> tuple[datetime, str]:
    for label, raw in sources:
        parsed=parse_document_date(raw)
        if parsed is not None:
            return parsed,label
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc),"Download-Datum (Ersatzwert)"


def filename_from_headers(url: str, content_disposition: str | None = None) -> str:
    """Choose HTTP filename* / filename where present, otherwise URL basename."""
    if content_disposition:
        extended=re.search(r"filename\*\s*=\s*(?:UTF-8'')([^;]+)",content_disposition,re.I)
        if extended:
            candidate=unquote(extended.group(1).strip().strip('"'))
            if candidate:
                return candidate.rsplit("/",1)[-1].rsplit("\\",1)[-1]
        simple=re.search(r'filename\s*=\s*(?:"([^"]+)"|([^;]+))',content_disposition,re.I)
        if simple:
            return (simple.group(1) or simple.group(2)).strip().rsplit("/",1)[-1].rsplit("\\",1)[-1]
    path=unquote(urlsplit(url).path)
    filename=path.rsplit("/",1)[-1] or "Dokument"
    if filename.lower().endswith(".php"):
        query=parse_qs(urlsplit(url).query)
        identifier=(query.get("doc_id") or query.get("id") or [""])[0]
        return "Dokument_"+clean_stem(identifier) if identifier else "Dokument"
    return filename


def resolve_extension(source: str, content_type: str) -> str:
    kind=content_type.lower()
    if "application/pdf" in kind: return ".pdf"
    if "wordprocessingml.document" in kind: return ".docx"
    if "application/msword" in kind: return ".doc"
    ext=Path(source).suffix.lower()
    if ext in EXTS:
        return ext
    raise ValueError("Unbekannter PDF-/Word-Dateityp")


def build_filename(source_name: str, extension: str, *,
                   mode: str, code: str, case: str,
                   date: datetime | None = None) -> str:
    if mode not in (ORIGINAL,RENAMED):
        raise ValueError("Ungültiger Dateinamensmodus")
    ext=extension.lower()
    if ext not in EXTS:
        raise ValueError("Nur PDF- und Word-Dateien erlaubt")
    stem=source_name.rsplit(".",1)[0] if Path(source_name).suffix.lower() in EXTS else source_name
    stem=clean_stem(stem)
    if mode==ORIGINAL:
        return stem[:105]+ext
    marker=origin_code(code)
    if case not in CASE_MODES:
        raise ValueError("Ungültige Grossschreibung")
    if case=="first":
        stem=stem[:1].upper()+stem[1:]
    elif case=="title":
        stem="_".join(s[:1].upper()+s[1:].lower() for s in stem.split("_"))
    else:
        stem=stem.upper()
    when=date or datetime.now(timezone.utc)
    return f"{when:%Y_%m_%d}_{marker}_{stem[:105]}{ext}"


def default_profile() -> dict:
    return {"mode":RENAMED,"code":"WEB","case":"title"}


def init(data: Path = DATA) -> None:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS document_name_profiles (
            site_id INTEGER PRIMARY KEY, mode TEXT NOT NULL,
            code TEXT NOT NULL, case_style TEXT NOT NULL
        )""")


def get_profile(site_id: int, data: Path = DATA) -> dict:
    init(data)
    with sqlite3.connect(database(data)) as db:
        row=db.execute("SELECT mode,code,case_style FROM document_name_profiles WHERE site_id=?",
                       (site_id,)).fetchone()
    return dict(mode=row[0],code=row[1],case=row[2]) if row else default_profile()


def set_profile(site_id: int, *, mode: str, code: str,
                case: str, data: Path = DATA) -> None:
    if mode not in (ORIGINAL,RENAMED) or case not in CASE_MODES:
        raise ValueError("Ungültige Renamer-Einstellung")
    code=origin_code(code)
    init(data)
    with sqlite3.connect(database(data)) as db:
        if not db.execute("SELECT 1 FROM sites WHERE id=?",(site_id,)).fetchone():
            raise ValueError("Website nicht gefunden")
        db.execute("""INSERT INTO document_name_profiles(site_id,mode,code,case_style)
                      VALUES(?,?,?,?) ON CONFLICT(site_id) DO UPDATE SET
                      mode=excluded.mode,code=excluded.code,
                      case_style=excluded.case_style""",
                   (site_id,mode,code,case))


def unique_name(path: Path) -> Path:
    """Suggest a new non-overwriting name; caller must create it exclusively."""
    if not path.exists():
        return path
    number=2
    while True:
        candidate=path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists():
            return candidate
        number+=1
