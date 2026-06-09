import unittest
from unittest.mock import Mock
import time
from smart_cache import SmartCache

class TestSmartCache(unittest.TestCase):
    def test_cache_type_switching(self):
        # ttl=None 应该使用 LRUCache
        cache_lru = SmartCache(maxsize=10, ttl=None)
        self.assertEqual(cache_lru._cache.__class__.__name__, 'LRUCache')

        # ttl 存在应该使用 TTLCache
        cache_ttl = SmartCache(maxsize=10, ttl=5)
        self.assertEqual(cache_ttl._cache.__class__.__name__, 'TTLCache')

    def test_get_or_compute_hit_and_miss(self):
        cache = SmartCache(maxsize=10)
        
        # 使用 mock 模拟耗时计算
        mock_compute = Mock(return_value="computed_value")
        
        # 第一次获取，缓存未命中，应该调用 compute_func
        val1 = cache.get_or_compute("key1", mock_compute)
        self.assertEqual(val1, "computed_value")
        mock_compute.assert_called_once()
        
        # 第二次获取，缓存命中，不应该再次调用 compute_func
        val2 = cache.get_or_compute("key1", mock_compute)
        self.assertEqual(val2, "computed_value")
        self.assertEqual(mock_compute.call_count, 1)

    def test_cleanup(self):
        # 设置很短的 ttl 方便测试过期
        cache = SmartCache(maxsize=10, ttl=0.1)
        
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # 等待缓存过期
        time.sleep(0.2)
        
        # 调用 cleanup 前，底层字典中可能还存有数据（TTLCache 只有在访问或其他操作时才清理）
        # 手动清理
        cache.cleanup()
        
        # 验证是否已清理 (在 TTLCache 的实现中，过期项会被清除)
        # 尝试直接访问底层数据结构来验证清理效果
        if hasattr(cache._cache, '_TTLCache__links'):
            # cachetools TTLCache 内部维护的数据结构
            self.assertEqual(len(cache._cache), 0)
        
        self.assertIsNone(cache.get("key1"))

if __name__ == '__main__':
    unittest.main()
