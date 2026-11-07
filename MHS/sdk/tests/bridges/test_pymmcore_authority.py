"""Construction and method authority is retained, including in-place mutation."""
import unittest

from tests.bridges import test_pymmcore_camera as camera_tests
from tests.bridges.pymmcore_fixture import CameraCore, CameraManager, CameraScenario


class CameraAuthorityTests(unittest.TestCase):
    make = camera_tests.CameraLifecycleTests.make
    context = camera_tests.CameraLifecycleTests.context
    capture = camera_tests.CameraLifecycleTests.capture
    settle = camera_tests.CameraLifecycleTests.settle

    def test_profile_mutation_is_refused_before_construction(self):
        scenario, bridge, store = self.make()
        object.__setattr__(bridge.profile, "exposure_max_ms", 101)
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(scenario.trace, [])

    def test_factory_mutation_is_refused_before_construction(self):
        scenario, bridge, store = self.make()
        calls = []
        def replacement(lease):
            calls.append(lease)
            return scenario.create(lease)
        object.__setattr__(bridge.factory, "create", replacement)
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(calls, [])
        self.assertEqual(scenario.trace, [])

    def test_retained_factory_function_code_change_is_refused(self):
        scenario, bridge, store = self.make()
        function = CameraScenario.create
        before = function.__code__
        def replacement(self, lease):
            self.hit("replacement_factory")
            raise RuntimeError("changed construction body")
        try:
            function.__code__ = replacement.__code__
            with self.assertRaises(Exception):
                self.capture(bridge, store)
            self.assertEqual(scenario.trace, [])
        finally:
            function.__code__ = before

    def test_receiver_method_code_defaults_and_dynamic_lookup_are_refused(self):
        for kind in ("code", "defaults", "lookup"):
            with self.subTest(kind=kind):
                scenario, bridge, store = self.make()
                self.capture(bridge, store)
                old_code = CameraManager.acquireSingleFrame.__code__
                old_defaults = CameraManager.acquireSingleFrame.__defaults__
                def replacement(self, cancelEvent=None, timeout=None, pollInterval=.05):
                    self._core.scenario.hit("replacement_acquisition")
                    return self._core.scenario.frame, "done"
                try:
                    if kind == "code":
                        CameraManager.acquireSingleFrame.__code__ = replacement.__code__
                    elif kind == "defaults":
                        CameraManager.acquireSingleFrame.__defaults__ = (None, None, .1)
                    else:
                        CameraCore.__getattr__ = lambda self, name: None
                    with self.assertRaises(Exception):
                        self.capture(bridge, store)
                    self.assertEqual(scenario.counts("start"), 1)
                    self.assertEqual(scenario.counts("replacement_acquisition"), 0)
                finally:
                    CameraManager.acquireSingleFrame.__code__ = old_code
                    CameraManager.acquireSingleFrame.__defaults__ = old_defaults
                    if kind == "lookup":
                        del CameraCore.__getattr__

    def test_constructor_failure_before_any_handle_remains_incomplete(self):
        scenario, bridge, store = self.make()
        def fail():
            raise RuntimeError("failure before a core handle is returned")
        scenario.hooks["core_creation"] = fail
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        bridge.close()
        self.assertIsNone(bridge.lease.core)
        self.assertFalse(bridge.safety_status()["closed"])
        self.assertTrue(bridge.safety_status()["reconciliation_needed"])
        self.assertEqual(scenario.counts("start"), 0)
        self.assertEqual(scenario.counts("unload"), 0)


if __name__ == "__main__":
    unittest.main()
