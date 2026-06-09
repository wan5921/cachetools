"""Inline smoke-test for the :mod:`cachetools.smart_cache` module.

This script exists for manual verification only; the formal test suite
lives in :mod:`tests.test_smart_cache`.

Run with: ``PYTHONPATH=src python3 src/cachetools/smart_cache.py``
"""

from cachetools.smart_cache import SmartCache


def _smoke_lru():
    cache = SmartCache(maxsize=3, ttl=None)
    cache["a"] = 1
    assert cache.get_or_compute("a", lambda: 99) == 1, "LRU miss unexpectedly called compute"
    assert cache.get_or_compute("b", lambda: "ok") == "ok"
    assert cache.cleanup() == 0
    return True


def _smoke_ttl():
    t = [0.0]

    def timer():
        return t[0]

    cache = SmartCache(maxsize=3, ttl=10, timer=timer)
    cache["a"] = 1
    t[0] = 5.0
    cache["b"] = 2
    t[0] = 15.0
    assert cache.cleanup() == 1
    assert cache.get("a") is None
    assert cache["b"] == 2
    return True


def _smoke_hit_calls_once():
    import unittest.mock

    cache = SmartCache(maxsize=5, ttl=60)
    func = unittest.mock.Mock(return_value=42)
    for _ in range(5):
        assert cache.get_or_compute("k", func) == 42
    assert func.call_count == 1, func.call_count
    return True


if __name__ == "__main__":
    assert _smoke_lru()
    assert _smoke_ttl()
    assert _smoke_hit_calls_once()
    print("All smoke assertions passed.")
