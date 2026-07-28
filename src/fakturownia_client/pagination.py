"""Pagination helpers for Fakturownia list endpoints.

List endpoints return a bare JSON array with no total count, so the only
stop condition is a page shorter than ``per_page``. As a safety net against
an API that ignores ``page`` (which would loop forever), iteration aborts
with :class:`~fakturownia_client.exceptions.FakturowniaError` when two
consecutive pages are identical.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TypeVar

from .exceptions import FakturowniaError

T = TypeVar("T")

MAX_PER_PAGE = 100

_NOT_ADVANCING = (
    "Pagination is not advancing: page {page} returned the same items as the "
    "previous page. The API may be ignoring the 'page' parameter."
)


def iter_pages(
    fetch_page: Callable[[int], list[T]], *, per_page: int = MAX_PER_PAGE
) -> Iterator[T]:
    """Yield items from consecutive pages until a short page ends the stream."""
    page = 1
    previous: list[T] | None = None
    while True:
        items = fetch_page(page)
        if previous is not None and items == previous:
            raise FakturowniaError(_NOT_ADVANCING.format(page=page))
        yield from items
        if len(items) < per_page:
            return
        previous = items
        page += 1


async def aiter_pages(
    fetch_page: Callable[[int], Awaitable[list[T]]], *, per_page: int = MAX_PER_PAGE
) -> AsyncIterator[T]:
    """Async twin of :func:`iter_pages`."""
    page = 1
    previous: list[T] | None = None
    while True:
        items = await fetch_page(page)
        if previous is not None and items == previous:
            raise FakturowniaError(_NOT_ADVANCING.format(page=page))
        for item in items:
            yield item
        if len(items) < per_page:
            return
        previous = items
        page += 1
