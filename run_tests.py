import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
import unittest
from tests.test_ttl import TTLCacheTest
from tests.test_ttl_threading import TTLThreadingTest

loader = unittest.TestLoader()
suite = unittest.TestSuite()
suite.addTests(loader.loadTestsFromTestCase(TTLCacheTest))
suite.addTests(loader.loadTestsFromTestCase(TTLThreadingTest))
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
