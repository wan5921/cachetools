"""TTL expiration tests using time.sleep to simulate real clock advance."""

import time

import pytest

from cachetools import TTLCache


class FakeTimer:
    """A manually-advanced timer that returns monotonically increasing values."""

    def __init__(self, start=0.0):
        self._time = start

    def __call__(self):
        return self._time

    def advance(self, seconds):
        self._time += seconds


def test_ttl_expire_shrinks_currsize_with_real_sleep():
    """After TTL elapses (time.sleep), currsize is automatically reduced on access."""
    ttl = 0.1
    cache = TTLCache(maxsize=10, ttl=ttl)
    for i in range(5):
        cache[i] = "v-%d" % i

    assert cache.currsize == 5
    assert len(cache) == 5

    time.sleep(ttl + 0.05)

    assert cache.currsize == 0, "currsize must reflect expired items"
    assert len(cache) == 0, "len must reflect expired items"
    for i in range(5):
        with pytest.raises(KeyError):
            _ = cache[i]


def test_ttl_partial_expire():
    """Items inserted at different times expire progressively."""
    timer = FakeTimer()
    cache = TTLCache(maxsize=10, ttl=10, timer=timer)

    cache[1] = "a"
    timer.advance(5)
    cache[2] = "b"
    assert cache.currsize == 2

    timer.advance(6)
    assert cache.currsize == 1
    assert 1 not in cache
    assert cache[2] == "b"

    timer.advance(5)
    assert cache.currsize == 0
    assert 2 not in cache


def test_ttl_expire_triggered_by_access():
    """Accessing the cache after TTL triggers lazy expiration of all items."""
    cache = TTLCache(maxsize=5, ttl=0.1)
    for i in range(5):
        cache[i] = i

    assert cache.currsize == 5

    time.sleep(0.15)

    assert 0 not in cache
    assert cache.currsize == 0


def test_ttl_reinsert_after_expire():
    """After expiration, re-inserting keys should repopulate the cache."""
    cache = TTLCache(maxsize=5, ttl=0.1)
    for i in range(3):
        cache[i] = i
    assert cache.currsize == 3

    time.sleep(0.15)
    assert cache.currsize == 0

    for i in range(3, 6):
        cache[i] = i
    assert cache.currsize == 3
    assert len(cache) == 3
    for i in range(3, 6):
        assert cache[i] == i


def test_ttl_expire_return_value():
    """TTLCache.expire() returns iterable of (key, value) expired pairs."""
    timer = FakeTimer()
    cache = TTLCache(maxsize=10, ttl=5, timer=timer)
    for i in range(3):
        cache[i] = i

    timer.advance(10)
    expired = list(cache.expire())
    assert len(expired) == 3
    assert {k for k, _ in expired} == {0, 1, 2}
    assert cache.currsize == 0


def test_ttl_currsize_bounded_by_maxsize_after_reinsert():
    """currsize must never exceed maxsize, even after expire + reinsert cycle."""
    cache = TTLCache(maxsize=3, ttl=0.1)
    for i in range(3):
        cache[i] = i
    assert cache.currsize == 3

    time.sleep(0.15)
    for i in range(3, 6):
        cache[i] = i

    assert cache.currsize <= cache.maxsize
    assert cache.currsize == 3
