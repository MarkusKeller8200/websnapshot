"""Consistent and recognisable Full/Partial snapshot choice labels."""
from __future__ import annotations

from .date_format import format_datetime

SNAPSHOT_ICONS = {"full":"📦","partial":"🧩"}
SNAPSHOT_NAMES = {"full":"Full","partial":"Partial"}


def snapshot_type_label(snapshot_kind: str) -> str:
    key=str(snapshot_kind).lower()
    return f"{SNAPSHOT_ICONS.get(key,'📸')} {SNAPSHOT_NAMES.get(key,key)}"


def snapshot_choice_label(snapshot_id: int, created_at: str,
                          snapshot_kind: str) -> str:
    """Exactly: icon - YYYY.MM.DD HH:MM:SS - ID."""
    key=str(snapshot_kind).lower()
    icon=SNAPSHOT_ICONS.get(key,"📸")
    return f"{icon} - {format_datetime(created_at)} - {snapshot_id}"


def snapshot_choices(history: list[tuple], get_kind) -> dict[int,str]:
    """Build labels once per view; the lookup keeps stored numeric IDs stable."""
    return {row[0]:snapshot_choice_label(row[0],row[1],get_kind(row[0])[0])
            for row in history}
