import threading
from contextlib import contextmanager
from typing import Iterator

from backend.src.core.errors import api_error


class AdventureLockService:
    _guard = threading.Lock()
    _locks: dict[int, threading.Lock] = {}

    @contextmanager
    def acquire(self, adventure_id: int) -> Iterator[None]:
        lock = self._lock_for(adventure_id)
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise api_error(409, "dm_busy", "DM is still responding.")
        try:
            yield
        finally:
            lock.release()

    def _lock_for(self, adventure_id: int) -> threading.Lock:
        with self._guard:
            if adventure_id not in self._locks:
                self._locks[adventure_id] = threading.Lock()
            return self._locks[adventure_id]
