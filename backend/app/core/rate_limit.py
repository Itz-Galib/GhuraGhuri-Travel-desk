"""In-memory sliding-window rate limiting (single process; v1 scale)."""

import threading
import time
from collections import defaultdict, deque

from app.core.config import get_settings
from app.core.errors import RateLimitedError

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(*, bucket: str, identifier: str, limit: int, window_seconds: int) -> None:
    """Raise RateLimitedError when the key exceeds `limit` in the window."""
    if not get_settings().rate_limit_enabled:
        return
    key = f"{bucket}:{identifier}"
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        hits = _hits[key]
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(hits[0] + window_seconds - now))
            raise RateLimitedError(
                "Too many requests. Try again later.",
                details={"retry_after_seconds": retry_after},
            )
        hits.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()
