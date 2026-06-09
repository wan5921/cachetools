"""Smart cache module with automatic LRU/TTL selection.

This module provides a :class:`SmartCache` that automatically selects
between an LRU and TTL backend based on the ``ttl`` argument, together
with a :meth:`SmartCache.get_or_compute` helper for cache-penetration
protection and an explicit :meth:`SmartCache.cleanup` method.
"""

__all__ = ("SmartCache",)

import threading
from typing import Any, Callable, Optional

from . import LRUCache, TTLCache


class SmartCache:
    """A smart cache that auto-switches between LRU and TTL backends.

    Parameters
    ----------
    maxsize:
        Maximum number of items the cache may hold.
    ttl:
        Optional time-to-live (in seconds) for each cached item.  When
        ``None`` the cache uses a plain :class:`LRUCache`; otherwise a
        :class:`TTLCache` is used and items automatically expire after
        ``ttl`` seconds.
    timer:
        Timer callable forwarded to :class:`TTLCache`.  Defaults to
        ``time.monotonic``.
    getsizeof:
        Optional size function forwarded to the underlying cache.
    """

    _sentinel = object()

    def __init__(
        self,
        maxsize: int,
        ttl: Optional[float] = None,
        *,
        timer: Optional[Callable[[], float]] = None,
        getsizeof: Optional[Callable[[Any], int]] = None,
    ) -> None:
        if ttl is None:
            self._backend: Any = (
                LRUCache(maxsize, getsizeof)
                if getsizeof is not None
                else LRUCache(maxsize)
            )
            self._ttl: Optional[float] = None
        else:
            kwargs: dict = {"ttl": ttl}
            if timer is not None:
                kwargs["timer"] = timer
            if getsizeof is not None:
                kwargs["getsizeof"] = getsizeof
            self._backend = TTLCache(maxsize, **kwargs)
            self._ttl = float(ttl)

        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Basic mapping interface
    # ------------------------------------------------------------------

    @property
    def maxsize(self) -> int:
        """The maximum number of items this cache can hold."""
        return self._backend.maxsize

    @property
    def currsize(self) -> int:
        """The current number of items in the cache."""
        return self._backend.currsize

    @property
    def ttl(self) -> Optional[float]:
        """The configured TTL, or ``None`` when the cache is LRU-only."""
        return self._ttl

    @property
    def backend_type(self) -> str:
        """Return ``"LRU"`` or ``"TTL"`` depending on the active backend."""
        return "TTL" if self._ttl is not None else "LRU"

    def __contains__(self, key: Any) -> bool:
        return key in self._backend

    def __getitem__(self, key: Any) -> Any:
        return self._backend[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._backend[key] = value

    def __delitem__(self, key: Any) -> None:
        del self._backend[key]

    def __len__(self) -> int:
        return len(self._backend)

    def __iter__(self):
        return iter(self._backend)

    def __repr__(self) -> str:
        return "SmartCache(maxsize=%r, ttl=%r, items=%r)" % (
            self.maxsize,
            self._ttl,
            dict(self._backend),
        )

    def get(self, key: Any, default: Any = None) -> Any:
        return self._backend.get(key, default)

    def pop(self, key: Any, default: Any = _sentinel) -> Any:
        if default is SmartCache._sentinel:
            return self._backend.pop(key)
        return self._backend.pop(key, default)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        return self._backend.setdefault(key, default)

    def clear(self) -> None:
        """Remove all items from the cache."""
        self._backend.clear()

    # ------------------------------------------------------------------
    # Smart helpers
    # ------------------------------------------------------------------

    def get_or_compute(
        self,
        key: Any,
        compute_func: Callable[[], Any],
        *,
        force: bool = False,
    ) -> Any:
        """Return the cached ``key`` or compute and store it on miss.

        This method provides protection against cache penetration
        (a.k.a. "thundering herd") by serializing calls to
        ``compute_func`` under a lock: concurrent misses for the same
        key only trigger a single recomputation.

        Parameters
        ----------
        key:
            The lookup key.
        compute_func:
            A zero-argument callable producing the value to cache.
        force:
            When ``True`` recompute the value even if it is already
            cached, replacing the previously stored value.
        """
        if not force:
            existing = self._backend.get(key, SmartCache._sentinel)
            if existing is not SmartCache._sentinel:
                return existing

        with self._lock:
            existing = self._backend.get(key, SmartCache._sentinel)
            if not force and existing is not SmartCache._sentinel:
                return existing
            value = compute_func()
            self._backend[key] = value
            return value

    def cleanup(self) -> int:
        """Manually remove all expired items from the cache.

        Returns
        -------
        int
            The number of items that were removed.  For LRU caches no
            item ever expires, so the return value is always ``0``.
        """
        if self._ttl is None:
            return 0
        expired = self._backend.expire()
        return len(expired)
