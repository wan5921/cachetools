import sys
import os
import time
import threading
import tracemalloc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cachetools import FIFOCache, LFUCache, LRUCache, RRCache, TTLCache


MAXSIZE_VALUES = [100, 1000, 10000]
CACHE_TYPES = {
    "LRUCache": LRUCache,
    "FIFOCache": FIFOCache,
    "LFUCache": LFUCache,
    "RRCache": RRCache,
    "TTLCache": TTLCache,
}


def benchmark_insert(cache_cls, maxsize, rounds=5):
    times = []
    for _ in range(rounds):
        cache = cache_cls(maxsize=maxsize) if cache_cls != TTLCache else cache_cls(maxsize=maxsize, ttl=60)
        start = time.perf_counter()
        for i in range(maxsize):
            cache[i] = i
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    avg = sum(times) / len(times)
    ops_per_sec = maxsize / avg if avg > 0 else 0
    return avg, ops_per_sec


def benchmark_query(cache_cls, maxsize, rounds=5):
    cache = cache_cls(maxsize=maxsize) if cache_cls != TTLCache else cache_cls(maxsize=maxsize, ttl=60)
    for i in range(maxsize):
        cache[i] = i

    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        for i in range(maxsize):
            cache.get(i)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    avg = sum(times) / len(times)
    ops_per_sec = maxsize / avg if avg > 0 else 0
    return avg, ops_per_sec


def benchmark_mixed(cache_cls, maxsize, rounds=5):
    cache = cache_cls(maxsize=maxsize) if cache_cls != TTLCache else cache_cls(maxsize=maxsize, ttl=60)
    for i in range(maxsize):
        cache[i] = i

    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        for i in range(maxsize):
            if i % 2 == 0:
                cache[i] = i * 2
            else:
                cache.get(i)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    avg = sum(times) / len(times)
    ops_per_sec = maxsize / avg if avg > 0 else 0
    return avg, ops_per_sec


def test_ttl_expiration():
    results = []
    cache = TTLCache(maxsize=100, ttl=0.3)
    for i in range(100):
        cache[i] = i
    size_before = cache.currsize
    time.sleep(0.4)
    size_after = cache.currsize
    results.append(("TTL full expire", size_before, size_after, size_after == 0))

    cache = TTLCache(maxsize=100, ttl=0.5)
    for i in range(50):
        cache[i] = i
    time.sleep(0.3)
    for i in range(50, 100):
        cache[i] = i
    size_before = cache.currsize
    time.sleep(0.3)
    size_after = cache.currsize
    results.append(("TTL partial expire", size_before, size_after, size_after == 50))

    return results


def test_concurrency():
    results = []
    for name, cls in CACHE_TYPES.items():
        if cls == TTLCache:
            cache = cls(maxsize=100, ttl=60)
        else:
            cache = cls(maxsize=100)

        errors = []
        nthreads = 10
        iterations = 500

        def worker(thread_id):
            try:
                for i in range(iterations):
                    key = thread_id * iterations + i
                    cache[key] = key
                    cache.get(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(nthreads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        passed = len(errors) == 0 and cache.currsize <= cache.maxsize
        results.append((name, cache.currsize, cache.maxsize, passed, len(errors)))

    return results


def test_memory_leak():
    results = []
    iterations = 5
    ops_per_round = 10000

    for name, cls in CACHE_TYPES.items():
        tracemalloc.start()
        if cls == TTLCache:
            cache = cls(maxsize=1000, ttl=60)
        else:
            cache = cls(maxsize=1000)

        baseline = tracemalloc.take_snapshot()

        for _ in range(iterations):
            for i in range(ops_per_round):
                cache[i % 2000] = i

        end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end.compare_to(baseline, "lineno")
        total_diff_kb = sum(s.size_diff for s in stats) / 1024

        passed = total_diff_kb < 512 and cache.currsize <= cache.maxsize
        results.append((name, cache.currsize, f"{total_diff_kb:.2f} KB", passed))

    return results


def format_table(headers, rows):
    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    sep = "+".join("-" * (w + 2) for w in col_widths)
    sep = "+" + sep + "+"

    def format_row(row):
        cells = [f" {str(row[i]):<{col_widths[i]}} " for i in range(len(row))]
        return "|" + "|".join(cells) + "|"

    lines = [sep, format_row(headers), sep]
    for row in rows:
        lines.append(format_row(row))
    lines.append(sep)
    return "\n".join(lines)


def main():
    print("=" * 80)
    print("  cachetools Performance & Correctness Test Report")
    print("=" * 80)

    print("\n[1] Insert Throughput (ops/sec)")
    print("-" * 80)
    headers = ["Cache Type", "maxsize=100", "maxsize=1000", "maxsize=10000"]
    rows = []
    for name, cls in CACHE_TYPES.items():
        row = [name]
        for ms in MAXSIZE_VALUES:
            _, ops = benchmark_insert(cls, ms)
            row.append(f"{ops:,.0f}")
        rows.append(row)
    print(format_table(headers, rows))

    print("\n[2] Query Throughput (ops/sec)")
    print("-" * 80)
    rows = []
    for name, cls in CACHE_TYPES.items():
        row = [name]
        for ms in MAXSIZE_VALUES:
            _, ops = benchmark_query(cls, ms)
            row.append(f"{ops:,.0f}")
        rows.append(row)
    print(format_table(headers, rows))

    print("\n[3] Mixed Read/Write Throughput (ops/sec)")
    print("-" * 80)
    rows = []
    for name, cls in CACHE_TYPES.items():
        row = [name]
        for ms in MAXSIZE_VALUES:
            _, ops = benchmark_mixed(cls, ms)
            row.append(f"{ops:,.0f}")
        rows.append(row)
    print(format_table(headers, rows))

    print("\n[4] TTL Expiration Test")
    print("-" * 80)
    ttl_results = test_ttl_expiration()
    headers = ["Test Case", "Size Before", "Size After", "Passed"]
    rows = [[r[0], str(r[1]), str(r[2]), "PASS" if r[3] else "FAIL"] for r in ttl_results]
    print(format_table(headers, rows))

    print("\n[5] Concurrency Test (10 threads)")
    print("-" * 80)
    conc_results = test_concurrency()
    headers = ["Cache Type", "currsize", "maxsize", "Passed", "Errors"]
    rows = [[r[0], str(r[1]), str(r[2]), "PASS" if r[3] else "FAIL", str(r[4])] for r in conc_results]
    print(format_table(headers, rows))

    print("\n[6] Memory Leak Check (tracemalloc)")
    print("-" * 80)
    mem_results = test_memory_leak()
    headers = ["Cache Type", "currsize", "Memory Growth", "Passed"]
    rows = [[r[0], str(r[1]), str(r[2]), "PASS" if r[3] else "FAIL"] for r in mem_results]
    print(format_table(headers, rows))

    print("\n" + "=" * 80)
    all_passed = (
        all(r[3] for r in ttl_results)
        and all(r[3] for r in conc_results)
        and all(r[3] for r in mem_results)
    )
    print(f"  Overall Result: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
