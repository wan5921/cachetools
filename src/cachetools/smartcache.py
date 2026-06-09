import threading
import time
from collections.abc import Callable, Iterator, MutableMapping
from typing import Generic, TypeVar

from . import LRUCache, TTLCache

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class SmartCache(MutableMapping, Generic[_KT, _VT]):
    """Smart cache that auto-switches between LRU and TTL based on ttl parameter.

    If ttl is None, uses LRUCache internally (no expiration).
    If ttl is provided, uses TTLCache internally (with per-item time-to-live).

    Provides get_or_compute() for cache penetration protection and cleanup()
    for manual expired item removal.
    """

    def __init__(
        self,
        maxsize: float,
        ttl: float | None = None,
        timer: Callable[[], float] = time.monotonic,
        getsizeof: Callable[[_VT], float] | None = None,
    ):
        self._ttl = ttl
        self._lock = threading.Lock()
        if ttl is None:
            self._cache: LRUCache[_KT, _VT] | TTLCache[_KT, _VT, float] = LRUCache(
                maxsize, getsizeof
            )
        else:
            self._cache = TTLCache(maxsize, ttl, timer, getsizeof)

    @property
    def cache_type(self) -> str:
        return type(self._cache).__name__

    @property
    def maxsize(self) -> float:
        return self._cache.maxsize

    @property
    def currsize(self) -> float:
        return self._cache.currsize

    @property
    def ttl(self) -> float | None:
        return self._ttl

    def get_or_compute(self, key: _KT, compute_func: Callable[[_KT], _VT]) -> _VT:
        """Return cached value for key, or compute and cache it if missing.

        This method provides cache penetration protection: if the key is not
        in the cache (or has expired), compute_func is called exactly once to
        produce the value, which is then stored and returned. Thread-safe via
        an internal lock to prevent cache stampede.
        """
        with self._lock:
            try:
                return self._cache[key]
            except KeyError:
                value = compute_func(key)
                self._cache[key] = value
                return value

    def cleanup(self) -> list[tuple[_KT, _VT]]:
        """Manually clean up expired items from the cache.

        For TTL-based caches, this removes all expired entries and returns
        them as a list of (key, value) pairs. For LRU caches (no ttl),
        this is a no-op and returns an empty list.
        """
        if isinstance(self._cache, TTLCache):
            with self._lock:
                return list(self._cache.expire())
        return []

    def __getitem__(self, key: _KT) -> _VT:
        return self._cache[key]

    def __setitem__(self, key: _KT, value: _VT) -> None:
        self._cache[key] = value

    def __delitem__(self, key: _KT) -> None:
        del self._cache[key]

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: object) -> bool:
        return key in self._cache

    def __repr__(self) -> str:
        return "SmartCache(%r, cache_type=%s, ttl=%r)" % (
            self._cache,
            self.cache_type,
            self._ttl,
        )
