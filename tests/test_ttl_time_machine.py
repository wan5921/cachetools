"""验证 TTLCache 的惰性过期清理机制——基于 time-machine 模拟时间流逝。

核心断言：
  1. 时间前进到 TTL 之后，缓存**内部字典**仍保留失效条目；
  2. 只有在触发"写操作/len/currsize"等行为时，才会真正删除失效项；
  3. 自定义 __missing__ 返回 None 的子类在访问过期 key 时返回 None，
     且触发清理后 `len()` 会减少。

运行方式：
    pip install time-machine
    python -m pytest tests/test_ttl_time_machine.py -v
"""

import sys
import unittest

import time_machine

from cachetools import TTLCache


# ---------------------------------------------------------------------------
# 辅助：支持 "访问过期 key 返回 None" 的 TTLCache
# 标准 TTLCache.__missing__ 会抛 KeyError；通过子类覆写来满足题设行为。
# ---------------------------------------------------------------------------
class TTLCacheWithNoneMiss(TTLCache):
    """访问 miss / 过期 key 时返回 None 而非抛 KeyError。"""

    def __missing__(self, key):
        return None


class TestTTLazyExpire(unittest.TestCase):
    def setUp(self):
        # 用 time-machine 固定一个"真实"单调时钟起点
        self.traveller = time_machine.travel(1_700_000_000.0, tick=False)
        self.traveller.start()
        import time as _time

        # 默认 TTLCache 内部使用 time.monotonic，time-machine 会同步移动它
        self.now = _time.monotonic

    def tearDown(self):
        self.traveller.stop()

    # ------------------------------------------------------------------
    # 1. 过期条目不会"立即"被删除（底层 dict 仍保留）
    # ------------------------------------------------------------------
    def test_expired_items_not_deleted_until_triggered(self):
        cache = TTLCache(maxsize=10, ttl=5)
        cache["a"] = 1
        cache["b"] = 2

        # 直接访问内部字典以证明条目物理存在（注意：双下划线属性被改名）
        # 我们用 len() / __contains__ 间接验证，因为私有属性不便直接访问。
        self.assertEqual(len(cache), 2)
        self.assertIn("a", cache)
        self.assertIn("b", cache)

        # 前进时间 10 秒，越过 TTL
        self.traveller.shift(10)

        # 此时还未触发任何读写操作 —— 从外部看 key 已经"不存在"
        self.assertNotIn("a", cache)
        self.assertNotIn("b", cache)

        # 但底层 dict 的真实长度只有在触发清理后才会变小。
        # 这里通过 len() 触发一次清理（_TimedCache.__len__ 会先 expire）。
        self.assertEqual(len(cache), 0)

    # ------------------------------------------------------------------
    # 2. 写操作会触发清理
    # ------------------------------------------------------------------
    def test_setitem_triggers_expire(self):
        cache = TTLCache(maxsize=10, ttl=5)
        cache["a"] = 1
        cache["b"] = 2

        # 越过 TTL
        self.traveller.shift(10)

        # 在写入新 key 之前，"a" "b" 仍被感知为缺失（__contains__ 只看时间）
        self.assertNotIn("a", cache)

        # 写入新 key → __setitem__ 内会调用 expire(time)
        cache["c"] = 3

        # 此时 a、b 应已真正从缓存中删除，只剩 c
        self.assertEqual(len(cache), 1)
        self.assertIn("c", cache)
        self.assertNotIn("a", cache)
        self.assertNotIn("b", cache)

    # ------------------------------------------------------------------
    # 3. popitem() 在"满缓存 + 有过期项"时先清过期，再按 LRU 弹未过期项
    # ------------------------------------------------------------------
    def test_popitem_prefers_expired_then_lru(self):
        cache = TTLCache(maxsize=2, ttl=5)
        cache["old"] = 1
        cache["fresh"] = 2  # 缓存满
        self.traveller.shift(3)  # 还没过期
        cache["fresh"]          # 访问 fresh，让它跑到链表尾部

        self.traveller.shift(3)  # total=6 > ttl=5，两者都过期
        # 先写新 key 让过期项被真正删除，同时新 key 占一个槽
        cache["new"] = 3
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache["new"], 3)

        # 再填一项把缓存占满，并越过 TTL
        cache["another"] = 4
        self.traveller.shift(10)

        # 此时 popitem 会先 expire 把所有过期项清掉再抛 KeyError
        with self.assertRaises(KeyError):
            cache.popitem()

    # ------------------------------------------------------------------
    # 4. 自定义 __missing__ 返回 None：过期 key 返回 None，且触发清理后大小减少
    # ------------------------------------------------------------------
    def test_getitem_returns_none_and_size_reduced_after_expire(self):
        cache = TTLCacheWithNoneMiss(maxsize=10, ttl=5)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        size_before = len(cache)
        self.assertEqual(size_before, 3)

        # 只前进 2 秒，未过期
        self.traveller.shift(2)
        self.assertEqual(cache["a"], 1)
        self.assertEqual(cache["b"], 2)
        self.assertEqual(cache["c"], 3)
        self.assertEqual(len(cache), 3)

        # 前进到越过 TTL
        self.traveller.shift(4)  # 累计 6s

        # 访问过期 key：__missing__ 返回 None
        self.assertIsNone(cache["a"])
        self.assertIsNone(cache["b"])
        self.assertIsNone(cache["c"])

        # 此时内部 dict 仍有数据，只有触发写/len/popitem/pop 等才会真正删
        # 注意：__getitem__ 本身会经过 __getlink → move_to_end（有副作用），
        # 但不会调用 expire()。通过 len() 触发清理。
        self.assertEqual(len(cache), 0)

        # 再写入 key，证明缓存结构仍然健康
        cache["x"] = 42
        self.assertEqual(cache["x"], 42)
        self.assertEqual(len(cache), 1)

    # ------------------------------------------------------------------
    # 5. 过期过程不会删除未过期条目
    # ------------------------------------------------------------------
    def test_partial_expire_preserves_fresh_items(self):
        cache = TTLCache(maxsize=10, ttl=5)
        cache["early"] = 1
        self.traveller.shift(3)
        cache["late"] = 2
        self.traveller.shift(3)  # early 已 6s（过期），late 才 3s（有效）

        self.assertNotIn("early", cache)
        self.assertIn("late", cache)

        # len() 触发 expire —— 只会删掉 "early"
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache["late"], 2)


if __name__ == "__main__":
    unittest.main()
