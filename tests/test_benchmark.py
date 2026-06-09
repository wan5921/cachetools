import pytest

from cachetools import LRUCache

pytest.importorskip("pytest_benchmark")

MAXSIZES = (100, 1000, 10000)


@pytest.mark.parametrize("maxsize", MAXSIZES, ids=lambda value: f"maxsize={value}")
@pytest.mark.benchmark(group="cache-insert-throughput")
def test_insert_throughput(benchmark, maxsize):
    def insert_batch():
        cache = LRUCache(maxsize=maxsize)
        for key in range(maxsize):
            cache[key] = key
        return cache.currsize

    assert benchmark.pedantic(insert_batch, rounds=5, iterations=1) == maxsize


@pytest.mark.parametrize("maxsize", MAXSIZES, ids=lambda value: f"maxsize={value}")
@pytest.mark.benchmark(group="cache-lookup-throughput")
def test_lookup_throughput(benchmark, maxsize):
    cache = LRUCache(maxsize=maxsize)
    for key in range(maxsize):
        cache[key] = key
    expected = maxsize * (maxsize - 1) // 2

    def lookup_batch():
        total = 0
        for key in range(maxsize):
            total += cache[key]
        return total

    assert benchmark.pedantic(lookup_batch, rounds=5, iterations=1) == expected
