"""Retry policy shared by the sync and async clients."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with jitter; honours Retry-After when given."""

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    statuses: frozenset[int] = field(default_factory=lambda: RETRYABLE_STATUSES)

    def should_retry(self, attempt: int, status_code: int | None) -> bool:
        """attempt is 0-based; status_code None means a transport error."""
        if attempt >= self.max_retries:
            return False
        return status_code is None or status_code in self.statuses

    def delay(self, attempt: int, *, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return min(retry_after, self.backoff_max)
        exp = min(self.backoff_base * (2**attempt), self.backoff_max)
        return random.uniform(0, exp)
