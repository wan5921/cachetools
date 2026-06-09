import unittest
from unittest.mock import Mock

from cachetools import LRUCache

from . import CacheTestMixin


class LRUCacheTest(unittest.TestCase, CacheTestMixin):
    Cache = LRUCache

    def test_lru(self):
        cache = LRUCache[int, int](maxsize=2)

        cache[1] = 1
        cache[2] = 2
        cache[3] = 3

        self.assertEqual(len(cache), 2)
        self.assertEqual(cache[2], 2)
        self.assertEqual(cache[3], 3)
        self.assertNotIn(1, cache)

        cache[2]
        cache[4] = 4
        self.assertEqual(len(cache), 2)
        self.assertEqual(cache[2], 2)
        self.assertEqual(cache[4], 4)
        self.assertNotIn(3, cache)

        cache[5] = 5
        self.assertEqual(len(cache), 2)
        self.assertEqual(cache[4], 4)
        self.assertEqual(cache[5], 5)
        self.assertNotIn(2, cache)

    def test_lru_getsizeof(self):
        cache = LRUCache[int, int](maxsize=3, getsizeof=lambda x: x)

        cache[1] = 1
        cache[2] = 2

        self.assertEqual(len(cache), 2)
        self.assertEqual(cache[1], 1)
        self.assertEqual(cache[2], 2)

        cache[3] = 3

        self.assertEqual(len(cache), 1)
        self.assertEqual(cache[3], 3)
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)

        with self.assertRaises(ValueError):
            cache[4] = 4
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache[3], 3)

    def test_lru_update_existing(self):
        cache = LRUCache[int, int | str](maxsize=2)

        cache[1] = 1
        cache[2] = 2
        cache[1] = "updated"
        cache[3] = 3

        self.assertEqual(cache[1], "updated")
        self.assertIn(3, cache)
        self.assertNotIn(2, cache)

    def test_lru_clear(self):
        cache = LRUCache[int, int](maxsize=2)

        cache[1] = 1
        cache[2] = 2
        cache.clear()

        self.assertEqual(0, len(cache))
        self.assertEqual(0, cache.currsize)

        cache[3] = 3
        cache[4] = 4
        cache[3]
        cache[5] = 5

        self.assertEqual(2, len(cache))
        self.assertIn(3, cache)
        self.assertIn(5, cache)
        self.assertNotIn(4, cache)

    def test_get_or_compute_uses_cached_value_after_first_load(self):
        cache = LRUCache[str, int](maxsize=2)
        compute = Mock(return_value=42)

        self.assertEqual(42, cache.get_or_compute("answer", compute))
        self.assertEqual(42, cache.get_or_compute("answer", compute))

        compute.assert_called_once_with()
        self.assertEqual(42, cache["answer"])

    def test_cleanup_is_noop_for_non_ttl_cache(self):
        cache = LRUCache[int, int](maxsize=2)
        cache[1] = 1

        self.assertEqual([], cache.cleanup())
        self.assertIn(1, cache)
