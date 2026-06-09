"""Performance benchmarks for cachetools with varying maxsize.

Tests insert and query throughput for LRUCache and TTLCache at different
maxsize values (100, 1000, 10000).  Run with:

    pytest tests/test_benchmark.py --benchmark-autosave
"""

import random
import sys
import time

import pytest

from cachetools import LRUCache, TTLCache


MAXSIZES = (100, 1000, 10000)


def _make_lru_cache(maxsize):
    cache = LRUCache(maxsize=maxsize)
    for i in range(maxsize):
        cache[i] = "value-%d" % i
    return cache


def _make_ttl_cache(maxsize):
    cache = TTLCache(maxsize=maxsize, ttl=3600)
    for i in range(maxsize):
        cache[i] = "value-%d" % i
    return cache


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_lru_insert(benchmark, maxsize):
    """Benchmark inserting `maxsize` unique items into an empty LRUCache."""

    def do_insert():
        cache = LRUCache(maxsize=maxsize)
        for i in range(maxsize):
            cache[i] = i
        return cache

    cache = benchmark(do_insert)
    assert cache.currsize <= maxsize
    assert len(cache) == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_lru_query_hit(benchmark, maxsize):
    """Benchmark successful lookups on a fully populated LRUCache."""
    cache = _make_lru_cache(maxsize)
    keys = list(range(maxsize))
    random.shuffle(keys)

    def do_query():
        total = 0
        for k in keys:
            if cache[k] is not None:
                total += 1
        return total

    hits = benchmark(do_query)
    assert hits == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_lru_query_miss(benchmark, maxsize):
    """Benchmark lookups of keys that are NOT in the LRUCache."""
    cache = _make_lru_cache(maxsize)
    miss_keys = [-i - 1 for i in range(maxsize)]

    def do_query():
        total = 0
        for k in miss_keys:
            try:
                cache[k]
            except KeyError:
                total += 1
        return total

    misses = benchmark(do_query)
    assert misses == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_ttl_insert(benchmark, maxsize):
    """Benchmark inserting `maxsize` unique items into an empty TTLCache."""

    def do_insert():
        cache = TTLCache(maxsize=maxsize, ttl=3600)
        for i in range(maxsize):
            cache[i] = i
        return cache

    cache = benchmark(do_insert)
    assert cache.currsize <= maxsize
    assert len(cache) == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_ttl_query_hit(benchmark, maxsize):
    """Benchmark successful lookups on a fully populated TTLCache."""
    cache = _make_ttl_cache(maxsize)
    keys = list(range(maxsize))
    random.shuffle(keys)

    def do_query():
        total = 0
        for k in keys:
            if cache[k] is not None:
                total += 1
        return total

    hits = benchmark(do_query)
    assert hits == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES)
def test_ttl_query_miss(benchmark, maxsize):
    """Benchmark lookups of keys that are NOT in the TTLCache."""
    cache = _make_ttl_cache(maxsize)
    miss_keys = [-i - 1 for i in range(maxsize)]

    def do_query():
        total = 0
        for k in miss_keys:
            try:
                cache[k]
            except KeyError:
                total += 1
        return total

    misses = benchmark(do_query)
    assert misses == maxsize


def test_throughput_summary():
    """Compute and print raw throughput (ops/sec) for each maxsize.

    This is NOT a benchmarked test (it runs once), but provides a quick
    human readable summary table alongside pytest-benchmark results.
    """
    print("")
    print("%-10s %-14s %-14s %-14s" % ("cache", "maxsize", "insert/s", "query_hit/s"))
    print("-" * 56)

    for CacheCls in (LRUCache, TTLCache):
        for maxsize in MAXSIZES:
            cache = CacheCls(maxsize=maxsize) if CacheCls is LRUCache else CacheCls(maxsize=maxsize, ttl=3600)
            start = time.perf_counter()
            for i in range(maxsize):
                cache[i] = i
            insert_t = time.perf_counter() - start
            insert_ops = maxsize / insert_t if insert_t > 0 else float("inf")

            start = time.perf_counter()
            for i in range(maxsize):
                _ = cache[i]
            query_t = time.perf_counter() - start
            query_ops = maxsize / query_t if query_t > 0 else float("inf")

            print(
                "%-10s %-14d %-14.0f %-14.0f"
                % (CacheCls.__name__, maxsize, insert_ops, query_ops)
            )
            assert cache.currsize <= maxsize

    sys.stdout.flush()
