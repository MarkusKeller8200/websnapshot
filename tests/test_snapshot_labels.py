"""Full and Partial snapshot selectors use icon – date/time – numeric ID."""
from pathlib import Path

from websnapshot.snapshot_labels import (
    SNAPSHOT_ICONS, snapshot_choice_label, snapshot_choices, snapshot_type_label,
)


def test_snapshot_choice_format_full_and_partial():
    stamp="2026-10-14T21:24:59+00:00"
    assert snapshot_choice_label(42,stamp,"full")=="📦 - 2026.10.14 21:24:59 - 42"
    assert snapshot_choice_label(43,stamp,"partial")=="🧩 - 2026.10.14 21:24:59 - 43"
    assert SNAPSHOT_ICONS["full"]!=SNAPSHOT_ICONS["partial"]
    assert snapshot_type_label("full")=="📦 Full"
    assert snapshot_type_label("partial")=="🧩 Partial"


def test_snapshot_choices_keep_numeric_ids_and_timezone():
    history=[
        (43,"2026-10-14T23:24:59+02:00","complete","[]"),
        (42,"2026-10-13T07:08:09+00:00","complete","[]")]
    def resolve_kind(snapshot_id):
        return ("partial",42) if snapshot_id==43 else ("full",None)
    choices=snapshot_choices(history,resolve_kind)
    assert list(choices)==[43,42]
    assert choices[43]=="🧩 - 2026.10.14 21:24:59 - 43"
    assert choices[42]=="📦 - 2026.10.13 07:08:09 - 42"


def test_every_snapshot_selection_uses_shared_format():
    source=(Path(__file__).resolve().parents[1]/"src"/"websnapshot"/"app.py"
            ).read_text(encoding="utf-8")
    assert source.count("snapshot_labels=snapshot_choices(history,kind)")==4
    for name in ("Snapshot-Details","Dokumentinventar","Snapshot",
                 "Vorher","Nachher"):
        assert f'"{name}"' in source
    assert source.count("format_func=lambda i:snapshot_labels[i]")==5
    assert 'format_func=lambda value:snapshot_type_label(value)' in source
    assert '"Typ":snapshot_type_label(kind(row[0])[0])' in source
