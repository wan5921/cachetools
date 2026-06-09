"""Generate a test report for the cachetools test suite.

Runs:
1. Throughput benchmarks (insert / query) across different maxsizes
2. TTL expiration tests with real time.sleep()
3. Concurrent access tests (10 threads)
4. tracemalloc-based memory leak checks

Produces an ASCII table summary on stdout plus an optional
``cachetools_report.html`` HTML report.

Usage::

    python tests/generate_report.py
    python tests/generate_report.py --html
"""

from __future__ import annotations

import argparse
import gc
import html
import os
import subprocess
import sys
import time
import tracemalloc
import threading
from typing import List, Tuple

# Allow running both as `python tests/generate_report.py` and
# as a module within an installed package.
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from cachetools import LRUCache, TTLCache


MAXSIZES = (100, 1000, 10000)
NTHREADS = 10
TIMEOUT = 60


# ---------------------------------------------------------------------------
# 1. Throughput benchmarks
# ---------------------------------------------------------------------------
def benchmark_throughput() -> List[Tuple[str, int, float, float]]:
    """Measure insert / query throughput (ops/sec) per cache class and maxsize."""
    rows: List[Tuple[str, int, float, float]] = []
    for CacheCls in (LRUCache, TTLCache):
        for maxsize in MAXSIZES:
            kwargs = {"maxsize": maxsize}
            if CacheCls is TTLCache:
                kwargs["ttl"] = 3600
            cache = CacheCls(**kwargs)

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

            rows.append((CacheCls.__name__, maxsize, insert_ops, query_ops))
    return rows


# ---------------------------------------------------------------------------
# 2. TTL expiration tests (using real time.sleep)
# ---------------------------------------------------------------------------
def run_ttl_tests() -> List[Tuple[str, bool, str]]:
    """Run a handful of TTL expiry checks; returns (name, passed, detail)."""
    results: List[Tuple[str, bool, str]] = []

    # --- full expiry ---
    try:
        ttl = 0.1
        cache = TTLCache(maxsize=10, ttl=ttl)
        for i in range(5):
            cache[i] = i
        before = cache.currsize
        time.sleep(ttl + 0.05)
        after = cache.currsize
        ok = before == 5 and after == 0
        results.append(
            ("full_expire_after_sleep", ok, "before=%d after=%d" % (before, after))
        )
    except Exception as exc:
        results.append(("full_expire_after_sleep", False, str(exc)))

    # --- partial expiry (FakeTimer) ---
    try:
        class FakeTimer:
            def __init__(self):
                self._t = 0.0

            def __call__(self):
                return self._t

            def advance(self, s):
                self._t += s

        timer = FakeTimer()
        cache = TTLCache(maxsize=10, ttl=10, timer=timer)
        cache[1] = 1
        timer.advance(5)
        cache[2] = 2
        timer.advance(6)
        ok = cache.currsize == 1 and 1 not in cache and cache[2] == 2
        results.append(
            ("partial_expire_staggered", ok, "currsize=%d" % cache.currsize)
        )
    except Exception as exc:
        results.append(("partial_expire_staggered", False, str(exc)))

    # --- expire() return value ---
    try:
        cache = TTLCache(maxsize=10, ttl=0.1)
        for i in range(3):
            cache[i] = i
        time.sleep(0.15)
        expired = list(cache.expire())
        ok = len(expired) == 3 and cache.currsize == 0
        results.append(
            ("expire_returns_pairs", ok, "expired_items=%d" % len(expired))
        )
    except Exception as exc:
        results.append(("expire_returns_pairs", False, str(exc)))

    return results


# ---------------------------------------------------------------------------
# 3. Concurrent access tests (10 threads)
# ---------------------------------------------------------------------------
def run_concurrent_tests() -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = []

    for name, make_cache in (
        ("LRU_concurrent_10_threads", lambda: LRUCache(maxsize=200)),
        ("TTL_concurrent_10_threads", lambda: TTLCache(maxsize=200, ttl=3600)),
    ):
        try:
            cache = make_cache()
            barrier = threading.Barrier(NTHREADS)
            errors: List[Exception] = []

            def worker(tid):
                try:
                    barrier.wait(timeout=TIMEOUT)
                    for i in range(500):
                        cache[tid * 500 + i] = (tid, i)
                    for i in range(500):
                        _ = cache.get(tid * 500 + i)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(NTHREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=TIMEOUT)

            ok = (
                not errors
                and cache.currsize <= cache.maxsize
                and len(cache) <= cache.maxsize
            )
            results.append(
                (name, ok, "currsize=%d maxsize=%d errors=%d" % (cache.currsize, cache.maxsize, len(errors)))
            )
        except Exception as exc:
            results.append((name, False, str(exc)))

    return results


# ---------------------------------------------------------------------------
# 4. tracemalloc memory leak check
# ---------------------------------------------------------------------------
def run_tracemalloc_check() -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = []
    tracemalloc.start()
    try:
        # --- LRU cache bounded growth ---
        gc.collect()
        gc.collect()
        gc.collect()

        def run_lru(n=50, items_per_cycle=10000, maxsize=1000):
            cache = LRUCache(maxsize=maxsize)
            for cycle in range(n):
                off = cycle * items_per_cycle
                for i in range(items_per_cycle):
                    cache[off + i] = "v-%d" % (off + i)
                    if i % 100 == 0:
                        _ = cache.get(off + i - 50)
            return cache

        _ = run_lru()
        gc.collect()
        snap1 = tracemalloc.take_snapshot()
        size1 = sum(s.size for s in snap1.statistics("lineno"))

        _ = run_lru()
        _ = run_lru()
        gc.collect()
        gc.collect()
        gc.collect()
        snap2 = tracemalloc.take_snapshot()
        size2 = sum(s.size for s in snap2.statistics("lineno"))

        ratio = size2 / max(size1, 1)
        ok = ratio < 3.0
        results.append(
            (
                "tracemalloc_lru_no_leak",
                ok,
                "snap1_size=%d snap2_size=%d ratio=%.2f" % (size1, size2, ratio),
            )
        )

        # --- TTL cache: many expire() cycles ---
        gc.collect()
        snap_before = tracemalloc.take_snapshot()
        before_size = sum(s.size for s in snap_before.statistics("filename"))

        for _ in range(20):
            cache = TTLCache(maxsize=100, ttl=0.005)
            for i in range(200):
                cache[i] = "x" * 100
            time.sleep(0.02)
            assert cache.currsize == 0
            del cache
            gc.collect()

        snap_after = tracemalloc.take_snapshot()
        after_size = sum(s.size for s in snap_after.statistics("filename"))
        ratio2 = after_size / max(before_size, 1)
        ok2 = ratio2 < 5.0
        results.append(
            (
                "tracemalloc_ttl_expire_no_leak",
                ok2,
                "before=%d after=%d ratio=%.2f" % (before_size, after_size, ratio2),
            )
        )

        # --- Top 5 diff stats (informational) ---
        diffs = snap_after.compare_to(snap_before, "lineno")
        top5 = [str(s) for s in diffs[:5]]
        results.append(("tracemalloc_top5_diff", True, "; ".join(top5)[:200]))
    finally:
        tracemalloc.stop()

    return results


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------
def render_ascii_table(rows: List[Tuple[str, int, float, float]]) -> str:
    header = ("cache", "maxsize", "insert ops/sec", "query_hit ops/sec")
    fmt = "%-12s %-10s %-18s %-20s"
    lines = [fmt % header]
    lines.append("-" * 62)
    for cache, maxsize, ins, qry in rows:
        lines.append(fmt % (cache, str(maxsize), "%.0f" % ins, "%.0f" % qry))
    return "\n".join(lines)


def render_test_table(results: List[Tuple[str, bool, str]]) -> str:
    header = ("test", "status", "detail")
    fmt = "%-40s %-10s %s"
    lines = [fmt % header]
    lines.append("-" * 90)
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        lines.append(fmt % (name, status, detail))
    return "\n".join(lines)


def render_html(throughput: List[Tuple[str, int, float, float]],
                ttl_results: List[Tuple[str, bool, str]],
                concurrent_results: List[Tuple[str, bool, str]],
                tracemalloc_results: List[Tuple[str, bool, str]]) -> str:
    def row(cells):
        return "<tr>" + "".join("<td>%s</td>" % html.escape(str(c)) for c in cells) + "</tr>"

    throughput_tbl = (
        "<table border='1' cellpadding='6' cellspacing='0'>\n"
        "<tr><th>cache</th><th>maxsize</th><th>insert ops/sec</th><th>query_hit ops/sec</th></tr>\n"
        + "\n".join(row(r) for r in [(a, b, "%.0f" % c, "%.0f" % d) for a, b, c, d in throughput])
        + "\n</table>"
    )

    def results_table(title, data):
        rows_html = "\n".join(
            "<tr><td>%s</td><td style='color:%s'>%s</td><td>%s</td></tr>"
            % (
                html.escape(name),
                "green" if ok else "red",
                "PASS" if ok else "FAIL",
                html.escape(detail),
            )
            for name, ok, detail in data
        )
        return (
            "<h3>%s</h3>\n"
            "<table border='1' cellpadding='6' cellspacing='0'>\n"
            "<tr><th>test</th><th>status</th><th>detail</th></tr>\n"
            "%s\n</table>" % (html.escape(title), rows_html)
        )

    return f"""
<!doctype html>
<html><head><meta charset="utf-8"><title>cachetools test report</title>
<style>
  body {{ font-family: sans-serif; margin: 2em; }}
  table {{ border-collapse: collapse; margin: 1em 0; }}
  th {{ background: #f0f0f0; }}
  h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
</style></head><body>
<h1>cachetools test report</h1>
<p>Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

<h2>1. Throughput benchmarks</h2>
{throughput_tbl}

<h2>2. TTL expiration tests</h2>
{results_table('TTL tests', ttl_results)}

<h2>3. Concurrent access tests</h2>
{results_table('Concurrent tests', concurrent_results)}

<h2>4. Memory leak check (tracemalloc)</h2>
{results_table('Memory leak check', tracemalloc_results)}

<hr><em>Report generated by tests/generate_report.py</em>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", action="store_true", help="emit HTML report")
    parser.add_argument(
        "--out",
        default=os.path.join(PROJECT_ROOT, "cachetools_report.html"),
        help="HTML output path (default: cachetools_report.html)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("cachetools test report")
    print("=" * 70)

    print("\n[1/4] Throughput benchmarks (LRUCache / TTLCache)")
    throughput = benchmark_throughput()
    print(render_ascii_table(throughput))

    print("\n[2/4] TTL expiration tests")
    ttl_results = run_ttl_tests()
    print(render_test_table(ttl_results))

    print("\n[3/4] Concurrent access tests (10 threads)")
    concurrent_results = run_concurrent_tests()
    print(render_test_table(concurrent_results))

    print("\n[4/4] Memory leak check (tracemalloc)")
    tracemalloc_results = run_tracemalloc_check()
    print(render_test_table(tracemalloc_results))

    all_results = ttl_results + concurrent_results + tracemalloc_results
    failed = [(n, d) for n, ok, d in all_results if not ok]
    if failed:
        print("\nFAILED tests:")
        for name, detail in failed:
            print("  - %s: %s" % (name, detail))
    else:
        print("\nAll functional + memory-leak checks passed.")

    if args.html:
        html_text = render_html(throughput, ttl_results, concurrent_results, tracemalloc_results)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        print("\nHTML report written to:", args.out)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
