import sys
sys.path.insert(0, '/app/cachetools/src')
import unittest
from tests.test_lfu import LFUCacheTest
suite = unittest.TestLoader().loadTestsFromTestCase(LFUCacheTest)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
