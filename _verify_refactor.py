import sys
import os
sys.path.insert(0, '/app/cachetools/src')
os.chdir('/app/cachetools')

from cachetools import LFUCache

def test_lfu():
    cache = LFUCache(maxsize=2)
    cache[1] = 1
    cache[1]
    cache[2] = 2
    cache[3] = 3
    assert len(cache) == 2
    assert cache[1] == 1
    assert (2 in cache) ^ (3 in cache)
    cache[4] = 4
    assert len(cache) == 2
    assert cache[4] == 4
    assert cache[1] == 1
    cache[1]
    assert len(cache) == 2
    assert cache[1] == 1
    assert cache[4] == 4
    print("PASS: test_lfu")

def test_lfu_getsizeof():
    cache = LFUCache(maxsize=3, getsizeof=lambda x: x)
    cache[1] = 1
    cache[2] = 2
    assert len(cache) == 2
    assert cache[1] == 1
    assert cache[2] == 2
    cache[3] = 3
    assert len(cache) == 1
    assert cache[3] == 3
    assert 1 not in cache
    assert 2 not in cache
    try:
        cache[4] = 4
        assert False
    except ValueError:
        pass
    assert len(cache) == 1
    assert cache[3] == 3
    print("PASS: test_lfu_getsizeof")

def test_lfu_update_existing():
    cache = LFUCache(maxsize=2)
    cache[1] = 1
    cache[2] = 2
    cache[1] = "updated"
    cache[3] = 3
    assert cache[1] == "updated"
    assert 3 in cache
    assert 2 not in cache
    print("PASS: test_lfu_update_existing")

def test_lfu_clear():
    cache = LFUCache(maxsize=2)
    cache[1] = 1
    cache[1]
    cache[1]
    cache[2] = 2
    cache.clear()
    assert 0 == len(cache)
    assert 0 == cache.currsize
    cache[3] = 3
    cache[4] = 4
    cache[3]
    cache[5] = 5
    assert 2 == len(cache)
    assert 3 in cache
    assert 5 in cache
    assert 4 not in cache
    print("PASS: test_lfu_clear")

def test_missing():
    class DefaultCache(LFUCache):
        def __missing__(self, key):
            self[key] = key
            return key
    cache = DefaultCache(maxsize=2)
    assert cache[1] == 1
    assert cache[2] == 2
    assert len(cache) == 2
    assert cache[3] == 3
    assert len(cache) == 2
    assert 3 in cache
    print("PASS: test_missing")

def test_missing_getsizeof():
    class DefaultCache(LFUCache):
        def __missing__(self, key):
            try:
                self[key] = key
            except ValueError:
                pass
            return key
    cache = DefaultCache(maxsize=2, getsizeof=lambda x: x)
    assert cache[1] == 1
    assert cache[2] == 2
    assert 1 not in cache
    assert 2 in cache
    assert cache[3] == 3
    assert cache[1] == 1
    assert (1, 1) == cache.popitem()
    print("PASS: test_missing_getsizeof")

def test_getsizeof_param():
    cache = LFUCache(maxsize=3, getsizeof=lambda x: x)
    cache.update({1: 1, 2: 2})
    assert cache[1] == 1
    assert cache[2] == 2
    cache[1] = 2
    assert 1 == len(cache)
    assert 2 == cache.currsize
    assert 2 == cache[1]
    assert 2 not in cache
    cache.update({1: 1, 2: 2})
    cache[3] = 3
    assert 1 == len(cache)
    assert 3 == cache.currsize
    assert 3 == cache[3]
    print("PASS: test_getsizeof_param")

def test_popitem():
    cache = LFUCache(maxsize=2)
    cache.update({1: 1, 2: 2})
    key, _ = cache.popitem()
    assert key in {1, 2}
    assert 1 == len(cache)
    key, _ = cache.popitem()
    assert key in {1, 2}
    assert 0 == len(cache)
    try:
        cache.popitem()
        assert False
    except KeyError:
        pass
    print("PASS: test_popitem")

def test_pickle():
    import pickle
    source = LFUCache(maxsize=2)
    source.update({1: 1, 2: 2})
    cache = pickle.loads(pickle.dumps(source))
    assert source == cache
    assert 2 == len(cache)
    assert 1 == cache[1]
    assert 2 == cache[2]
    cache[3] = 3
    assert 2 == len(cache)
    assert 3 == cache[3]
    print("PASS: test_pickle")

test_lfu()
test_lfu_getsizeof()
test_lfu_update_existing()
test_lfu_clear()
test_missing()
test_missing_getsizeof()
test_getsizeof_param()
test_popitem()
test_pickle()
print("\n=== ALL TESTS PASSED ===")
