import math
import threading
import time
import unittest

from cachetools import TTLCache

from . import CacheTestMixin


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


class ThreadSafeTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self.time = 0

    def __call__(self):
        with self._lock:
            return self.time

    def tick(self, delta=1):
        with self._lock:
            self.time += delta
            return self.time


class TTLTestCache(TTLCache):
    def __init__(self, maxsize, ttl=math.inf, **kwargs):
        TTLCache.__init__(self, maxsize, ttl=ttl, timer=Timer(), **kwargs)


class TTLCacheTest(unittest.TestCase, CacheTestMixin):
    Cache = TTLTestCache

    def test_ttl(self):
        cache = TTLCache[int, int, int](maxsize=2, ttl=2, timer=Timer())
        self.assertEqual(0, cache.timer())
        self.assertEqual(2, cache.ttl)

        cache[1] = 1
        self.assertEqual(1, cache[1])
        self.assertEqual(1, len(cache))
        self.assertEqual({1}, set(cache))

        cache.timer.tick()
        self.assertEqual(1, cache[1])
        self.assertEqual(1, len(cache))
        self.assertEqual({1}, set(cache))

        cache[2] = 2
        self.assertEqual(1, cache[1])
        self.assertEqual(2, cache[2])
        self.assertEqual(2, len(cache))
        self.assertEqual({1, 2}, set(cache))

        cache.timer.tick()
        self.assertNotIn(1, cache)
        self.assertEqual(2, cache[2])
        self.assertEqual(1, len(cache))
        self.assertEqual({2}, set(cache))

        cache[3] = 3
        self.assertNotIn(1, cache)
        self.assertEqual(2, cache[2])
        self.assertEqual(3, cache[3])
        self.assertEqual(2, len(cache))
        self.assertEqual({2, 3}, set(cache))

        cache.timer.tick()
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)
        self.assertEqual(3, cache[3])
        self.assertEqual(1, len(cache))
        self.assertEqual({3}, set(cache))

        cache.timer.tick()
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)
        self.assertNotIn(3, cache)

        with self.assertRaises(KeyError):
            del cache[1]
        with self.assertRaises(KeyError):
            cache.pop(2)
        with self.assertRaises(KeyError):
            del cache[3]

        self.assertEqual(0, len(cache))
        self.assertEqual(set(), set(cache))

    def test_ttl_timer(self):
        cache = TTLCache[int, int, int](maxsize=2, ttl=2, timer=Timer())
        self.assertEqual(cache.timer.time, 0)
        self.assertFalse(cache.timer.auto)

        cache[1] = 1
        cache.timer.tick()
        self.assertEqual(cache.timer.time, 1)
        self.assertEqual(1, cache[1])

        cache.timer.tick()
        self.assertEqual(cache.timer.time, 2)
        self.assertNotIn(1, cache)

    def test_ttl_lru(self):
        cache = TTLCache[int, int, int](maxsize=2, ttl=1, timer=Timer())

        cache[1] = 1
        cache[2] = 2
        cache[3] = 3

        self.assertEqual(len(cache), 2)
        self.assertNotIn(1, cache)
        self.assertEqual(cache[2], 2)
        self.assertEqual(cache[3], 3)

        cache[2]
        cache[4] = 4
        self.assertEqual(len(cache), 2)
        self.assertNotIn(1, cache)
        self.assertEqual(cache[2], 2)
        self.assertNotIn(3, cache)
        self.assertEqual(cache[4], 4)

        cache[5] = 5
        self.assertEqual(len(cache), 2)
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)
        self.assertNotIn(3, cache)
        self.assertEqual(cache[4], 4)
        self.assertEqual(cache[5], 5)

    def test_ttl_expire(self):
        cache = TTLCache[int, int, int](maxsize=3, ttl=3, timer=Timer())
        with cache.timer as time:
            self.assertEqual(time, cache.timer())
        self.assertEqual(3, cache.ttl)

        cache[1] = 1
        cache.timer.tick()
        cache[2] = 2
        cache.timer.tick()
        cache[3] = 3
        self.assertEqual(2, cache.timer())

        self.assertEqual({1, 2, 3}, set(cache))
        self.assertEqual(3, len(cache))
        self.assertEqual(1, cache[1])
        self.assertEqual(2, cache[2])
        self.assertEqual(3, cache[3])

        items = cache.expire()
        self.assertEqual(set(), set(items))
        self.assertEqual({1, 2, 3}, set(cache))
        self.assertEqual(3, len(cache))
        self.assertEqual(1, cache[1])
        self.assertEqual(2, cache[2])
        self.assertEqual(3, cache[3])

        items = cache.expire(3)
        self.assertEqual({(1, 1)}, set(items))
        self.assertEqual({2, 3}, set(cache))
        self.assertEqual(2, len(cache))
        self.assertNotIn(1, cache)
        self.assertEqual(2, cache[2])
        self.assertEqual(3, cache[3])

        items = cache.expire(4)
        self.assertEqual({(2, 2)}, set(items))
        self.assertEqual({3}, set(cache))
        self.assertEqual(1, len(cache))
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)
        self.assertEqual(3, cache[3])

        items = cache.expire(5)
        self.assertEqual({(3, 3)}, set(items))
        self.assertEqual(set(), set(cache))
        self.assertEqual(0, len(cache))
        self.assertNotIn(1, cache)
        self.assertNotIn(2, cache)
        self.assertNotIn(3, cache)

    def test_ttl_atomic(self):
        cache = TTLCache[int, int, int](maxsize=1, ttl=2, timer=Timer(auto=True))
        cache[1] = 1
        self.assertEqual(1, cache[1])
        cache[1] = 1
        self.assertEqual(1, cache.get(1))
        cache[1] = 1
        self.assertEqual(1, cache.pop(1))
        cache[1] = 1
        self.assertEqual(1, cache.setdefault(1))
        cache[1] = 1
        cache.clear()
        self.assertEqual(0, len(cache))

    def test_ttl_tuple_key(self):
        cache = TTLCache[tuple[int, ...], int, int](maxsize=1, ttl=1, timer=Timer())
        self.assertEqual(1, cache.ttl)

        cache[(1, 2, 3)] = 42
        self.assertEqual(42, cache[(1, 2, 3)])
        cache.timer.tick()
        with self.assertRaises(KeyError):
            cache[(1, 2, 3)]
        self.assertNotIn((1, 2, 3), cache)

    def test_ttl_datetime(self):
        from datetime import datetime, timedelta

        cache = TTLCache[int, int, datetime](
            maxsize=1, ttl=timedelta(days=1), timer=datetime.now
        )

        cache[1] = 1
        self.assertEqual(1, len(cache))
        items = cache.expire(datetime.now())
        self.assertEqual([], list(items))
        self.assertEqual(1, len(cache))
        items = cache.expire(datetime.now() + timedelta(days=1))
        self.assertEqual([(1, 1)], list(items))
        self.assertEqual(0, len(cache))

    def test_ttl_clear(self):
        cache = TTLCache[int, int, int](maxsize=2, ttl=2, timer=Timer())

        cache[1] = 1
        cache[2] = 2
        cache.clear()

        self.assertEqual(0, len(cache))
        self.assertEqual(0, cache.currsize)

        # verify LRU eviction order is reset after clear
        cache[3] = 3
        cache[4] = 4
        cache[3]  # access 3 to make it most recently used
        cache[5] = 5  # should evict 4 (least recently used)

        self.assertEqual(2, len(cache))
        self.assertIn(3, cache)
        self.assertIn(5, cache)
        self.assertNotIn(4, cache)

        # verify TTL expiry still works after clear
        cache[42] = 42
        cache.timer.tick()
        cache.timer.tick()
        cache.timer.tick()  # past TTL
        self.assertNotIn(42, cache)


class TTLCacheConcurrencyTest(unittest.TestCase):
    """Test cases to verify TTLCache thread-safety and proper expiry handling
    under concurrent access."""

    NTHREADS = 20
    TIMEOUT = 30

    def test_concurrent_read_write(self):
        """Verify that concurrent reads and writes do not corrupt the cache."""
        cache = TTLCache(maxsize=1000, ttl=1.0)
        errors = []

        def writer(tid):
            try:
                for i in range(100):
                    key = f"key-{tid}-{i}"
                    cache[key] = i
            except Exception as e:
                errors.append(e)

        def reader(tid):
            try:
                for i in range(100):
                    key = f"key-{tid % 5}-{i}"
                    try:
                        _ = cache[key]
                    except KeyError:
                        pass  # expected for keys that don't exist yet
                    _ = len(cache)
                    _ = f"key-{tid}-{i}" in cache
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(self.NTHREADS):
            if i % 2 == 0:
                threads.append(threading.Thread(target=writer, args=(i,)))
            else:
                threads.append(threading.Thread(target=reader, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        self.assertEqual([], errors, f"Concurrency errors: {errors}")

    def test_expiry_returns_keyerror(self):
        """Verify that accessing an expired key raises KeyError."""
        cache = TTLCache(maxsize=10, ttl=0.05)
        cache["foo"] = "bar"
        self.assertEqual("bar", cache["foo"])

        time.sleep(0.1)

        with self.assertRaises(KeyError):
            _ = cache["foo"]

        self.assertNotIn("foo", cache)

    def test_expired_item_removed_on_read(self):
        """Verify that expired items are actually removed from the cache when
        accessed via __getitem__, not just when __setitem__ is called."""
        cache = TTLCache(maxsize=10, ttl=0.05)

        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        self.assertEqual(3, len(cache))

        time.sleep(0.1)

        with self.assertRaises(KeyError):
            _ = cache["a"]

        self.assertEqual(0, len(cache),
                         "Expired items should be removed on read, not just on write")
        self.assertNotIn("a", cache)
        self.assertNotIn("b", cache)
        self.assertNotIn("c", cache)

    def test_concurrent_expiry(self):
        """Verify that concurrent access during expiry window correctly raises
        KeyError for expired keys."""
        cache = TTLCache(maxsize=100, ttl=0.05)
        keyerrors_reported = []
        unexpected_values = []
        errors = []

        for i in range(50):
            cache[f"key-{i}"] = i

        time.sleep(0.1)

        def access_expired(tid):
            try:
                key = f"key-{tid % 50}"
                try:
                    val = cache[key]
                    unexpected_values.append((key, val))
                except KeyError:
                    keyerrors_reported.append(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=access_expired, args=(i,))
            for i in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        self.assertEqual([], errors, f"Concurrency errors: {errors}")
        self.assertEqual(
            [], unexpected_values,
            f"Expired keys should not return values: {unexpected_values}"
        )
        self.assertTrue(
            len(keyerrors_reported) > 0,
            "At least some expired accesses should raise KeyError"
        )
        self.assertEqual(0, len(cache), "Cache should be empty after expiry")

    def test_concurrent_write_and_expire(self):
        """Verify that concurrent writes during natural expiry maintain
        consistency."""
        cache = TTLCache(maxsize=100, ttl=0.02)
        errors = []
        barrier = threading.Barrier(self.NTHREADS)

        def worker(tid):
            try:
                barrier.wait(timeout=self.TIMEOUT)
                for i in range(50):
                    key = f"k-{tid}-{i}"
                    cache[key] = i
                    try:
                        _ = cache[key]
                    except KeyError:
                        pass
                    _ = len(cache)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        self.assertEqual([], errors, f"Concurrency errors: {errors}")
        self.assertTrue(len(cache) >= 0)
        for key in list(cache):
            self.assertIn(key, cache)

    def test_concurrent_read_write_after_expiry_raises_keyerror(self):
        """Verify that expired entries never leak values during concurrent
        reads, writes, and cleanup."""
        timer = ThreadSafeTimer()
        cache = TTLCache(maxsize=512, ttl=2, timer=timer)
        barrier = threading.Barrier(self.NTHREADS + 1)
        expired = threading.Event()
        errors = []
        stale_reads = []

        cache["shared"] = "value"

        def writer(tid):
            try:
                barrier.wait(timeout=self.TIMEOUT)
                expired.wait(timeout=self.TIMEOUT)
                for i in range(100):
                    cache[f"key-{tid}-{i}"] = i
                    if i % 5 == 0:
                        cache.expire()
                    _ = len(cache)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                barrier.wait(timeout=self.TIMEOUT)
                expired.wait(timeout=self.TIMEOUT)
                for _ in range(50):
                    try:
                        stale_reads.append(cache["shared"])
                    except KeyError:
                        return
                stale_reads.append("value-returned-after-expiry")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(self.NTHREADS // 2):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()

        barrier.wait(timeout=self.TIMEOUT)
        timer.tick(3)
        expired.set()

        for t in threads:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        self.assertEqual([], errors, f"Concurrency errors: {errors}")
        self.assertEqual([], stale_reads, f"Expired key returned values: {stale_reads}")
        with self.assertRaises(KeyError):
            _ = cache["shared"]
        self.assertNotIn("shared", cache)

    def test_lock_attribute_exists(self):
        """Verify that TTLCache exposes a _lock attribute for external
        synchronization if needed."""
        cache = TTLCache(maxsize=10, ttl=1.0)
        self.assertTrue(hasattr(cache, "_lock"))


if __name__ == "__main__":
    unittest.main()
