import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from cachetools import FIFOCache, LFUCache, LRUCache, RRCache, TTLCache


MAXSIZE_VALUES = [100, 1000, 10000]

CACHE_TYPES = {
    "LRUCache": LRUCache,
    "FIFOCache": FIFOCache,
    "LFUCache": LFUCache,
    "RRCache": RRCache,
}


def _cache_id(params):
    cache_cls, maxsize = params
    return f"{cache_cls.__name__}-maxsize={maxsize}"


def _fill_cache(cache, count):
    for i in range(count):
        cache[i] = i * 10


# ============================================================
# 1. pytest-benchmark: insertion and query throughput
# ============================================================


@pytest.fixture(
    params=[
        (cls, ms) for cls in CACHE_TYPES.values() for ms in MAXSIZE_VALUES
    ],
    ids=_cache_id,
)
def cache_instance(request):
    cls, maxsize = request.param
    return cls(maxsize=maxsize)


class TestBenchmarkInsert:
    def test_insert_throughput(self, benchmark, cache_instance):
        maxsize = cache_instance.maxsize

        def bench_insert():
            cache_instance.clear()
            for i in range(maxsize):
                cache_instance[i] = i

        benchmark(bench_insert)
        assert cache_instance.currsize <= maxsize


class TestBenchmarkQuery:
    @pytest.fixture(autouse=True)
    def populate_cache(self, cache_instance):
        _fill_cache(cache_instance, cache_instance.maxsize)

    def test_query_throughput(self, benchmark, cache_instance):
        maxsize = cache_instance.maxsize

        def bench_query():
            for i in range(maxsize):
                _ = cache_instance.get(i)

        benchmark(bench_query)


class TestBenchmarkMixed:
    def test_mixed_read_write(self, benchmark, cache_instance):
        maxsize = cache_instance.maxsize
        _fill_cache(cache_instance, maxsize)

        def bench_mixed():
            for i in range(maxsize):
                if i % 2 == 0:
                    cache_instance[i] = i * 2
                else:
                    cache_instance.get(i)

        benchmark(bench_mixed)


# ============================================================
# 2. TTL expiration: time.sleep to verify auto-shrink
# ============================================================


class TestTTLExpiration:
    def test_ttl_expire_shrinks_currsize(self):
        cache = TTLCache(maxsize=100, ttl=0.3)
        for i in range(100):
            cache[i] = i

        assert cache.currsize == 100
        assert len(cache) == 100

        time.sleep(0.4)

        assert cache.currsize == 0
        assert len(cache) == 0

    def test_ttl_partial_expire(self):
        cache = TTLCache(maxsize=100, ttl=0.5)
        for i in range(50):
            cache[i] = i

        time.sleep(0.3)

        for i in range(50, 100):
            cache[i] = i

        assert cache.currsize == 100

        time.sleep(0.3)

        assert cache.currsize == 50
        assert len(cache) == 50

        for i in range(50, 100):
            assert i in cache
        for i in range(50):
            assert i not in cache

    def test_ttl_expire_does_not_exceed_maxsize(self):
        cache = TTLCache(maxsize=10, ttl=0.3)
        for i in range(20):
            cache[i] = i

        assert cache.currsize <= 10

        time.sleep(0.4)

        assert cache.currsize == 0

        for i in range(5):
            cache[i] = i

        assert cache.currsize == 5
        assert cache.currsize <= cache.maxsize

    def test_ttl_expire_with_different_ttls(self):
        cache = TTLCache(maxsize=50, ttl=0.2)
        for i in range(50):
            cache[i] = i

        assert cache.currsize == 50

        time.sleep(0.25)

        assert cache.currsize == 0

        for i in range(30):
            cache[i] = i

        assert cache.currsize == 30

        time.sleep(0.25)

        assert cache.currsize == 0

    def test_ttl_currsize_never_exceeds_maxsize(self):
        cache = TTLCache(maxsize=100, ttl=1.0)
        for i in range(200):
            cache[i] = i

        assert cache.currsize <= 100
        assert len(cache) <= 100


# ============================================================
# 3. Concurrency: 10 threads, assert currsize <= maxsize
# ============================================================


class TestConcurrency:
    NTHREADS = 10
    ITERATIONS = 500

    def test_concurrent_insert_lru(self):
        cache = LRUCache(maxsize=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    cache[key] = key
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert cache.currsize <= cache.maxsize, (
            f"currsize={cache.currsize} exceeds maxsize={cache.maxsize}"
        )

    def test_concurrent_insert_fifo(self):
        cache = FIFOCache(maxsize=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    cache[key] = key
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert cache.currsize <= cache.maxsize

    def test_concurrent_insert_lfu(self):
        cache = LFUCache(maxsize=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    cache[key] = key
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert cache.currsize <= cache.maxsize

    def test_concurrent_insert_rr(self):
        cache = RRCache(maxsize=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    cache[key] = key
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert cache.currsize <= cache.maxsize

    def test_concurrent_ttl_cache(self):
        cache = TTLCache(maxsize=100, ttl=2.0)
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    cache[key] = key
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert cache.currsize <= cache.maxsize

    def test_concurrent_read_heavy(self):
        cache = LRUCache(maxsize=100)
        for i in range(100):
            cache[i] = i

        errors = []
        hits = [0] * self.NTHREADS

        def reader(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    val = cache.get(i % 100)
                    if val is not None:
                        hits[thread_id] += 1
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader, args=(tid,))
            for tid in range(self.NTHREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.currsize <= cache.maxsize
        assert all(h > 0 for h in hits)

    def test_concurrent_with_threadpool(self):
        cache = LRUCache(maxsize=100)
        lock = threading.Lock()
        errors = []

        def worker(thread_id):
            try:
                for i in range(self.ITERATIONS):
                    key = thread_id * self.ITERATIONS + i
                    with lock:
                        cache[key] = key
                        _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=self.NTHREADS) as executor:
            futures = [
                executor.submit(worker, tid) for tid in range(self.NTHREADS)
            ]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert cache.currsize <= cache.maxsize


# ============================================================
# 4. Memory leak check with tracemalloc
# ============================================================


class TestMemoryLeak:
    ITERATIONS = 5
    OPS_PER_ROUND = 10000

    def test_no_memory_leak_lru(self):
        tracemalloc.start()

        cache = LRUCache(maxsize=1000)
        baseline_snapshot = tracemalloc.take_snapshot()

        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(baseline_snapshot, "lineno")
        total_diff = sum(s.size_diff for s in stats)
        total_diff_kb = total_diff / 1024

        assert cache.currsize <= cache.maxsize
        assert total_diff_kb < 512, (
            f"Potential memory leak: {total_diff_kb:.2f} KB growth detected"
        )

    def test_no_memory_leak_fifo(self):
        tracemalloc.start()

        cache = FIFOCache(maxsize=1000)
        baseline_snapshot = tracemalloc.take_snapshot()

        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(baseline_snapshot, "lineno")
        total_diff = sum(s.size_diff for s in stats)
        total_diff_kb = total_diff / 1024

        assert cache.currsize <= cache.maxsize
        assert total_diff_kb < 512, (
            f"Potential memory leak: {total_diff_kb:.2f} KB growth detected"
        )

    def test_no_memory_leak_lfu(self):
        tracemalloc.start()

        cache = LFUCache(maxsize=1000)
        baseline_snapshot = tracemalloc.take_snapshot()

        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(baseline_snapshot, "lineno")
        total_diff = sum(s.size_diff for s in stats)
        total_diff_kb = total_diff / 1024

        assert cache.currsize <= cache.maxsize
        assert total_diff_kb < 512, (
            f"Potential memory leak: {total_diff_kb:.2f} KB growth detected"
        )

    def test_no_memory_leak_ttl(self):
        tracemalloc.start()

        cache = TTLCache(maxsize=1000, ttl=10.0)
        baseline_snapshot = tracemalloc.take_snapshot()

        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(baseline_snapshot, "lineno")
        total_diff = sum(s.size_diff for s in stats)
        total_diff_kb = total_diff / 1024

        assert cache.currsize <= cache.maxsize
        assert total_diff_kb < 512, (
            f"Potential memory leak: {total_diff_kb:.2f} KB growth detected"
        )

    def test_no_memory_leak_with_clear(self):
        tracemalloc.start()

        cache = LRUCache(maxsize=1000)
        baseline_snapshot = tracemalloc.take_snapshot()

        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i
            cache.clear()

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(baseline_snapshot, "lineno")
        total_diff = sum(s.size_diff for s in stats)
        total_diff_kb = total_diff / 1024

        assert cache.currsize == 0
        assert total_diff_kb < 256, (
            f"Potential memory leak after clear: {total_diff_kb:.2f} KB growth detected"
        )

    def test_tracemalloc_top_allocations(self):
        tracemalloc.start()

        cache = LRUCache(maxsize=1000)
        for _ in range(self.ITERATIONS):
            for i in range(self.OPS_PER_ROUND):
                cache[i % 2000] = i

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot.statistics("lineno")
        print("\nTop 10 memory allocations:")
        for stat in top_stats[:10]:
            print(stat)

        assert cache.currsize <= cache.maxsize
