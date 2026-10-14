"""Website-specific path exclusions, applied before discovery/visiting.

One path rule covers the exact path, its trailing slash variant and descendants.
A directory/landing stem also covers its .html/.htm landing document.
Query strings and fragments do not affect the path match.
"""
from __future__ import annotations

from urllib.parse import unquote, urlsplit
import posixpath

MAX_RULES = 2000
MAX_LENGTH = 2000


def _path(value: str) -> str:
    raw = unquote(value)
    if chr(0) in raw or "\\" in raw:
        raise ValueError("Ungültiger URL-Pfad")
    if not raw.startswith("/") or raw.startswith("//"):
        raise ValueError("Ausschlüsse müssen mit / beginnen (keine vollständigen URLs).")
    if any(char in raw for char in ("?", "#", "*")):
        raise ValueError("Nur URL-Pfade ohne Query, Fragment oder Wildcards eingeben.")
    if len(raw) > MAX_LENGTH:
        raise ValueError("Ausschlusspfad zu lang (maximal 2'000 Zeichen).")
    # Canonicalise decoded percent-encoded separators and dot segments.
    normal = posixpath.normpath(raw)
    return normal if normal.startswith("/") else "/" + normal


def parse_excludes(text: str | list[str] | tuple[str, ...]) -> list[str]:
    """Validate and de-duplicate rules, preserving their configured order."""
    if isinstance(text,str):
        lines = text.splitlines()
    elif isinstance(text,(list,tuple)):
        lines = text
    else:
        raise ValueError("Ungültige Ausschlussliste")
    result=[]
    seen=set()
    for item in lines:
        if not isinstance(item,str):
            raise ValueError("Ausschlüsse müssen Textzeilen sein.")
        stripped=item.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rule=_path(stripped)
        if rule not in seen:
            seen.add(rule)
            result.append(rule)
            if len(result)>MAX_RULES:
                raise ValueError("Maximal 2'000 Ausschlusspfade pro Website.")
    return result


def excluded_by(url: str, rules: list[str] | tuple[str, ...]) -> str | None:
    """Return the matching rule, if any (no cross-prefix false positives)."""
    # All candidate URLs come from the existing normaliser, which validates
    # schemes and hostnames. This function only inspects the path.
    path = posixpath.normpath(unquote(urlsplit(url).path) or "/")
    for rule in rules:
        if rule == "/":
            return rule
        if path == rule or path.startswith(rule + "/"):
            return rule
        if not posixpath.splitext(rule)[1] and path in (rule + ".html",rule + ".htm"):
            return rule
    return None
