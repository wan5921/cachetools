"""Smoke test - run with: python /app/cachetools/smoke.py"""
import sys
sys.path.insert(0, '/app/cachetools/src')
sys.path.insert(0, '/app/cachetools')

import unittest
import threading
import time

from cachetools import TTLCache


class Timer:
    def __init__(self):
        self.t = 0.0
        self.lk = threading.Lock()
    def __call__(self):
        with self.lk:
            return self.t
    def tick(self, d=1.0):
        with self.lk:
            self.t += d


def run():
    # test 1: basic expiry
    cache = TTLCache(maxsize=10, ttl=1.0, timer=Timer())
    cache[1] = 42
    assert cache[1] == 42
    cache.timer.tick(2.0)
    try:
        v = cache[1]
        print("FAIL: cache[1] returned %r after expiry" % v)
        return 1
    except KeyError:
        print("OK: test1 expired key raised KeyError")

    # test 2: len shrinks on read-only access
    cache = TTLCache(maxsize=10, ttl=1.0, timer=Timer())
    for k in range(5):
        cache[k] = k
    assert len(cache) == 5
    cache.timer.tick(5.0)
    for k in range(5):
        try:
            _ = cache[k]
            print("FAIL: cache[%d] not expired" % k)
            return 1
        except KeyError:
            pass
    assert len(cache) == 0, "len should be 0 after reads caused expiry"
    print("OK: test2 len reflects expiry after only reads")

    # test 3: concurrent reads on expired key
    cache = TTLCache(maxsize=10, ttl=1.0, timer=Timer())
    cache[1] = 42
    cache.timer.tick(2.0)
    bad = []
    def w():
        for _ in range(500):
            try:
                v = cache[1]
                bad.append(v)
            except KeyError:
                pass
    threads = [threading.Thread(target=w) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)
    if bad:
        print("FAIL: test3 got %d non-KeyError hits: %r" % (len(bad), bad[:5]))
        return 1
    print("OK: test3 concurrent reads of expired key always KeyError")

    # test 4: concurrent mixed read/write
    cache = TTLCache(maxsize=128, ttl=0.005, timer=time.monotonic)
    stop = threading.Event()
    def writer():
        for i in range(500):
            cache[i % 100] = i
    def reader():
        while not stop.is_set():
            for i in range(100):
                try:
                    _ = cache[i]
                except KeyError:
                    pass
    ws = [threading.Thread(target=writer) for _ in range(4)]
    rs = [threading.Thread(target=reader) for _ in range(4)]
    for t in ws+rs: t.start()
    for t in ws: t.join(timeout=10)
    stop.set()
    for t in rs: t.join(timeout=10)
    assert len(cache) <= 128
    print("OK: test4 mixed concurrency ok, len=%d" % len(cache))
    return 0

if __name__ == "__main__":
    sys.exit(run())
