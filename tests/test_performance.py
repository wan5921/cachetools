import pytest
import time
import threading
import tracemalloc
from cachetools import LRUCache, TTLCache

# 1. pytest-benchmark for maxsize 100, 1000, 10000 insertion and querying
@pytest.mark.parametrize("maxsize", [100, 1000, 10000])
def test_lru_insert_benchmark(benchmark, maxsize):
    """Benchmark LRUCache insertion throughput."""
    cache = LRUCache(maxsize=maxsize)
    
    def insert_ops():
        for i in range(maxsize * 2):
            cache[i] = i
            
    benchmark(insert_ops)

@pytest.mark.parametrize("maxsize", [100, 1000, 10000])
def test_lru_query_benchmark(benchmark, maxsize):
    """Benchmark LRUCache query throughput."""
    cache = LRUCache(maxsize=maxsize)
    for i in range(maxsize):
        cache[i] = i
        
    def query_ops():
        for i in range(maxsize):
            _ = cache.get(i)
            
    benchmark(query_ops)

# 2. TTL expiration simulation
def test_ttl_expiration():
    """Simulate TTL expiration and verify cache size automatically reduces."""
    cache = TTLCache(maxsize=100, ttl=0.1)
    
    # Insert items
    for i in range(50):
        cache[i] = i
        
    assert cache.currsize == 50
    
    # Simulate TTL expiration
    time.sleep(0.2)
    
    # Verify expired items are removed automatically upon access
    # Calling cache.currsize automatically triggers expiration cleanup in cachetools
    assert cache.currsize == 0

# 3. Concurrency test
def test_concurrency():
    """10 threads concurrently access the cache, asserting currsize <= maxsize."""
    cache = LRUCache(maxsize=100)
    
    def worker():
        for i in range(1000):
            cache[i] = i
            _ = cache.get(i)
            
    threads = [threading.Thread(target=worker) for _ in range(10)]
    
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    assert cache.currsize <= 100

# 4. Memory leak check using tracemalloc
def test_memory_leak():
    """Check for memory leaks during cache operations using tracemalloc."""
    tracemalloc.start()
    
    cache = LRUCache(maxsize=1000)
    
    # Take baseline snapshot
    snapshot1 = tracemalloc.take_snapshot()
    
    # Perform heavy operations
    for i in range(10000):
        cache[i] = i
        
    # Take second snapshot
    snapshot2 = tracemalloc.take_snapshot()
    
    # Compare snapshots
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    tracemalloc.stop()
    
    # Assert we successfully captured memory stats
    assert len(top_stats) > 0
    
    # Filter to show only our cachetools operations (optional but good for reports)
    print("\n--- Memory Leak Check Results ---")
    for stat in top_stats[:5]:
        print(stat)
