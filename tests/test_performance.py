import json
import os
import threading
import time
import tracemalloc
import unittest

import pytest

from cachetools import LRUCache, TTLCache


class TestBenchmarkCacheThroughput:

    MAXSIZES = [100, 1000, 10000]

    @pytest.mark.parametrize("maxsize", MAXSIZES)
    def test_cache_insert_throughput(self, benchmark, maxsize):
        cache = LRUCache(maxsize=maxsize)

        def insert_loop():
            for i in range(maxsize):
                cache[i] = f"value-{i}"

        benchmark(insert_loop)

    @pytest.mark.parametrize("maxsize", MAXSIZES)
    def test_cache_query_throughput(self, benchmark, maxsize):
        cache = LRUCache(maxsize=maxsize)
        for i in range(maxsize):
            cache[i] = f"value-{i}"

        def query_loop():
            for i in range(maxsize):
                _ = cache[i]

        benchmark(query_loop)

    @pytest.mark.parametrize("maxsize", MAXSIZES)
    def test_cache_mixed_workload_throughput(self, benchmark, maxsize):
        cache = LRUCache(maxsize=maxsize)
        for i in range(maxsize // 2):
            cache[i] = f"value-{i}"

        def mixed_loop():
            for i in range(maxsize):
                if i % 3 == 0:
                    cache[i] = f"value-{i}"
                else:
                    _ = cache.get(i, None)

        benchmark(mixed_loop)


class TestTTLExpiration(unittest.TestCase):

    def test_ttl_expiration_shrinks_cache(self):
        cache = TTLCache(maxsize=100, ttl=0.5, timer=time.monotonic)
        for i in range(50):
            cache[i] = f"value-{i}"
        self.assertEqual(len(cache), 50)
        self.assertEqual(cache.currsize, 50)

        time.sleep(0.6)

        self.assertLess(len(cache), 50)
        self.assertLess(cache.currsize, 50)

    def test_ttl_expiration_multiple_rounds(self):
        cache = TTLCache(maxsize=200, ttl=0.3, timer=time.monotonic)

        cache.update({i: f"a-{i}" for i in range(20)})
        self.assertEqual(len(cache), 20)

        time.sleep(0.2)
        cache.update({i + 20: f"b-{i}" for i in range(20)})
        self.assertEqual(len(cache), 40)

        time.sleep(0.2)
        self.assertLessEqual(len(cache), 20)
        for i in range(20):
            self.assertEqual(cache[i + 20], f"b-{i}")

    def test_ttl_expiration_gradual_shrink(self):
        cache = TTLCache(maxsize=100, ttl=0.3, timer=time.monotonic)

        cache.update({i: f"batch1-{i}" for i in range(30)})
        time.sleep(0.15)
        cache.update({i + 30: f"batch2-{i}" for i in range(30)})
        time.sleep(0.15)
        cache.update({i + 60: f"batch3-{i}" for i in range(30)})

        self.assertLessEqual(len(cache), 60)

        time.sleep(0.2)
        self.assertLessEqual(len(cache), 30)
        for i in range(60, 90):
            self.assertEqual(cache[i], f"batch3-{i}")

    def test_ttl_currsize_matches_after_expiration(self):
        cache = TTLCache(maxsize=200, ttl=0.4, timer=time.monotonic)

        for i in range(80):
            cache[i] = f"data-{i}"

        time.sleep(0.5)

        expired_items = cache.expire()
        self.assertGreater(len(expired_items), 0)
        self.assertEqual(len(cache), cache.currsize)
        self.assertLess(cache.currsize, 80)


class TestConcurrentCacheAccess(unittest.TestCase):

    NTHREADS = 10
    MAXSIZE = 50
    ITERATIONS = 2000

    def _worker(self, cache, start_barrier, results_list, errors_list):
        start_barrier.wait()
        try:
            for i in range(self.ITERATIONS):
                key = i % (self.MAXSIZE * 2)
                if i % 3 == 0:
                    cache[key] = f"thread-val-{key}"
                else:
                    _ = cache.get(key, None)
                if cache.currsize > self.MAXSIZE:
                    errors_list.append(
                        f"currsize {cache.currsize} exceeded maxsize {self.MAXSIZE}"
                    )
                results_list.append(cache.currsize)
        except Exception as e:
            errors_list.append(str(e))

    def test_concurrent_lru_cache_currsize_never_exceeds_maxsize(self):
        cache = LRUCache(maxsize=self.MAXSIZE)
        start_barrier = threading.Barrier(self.NTHREADS)
        threads = []
        results = []
        errors = []

        for _ in range(self.NTHREADS):
            t = threading.Thread(
                target=self._worker, args=(cache, start_barrier, results, errors)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
            self.assertFalse(t.is_alive())

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        for i, currsize in enumerate(results):
            self.assertLessEqual(
                currsize,
                self.MAXSIZE,
                f"currsize {currsize} > maxsize {self.MAXSIZE} at result index {i}",
            )
        self.assertLessEqual(cache.currsize, self.MAXSIZE)
        self.assertLessEqual(len(cache), self.MAXSIZE)

    def test_concurrent_ttl_cache_currsize_never_exceeds_maxsize(self):
        cache = TTLCache(maxsize=self.MAXSIZE, ttl=10.0, timer=time.monotonic)
        start_barrier = threading.Barrier(self.NTHREADS)
        threads = []
        results = []
        errors = []

        for _ in range(self.NTHREADS):
            t = threading.Thread(
                target=self._worker, args=(cache, start_barrier, results, errors)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
            self.assertFalse(t.is_alive())

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        for i, currsize in enumerate(results):
            self.assertLessEqual(
                currsize,
                self.MAXSIZE,
                f"currsize {currsize} > maxsize {self.MAXSIZE} at result index {i}",
            )
        self.assertLessEqual(cache.currsize, self.MAXSIZE)
        self.assertLessEqual(len(cache), self.MAXSIZE)


class TestMemoryLeakCheck(unittest.TestCase):

    ITERATIONS = 100000

    def test_lru_cache_no_memory_leak(self):
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        cache = LRUCache(maxsize=100)
        for n in range(self.ITERATIONS):
            key = n % 200
            cache[key] = f"value-{key}"
            val = cache.get(key, None)
        del cache

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        top_stats = [s for s in stats if s.size_diff > 0]
        top_stats.sort(key=lambda s: s.size_diff, reverse=True)

        total_diff = sum(s.size_diff for s in top_stats)
        self.assertLess(
            total_diff,
            1024 * 1024,
            f"Potential memory leak detected: {total_diff} bytes difference",
        )


def generate_performance_report():
    """Generate a performance comparison report and save to artifacts directory."""

    import datetime

    report = {
        "title": "Cachetools Performance Test Report",
        "generated_at": datetime.datetime.now().isoformat(),
        "performance_comparison": {
            "maxsize_100": {
                "insert_ops_per_second": "see pytest-benchmark output",
                "query_ops_per_second": "see pytest-benchmark output",
                "mixed_ops_per_second": "see pytest-benchmark output",
            },
            "maxsize_1000": {
                "insert_ops_per_second": "see pytest-benchmark output",
                "query_ops_per_second": "see pytest-benchmark output",
                "mixed_ops_per_second": "see pytest-benchmark output",
            },
            "maxsize_10000": {
                "insert_ops_per_second": "see pytest-benchmark output",
                "query_ops_per_second": "see pytest-benchmark output",
                "mixed_ops_per_second": "see pytest-benchmark output",
            },
        },
        "ttl_expiration_tests": {
            "test_ttl_expiration_shrinks_cache": "verifies cache shrinks after TTL",
            "test_ttl_expiration_multiple_rounds": "verifies staggered expiration",
            "test_ttl_expiration_gradual_shrink": "verifies gradual expiration behavior",
            "test_ttl_currsize_matches_after_expiration": "verifies len == currsize",
        },
        "concurrent_tests": {
            "threads": 10,
            "assertion": "currsize never exceeds maxsize under concurrent access",
        },
        "memory_leak_check": {
            "tool": "tracemalloc",
            "iterations": 100000,
            "threshold_bytes": 1048576,
        },
    }

    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    report_path = os.path.join(artifacts_dir, "performance_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Performance report saved to: {report_path}")
    return report


class TestGenerateReport(unittest.TestCase):

    def test_generate_performance_report(self):
        report = generate_performance_report()
        self.assertIn("performance_comparison", report)
        self.assertIn("ttl_expiration_tests", report)
        self.assertIn("concurrent_tests", report)
        self.assertIn("memory_leak_check", report)