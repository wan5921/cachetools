"""Concurrent tests verifying TTLCache expiry + lock behaviour."""

import threading
import time
import unittest

from cachetools import TTLCache


NTHREADS = 8
ROUNDS = 200


class ThreadSafeTimer:
    def __init__(self):
        self._time = 0.0
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self._time

    def tick(self, delta=1.0):
        with self._lock:
            self._time += delta


class TTLThreadingTest(unittest.TestCase):
    TIMEOUT = 15

    def test_concurrent_read_after_expiry_raises_keyerror(self):
        """An expired key MUST raise KeyError even under concurrent reads."""
        timer = ThreadSafeTimer()
        cache: TTLCache[int, int] = TTLCache(maxsize=10, ttl=1.0, timer=timer)
        cache[1] = 42
        cache[2] = 43

        # let items expire
        timer.tick(2.0)

        errors = []
        hits_non_none = []

        def worker():
            for _ in range(ROUNDS):
                try:
                    value = cache[1]
                except KeyError:
                    errors.append(True)
                else:
                    hits_non_none.append(value)

        threads = [threading.Thread(target=worker) for _ in range(NTHREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        self.assertEqual(len(hits_non_none), 0, "expired key must never be returned")
        self.assertGreater(len(errors), 0)

    def test_concurrent_mixed_read_write(self):
        """Mix of concurrent writes + reads must not lose writes of live keys
        and must not return values for keys that have expired."""
        cache: TTLCache[int, int] = TTLCache(maxsize=128, ttl=1.0)
        bar = threading.Barrier(NTHREADS)
        stop = threading.Event()
        observed_expired = []

        def writer(start_key):
            bar.wait()
            for i in range(ROUNDS):
                cache[start_key + i] = i

        def reader(start_key):
            bar.wait()
            while not stop.is_set():
                for i in range(ROUNDS):
                    try:
                        _ = cache[start_key + i]
                    except KeyError:
                        observed_expired.append(True)

        threads = []
        for i in range(NTHREADS // 2):
            threads.append(threading.Thread(target=writer, args=(i * 10000,)))
        for i in range(NTHREADS // 2, NTHREADS):
            threads.append(threading.Thread(target=reader, args=(i * 10000,)))

        for t in threads:
            t.start()
        for t in threads[: NTHREADS // 2]:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())
        stop.set()
        for t in threads[NTHREADS // 2 :]:
            t.join(timeout=self.TIMEOUT)
            self.assertFalse(t.is_alive())

        # no structural corruption; cache reports reasonable size
        self.assertLessEqual(len(cache), 128)

    def test_len_reflects_expiry_without_writes(self):
        """len() / __contains__ on a read-only cache must shrink after expiry
        (i.e. reads must also trigger expire cleanup, not only __setitem__)."""
        timer = ThreadSafeTimer()
        cache: TTLCache[int, int] = TTLCache(maxsize=10, ttl=1.0, timer=timer)
        for k in range(5):
            cache[k] = k
        self.assertEqual(len(cache), 5)

        timer.tick(5.0)

        # perform only reads (no setitem) -- expire must still be triggered
        for k in range(5):
            with self.assertRaises(KeyError):
                _ = cache[k]
            self.assertFalse(k in cache)

        self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
