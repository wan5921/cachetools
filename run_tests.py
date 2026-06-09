import sys
import unittest

sys.path.insert(0, "src")
loader = unittest.TestLoader()
suite = loader.loadTestsFromName("tests.test_smart_cache")
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
