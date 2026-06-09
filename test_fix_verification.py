import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import threading
import time
from cachetools import TTLCache

print("=" * 60)
print("Verifying TTLCache fix")
print("=" * 60)

# Test 1: Basic expiry and KeyError
print("\n[Test 1] Basic expiry returns KeyError...")
cache = TTLCache(maxsize=10, ttl=0.05)
cache["foo"] = "bar"
assert cache["foo"] == "bar", "Should return 'bar' before expiry"
time.sleep(0.1)
try:
    _ = cache["foo"]
    assert False, "Should have raised KeyError"
except KeyError:
    pass
assert "foo" not in cache, "Expired key should not be in cache"
print("  PASSED")

# Test 2: Expired items removed on read (not just on write)
print("\n[Test 2] Expired items removed on read...")
cache = TTLCache(maxsize=10, ttl=0.05)
cache["a"] = 1
cache["b"] = 2
cache["c"] = 3
assert len(cache) == 3
time.sleep(0.1)
try:
    _ = cache["a"]
    assert False, "Should have raised KeyError"
except KeyError:
    pass
assert len(cache) == 0, f"Expected 0, got {len(cache)}"
print("  PASSED")

# Test 3: _lock attribute exists
print("\n[Test 3] _lock attribute exists...")
cache = TTLCache(maxsize=10, ttl=1.0)
assert hasattr(cache, "_lock"), "_lock attribute missing"
print("  PASSED")

# Test 4: Concurrent access
print("\n[Test 4] Concurrent read/write access...")
cache = TTLCache(maxsize=1000, ttl=1.0)
errors = []

def writer(tid):
    try:
        for i in range(100):
            key = f"key-{tid}-{i}"
            cache[key] = i
    except Exception as e:
        errors.append(e)

def reader(tid):
    try:
        for i in range(100):
            key = f"key-{tid % 5}-{i}"
            try:
                _ = cache[key]
            except KeyError:
                pass
            _ = len(cache)
            _ = f"key-{tid}-{i}" in cache
    except Exception as e:
        errors.append(e)

threads = []
for i in range(20):
    if i % 2 == 0:
        threads.append(threading.Thread(target=writer, args=(i,)))
    else:
        threads.append(threading.Thread(target=reader, args=(i,)))
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=30)
    assert not t.is_alive(), "Thread timed out"

assert len(errors) == 0, f"Concurrency errors: {errors}"
print("  PASSED")

# Test 5: Concurrent access to expired items
print("\n[Test 5] Concurrent access to expired items returns KeyError...")
cache = TTLCache(maxsize=100, ttl=0.05)
keyerrors_reported = []
unexpected_values = []
errors = []

for i in range(50):
    cache[f"key-{i}"] = i

time.sleep(0.1)

def access_expired(tid):
    try:
        key = f"key-{tid % 50}"
        try:
            val = cache[key]
            unexpected_values.append((key, val))
        except KeyError:
            keyerrors_reported.append(key)
    except Exception as e:
        errors.append(e)

threads = [
    threading.Thread(target=access_expired, args=(i,))
    for i in range(20)
]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=30)
    assert not t.is_alive()

assert len(errors) == 0, f"Concurrency errors: {errors}"
assert len(unexpected_values) == 0, f"Expired keys returned values: {unexpected_values}"
assert len(keyerrors_reported) > 0, "No KeyError raised"
assert len(cache) == 0, f"Cache not empty: {len(cache)}"
print("  PASSED")

# Test 6: Concurrent write + expire maintains consistency
print("\n[Test 6] Concurrent write + expire maintains consistency...")
cache = TTLCache(maxsize=100, ttl=0.02)
errors = []
barrier = threading.Barrier(20)

def worker(tid):
    try:
        barrier.wait(timeout=30)
        for i in range(50):
            key = f"k-{tid}-{i}"
            cache[key] = i
            try:
                _ = cache[key]
            except KeyError:
                pass
            _ = len(cache)
    except Exception as e:
        errors.append(e)

threads = [
    threading.Thread(target=worker, args=(i,))
    for i in range(20)
]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=30)
    assert not t.is_alive()

assert len(errors) == 0, f"Concurrency errors: {errors}"
print("  PASSED")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
