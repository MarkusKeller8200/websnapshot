"""Restrict the crawl to a logical URL subtree without dropping linked files."""
from urllib.parse import unquote, urlsplit
from .core import normalize_url

SCOPE_AUTO = "auto"
SCOPE_PATH = "path"
SCOPE_HOST = "host"
SCOPES = {SCOPE_AUTO:"Automatisch (Unterbereich bei Unterseiten)",
          SCOPE_PATH:"Nur Startseite und darunterliegende Pfade",
          SCOPE_HOST:"Gesamte Domain"}
DOCUMENT_SUFFIXES = (".pdf",".doc",".docx")


def logical_root(start: str) -> str:
    path=unquote(urlsplit(normalize_url(start)).path).rstrip("/") or "/"
    # Many government sites put the landing page at /de/bildung.html,
    # with descendants at /de/bildung/...
    if path.lower().endswith((".html",".htm")):
        path=path.rsplit(".",1)[0]
    return path


def effective_scope(start: str, mode: str = SCOPE_AUTO) -> str:
    if mode not in SCOPES:
        raise ValueError("Unbekannter Crawl-Bereich")
    if mode == SCOPE_AUTO:
        return SCOPE_HOST if logical_root(start)=="/" else SCOPE_PATH
    return mode


def within_scope(url: str, start: str, mode: str = SCOPE_AUTO) -> bool:
    try:
        target=urlsplit(normalize_url(url))
        origin=urlsplit(normalize_url(start))
        if target.netloc!=origin.netloc:
            return False
        if effective_scope(start,mode)==SCOPE_HOST:
            return True
        path=unquote(target.path).rstrip("/") or "/"
        root=logical_root(start)
        return (root=="/" or path==root
                or path.lower()==root.lower()+".html"
                or path.lower()==root.lower()+".htm"
                or path.startswith(root+"/"))
    except (TypeError,ValueError):
        return False


def is_document(url: str) -> bool:
    try:
        return urlsplit(normalize_url(url)).path.lower().endswith(DOCUMENT_SUFFIXES)
    except (TypeError,ValueError):
        return False


def eligible_link(url: str, start: str, mode: str = SCOPE_AUTO, *,
                  directly_linked: bool = True) -> bool:
    """Pages must be in scope; referenced PDFs may sit in a shared /content/dam folder.

    A full-domain sitemap must NOT inject unrelated PDF files from outside scope.
    """
    if within_scope(url,start,mode):
        return True
    target=urlsplit(normalize_url(url))
    origin=urlsplit(normalize_url(start))
    return (directly_linked and target.netloc==origin.netloc
            and is_document(url))
