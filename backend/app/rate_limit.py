"""Slows down password guessing: after too many failed logins for one email
address within a time window, the login answers 429 Too Many Requests.

Kept in memory: fine for one server process. With more processes or servers
this would move to a shared store such as Redis.
"""

import threading
import time
from collections import deque


class LoginThrottle:
    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}  # email -> times of recent failures
        self._lock = threading.Lock()  # endpoints run in several threads at once

    def retry_after(self, key: str) -> int:
        """0 if this key may try now, otherwise the number of seconds to wait."""
        now = time.monotonic()
        with self._lock:
            times = self._failures.get(key)
            if not times:
                return 0
            while times and times[0] <= now - self.window_seconds:
                times.popleft()  # forget failures older than the window
            if not times:
                del self._failures[key]
                return 0
            if len(times) < self.max_failures:
                return 0
            return int(times[0] + self.window_seconds - now) + 1

    def record_failure(self, key: str) -> None:
        with self._lock:
            # maxlen: we never need more than the last max_failures timestamps.
            # The number of keys stays small because every failed login costs an
            # Argon2 hash first, which limits how fast anyone can add keys.
            times = self._failures.setdefault(key, deque(maxlen=self.max_failures))
            times.append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
