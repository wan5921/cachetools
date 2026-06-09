"""Concurrent access tests for cachetools caches.

10 threads simultaneously read and write to the same cache instance.
After all threads finish, we assert ``currsize <= maxsize``.
"""

import threading
import time

import pytest

from cachetools import LRUCache, TTLCache


NTHREADS = 10
NITEMS_PER_THREAD = 500
TIMEOUT = 30


def _thread_worker_lru(cache, thread_id, barrier, errors):
    """Each thread inserts a range of keys and then reads them back."""
    try:
        barrier.wait(timeout=TIMEOUT)
        base = thread_id * NITEMS_PER_THREAD
        for i in range(NITEMS_PER_THREAD):
            cache[base + i] = (thread_id, i)
        for i in range(NITEMS_PER_THREAD):
            _ = cache.get(base + i)
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(exc)


def _thread_worker_ttl(cache, thread_id, barrier, errors):
    try:
        barrier.wait(timeout=TIMEOUT)
        base = thread_id * NITEMS_PER_THREAD
        for i in range(NITEMS_PER_THREAD):
            cache[base + i] = (thread_id, i)
        for i in range(NITEMS_PER_THREAD):
            try:
                _ = cache[base + i]
            except KeyError:
                pass
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(exc)


def test_lru_concurrent_currsize_bounded():
    """10 threads insert+query LRUCache concurrently; currsize must stay <= maxsize."""
    cache = LRUCache(maxsize=200)
    barrier = threading.Barrier(NTHREADS)
    errors = []
    threads = [
        threading.Thread(target=_thread_worker_lru, args=(cache, i, barrier, errors))
        for i in range(NTHREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=TIMEOUT)
        assert not t.is_alive(), "thread did not finish in time"

    assert not errors, "worker thread raised: %r" % (errors,)
    assert cache.currsize <= cache.maxsize, (
        "currsize=%d exceeded maxsize=%d" % (cache.currsize, cache.maxsize)
    )
    assert len(cache) <= cache.maxsize


def test_ttl_concurrent_currsize_bounded():
    """10 threads insert+query TTLCache concurrently; currsize must stay <= maxsize."""
    cache = TTLCache(maxsize=200, ttl=3600)
    barrier = threading.Barrier(NTHREADS)
    errors = []
    threads = [
        threading.Thread(target=_thread_worker_ttl, args=(cache, i, barrier, errors))
        for i in range(NTHREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=TIMEOUT)
        assert not t.is_alive(), "thread did not finish in time"

    assert not errors, "worker thread raised: %r" % (errors,)
    assert cache.currsize <= cache.maxsize, (
        "currsize=%d exceeded maxsize=%d" % (cache.currsize, cache.maxsize)
    )


def test_lru_concurrent_no_lost_items_small_cache():
    """Even with maxsize < NTHREADS * NITEMS, currsize stays bounded and stable."""
    maxsize = 50
    cache = LRUCache(maxsize=maxsize)
    barrier = threading.Barrier(NTHREADS)
    errors = []
    threads = [
        threading.Thread(target=_thread_worker_lru, args=(cache, i, barrier, errors))
        for i in range(NTHREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=TIMEOUT)

    assert not errors
    assert cache.currsize <= maxsize
    assert 0 < len(cache) <= maxsize


def test_ttl_concurrent_expire_during_access():
    """Concurrent TTLCache access with real TTL expiration in the middle."""
    cache = TTLCache(maxsize=50, ttl=0.05)

    def worker():
        for i in range(1000):
            key = i % 200
            cache[key] = i
            try:
                _ = cache[key]
            except KeyError:
                pass

    threads = [threading.Thread(target=worker) for _ in range(NTHREADS)]
    for t in threads:
        t.start()
    time.sleep(0.15)
    for t in threads:
        t.join(timeout=TIMEOUT)

    assert cache.currsize <= cache.maxsize


def test_lru_concurrent_setdefault():
    """Concurrent setdefault() calls must not violate currsize <= maxsize."""
    cache = LRUCache(maxsize=30)

    def worker(tid):
        for i in range(200):
            key = (tid * 7 + i) % 100
            cache.setdefault(key, i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(NTHREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=TIMEOUT)

    assert cache.currsize <= cache.maxsize
