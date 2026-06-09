import unittest

try:
    import time_machine
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("time-machine not installed")

import time

# time-machine 默认 patch time.time / datetime.now；TTLCache 默认 timer 是
# time.monotonic，该 timer 不会被 time-machine 影响，因此我们改用 time.time
# 作为可被 time-machine 控制的时间源。
from cachetools import TTLCache

_TIMER = time.time


class NoneOnMissingTTLCache(TTLCache):
    """TTLCache 的一个子类：对已过期或不存在的键，__getitem__ 返回 None 而不是抛 KeyError。"""

    def __missing__(self, key):
        return None


class TTLCacheTimeMachineTest(unittest.TestCase):
    """使用 time-machine 验证 TTLCache 的惰性过期清理行为。"""

    # ------------------------------------------------------------------
    # 测试 1：默认 TTLCache 对过期键抛 KeyError，
    #         且过期条目不会立即被删除，需要读写操作触发 expire
    # ------------------------------------------------------------------
    def test_default_ttlcache_raises_keyerror_on_expired(self):
        with time_machine.travel(0.0, tick=False) as traveller:
            cache: TTLCache[int, int] = TTLCache(maxsize=10, ttl=5.0, timer=_TIMER)

            cache[1] = 100
            cache[2] = 200
            cache[3] = 300
            self.assertEqual(len(cache), 3)

            # 时间推进到 t=6，让所有条目过期
            traveller.move_to(6.0)

            # 1) __getitem__ 对过期键抛 KeyError —— 此时 *未* 清理数据结构
            with self.assertRaises(KeyError):
                cache[1]
            with self.assertRaises(KeyError):
                cache[2]

            # 2) 物理条目此时仍在缓存里。
            #    触发清理的操作（例如 len() / currsize / __setitem__ 等）
            #    会调用 expire() 才真正删除。
            self.assertEqual(len(cache), 0)  # len() 内部调用 expire()，结果为 0

    # ------------------------------------------------------------------
    # 测试 2：使用返回 None 的子类 —— 直接断言 __getitem__ 返回 None
    #         并且在下一次触发清理的操作后缓存大小减少
    # ------------------------------------------------------------------
    def test_getitem_returns_none_then_size_reduces(self):
        with time_machine.travel(0.0, tick=False) as traveller:
            cache: NoneOnMissingTTLCache[int, int] = NoneOnMissingTTLCache(
                maxsize=10, ttl=5.0, timer=_TIMER
            )

            cache[1] = 100
            cache[2] = 200
            cache[3] = 300
            initial_len = len(cache)
            self.assertEqual(initial_len, 3)

            # 推进时间让 1、2 过期，让 3 仍然存活
            traveller.move_to(3.0)
            cache[3] = 301  # 刷新 3 的 expires = 3.0 + 5.0 = 8.0
            traveller.move_to(6.0)  # 1、2 在 t=5.0 过期；3 到 t=8.0 才过期

            # 1) 断言 __getitem__ 对过期键返回 None
            self.assertIsNone(cache[1], "已过期键 1 应返回 None")
            self.assertIsNone(cache[2], "已过期键 2 应返回 None")

            # 2) 对未过期键 3 仍可读取
            self.assertEqual(cache[3], 301)

            # 3) 在 __getitem__ 返回 None 之后，下一次触发清理的操作
            #    （这里用 len()，它会调用 expire()）应当让缓存大小减少
            size_after_getitem_none = len(cache)
            self.assertEqual(
                size_after_getitem_none,
                1,
                "触发清理后 1、2 应被删除，只剩 3",
            )

            # 4) 进一步：推进时间让 3 也过期，再次验证
            traveller.move_to(10.0)
            self.assertIsNone(cache[3], "已过期键 3 应返回 None")
            self.assertEqual(len(cache), 0, "全部过期后大小应为 0")

    # ------------------------------------------------------------------
    # 测试 3：写入操作触发清理
    # ------------------------------------------------------------------
    def test_write_triggers_cleanup(self):
        with time_machine.travel(100.0, tick=False) as traveller:
            cache: TTLCache[int, int] = TTLCache(maxsize=2, ttl=1.0, timer=_TIMER)

            cache[1] = 1
            cache[2] = 2

            # 让所有条目过期
            traveller.move_to(105.0)

            # 写入新条目：__setitem__ 会先调用 expire() 清理 1、2，再放 3
            cache[3] = 3
            self.assertEqual(len(cache), 1)
            self.assertEqual(cache[3], 3)

    # ------------------------------------------------------------------
    # 测试 4：popitem() 的 TTL 策略 —— 先清理过期，再按 LRU 返回
    # ------------------------------------------------------------------
    def test_popitem_expires_first(self):
        with time_machine.travel(0.0, tick=False) as traveller:
            cache: TTLCache[int, int] = TTLCache(maxsize=5, ttl=2.0, timer=_TIMER)

            cache[1] = 1  # expires at 2.0
            traveller.move_to(1.0)
            cache[2] = 2  # expires at 3.0
            cache[3] = 3  # expires at 3.0
            traveller.move_to(2.5)  # 1 已过期；2、3 未过期

            # popitem 应先 expire() 清理 1，再按 LRU 返回 (2, 2)
            key, value = cache.popitem()
            self.assertEqual((key, value), (2, 2))
            self.assertEqual(len(cache), 1)


if __name__ == "__main__":
    unittest.main()
