"""Nur bekannte, zugehörige Dokument-Subdomains ins Inventar aufnehmen."""
from urllib.parse import urlsplit
from .core import normalize_url

DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xlsx", ".xls", ".txt", ".csv")

def related_document(url: str, website: str) -> bool:
    """Allow explicit PDF/Word links on docs.<website-host>, not foreign-site crawling."""
    try:
        target = urlsplit(normalize_url(url))
        origin = urlsplit(normalize_url(website))
    except (ValueError, TypeError):
        return False
    base = origin.hostname.removeprefix("www.")
    return (target.scheme == "https" and
            target.hostname == "docs." + base and
            target.path.lower().endswith(DOCUMENT_EXTENSIONS))
