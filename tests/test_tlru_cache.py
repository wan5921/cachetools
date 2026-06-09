import time

import pytest

from cachetools import TLRUCache


def ttl_ttu(ttl):
    return lambda _key, _value, now: now + ttl


def test_tlru_cache_evicts_oldest_item_when_maxsize_is_exceeded():
    cache = TLRUCache(maxsize=2, ttu=ttl_ttu(10.0))

    cache["first"] = "a"
    cache["second"] = "b"
    cache["third"] = "c"

    assert len(cache) == 2
    assert "first" not in cache
    assert cache["second"] == "b"
    assert cache["third"] == "c"


def test_tlru_cache_expires_items_after_ttl():
    cache = TLRUCache(maxsize=2, ttu=ttl_ttu(0.05))

    cache["session"] = "value"

    assert cache["session"] == "value"

    time.sleep(0.08)

    assert "session" not in cache
    assert len(cache) == 0
    with pytest.raises(KeyError):
        cache["session"]


def test_tlru_cache_prefers_expired_entries_before_maxsize_eviction():
    def ttu(key, _value, now):
        ttl = 0.05 if key == "expired" else 10.0
        return now + ttl

    cache = TLRUCache(maxsize=2, ttu=ttu)

    cache["expired"] = "old"
    cache["fresh"] = "keep"

    time.sleep(0.08)

    cache["new"] = "value"

    assert len(cache) == 2
    assert "expired" not in cache
    assert cache["fresh"] == "keep"
    assert cache["new"] == "value"
    assert set(cache) == {"fresh", "new"}
