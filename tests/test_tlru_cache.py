import time
import pytest
from cachetools import TLRUCache

def test_tlru_cache_maxsize():
    """测试 maxsize 限制生效，超出时自动淘汰最旧项"""
    # 设置 ttu 较长，确保不会因为超时而被淘汰
    cache = TLRUCache(maxsize=2, ttu=lambda k, v, t: t + 1000)
    
    cache['a'] = 1
    cache['b'] = 2
    assert len(cache) == 2
    assert 'a' in cache
    assert 'b' in cache
    
    # 超出 maxsize，淘汰最旧的 'a'
    cache['c'] = 3
    assert len(cache) == 2
    assert 'a' not in cache
    assert 'b' in cache
    assert 'c' in cache
    
    # 访问 'b'，使其成为最近使用
    _ = cache['b']
    
    # 插入新项，淘汰最旧的 'c'
    cache['d'] = 4
    assert len(cache) == 2
    assert 'c' not in cache
    assert 'b' in cache
    assert 'd' in cache


def test_tlru_cache_ttl_expiration():
    """测试 TTL 过期后条目自动失效（time.sleep 模拟）"""
    # 设置 TTL 为 0.1 秒
    cache = TLRUCache(maxsize=5, ttu=lambda k, v, t: t + 0.1)
    
    cache['a'] = 1
    cache['b'] = 2
    assert len(cache) == 2
    assert 'a' in cache
    assert 'b' in cache
    
    # 等待超过 TTL 时间
    time.sleep(0.15)
    
    # 此时项已经过期
    assert 'a' not in cache
    assert 'b' not in cache
    assert len(cache) == 0


def test_tlru_cache_eviction_priority():
    """测试点淘汰机制：同时触发 TTL 和 maxsize 时优先淘汰到期条目"""
    # 设置 TTL 为 0.1 秒
    cache = TLRUCache(maxsize=2, ttu=lambda k, v, t: t + 0.1)
    
    cache['a'] = 1
    cache['b'] = 2
    assert len(cache) == 2
    
    # 等待超过 TTL 时间
    time.sleep(0.15)
    
    # 插入新项，触发 __setitem__ 
    # 此时因为 a 和 b 已过期，expire() 会先清理掉 a 和 b
    # 而不是通过 popitem (LRU) 淘汰
    cache['c'] = 3
    
    # 清理后，缓存中只剩下新插入的 'c'
    assert len(cache) == 1
    assert 'c' in cache
    assert 'a' not in cache
    assert 'b' not in cache
