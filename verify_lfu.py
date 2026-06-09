import sys
sys.path.insert(0, '/app/cachetools/src')

from cachetools import LFUCache
import pickle

passed = 0
failed = 0

def test(name, condition, msg=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} - {msg}")

print("=== LFUCache heapq refactoring tests ===")

# Test 1: Basic LFU eviction
print("\n1. Basic LFU eviction")
c = LFUCache(maxsize=2)
c[1] = 1
c[1]  # access key 1, count=2
c[2] = 2  # count=1
c[3] = 3  # count=1, should evict key 2 (same count as 3, arbitrary)
test("len=2", len(c) == 2, f"got {len(c)}")
test("key 1 in cache", 1 in c, f"keys: {list(c)}")
test("key 1 value", c[1] == 1, f"got {c[1]}")
test("key 2 or 3 in cache", 2 in c or 3 in c, f"keys: {list(c)}")

# Test 2: LFU with access frequency
print("\n2. LFU with access frequency")
c = LFUCache(maxsize=2)
c[1] = 1
c[1]  # count=2
c[2] = 2  # count=1
c[3] = 3  # evicts 2 (count=1), 3 count=1
test("len=2", len(c) == 2, f"got {len(c)}")
test("key 1 still in cache (freq=2)", c[1] == 1, f"got {c.get(1, 'NOT FOUND')}")
c[4] = 4  # evicts 3 (count=1), 4 count=1
test("len=2", len(c) == 2, f"got {len(c)}")
test("key 4 in cache", c[4] == 4, f"got {c.get(4, 'NOT FOUND')}")
test("key 1 still in cache (freq=2)", c[1] == 1, f"got {c.get(1, 'NOT FOUND')}")
c[1]  # access key 1, count=3
test("key 1 value after access", c[1] == 1, f"got {c[1]}")
test("key 4 value", c[4] == 4, f"got {c[4]}")

# Test 3: Update existing key
print("\n3. Update existing key")
c = LFUCache(maxsize=2)
c[1] = 1
c[2] = 2
c[1] = "updated"  # updates value, increments count
c[3] = 3  # should evict key 2 (count=1)
test("key 1 updated value", c[1] == "updated", f"got {c[1]}")
test("key 3 in cache", 3 in c, f"keys: {list(c)}")
test("key 2 not in cache", 2 not in c, f"keys: {list(c)}")

# Test 4: Clear and reuse
print("\n4. Clear and reuse")
c = LFUCache(maxsize=2)
c[1] = 1
c[1]  # count=2
c[1]  # count=3
c[2] = 2
c.clear()
test("len=0 after clear", len(c) == 0, f"got {len(c)}")
test("currsize=0 after clear", c.currsize == 0, f"got {c.currsize}")
c[3] = 3
c[4] = 4
c[3]  # count=2
c[5] = 5  # should evict 4 (count=1)
test("len=2", len(c) == 2, f"got {len(c)}")
test("key 3 in cache", 3 in c, f"keys: {list(c)}")
test("key 5 in cache", 5 in c, f"keys: {list(c)}")
test("key 4 not in cache", 4 not in c, f"keys: {list(c)}")

# Test 5: getsizeof
print("\n5. getsizeof")
c = LFUCache(maxsize=3, getsizeof=lambda x: x)
c[1] = 1
c[2] = 2
test("len=2", len(c) == 2, f"got {len(c)}")
c[3] = 3
test("len=1 after adding size 3", len(c) == 1, f"got {len(c)}")
test("key 3 in cache", c[3] == 3, f"got {c[3]}")
test("key 1 not in cache", 1 not in c, f"keys: {list(c)}")
test("key 2 not in cache", 2 not in c, f"keys: {list(c)}")
try:
    c[4] = 4
    test("ValueError for too large value", False, "no exception raised")
except ValueError:
    test("ValueError for too large value", True)

# Test 6: popitem
print("\n6. popitem")
c = LFUCache(maxsize=2)
c.update({1: 1, 2: 2})
key, val = c.popitem()
test("popitem returns valid key", key in {1, 2}, f"got {key}")
test("len=1 after popitem", len(c) == 1, f"got {len(c)}")
key2, val2 = c.popitem()
test("popitem returns valid key", key2 in {1, 2}, f"got {key2}")
test("len=0 after popitem", len(c) == 0, f"got {len(c)}")
try:
    c.popitem()
    test("KeyError on empty popitem", False, "no exception raised")
except KeyError:
    test("KeyError on empty popitem", True)

# Test 7: popitem evicts least frequently used
print("\n7. popitem evicts LFU")
c = LFUCache(maxsize=3)
c[1] = 1
c[1]  # count=2
c[1]  # count=3
c[2] = 2
c[2]  # count=2
c[3] = 3  # count=1
key, val = c.popitem()
test("popitem evicts key 3 (lowest count)", key == 3, f"got key={key}")
key2, val2 = c.popitem()
test("popitem evicts key 2 (next lowest count)", key2 == 2, f"got key={key2}")

# Test 8: delete
print("\n8. Delete")
c = LFUCache(maxsize=2)
c.update({1: 1, 2: 2})
del c[2]
test("len=1 after delete", len(c) == 1, f"got {len(c)}")
test("key 1 in cache", 1 in c, f"keys: {list(c)}")
test("key 2 not in cache", 2 not in c, f"keys: {list(c)}")
del c[1]
test("len=0 after delete", len(c) == 0, f"got {len(c)}")

# Test 9: pickle
print("\n9. Pickle")
source = LFUCache(maxsize=2)
source.update({1: 1, 2: 2})
cache = pickle.loads(pickle.dumps(source))
test("pickle roundtrip len", len(cache) == 2, f"got {len(cache)}")
test("pickle roundtrip value 1", cache[1] == 1, f"got {cache[1]}")
test("pickle roundtrip value 2", cache[2] == 2, f"got {cache[2]}")
cache[3] = 3
test("eviction after pickle", len(cache) == 2, f"got {len(cache)}")
test("key 3 in cache", 3 in cache, f"keys: {list(cache)}")
cache2 = pickle.loads(pickle.dumps(cache))
test("second pickle roundtrip", cache == cache2)

# Test 10: pop
print("\n10. Pop")
c = LFUCache(maxsize=2)
c.update({1: 1, 2: 2})
test("pop returns value", c.pop(2) == 2, f"got {c.pop(2) if 2 in c else 'N/A'}")
test("len after pop", len(c) == 1, f"got {len(c)}")
test("pop with default", c.pop(99, None) is None, f"got {c.pop(99, None)}")

# Test 11: Heap cleanup (stress test)
print("\n11. Heap cleanup stress test")
c = LFUCache(maxsize=10)
for i in range(100):
    c[i] = i
    c[i]  # access once
test("maxsize respected", len(c) <= 10, f"got {len(c)}")
for i in range(90, 100):
    test(f"recent key {i} in cache", i in c, f"keys: {list(c)}")

# Test 12: popitem exception context
print("\n12. popitem exception context")
try:
    LFUCache(maxsize=2).popitem()
    test("KeyError raised", False)
except KeyError as e:
    test("KeyError raised", True)
    test("no __cause__", e.__cause__ is None, f"got {e.__cause__}")
    test("__suppress_context__", e.__suppress_context__, f"got {e.__suppress_context__}")

# Test 13: Missing key
print("\n13. Missing key")
c = LFUCache(maxsize=2)
try:
    c[999]
    test("KeyError for missing key", False)
except KeyError:
    test("KeyError for missing key", True)

# Test 14: get method
print("\n14. get method")
c = LFUCache(maxsize=2)
c[1] = 1
test("get existing key", c.get(1) == 1, f"got {c.get(1)}")
test("get missing key returns None", c.get(999) is None, f"got {c.get(999)}")
test("get missing key with default", c.get(999, "default") == "default", f"got {c.get(999, 'default')}")

# Test 15: setdefault
print("\n15. setdefault")
c = LFUCache(maxsize=2)
c[1] = 1
val = c.setdefault(1, "default")
test("setdefault existing key", val == 1, f"got {val}")
val = c.setdefault(2, "new")
test("setdefault new key", val == "new", f"got {val}")

# Test 16: update
print("\n16. update")
c = LFUCache(maxsize=2)
c.update({1: 1, 2: 2})
test("len after update", len(c) == 2, f"got {len(c)}")
test("value 1", c[1] == 1, f"got {c[1]}")
test("value 2", c[2] == 2, f"got {c[2]}")

# Test 17: iterator
print("\n17. iterator")
c = LFUCache(maxsize=3)
c[1] = 1
c[2] = 2
c[3] = 3
keys = list(c)
test("iterator returns all keys", set(keys) == {1, 2, 3}, f"got {keys}")

# Test 18: contains
print("\n18. contains")
c = LFUCache(maxsize=2)
c[1] = 1
test("key 1 in cache", 1 in c)
test("key 2 not in cache", 2 not in c)

# Test 19: repr
print("\n19. repr")
c = LFUCache(maxsize=2)
test("repr starts with class name", repr(c).startswith("LFUCache"), f"got {repr(c)}")

# Test 20: maxsize and currsize
print("\n20. maxsize and currsize")
c = LFUCache(maxsize=2)
test("maxsize", c.maxsize == 2, f"got {c.maxsize}")
test("currsize empty", c.currsize == 0, f"got {c.currsize}")
c[1] = 1
test("currsize after insert", c.currsize == 1, f"got {c.currsize}")

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED!")
    sys.exit(0)
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)
