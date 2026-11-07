"""The SDK test suite.  Python 3.10 compatibility: ``unittest.TestCase.enterContext`` arrived in Python 3.11."""

import unittest

if not hasattr(unittest.TestCase, "enterContext"):  # pragma: no cover - Python 3.10 only

    def _enter_context(self, context_manager):
        result = type(context_manager).__enter__(context_manager)
        self.addCleanup(type(context_manager).__exit__, context_manager, None, None, None)
        return result

    unittest.TestCase.enterContext = _enter_context
