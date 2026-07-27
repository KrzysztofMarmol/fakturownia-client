"""Pagination helper for Fakturownia list endpoints.

List endpoints return a bare JSON array with no total count, so the only
stop condition is a page shorter than ``per_page``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TypeVar

T = TypeVar("T")

MAX_PER_PAGE = 100


def iter_pages(
    fetch_page: Callable[[int], list[T]], *, per_page: int = MAX_PER_PAGE
) -> Iterator[T]:
    """Yield items from consecutive pages until a short page ends the stream."""
    page = 1
    while True:
        items = fetch_page(page)
        yield from items
        if len(items) < per_page:
            return
        page += 1
