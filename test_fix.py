#!/usr/bin/env python3
"""Simple test script to verify the TTLCache fix."""

import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cachetools import TTLCache

def test_basic_ttl():
    """Test basic TTL functionality."""
    cache = TTLCache(maxsize=10, ttl=0.1)
    cache['key1'] = 'value1'
    assert cache['key1'] == 'value1', "Basic get should work"
    time.sleep(0.15)
    try:
        cache['key1']
        assert False, "Should raise KeyError after TTL"
    except KeyError:
        pass
    print("✓ Basic TTL test passed")

def test_concurrent_read_write():
    """Test concurrent read/write operations."""
    cache = TTLCache(maxsize=100, ttl=0.05)
    errors = []
    success_count = [0]
    keyerror_count = [0]
    lock = threading.Lock()

    def writer(thread_id):
        try:
            for i in range(100):
                key = f"key_{thread_id}_{i}"
                cache[key] = f"value_{thread_id}_{i}"
        except Exception as e:
            with lock:
                errors.append(f"Writer {thread_id} error: {e}")

    def reader(thread_id):
        try:
            for i in range(100):
                key = f"key_{thread_id}_{i}"
                try:
                    value = cache[key]
                    with lock:
                        success_count[0] += 1
                except KeyError:
                    with lock:
                        keyerror_count[0] += 1
        except Exception as e:
            with lock:
                errors.append(f"Reader {thread_id} error: {e}")

    threads = []
    for i in range(5):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)
    for i in range(5):
        t = threading.Thread(target=reader, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(errors) == 0, f"Concurrent access caused errors: {errors}"
    assert keyerror_count[0] > 0, "Expected some KeyError for expired items"
    print(f"✓ Concurrent read/write test passed (success={success_count[0]}, keyerror={keyerror_count[0]})")

def test_expired_cleanup_under_reads():
    """Test that expired items are cleaned up under read-only access."""
    cache = TTLCache(maxsize=10, ttl=0.01)
    cache["test_key"] = "test_value"
    time.sleep(0.02)

    errors = []
    keyerror_count = [0]
    lock = threading.Lock()

    def reader():
        try:
            for _ in range(100):
                try:
                    cache["test_key"]
                except KeyError:
                    with lock:
                        keyerror_count[0] += 1
        except Exception as e:
            with lock:
                errors.append(f"Reader error: {e}")

    threads = []
    for i in range(10):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10)

    assert len(errors) == 0, f"Read-only concurrent access caused errors: {errors}"
    assert keyerror_count[0] > 0, "Expired items should return KeyError under concurrent reads"
    print(f"✓ Expired cleanup under reads test passed (keyerror={keyerror_count[0]})")

def test_high_contention():
    """Test high contention scenario."""
    cache = TTLCache(maxsize=5, ttl=0.05)
    errors = []
    operations = [0]
    lock = threading.Lock()

    def worker(thread_id):
        try:
            for i in range(100):
                key = f"hot_key_{i % 3}"
                try:
                    cache[key] = f"value_{thread_id}_{i}"
                    cache[key]
                    with lock:
                        operations[0] += 1
                except KeyError:
                    with lock:
                        operations[0] += 1
        except Exception as e:
            with lock:
                errors.append(f"Worker {thread_id} error: {e}")

    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10)

    assert len(errors) == 0, f"High contention caused errors: {errors}"
    assert operations[0] > 0, "Expected some operations to complete"
    print(f"✓ High contention test passed (operations={operations[0]})")

if __name__ == "__main__":
    print("Running TTLCache thread safety tests...")
    test_basic_ttl()
    test_concurrent_read_write()
    test_expired_cleanup_under_reads()
    test_high_contention()
    print("\n✓ All tests passed!")
