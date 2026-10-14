"""Content-aware auto-sizing for every visible Streamlit table column.

Streamlit/AG Grid does not expose an automatic 'fit all cell contents' option
for every column type in the st.column_config API. Calculate practical column
widths based on the column header and a bounded, representative cell sample.
All columns, including the last one, receive a calculated width. Long URLs
remain scrollable/accessible instead of making every other column unusable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from math import ceil

NUMERIC_NAMES = {
    "id","nr.","seiten","snapshots","dokumente","urls",
    "zeichen","varianten","vorkommen","fehler","offene urls",
    "warnungen/fehler","archivierter text (mb)","grösse","grösse (http)",
    "aufklappen","fundstellen","messungen","anzahl",
    "min. (ms)","ø (ms)","max. (ms)","summe (ms)",
    "minimum (ms)","durchschnitt (ms)","maximum (ms)",
    "ausgeschlossene url-kandidaten","übersprungene url-kandidaten",
}
WIDE_NAMES = {
    "website","dokument","dokument / url","url","meldung","pfad",
    "titel","seitentitel","wert","quellseite","ausgeschlossene url",
    "fundstelle","öffnen","langsamste url","ausgeschlossener pfad",
    "ebene / pfad",
}
DATE_NAMES = {
    "zeit (utc)","datum (utc)","letzter snapshot (utc)",
    "erstellt","geändert","letzte speicherung","inhalt erstellt",
}
STATUS_NAMES = {"status","änderungsstatus","erfassung","typ","quelle","grund"}
CHECK_NAMES = {"auswahl","gespeichert","heruntergeladen","aufklappen"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value,bool):
        return "Ja" if value else "Nein"
    if isinstance(value,(datetime,date)):
        return str(value)
    return str(value)


def _sample(rows: Sequence[Mapping], limit: int = 400):
    """Look at both ends and the middle of large tables, not only row 1-250."""
    length=len(rows)
    if length<=limit:
        yield from rows
        return
    # No copies of huge documents or intermediate column-value arrays.
    head=min(80,length)
    for index in range(head):
        yield rows[index]
    middle=limit-head-80
    for i in range(middle):
        yield rows[(i+1)*(length-1)//(middle+1)]
    for index in range(length-80,length):
        yield rows[index]


def column_width(rows: Sequence[Mapping], column: str, *,
                 cap: int | None = None, header: str | None = None,
                 link: bool = False) -> int:
    """Estimate the width needed by a grid column, with reasonable guardrails."""
    key=column.casefold()
    title=header or column
    if key in CHECK_NAMES:
        return min(cap or 130,max(110,len(title)*8+30))
    if key in NUMERIC_NAMES:
        lower,upper=80,220
    elif key in DATE_NAMES:
        lower,upper=165,245
    elif key in STATUS_NAMES:
        lower,upper=120,320
    elif key in WIDE_NAMES or link:
        lower,upper=165,720
    else:
        lower,upper=110,450
    if cap is not None:
        upper=min(upper,cap)
        lower=min(lower,upper)
    measured=max((max((len(part) for part in _as_text(row.get(column)).splitlines()),default=0)
                  for row in _sample(rows)),default=0)
    # Approximate proportional UI font; account for cell paddings and sort icons.
    pixels=max(len(title)*8+38,measured*7+38)
    return max(lower,min(upper,pixels))


def widths(rows: Sequence[Mapping]) -> dict[str,int]:
    if not rows:
        return {}
    return {name:column_width(rows,name) for name in rows[0]}


def streamlit_columns(rows: Sequence[Mapping], *, links=(), checks=(),
                      labels: Mapping[str,str] | None = None) -> dict:
    """Return fitted Streamlit configs for ALL columns, including the last."""
    import streamlit as st
    links=set(links)
    checks=set(checks)
    labels=labels or {}
    result={}
    for name in rows[0] if rows else ():
        heading=labels.get(name,name)
        size=column_width(rows,name,header=heading,link=name in links)
        if name in links:
            result[name]=st.column_config.LinkColumn(heading,width=size)
        elif name in checks:
            result[name]=st.column_config.CheckboxColumn(heading,width=size)
        else:
            result[name]=st.column_config.Column(heading,width=size)
    return result
