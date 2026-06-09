import sys
sys.path.insert(0, '/app/cachetools/src')
from cachetools import LFUCache
import pickle

results = []
passed = 0
failed = 0

def test(name, condition, msg=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(f"PASS: {name}")
    else:
        failed += 1
        results.append(f"FAIL: {name} - {msg}")

try:
    c = LFUCache(maxsize=2)
    c[1] = 1
    c[1]
    c[2] = 2
    c[3] = 3
    test("basic_lfu_len", len(c) == 2, f"got {len(c)}")
    test("basic_lfu_key1", c[1] == 1, f"got {c.get(1)}")
    test("basic_lfu_2or3", 2 in c or 3 in c, f"keys: {list(c)}")

    c = LFUCache(maxsize=2)
    c[1] = 1
    c[1]
    c[2] = 2
    c[3] = 3
    test("lfu_freq_len", len(c) == 2, f"got {len(c)}")
    test("lfu_freq_key1", c[1] == 1, f"got {c.get(1)}")
    c[4] = 4
    test("lfu_freq_key4", c[4] == 4, f"got {c.get(4)}")
    test("lfu_freq_key1_still", c[1] == 1, f"got {c.get(1)}")

    c = LFUCache(maxsize=2)
    c[1] = 1
    c[2] = 2
    c[1] = "updated"
    c[3] = 3
    test("update_existing_val", c[1] == "updated", f"got {c[1]}")
    test("update_existing_3", 3 in c, f"keys: {list(c)}")
    test("update_existing_2_gone", 2 not in c, f"keys: {list(c)}")

    c = LFUCache(maxsize=2)
    c[1] = 1
    c[1]
    c[1]
    c[2] = 2
    c.clear()
    test("clear_len", len(c) == 0, f"got {len(c)}")
    test("clear_currsize", c.currsize == 0, f"got {c.currsize}")
    c[3] = 3
    c[4] = 4
    c[3]
    c[5] = 5
    test("clear_reuse_len", len(c) == 2, f"got {len(c)}")
    test("clear_reuse_3", 3 in c, f"keys: {list(c)}")
    test("clear_reuse_5", 5 in c, f"keys: {list(c)}")
    test("clear_reuse_4_gone", 4 not in c, f"keys: {list(c)}")

    c = LFUCache(maxsize=3, getsizeof=lambda x: x)
    c[1] = 1
    c[2] = 2
    c[3] = 3
    test("getsizeof_len", len(c) == 1, f"got {len(c)}")
    test("getsizeof_3", c[3] == 3, f"got {c[3]}")
    test("getsizeof_1_gone", 1 not in c, f"keys: {list(c)}")
    try:
        c[4] = 4
        test("getsizeof_valueerror", False)
    except ValueError:
        test("getsizeof_valueerror", True)

    c = LFUCache(maxsize=2)
    c.update({1: 1, 2: 2})
    key, val = c.popitem()
    test("popitem_key", key in {1, 2}, f"got {key}")
    test("popitem_len", len(c) == 1, f"got {len(c)}")
    key2, val2 = c.popitem()
    test("popitem_key2", key2 in {1, 2}, f"got {key2}")
    try:
        c.popitem()
        test("popitem_empty_error", False)
    except KeyError:
        test("popitem_empty_error", True)

    c = LFUCache(maxsize=3)
    c[1] = 1
    c[1]
    c[1]
    c[2] = 2
    c[2]
    c[3] = 3
    key, val = c.popitem()
    test("popitem_lfu_key3", key == 3, f"got key={key}")
    key2, val2 = c.popitem()
    test("popitem_lfu_key2", key2 == 2, f"got key={key2}")

    c = LFUCache(maxsize=2)
    c.update({1: 1, 2: 2})
    del c[2]
    test("del_len", len(c) == 1, f"got {len(c)}")
    test("del_1_in", 1 in c)
    test("del_2_out", 2 not in c)
    del c[1]
    test("del_empty", len(c) == 0, f"got {len(c)}")

    source = LFUCache(maxsize=2)
    source.update({1: 1, 2: 2})
    cache = pickle.loads(pickle.dumps(source))
    test("pickle_len", len(cache) == 2, f"got {len(cache)}")
    test("pickle_val1", cache[1] == 1, f"got {cache[1]}")
    test("pickle_val2", cache[2] == 2, f"got {cache[2]}")
    cache[3] = 3
    test("pickle_evict", len(cache) == 2, f"got {len(cache)}")
    test("pickle_3_in", 3 in cache, f"keys: {list(cache)}")
    cache2 = pickle.loads(pickle.dumps(cache))
    test("pickle_roundtrip", cache == cache2)

    c = LFUCache(maxsize=10)
    for i in range(100):
        c[i] = i
        c[i]
    test("stress_len", len(c) <= 10, f"got {len(c)}")
    for i in range(90, 100):
        test(f"stress_{i}_in", i in c, f"keys: {list(c)}")

    try:
        LFUCache(maxsize=2).popitem()
        test("popitem_exc", False)
    except KeyError as e:
        test("popitem_exc", True)
        test("popitem_no_cause", e.__cause__ is None, f"got {e.__cause__}")
        test("popitem_suppress", e.__suppress_context__, f"got {e.__suppress_context__}")

    c = LFUCache(maxsize=2)
    c[1] = 1
    test("get_existing", c.get(1) == 1, f"got {c.get(1)}")
    test("get_missing", c.get(999) is None, f"got {c.get(999)}")
    test("get_default", c.get(999, "d") == "d", f"got {c.get(999, 'd')}")

    c = LFUCache(maxsize=2)
    c[1] = 1
    val = c.setdefault(1, "default")
    test("setdefault_existing", val == 1, f"got {val}")
    val = c.setdefault(2, "new")
    test("setdefault_new", val == "new", f"got {val}")

    c = LFUCache(maxsize=3)
    c[1] = 1
    c[2] = 2
    c[3] = 3
    test("iter", set(list(c)) == {1, 2, 3}, f"got {list(c)}")

    c = LFUCache(maxsize=2)
    test("repr", repr(c).startswith("LFUCache"), f"got {repr(c)}")
    test("maxsize", c.maxsize == 2, f"got {c.maxsize}")
    test("currsize_empty", c.currsize == 0, f"got {c.currsize}")
    c[1] = 1
    test("currsize_after", c.currsize == 1, f"got {c.currsize}")

except Exception as e:
    results.append(f"EXCEPTION: {type(e).__name__}: {e}")
    import traceback
    results.append(traceback.format_exc())

results.append(f"\nResults: {passed} passed, {failed} failed")
if failed == 0:
    results.append("ALL TESTS PASSED!")
else:
    results.append("SOME TESTS FAILED!")

with open('/app/cachetools/test_results.txt', 'w') as f:
    f.write('\n'.join(results))
