"""Memory leak detection using :mod:`tracemalloc`.

Runs a large number of insert/evict/expire cycles on LRUCache and TTLCache,
then compares tracemalloc snapshots to flag unexpected memory growth.
"""

import gc
import sys
import tracemalloc
import time

import pytest

from cachetools import LRUCache, TTLCache


CYCLES = 50
ITEMS_PER_CYCLE = 10000
MAXSIZE = 1000


def _run_lru_cycles():
    cache = LRUCache(maxsize=MAXSIZE)
    for cycle in range(CYCLES):
        offset = cycle * ITEMS_PER_CYCLE
        for i in range(ITEMS_PER_CYCLE):
            cache[offset + i] = "value-%d" % (offset + i)
            if i % 100 == 0:
                _ = cache.get(offset + i - 50)
    return cache


def _run_ttl_cycles():
    cache = TTLCache(maxsize=MAXSIZE, ttl=0.01)
    for cycle in range(CYCLES):
        offset = cycle * ITEMS_PER_CYCLE
        for i in range(ITEMS_PER_CYCLE):
            cache[offset + i] = "value-%d" % (offset + i)
        time.sleep(0.02)
    return cache


def test_lru_no_memory_leak():
    """LRUCache memory usage must not grow linearly with number of insertions."""
    tracemalloc.start()
    try:
        gc.collect()
        gc.collect()
        gc.collect()

        _run_lru_cycles()
        snapshot1 = tracemalloc.take_snapshot()
        size1 = sum(stat.size for stat in snapshot1.statistics("lineno"))

        _run_lru_cycles()
        _run_lru_cycles()
        gc.collect()
        gc.collect()
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        size2 = sum(stat.size for stat in snapshot2.statistics("lineno"))

        ratio = size2 / max(size1, 1)
        assert ratio < 3.0, (
            "Possible memory leak: size1=%d, size2=%d, ratio=%.2f"
            % (size1, size2, ratio)
        )
    finally:
        tracemalloc.stop()


def test_ttl_no_memory_leak():
    """TTLCache memory usage must not grow linearly with number of insertions."""
    tracemalloc.start()
    try:
        gc.collect()
        gc.collect()
        gc.collect()

        _run_ttl_cycles()
        gc.collect()
        gc.collect()
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        size1 = sum(stat.size for stat in snapshot1.statistics("lineno"))

        _run_ttl_cycles()
        _run_ttl_cycles()
        gc.collect()
        gc.collect()
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        size2 = sum(stat.size for stat in snapshot2.statistics("lineno"))

        ratio = size2 / max(size1, 1)
        assert ratio < 3.0, (
            "Possible memory leak: size1=%d, size2=%d, ratio=%.2f"
            % (size1, size2, ratio)
        )
    finally:
        tracemalloc.stop()


def test_tracemalloc_top_differences_reported(capsys):
    """After running LRU insert/evict cycles, dump top tracemalloc diffs."""
    tracemalloc.start()
    try:
        gc.collect()
        snapshot_before = tracemalloc.take_snapshot()

        cache = LRUCache(maxsize=500)
        for cycle in range(10):
            for i in range(5000):
                cache[cycle * 5000 + i] = i
        del cache
        gc.collect()

        snapshot_after = tracemalloc.take_snapshot()
        stats = snapshot_after.compare_to(snapshot_before, "lineno")

        with capsys.disabled():
            print("")
            print("Top 5 tracemalloc differences after LRU workload:")
            for stat in stats[:5]:
                print("  ", stat)
            sys.stdout.flush()
    finally:
        tracemalloc.stop()


def test_tracemalloc_ttl_expire_no_leak():
    """Repeated TTL expire cycles: final currsize should be 0 and memory stable."""
    tracemalloc.start()
    try:
        gc.collect()
        baseline = tracemalloc.take_snapshot()
        base_size = sum(s.size for s in baseline.statistics("filename"))

        for _ in range(20):
            cache = TTLCache(maxsize=100, ttl=0.005)
            for i in range(200):
                cache[i] = "x" * 100
            time.sleep(0.02)
            assert cache.currsize == 0
            del cache
            gc.collect()

        final = tracemalloc.take_snapshot()
        final_size = sum(s.size for s in final.statistics("filename"))
        ratio = final_size / max(base_size, 1)
        assert ratio < 5.0, (
            "TTL cache may be leaking: base=%d, final=%d, ratio=%.2f"
            % (base_size, final_size, ratio)
        )
    finally:
        tracemalloc.stop()
