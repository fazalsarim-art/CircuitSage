"""A small, process-local fixed-window rate limiter.

Used to throttle authentication attempts (§7.12). It is intentionally in-memory and
per-process: it defends a single instance against brute-force bursts without adding a Redis
dependency. A multi-instance deployment would need a shared store; that limitation is recorded
in docs/threat-model.md. State is held per app instance (see ``create_app``) so tests are
isolated from one another.
"""

import threading
import time


class FixedWindowRateLimiter:
    """Allow at most ``max_events`` per ``window_seconds`` for each key."""

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self._max_events = max_events
        self._window = window_seconds
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record an event for ``key``; return True if it is within the limit, else False."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._hits.get(key, (now, 0))
            if now - window_start >= self._window:
                window_start, count = now, 0
            count += 1
            self._hits[key] = (window_start, count)
            return count <= self._max_events

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)
