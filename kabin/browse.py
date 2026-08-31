from __future__ import annotations

import secrets


def first_index_for_prefix(titles: list[str], prefix: str) -> int | None:
    """Jump to the first visible title that starts with prefix (ES-DE letter skip)."""
    needle = prefix.casefold()
    if not needle:
        return None
    for index, title in enumerate(titles):
        text = (title or "").casefold()
        if needle == "#":
            if text[:1].isdigit():
                return index
            continue
        if text.startswith(needle):
            return index
    return None


def pick_random_index(count: int, rng=None) -> int | None:
    """Pick a random index from the current filtered view (Playnite surprise)."""
    if count <= 0:
        return None
    chooser = rng.randbelow if rng is not None else secrets.randbelow
    return chooser(count)
