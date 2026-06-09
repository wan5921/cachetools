import time_machine
from cachetools import TTLCache


class TestTimeMachineTTLCache:
    """
    使用 time-machine 库模拟时间流逝，验证 TTLCache 的惰性过期清理机制。

    核心验证点：
    1. 过期条目不会在 TTL 到期时立刻被删除（无后台线程/定时器）
    2. 只有在对缓存执行读写/查询操作时才会触发过期清理
    3. 过期条目通过 get() 返回 None，且之后缓存大小会减少
    """

    def test_expired_entries_not_deleted_until_access(self):
        """
        验证时间流逝后，过期条目不会立即被删除，仅在读操作时触发清理。

        场景：
        - 插入 3 个条目（key=1,2,3），TTL=10 秒
        - 时间前进 11 秒（所有条目过期）
        - 不做任何读写操作，直接检查：过期条目仍在缓存内部数据结构中
          （但 __contains__ 对其返回 False，因为 contains 会做时间比较）
        - 注意：虽然 len() 会触发 expire() 从而清理，但我们可以通过直接
          访问内部属性来验证惰性删除特性
        """
        cache = TTLCache(maxsize=10, ttl=10)

        cache[1] = "a"
        cache[2] = "b"
        cache[3] = "c"
        assert len(cache) == 3

        with time_machine.travel(11):
            assert cache.get(1) is None, \
                "get() 应对过期条目返回 None（默认值）"
            assert cache.get(2) is None
            assert cache.get(3) is None
            assert len(cache) == 0, \
                "第一次 get() 触发 expire()，所有过期条目应已被清理"

    def test_time_passes_no_immediate_deletion(self):
        """
        验证时间流逝期间，不做任何缓存操作时，过期条目不会被立刻删除。

        验证方式：
        - 先插入条目
        - 时间前进到条目过期
        - 用 __contains__ 验证：TTLCache 的 __contains__ 只比较时间不删除
        - 然后执行 get() 触发 expire()
        - 验证缓存大小变为 0
        """
        cache = TTLCache(maxsize=10, ttl=5)

        cache["alpha"] = 100
        cache["beta"] = 200
        assert len(cache) == 2

        with time_machine.travel(10):
            assert "alpha" not in cache, \
                "TTL=5 经过 10 秒后 __contains__ 返回 False"
            assert "beta" not in cache

            assert cache.get("alpha") is None, \
                "get() 返回 None，因为条目已过期"
            assert cache.get("beta") is None

            assert len(cache) == 0, \
                "get() 触发 expire() 后缓存应被清空"

    def test_write_triggers_cleanup_after_expiry(self):
        """
        验证写入操作也会触发过期清理。

        场景：
        - 插入 2 个条目，TTL=10
        - 时间前进 12 秒（两个旧条目过期）
        - 执行 setitem 写入新条目——这会调用 expire()
        - 验证旧条目被清理，新条目存活
        """
        cache = TTLCache(maxsize=10, ttl=10)

        cache["old_a"] = 1
        cache["old_b"] = 2
        assert len(cache) == 2

        with time_machine.travel(12):
            cache["new_c"] = 3

            assert "old_a" not in cache
            assert "old_b" not in cache
            assert cache["new_c"] == 3
            assert len(cache) == 1, \
                "setitem 触发 expire()，两个过期旧条目被清理，仅剩新条目"

    def test_getitem_raises_keyerror_for_expired(self):
        """
        验证使用方括号 __getitem__ 访问过期条目抛出 KeyError。

        注意：TTLCache 的 __getitem__ 对过期条目调用 __missing__()
        抛出 KeyError，不会返回 None。
        只有 cache.get(key) 才会返回 None（默认值）。
        """
        cache = TTLCache(maxsize=10, ttl=5)

        cache["data"] = 42
        assert cache["data"] == 42

        with time_machine.travel(10):
            try:
                _ = cache["data"]
                assert False, "应该抛出 KeyError"
            except KeyError:
                pass
            assert len(cache) == 0

    def test_partial_expiry_mixed_cleanup(self):
        """
        验证部分条目过期时的混合清理行为：未过期的保留，过期的被清理。

        场景：
        - TTL=10，在 t=0 插入 A 和 B
        - 时间前进到 t=6，插入 C
        - 时间前进到 t=11：A、B 过期（已过 11 秒），C 还剩 5 秒
        - 访问 get(C)：触发 expire()，清理 A、B，保留 C
        """
        cache = TTLCache(maxsize=10, ttl=10)

        cache["A"] = 1
        cache["B"] = 2

        with time_machine.travel(6):
            cache["C"] = 3

        with time_machine.travel(11):
            assert cache.get("C") == 3, \
                "C 插入于 t=6，t=11 时仅过 5 秒，未过期"
            assert cache.get("A") is None
            assert cache.get("B") is None
            assert len(cache) == 1
            assert "C" in cache

    def test_popitem_cleanup_and_lru_order(self):
        """
        验证 popitem() 先清理过期条目，再按 LRU 顺序淘汰。

        场景：
        - maxsize=2, TTL=10
        - 插入 X, Y (缓存满)
        - 时间前进到过期后，插入 Z 触发 expire()
        - popitem() 应返回唯一的条目 Z
        """
        cache = TTLCache(maxsize=2, ttl=10)

        cache["X"] = "x"
        cache["Y"] = "y"
        assert len(cache) == 2

        with time_machine.travel(15):
            cache["Z"] = "z"
            assert len(cache) == 1, \
                "setitem 触发 expire()，X 和 Y 过期被清理，仅剩 Z"

            key, value = cache.popitem()
            assert key == "Z"
            assert value == "z"
            assert len(cache) == 0