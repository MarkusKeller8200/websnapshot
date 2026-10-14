"""Pure selection/filter helpers for the document download inventory."""
from __future__ import annotations
from collections.abc import Iterable, Mapping

def filter_documents(documents: list[dict], search: str) -> list[dict]:
    query = search.strip().casefold()
    if not query:
        return documents
    return [item for item in documents if query in " ".join(str(item.get(k) or "")
            for k in ("url", "status", "length")).casefold()]

def bulk_selection(current: Iterable[str], all_urls: Iterable[str],
                   filtered_urls: Iterable[str], action: str) -> set[str]:
    """Return a new selection; never discard hidden matches inadvertently."""
    valid = set(all_urls)
    visible = set(filtered_urls) & valid
    result = set(current) & valid
    if action == "all_select":
        return valid
    if action == "all_clear":
        return set()
    if action == "filtered_select":
        return result | visible
    if action == "filtered_clear":
        return result - visible
    raise ValueError(f"Unbekannte Auswahlaktion: {action}")

def merge_visible(current: Iterable[str], all_urls: Iterable[str],
                  filtered_urls: Iterable[str], selected_visible: Iterable[str]) -> set[str]:
    valid = set(all_urls)
    visible = set(filtered_urls) & valid
    return ((set(current) & valid) - visible) | (set(selected_visible) & visible)
