"""Content-aware column widths for Streamlit dataframes.

Widths are heuristics in pixels. Very long URLs, diffs and messages get a
generous but bounded width so a single cell cannot hide every other column.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from itertools import islice

NUMERIC_NAMES = {
    "id", "nr.", "seiten", "snapshots", "dokumente", "urls",
    "zeichen", "varianten", "vorkommen", "fehler", "offene urls",
    "warnungen/fehler", "archivierter text (mb)", "grösse", "grösse (http)",
}
WIDE_NAMES = {"website", "dokument", "dokument / url", "url", "meldung", "pfad", "titel", "seitentitel", "wert"}
DATE_NAMES = {"zeit (utc)", "datum (utc)", "letzter snapshot (utc)", "laufzeit"}
STATUS_NAMES = {"status", "änderungsstatus", "erfassung", "typ", "quelle"}
CHECK_NAMES = {"auswahl", "gespeichert", "heruntergeladen"}


def column_width(rows: Sequence[Mapping], column: str, *, cap: int | None = None) -> int:
    key=column.casefold()
    if key in CHECK_NAMES:
        return 112
    if key in NUMERIC_NAMES:
        lower,upper=75,155
    elif key in DATE_NAMES:
        lower,upper=120,205
    elif key in STATUS_NAMES:
        lower,upper=115,225
    elif key in WIDE_NAMES:
        lower,upper=175,580
    else:
        lower,upper=110,285
    if cap is not None:
        upper=min(upper,cap)
    header=len(column)
    measured=max((len(str(row.get(column,"") or "")) for row in islice(rows,250)),default=0)
    # A proportional-font estimate; favour legibility over wasting space.
    pixels=max(header*8+28,measured*7+28)
    return max(lower,min(upper,pixels))


def widths(rows: Sequence[Mapping]) -> dict[str,int]:
    if not rows:
        return {}
    return {name:column_width(rows,name) for name in rows[0]}


def streamlit_columns(rows: Sequence[Mapping], *, links=(), checks=()) -> dict:
    """Preserve dataframe column types; set widths only, plus explicit links."""
    import streamlit as st
    links=set(links)
    checks=set(checks)
    result={}
    for name,value in widths(rows).items():
        if name in links:
            result[name]=st.column_config.LinkColumn(name,width=value)
        elif name in checks:
            result[name]=st.column_config.CheckboxColumn(name,width=value)
        else:
            result[name]=st.column_config.Column(name,width=value)
    return result
