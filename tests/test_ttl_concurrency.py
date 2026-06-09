"""Test cases for TTLCache concurrency bugs and thread safety."""

import threading
import time
import unittest

from cachetools import TTLCache


class TTLCacheConcurrencyTest(unittest.TestCase):
    """Test concurrent access to TTLCache for race conditions."""

    def test_concurrent_read_write_expired_key_raises_keyerror(self):
        """
        复现并发 Bug: 高并发读写场景下，过期项应该正确返回 KeyError。
        
        场景:
        - 多个线程同时写入新数据
        - 多个线程同时读取数据
        - 数据过期后，读取应该返回 KeyError
        """
        cache = TTLCache(maxsize=100, ttl=0.05)  # 50ms TTL
        errors = []
        success_count = [0]
        keyerror_count = [0]

        def writer(thread_id):
            """写入线程：不断写入数据"""
            try:
                for i in range(100):
                    key = f"key_{thread_id}_{i}"
                    cache[key] = f"value_{thread_id}_{i}"
            except Exception as e:
                errors.append(f"Writer {thread_id} error: {e}")

        def reader(thread_id):
            """读取线程：不断读取数据，验证过期行为"""
            try:
                for i in range(100):
                    key = f"key_{thread_id}_{i}"
                    try:
                        value = cache[key]
                        success_count[0] += 1
                    except KeyError:
                        keyerror_count[0] += 1
            except Exception as e:
                errors.append(f"Reader {thread_id} error: {e}")

        threads = []
        
        # 启动写入线程
        for i in range(5):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
        
        # 启动读取线程
        for i in range(5):
            t = threading.Thread(target=reader, args=(i,))
            threads.append(t)

        # 启动所有线程
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=10)

        # 验证没有异常
        self.assertEqual([], errors, "Concurrent access caused errors")
        
        # 验证有 KeyError 出现（说明过期项被正确识别）
        self.assertGreater(keyerror_count[0], 0, 
                          "Expected some KeyError for expired items")

    def test_concurrent_access_no_data_corruption(self):
        """
        验证高并发下不会出现数据损坏。
        
        场景:
        - 多个线程同时读写同一个 key
        - 不应该出现数据损坏或异常
        """
        cache = TTLCache(maxsize=10, ttl=1.0)
        errors = []
        write_count = [0]
        read_count = [0]

        def worker(thread_id):
            try:
                for i in range(50):
                    key = f"shared_key_{i % 5}"
                    # 写入
                    cache[key] = f"value_{thread_id}_{i}"
                    write_count[0] += 1
                    # 读取
                    try:
                        value = cache[key]
                        read_count[0] += 1
                    except KeyError:
                        pass  # 过期是正常的
            except Exception as e:
                errors.append(f"Worker {thread_id} error: {e}")

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        # 验证没有异常
        self.assertEqual([], errors, "Concurrent access caused data corruption")
        self.assertGreater(write_count[0], 0)
        self.assertGreater(read_count[0], 0)

    def test_expired_item_cleaned_up_under_concurrent_read(self):
        """
        验证只有读操作时，过期项也能被正确清理。
        
        Bug 场景:
        - 写入一个 item
        - 等待过期
        - 只有读操作（没有新的写入）
        - 读取应该返回 KeyError
        """
        cache = TTLCache(maxsize=10, ttl=0.01)  # 10ms TTL
        errors = []
        keyerror_count = [0]

        # 写入数据
        cache["test_key"] = "test_value"
        
        # 等待过期
        time.sleep(0.02)

        def reader():
            try:
                for _ in range(100):
                    try:
                        cache["test_key"]
                    except KeyError:
                        keyerror_count[0] += 1
            except Exception as e:
                errors.append(f"Reader error: {e}")

        threads = []
        for i in range(10):
            t = threading.Thread(target=reader)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        # 验证没有异常
        self.assertEqual([], errors, "Read-only concurrent access caused errors")
        
        # 所有读取都应该返回 KeyError（因为已过期）
        self.assertGreater(keyerror_count[0], 0,
                          "Expired items should return KeyError under concurrent reads")

    def test_concurrent_expire_cleanup(self):
        """
        验证 expire 方法在并发调用时不会出现问题。
        """
        cache = TTLCache(maxsize=100, ttl=0.01)
        errors = []
        expired_counts = []

        # 写入大量数据
        for i in range(50):
            cache[f"key_{i}"] = f"value_{i}"

        # 等待过期
        time.sleep(0.02)

        def expire_worker():
            try:
                for _ in range(10):
                    expired = cache.expire()
                    expired_counts.append(len(expired))
            except Exception as e:
                errors.append(f"Expire worker error: {e}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=expire_worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        # 验证没有异常
        self.assertEqual([], errors, "Concurrent expire caused errors")

    def test_high_contention_scenario(self):
        """
        高竞争场景：大量线程同时访问少量 key。
        
        这是最容易暴露竞态条件的场景。
        """
        cache = TTLCache(maxsize=5, ttl=0.05)
        errors = []
        operations = [0]
        lock = threading.Lock()

        def high_contention_worker(thread_id):
            try:
                for i in range(100):
                    key = f"hot_key_{i % 3}"  # 只有 3 个 key，高竞争
                    try:
                        cache[key] = f"value_{thread_id}_{i}"
                        cache[key]  # 立即读取
                        with lock:
                            operations[0] += 1
                    except KeyError:
                        with lock:
                            operations[0] += 1
            except Exception as e:
                errors.append(f"High contention worker {thread_id} error: {e}")

        threads = []
        for i in range(20):
            t = threading.Thread(target=high_contention_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        # 验证没有异常
        self.assertEqual([], errors, "High contention caused errors")
        self.assertGreater(operations[0], 0)


if __name__ == "__main__":
    unittest.main()
