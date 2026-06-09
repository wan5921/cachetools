import threading
from cachetools import LRUCache, TTLCache

class SmartCache:
    """
    支持自动切换缓存类型的智能缓存类。
    ttl=None 时使用 LRUCache，否则使用 TTLCache。
    """
    def __init__(self, maxsize, ttl=None, **kwargs):
        self.maxsize = maxsize
        self.ttl = ttl
        self._lock = threading.RLock()
        
        if ttl is None:
            self._cache = LRUCache(maxsize=maxsize, **kwargs)
        else:
            self._cache = TTLCache(maxsize=maxsize, ttl=ttl, **kwargs)

    def get(self, key, default=None):
        with self._lock:
            return self._cache.get(key, default)

    def set(self, key, value):
        with self._lock:
            self._cache[key] = value

    def delete(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def get_or_compute(self, key, compute_func):
        """
        获取缓存值，如果不存在则调用 compute_func 计算并存入缓存。
        通过 RLock 保证并发情况下的线程安全，起到一定的缓存击穿/穿透保护作用。
        即使 compute_func 返回 None 也会被缓存，防止缓存穿透。
        """
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            
            # 缓存未命中，进行计算（回源）
            value = compute_func()
            self._cache[key] = value
            return value

    def cleanup(self):
        """
        手动清理过期项。仅当底层缓存支持 expire 方法（如 TTLCache）时生效。
        """
        with self._lock:
            if hasattr(self._cache, 'expire'):
                self._cache.expire()
