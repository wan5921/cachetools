import time
from cachetools import TTLCache

class Timer:
    def __init__(self):
        self.time = 0
    def __call__(self):
        return self.time

timer = Timer()
cache = TTLCache(maxsize=10, ttl=10, timer=timer)
cache["a"] = 1
print("Internal size after set:", len(cache.__dict__["_Cache__data"]))

timer.time = 15
print("Value from get():", cache.get("a"))
try:
    cache["a"]
except KeyError:
    print("__getitem__ raised KeyError")
print("Internal size after get:", len(cache.__dict__["_Cache__data"]))

cache["b"] = 2
print("Internal size after write:", len(cache.__dict__["_Cache__data"]))

timer.time = 30
print("Value from get():", cache.get("b"))
print("Internal size after get:", len(cache.__dict__["_Cache__data"]))
print("Len() result:", len(cache))
print("Internal size after len():", len(cache.__dict__["_Cache__data"]))
