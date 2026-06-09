import gc
import threading
import tracemalloc
import time
import unittest

from cachetools import LRUCache, TTLCache, cached


class RuntimePropertiesTest(unittest.TestCase):
    NTHREADS = 10
    TIMEOUT = 10

    def test_ttl_expiry_shrinks_currsize(self):
        cache = TTLCache[int, int](maxsize=8, ttl=0.05)

        for key in range(6):
            cache[key] = key

        self.assertEqual(6, cache.currsize)

        time.sleep(0.08)

        self.assertEqual(0, cache.currsize)
        self.assertEqual(0, len(cache))

    def test_shared_cache_currsize_stays_within_maxsize(self):
        maxsize = 64
        cache = LRUCache[int, int](maxsize=maxsize)
        lock = threading.Lock()
        barrier = threading.Barrier(self.NTHREADS)
        errors = []

        @cached(cache=cache, lock=lock)
        def load(key):
            return key * 2

        def worker(index):
            try:
                barrier.wait(timeout=self.TIMEOUT)
                for step in range(500):
                    key = (index * 53 + step) % (maxsize * 4)
                    self.assertEqual(key * 2, load(key))
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(index,))
            for index in range(self.NTHREADS)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=self.TIMEOUT)
            self.assertFalse(thread.is_alive())

        if errors:
            raise errors[0]

        self.assertLessEqual(cache.currsize, cache.maxsize)
        self.assertLessEqual(len(cache), cache.maxsize)

    def test_tracemalloc_detects_no_unbounded_growth(self):
        def exercise_cache():
            cache = LRUCache[int, int](maxsize=256)
            for _ in range(20):
                for key in range(1024):
                    cache[key] = key
                    self.assertEqual(key, cache[key])
            cache.clear()

        tracemalloc.start()
        try:
            exercise_cache()
            gc.collect()
            baseline_current, _ = tracemalloc.get_traced_memory()

            for _ in range(5):
                exercise_cache()

            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertLess(current - baseline_current, 512 * 1024)
        self.assertGreaterEqual(peak, current)
