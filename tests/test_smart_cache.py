"""Unit tests for :mod:`cachetools.smart_cache`."""

import time
import threading
import unittest
import unittest.mock

from cachetools.smart_cache import SmartCache


class SmartCacheTypeSelectionTests(unittest.TestCase):
    """Tests for automatic LRU/TTL selection based on ``ttl``."""

    def test_lru_when_ttl_is_none(self):
        cache = SmartCache(maxsize=10, ttl=None)
        self.assertEqual(cache.backend_type, "LRU")
        self.assertIsNone(cache.ttl)

    def test_ttl_when_ttl_is_set(self):
        cache = SmartCache(maxsize=10, ttl=5)
        self.assertEqual(cache.backend_type, "TTL")
        self.assertEqual(cache.ttl, 5.0)

    def test_ttl_zero_uses_ttl_backend(self):
        # ttl=0 explicitly enables TTL mode, even though items expire immediately.
        cache = SmartCache(maxsize=10, ttl=0)
        self.assertEqual(cache.backend_type, "TTL")


class SmartCacheBasicMappingTests(unittest.TestCase):
    """Tests that :class:`SmartCache` behaves like a mapping."""

    def test_set_and_get_lru(self):
        cache = SmartCache(maxsize=2, ttl=None)
        cache["a"] = 1
        cache["b"] = 2
        self.assertEqual(cache["a"], 1)
        self.assertEqual(cache["b"], 2)

    def test_set_and_get_ttl(self):
        cache = SmartCache(maxsize=2, ttl=60)
        cache["a"] = 1
        cache["b"] = 2
        self.assertEqual(cache["a"], 1)

    def test_eviction_on_maxsize(self):
        cache = SmartCache(maxsize=2, ttl=None)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertIn("c", cache)

    def test_len_and_clear(self):
        cache = SmartCache(maxsize=5, ttl=60)
        cache["a"] = 1
        cache["b"] = 2
        self.assertEqual(len(cache), 2)
        cache.clear()
        self.assertEqual(len(cache), 0)

    def test_get_default(self):
        cache = SmartCache(maxsize=5)
        self.assertIsNone(cache.get("missing"))
        self.assertEqual(cache.get("missing", 42), 42)

    def test_contains(self):
        cache = SmartCache(maxsize=5, ttl=60)
        cache["x"] = 1
        self.assertIn("x", cache)
        self.assertNotIn("y", cache)


class GetOrComputeTests(unittest.TestCase):
    """Tests for :meth:`SmartCache.get_or_compute`."""

    def test_cache_miss_calls_compute(self):
        cache = SmartCache(maxsize=5, ttl=None)
        compute_func = unittest.mock.Mock(return_value="computed")

        result = cache.get_or_compute("k", compute_func)

        self.assertEqual(result, "computed")
        compute_func.assert_called_once_with()

    def test_cache_hit_skips_compute(self):
        cache = SmartCache(maxsize=5, ttl=None)
        cache["k"] = "cached"
        compute_func = unittest.mock.Mock(return_value="computed")

        result = cache.get_or_compute("k", compute_func)

        self.assertEqual(result, "cached")
        compute_func.assert_not_called()

    def test_mock_expensive_compute_only_runs_once(self):
        cache = SmartCache(maxsize=5, ttl=None)
        compute_func = unittest.mock.Mock(return_value=42)

        first = cache.get_or_compute("k", compute_func)
        second = cache.get_or_compute("k", compute_func)
        third = cache.get_or_compute("k", compute_func)

        self.assertEqual(first, 42)
        self.assertEqual(second, 42)
        self.assertEqual(third, 42)
        self.assertEqual(compute_func.call_count, 1)

    def test_mock_expensive_compute_is_slow_only_once(self):
        cache = SmartCache(maxsize=5, ttl=None)

        # Simulate an "expensive" computation: the mock takes a fake long
        # time but only runs once on repeated lookups.
        compute_func = unittest.mock.Mock(return_value="expensive_value")

        start = time.monotonic()
        first = cache.get_or_compute("key", compute_func)
        first_elapsed = time.monotonic() - start

        start = time.monotonic()
        for _ in range(100):
            cache.get_or_compute("key", compute_func)
        hits_elapsed = time.monotonic() - start

        self.assertEqual(first, "expensive_value")
        self.assertEqual(compute_func.call_count, 1)
        self.assertLess(hits_elapsed, first_elapsed + 0.1)

    def test_force_flag_recomputes(self):
        cache = SmartCache(maxsize=5, ttl=None)
        cache["k"] = "old"

        compute_func = unittest.mock.Mock(return_value="new")
        result = cache.get_or_compute("k", compute_func, force=True)

        self.assertEqual(result, "new")
        compute_func.assert_called_once_with()

    def test_concurrent_misses_serialize(self):
        cache = SmartCache(maxsize=5, ttl=None)
        barrier = threading.Barrier(5)
        compute_func = unittest.mock.Mock(return_value=100)

        def slow_compute():
            barrier.wait(timeout=5)
            return compute_func()

        threads = [
            threading.Thread(
                target=lambda: cache.get_or_compute("k", slow_compute)
            )
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(cache["k"], 100)
        self.assertEqual(compute_func.call_count, 1)


class CleanupTests(unittest.TestCase):
    """Tests for :meth:`SmartCache.cleanup`."""

    def test_cleanup_lru_is_noop(self):
        cache = SmartCache(maxsize=5, ttl=None)
        cache["a"] = 1
        cache["b"] = 2
        removed = cache.cleanup()
        self.assertEqual(removed, 0)
        self.assertEqual(len(cache), 2)

    def test_cleanup_removes_expired_ttl(self):
        current = [0.0]

        def fake_timer():
            return current[0]

        cache = SmartCache(maxsize=5, ttl=10, timer=fake_timer)
        cache["a"] = 1
        cache["b"] = 2
        current[0] = 5.0
        cache["c"] = 3

        # Advance time so a and b have expired but c is still valid.
        current[0] = 15.0
        removed = cache.cleanup()

        self.assertEqual(removed, 2)
        self.assertNotIn("a", cache)
        self.assertNotIn("b", cache)
        self.assertIn("c", cache)

    def test_cleanup_with_mock_timer(self):
        with unittest.mock.patch("cachetools.smart_cache.time.monotonic") as mock_time:
            mock_time.return_value = 1000.0

            cache = SmartCache(maxsize=5, ttl=5, timer=mock_time)
            cache["k"] = "value"

            mock_time.return_value = 1004.9
            self.assertEqual(cache["k"], "value")
            removed = cache.cleanup()
            self.assertEqual(removed, 0)

            mock_time.return_value = 1006.0
            removed = cache.cleanup()
            self.assertEqual(removed, 1)
            self.assertNotIn("k", cache)

    def test_cleanup_after_reinsertion(self):
        current = [0.0]

        def fake_timer():
            return current[0]

        cache = SmartCache(maxsize=5, ttl=10, timer=fake_timer)
        cache["k"] = 1
        current[0] = 5.0
        cache["k"] = 2  # reinsert, refresh the TTL
        current[0] = 15.0

        # Original expiry would have passed, but the refresh keeps it alive.
        removed = cache.cleanup()
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
