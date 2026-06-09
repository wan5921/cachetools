import unittest

import cachetools

from . import CacheTestMixin


class CacheTest(unittest.TestCase, CacheTestMixin):
    Cache = cachetools.Cache


class CreateCacheTest(unittest.TestCase):
    def test_create_cache_uses_lru_when_ttl_is_none(self):
        cache = cachetools.create_cache(maxsize=2, ttl=None)

        self.assertIsInstance(cache, cachetools.LRUCache)
        self.assertNotIsInstance(cache, cachetools.TTLCache)

    def test_create_cache_uses_ttl_when_ttl_is_provided(self):
        timer = iter(range(10)).__next__
        cache = cachetools.create_cache(maxsize=2, ttl=1, timer=timer)

        self.assertIsInstance(cache, cachetools.TTLCache)
        self.assertEqual(1, cache.ttl)
