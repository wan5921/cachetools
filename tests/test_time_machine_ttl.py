"""
Tests for TTLCache lazy cleanup behavior using time-machine.

Demonstrates that:
1. Expired entries are NOT immediately deleted when time passes.
2. Cleanup only happens on read/write operations.
3. __getitem__ returns None (via __missing__) for expired items,
   and the cache size decreases after a write operation triggers cleanup.
"""

import time_machine
from datetime import datetime, timedelta

import pytest

from cachetools import TTLCache


class TestTTLCacheLazyCleanup:
    """Verify TTLCache lazy cleanup semantics with time-machine."""

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_expired_entries_not_immediately_deleted(self):
        """Time passing alone does NOT remove expired entries from the cache."""
        cache = TTLCache(maxsize=10, ttl=60)

        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        initial_size = len(cache)
        assert initial_size == 3

        # Move time forward past the TTL
        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        # Expired entries are STILL in the cache (lazy cleanup)
        assert len(cache) == initial_size
        assert cache.currsize == initial_size

        # __contains__ correctly reports them as not present (checks expires)
        assert "a" not in cache
        assert "b" not in cache
        assert "c" not in cache

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_getitem_returns_missing_for_expired(self):
        """__getitem__ on an expired key triggers __missing__ (KeyError by default)."""
        cache = TTLCache(maxsize=10, ttl=60)
        cache["a"] = 1

        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        with pytest.raises(KeyError):
            _ = cache["a"]

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_read_does_not_remove_expired_entries(self):
        """Reading an expired key does NOT remove it from the cache."""
        cache = TTLCache(maxsize=10, ttl=60)
        cache["a"] = 1
        cache["b"] = 2

        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        # Reading expired key raises KeyError but does NOT clean up
        with pytest.raises(KeyError):
            _ = cache["a"]

        # "a" is still physically in the cache (lazy cleanup)
        assert len(cache) == 2
        assert "b" not in cache  # but __contains__ knows it's expired

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_write_triggers_cleanup_and_size_decreases(self):
        """A write operation triggers expire() and removes all expired entries."""
        cache = TTLCache(maxsize=10, ttl=60)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        # All entries are expired but still occupy space
        assert len(cache) == 3

        # Writing a new item triggers expire() which cleans up all expired entries
        cache["d"] = 4

        # Now the cache only contains the new item
        assert len(cache) == 1
        assert "d" in cache
        assert cache["d"] == 4

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_getitem_none_then_cache_size_decreases(self):
        """
        Demonstrate the full lifecycle:
        1. Insert items
        2. Time passes (items expire but are not deleted)
        3. __getitem__ on expired key returns None (via custom __missing__)
        4. A write operation triggers cleanup, cache size decreases
        """

        class TTLCacheWithMissing(TTLCache):
            """TTLCache that returns None instead of raising KeyError for missing/expired keys."""

            def __missing__(self, key):
                return None

        cache = TTLCacheWithMissing(maxsize=10, ttl=60)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        assert len(cache) == 3

        # Move time forward past TTL
        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        # Items are expired but still in the cache (lazy cleanup)
        assert len(cache) == 3

        # __getitem__ returns None for expired keys (custom __missing__)
        assert cache["a"] is None
        assert cache["b"] is None
        assert cache["c"] is None

        # Size has NOT decreased yet (read doesn't trigger cleanup)
        assert len(cache) == 3

        # Write operation triggers expire() cleanup
        cache["d"] = 4

        # Now cache size has decreased - only the new item remains
        assert len(cache) == 1
        assert cache["d"] == 4

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_partial_expiry_with_write(self):
        """Only items that have expired by the current time are cleaned up."""
        cache = TTLCache(maxsize=10, ttl=60, timer=time_machine.time_machine.get_current_time)

        cache["a"] = 1  # expires at t=60
        time_machine.move_to(datetime(2024, 1, 1, 0, 0, 30))  # t=30
        cache["b"] = 2  # expires at t=90

        time_machine.move_to(datetime(2024, 1, 1, 0, 1, 30))  # t=90

        # "a" is expired (t=90 >= expires=60), "b" is not yet (t=90 == expires=90, not <)
        assert "a" not in cache
        assert "b" not in cache  # t=90 is NOT < expires=90

        # Write triggers cleanup
        cache["c"] = 3

        # Only "b" was expired at t=90 boundary; both should be cleaned
        assert len(cache) == 1
        assert "c" in cache

    @time_machine.travel("2024-01-01 00:00:00", tick=False)
    def test_explicit_expire_method(self):
        """Calling expire() manually removes expired entries without a write."""
        cache = TTLCache(maxsize=10, ttl=60)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        time_machine.move_to(datetime(2024, 1, 1, 0, 2, 0))  # +120 seconds

        assert len(cache) == 3

        # Explicitly call expire() to clean up
        expired = cache.expire()

        assert len(expired) == 3
        assert set(expired) == {("a", 1), ("b", 2), ("c", 3)}
        assert len(cache) == 0
