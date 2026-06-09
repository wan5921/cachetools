import sys
sys.path.insert(0, '/app/cachetools/src')

from cachetools import LFUCache

c = LFUCache(maxsize=2)
c[1] = 1
c[1]
c[2] = 2
c[3] = 3
assert len(c) == 2, f"Expected len=2, got {len(c)}"
assert c[1] == 1, f"Expected c[1]=1, got {c[1]}"
assert 2 in c or 3 in c, "Expected 2 or 3 in cache"
print("Basic LFU test: PASSED")

c[4] = 4
assert len(c) == 2, f"Expected len=2, got {len(c)}"
assert c[4] == 4, f"Expected c[4]=4, got {c[4]}"
assert c[1] == 1, f"Expected c[1]=1, got {c[1]}"
print("LFU eviction test: PASSED")

c2 = LFUCache(maxsize=2)
c2[1] = 1
c2[2] = 2
c2[1] = "updated"
c2[3] = 3
assert c2[1] == "updated", f"Expected 'updated', got {c2[1]}"
assert 3 in c2, "Expected 3 in cache"
assert 2 not in c2, "Expected 2 not in cache"
print("LFU update existing test: PASSED")

c3 = LFUCache(maxsize=2)
c3[1] = 1
c3[1]
c3[1]
c3[2] = 2
c3.clear()
assert len(c3) == 0, f"Expected len=0, got {len(c3)}"
assert c3.currsize == 0, f"Expected currsize=0, got {c3.currsize}"
c3[3] = 3
c3[4] = 4
c3[3]
c3[5] = 5
assert len(c3) == 2, f"Expected len=2, got {len(c3)}"
assert 3 in c3, "Expected 3 in cache"
assert 5 in c3, "Expected 5 in cache"
assert 4 not in c3, "Expected 4 not in cache"
print("LFU clear test: PASSED")

import pickle
c4 = LFUCache(maxsize=2)
c4.update({1: 1, 2: 2})
c4_unpickled = pickle.loads(pickle.dumps(c4))
assert len(c4_unpickled) == 2, f"Expected len=2, got {len(c4_unpickled)}"
assert c4_unpickled[1] == 1, f"Expected c[1]=1, got {c4_unpickled[1]}"
assert c4_unpickled[2] == 2, f"Expected c[2]=2, got {c4_unpickled[2]}"
c4_unpickled[3] = 3
assert len(c4_unpickled) == 2, f"Expected len=2, got {len(c4_unpickled)}"
assert 3 in c4_unpickled, "Expected 3 in cache"
print("LFU pickle test: PASSED")

c5 = LFUCache(maxsize=3, getsizeof=lambda x: x)
c5[1] = 1
c5[2] = 2
assert len(c5) == 2
c5[3] = 3
assert len(c5) == 1
assert c5[3] == 3
assert 1 not in c5
assert 2 not in c5
print("LFU getsizeof test: PASSED")

c6 = LFUCache(maxsize=2)
c6.update({1: 1, 2: 2})
key, val = c6.popitem()
assert key in {1, 2}, f"Expected key in {{1,2}}, got {key}"
assert len(c6) == 1
key2, val2 = c6.popitem()
assert key2 in {1, 2}, f"Expected key in {{1,2}}, got {key2}"
assert len(c6) == 0
try:
    c6.popitem()
    assert False, "Expected KeyError"
except KeyError:
    pass
print("LFU popitem test: PASSED")

c7 = LFUCache(maxsize=2)
c7.update({1: 1, 2: 2})
del c7[2]
assert len(c7) == 1
assert 1 in c7
assert 2 not in c7
del c7[1]
assert len(c7) == 0
print("LFU delete test: PASSED")

print("\nAll basic tests PASSED!")
