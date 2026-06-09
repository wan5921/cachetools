import threading
import unittest
from unittest.mock import Mock, call

from cachetools.smartcache import SmartCache


class Timer:
    def __init__(self, auto=False):
        self.auto = auto
        self.time = 0

    def __call__(self):
        if self.auto:
            self.time += 1
        return self.time

    def tick(self):
        self.time += 1


class TestSmartCacheAutoSwitch(unittest.TestCase):
    def test_ttl_none_uses_lru(self):
        cache = SmartCache(maxsize=10, ttl=None)
        self.assertEqual("LRUCache", cache.cache_type)
        self.assertIsNone(cache.ttl)

    def test_ttl_set_uses_ttl(self):
        cache = SmartCache(maxsize=10, ttl=60)
        self.assertEqual("TTLCache", cache.cache_type)
        self.assertEqual(60, cache.ttl)

    def test_ttl_zero_uses_ttl(self):
        cache = SmartCache(maxsize=10, ttl=0)
        self.assertEqual("TTLCache", cache.cache_type)

    def test_maxsize_property(self):
        cache = SmartCache(maxsize=42, ttl=None)
        self.assertEqual(42, cache.maxsize)

    def test_currsize_property(self):
        cache = SmartCache(maxsize=10, ttl=None)
        self.assertEqual(0, cache.currsize)
        cache["a"] = 1
        self.assertEqual(1, cache.currsize)


class TestSmartCacheGetOrComputeLRU(unittest.TestCase):
    def test_cache_hit(self):
        cache = SmartCache(maxsize=10, ttl=None)
        compute = Mock(return_value=42)

        cache["key1"] = 100
        result = cache.get_or_compute("key1", compute)

        self.assertEqual(100, result)
        compute.assert_not_called()

    def test_cache_miss_computes(self):
        cache = SmartCache(maxsize=10, ttl=None)
        compute = Mock(return_value=42)

        result = cache.get_or_compute("key1", compute)

        self.assertEqual(42, result)
        compute.assert_called_once_with("key1")

    def test_computed_value_is_cached(self):
        cache = SmartCache(maxsize=10, ttl=None)
        compute = Mock(return_value=42)

        result1 = cache.get_or_compute("key1", compute)
        result2 = cache.get_or_compute("key1", compute)

        self.assertEqual(42, result1)
        self.assertEqual(42, result2)
        compute.assert_called_once_with("key1")

    def test_different_keys_computed_separately(self):
        cache = SmartCache(maxsize=10, ttl=None)
        compute = Mock(side_effect=lambda k: len(k))

        result1 = cache.get_or_compute("hi", compute)
        result2 = cache.get_or_compute("hello", compute)

        self.assertEqual(2, result1)
        self.assertEqual(5, result2)
        self.assertEqual(2, compute.call_count)

    def test_lru_eviction(self):
        cache = SmartCache(maxsize=2, ttl=None)
        compute = Mock(side_effect=lambda k: k * 10)

        cache.get_or_compute(1, compute)
        cache.get_or_compute(2, compute)
        cache.get_or_compute(3, compute)

        self.assertNotIn(1, cache)
        self.assertIn(2, cache)
        self.assertIn(3, cache)


class TestSmartCacheGetOrComputeTTL(unittest.TestCase):
    def test_cache_hit_within_ttl(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=5, timer=timer)
        compute = Mock(return_value=42)

        cache["key1"] = 100
        result = cache.get_or_compute("key1", compute)

        self.assertEqual(100, result)
        compute.assert_not_called()

    def test_cache_miss_computes(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=5, timer=timer)
        compute = Mock(return_value=42)

        result = cache.get_or_compute("key1", compute)

        self.assertEqual(42, result)
        compute.assert_called_once_with("key1")

    def test_expired_item_recomputed(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=2, timer=timer)
        compute = Mock(side_effect=["first", "second"])

        cache.get_or_compute("key1", compute)
        timer.tick()
        timer.tick()

        result = cache.get_or_compute("key1", compute)

        self.assertEqual("second", result)
        self.assertEqual(2, compute.call_count)

    def test_computed_value_cached_within_ttl(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=5, timer=timer)
        compute = Mock(return_value=42)

        cache.get_or_compute("key1", compute)
        timer.tick()

        result = cache.get_or_compute("key1", compute)

        self.assertEqual(42, result)
        compute.assert_called_once_with("key1")


class TestSmartCacheCleanup(unittest.TestCase):
    def test_cleanup_lru_noop(self):
        cache = SmartCache(maxsize=10, ttl=None)
        cache["a"] = 1
        cache["b"] = 2

        expired = cache.cleanup()

        self.assertEqual([], expired)
        self.assertEqual(2, len(cache))

    def test_cleanup_ttl_removes_expired(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=2, timer=timer)

        cache["a"] = 1
        timer.tick()
        cache["b"] = 2
        timer.tick()

        expired = cache.cleanup()

        self.assertEqual({("a", 1)}, set(expired))
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)

    def test_cleanup_ttl_nothing_expired(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=10, timer=timer)

        cache["a"] = 1
        cache["b"] = 2

        expired = cache.cleanup()

        self.assertEqual([], expired)
        self.assertEqual(2, len(cache))

    def test_cleanup_ttl_all_expired(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=1, timer=timer)

        cache["a"] = 1
        cache["b"] = 2
        timer.tick()
        timer.tick()

        expired = cache.cleanup()

        self.assertEqual({("a", 1), ("b", 2)}, set(expired))
        self.assertEqual(0, len(cache))

    def test_cleanup_after_partial_expiry(self):
        timer = Timer()
        cache = SmartCache(maxsize=10, ttl=3, timer=timer)

        cache["a"] = 1
        timer.tick()
        cache["b"] = 2
        timer.tick()
        cache["c"] = 3
        timer.tick()

        expired = cache.cleanup()

        self.assertEqual({("a", 1)}, set(expired))
        self.assertEqual(2, len(cache))
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertIn("c", cache)


class TestSmartCacheMutableMapping(unittest.TestCase):
    def test_setitem_getitem(self):
        cache = SmartCache(maxsize=10, ttl=None)
        cache["x"] = 99
        self.assertEqual(99, cache["x"])

    def test_delitem(self):
        cache = SmartCache(maxsize=10, ttl=None)
        cache["x"] = 99
        del cache["x"]
        self.assertNotIn("x", cache)

    def test_len(self):
        cache = SmartCache(maxsize=10, ttl=None)
        self.assertEqual(0, len(cache))
        cache["a"] = 1
        cache["b"] = 2
        self.assertEqual(2, len(cache))

    def test_iter(self):
        cache = SmartCache(maxsize=10, ttl=None)
        cache["a"] = 1
        cache["b"] = 2
        self.assertEqual({"a", "b"}, set(cache))

    def test_contains(self):
        cache = SmartCache(maxsize=10, ttl=None)
        cache["a"] = 1
        self.assertIn("a", cache)
        self.assertNotIn("b", cache)

    def test_repr(self):
        cache = SmartCache(maxsize=10, ttl=None)
        r = repr(cache)
        self.assertTrue(r.startswith("SmartCache"))
        self.assertIn("LRUCache", r)

    def test_repr_ttl(self):
        cache = SmartCache(maxsize=10, ttl=60)
        r = repr(cache)
        self.assertIn("TTLCache", r)
        self.assertIn("60", r)


class TestSmartCachePenetrationProtection(unittest.TestCase):
    def test_concurrent_access_single_compute(self):
        cache = SmartCache(maxsize=10, ttl=None)
        compute = Mock(return_value=42)
        call_count = 0
        lock = threading.Lock()

        def slow_compute(key):
            nonlocal call_count
            with lock:
                call_count += 1
            return compute(key)

        threads = []
        for _ in range(10):
            t = threading.Thread(
                target=cache.get_or_compute, args=("key1", slow_compute)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(1, call_count)
        self.assertEqual(42, cache["key1"])

    def test_get_or_compute_with_expensive_function(self):
        cache = SmartCache(maxsize=10, ttl=None)
        expensive = Mock(side_effect=lambda k: k ** 2)

        self.assertEqual(9, cache.get_or_compute(3, expensive))
        self.assertEqual(9, cache.get_or_compute(3, expensive))
        self.assertEqual(16, cache.get_or_compute(4, expensive))

        self.assertEqual(2, expensive.call_count)
        expensive.assert_has_calls([call(3), call(4)])


class TestSmartCacheTTLWithTimer(unittest.TestCase):
    def test_full_lifecycle(self):
        timer = Timer()
        cache = SmartCache(maxsize=5, ttl=3, timer=timer)
        compute = Mock(side_effect=lambda k: k * 100)

        self.assertEqual(100, cache.get_or_compute(1, compute))
        self.assertEqual(200, cache.get_or_compute(2, compute))

        timer.tick()
        self.assertEqual(100, cache.get_or_compute(1, compute))
        self.assertEqual(2, compute.call_count)

        timer.tick()
        timer.tick()

        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)

        expired = cache.cleanup()
        self.assertEqual({(1, 100), (2, 200)}, set(expired))

        compute.side_effect = lambda k: k * 999
        self.assertEqual(999, cache.get_or_compute(1, compute))
        self.assertEqual(1998, cache.get_or_compute(2, compute))


if __name__ == "__main__":
    unittest.main()
