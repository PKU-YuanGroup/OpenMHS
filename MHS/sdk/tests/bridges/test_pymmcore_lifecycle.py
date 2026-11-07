"""Adversarial startup, reset and cleanup scheduling for the finite camera helper."""
import threading
import time
import unittest
from unittest.mock import patch

from mhs import signals
from mhs.bridge.pymmcore_camera import PymmcoreCameraBridge
from tests.bridges import test_pymmcore_camera as camera_tests


class CameraOwnerBoundaryTests(unittest.TestCase):
    make = camera_tests.CameraLifecycleTests.make
    context = camera_tests.CameraLifecycleTests.context
    capture = camera_tests.CameraLifecycleTests.capture
    worker = camera_tests.CameraLifecycleTests.worker
    hold = camera_tests.CameraLifecycleTests.hold
    joined = camera_tests.CameraLifecycleTests.joined
    settle = camera_tests.CameraLifecycleTests.settle

    def test_timeout_attempts_protective_stop_and_retains_late_acquisition(self):
        scenario, bridge, store = self.make()
        entered, release = self.hold(scenario, "start")
        owner, result = self.worker(lambda: self.capture(bridge, store, deadline_ms=30))
        self.assertTrue(entered.wait(1))
        self.joined(owner)
        self.assertIn("error", result)
        retained = bridge._jobs["acquisition"]
        try:
            self.assertIn(("stop", "Camera"), scenario.trace)
            self.assertIsNotNone(bridge._claim)
            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
            with self.assertRaises(Exception):
                bridge.reset()
            with self.assertRaises(Exception):
                self.capture(bridge, store)
            self.assertIs(bridge._jobs["acquisition"], retained)
        finally:
            release.set()
            self.assertTrue(retained.done.wait(1))
        self.settle(bridge)
        before = scenario.trace.count(("stop", "Camera"))
        bridge.safe_state()
        self.assertGreater(scenario.trace.count(("stop", "Camera")), before)
        bridge.reset()
        self.assertEqual(scenario.counts("start"), 1)
        self.assertEqual(store._grants, {})

    def test_preflight_refusal_does_not_preempt_a_native_sequence(self):
        for kind in ("foreign_live", "wrong_geometry"):
            with self.subTest(kind=kind):
                scenario, bridge, store = self.make()
                if kind == "foreign_live":
                    scenario.hooks["manager_constructed"] = lambda: setattr(scenario.core, "running", True)
                with self.assertRaises(Exception):
                    self.capture(bridge, store, {"width": 4} if kind == "wrong_geometry" else {})
                self.assertEqual(scenario.counts("start"), 0)
                self.assertEqual(scenario.counts("stop"), 0)

    def test_final_stop_timeout_retains_exclusive_claim_until_stop_settles(self):
        scenario, bridge, store = self.make()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def hold_labelled_stop(label=None):
            if label == "Camera":
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("labelled stop barrier")
        scenario.hooks["stop"] = hold_labelled_stop
        owner, result = self.worker(lambda: self.capture(bridge, store, deadline_ms=40))
        self.assertTrue(entered.wait(1))
        self.joined(owner)
        self.assertIn("error", result)
        retained = bridge._jobs["stop"]
        try:
            self.assertIsNotNone(bridge._claim)
            self.assertEqual(scenario.manager._exclusiveOwner, bridge._claim)
            self.assertEqual(scenario.counts("release"), 0)
            with self.assertRaises(Exception):
                self.capture(bridge, store)
        finally:
            release.set()
            self.assertTrue(retained.done.wait(1))
        self.settle(bridge)
        self.assertEqual(bridge.safe_state(), {"achieved": True})
        self.assertIsNone(bridge._claim)
        self.assertEqual(scenario.counts("release"), 1)
        self.assertEqual(store._grants, {})
        bridge.reset()
        self.assertEqual(scenario.counts("start"), 1)

    def test_new_estop_generation_wins_over_pending_reset_observation(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        bridge.estop()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def hold_reset(*_):
            if threading.current_thread().name == "mhs-native-reset_observation":
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("reset observation barrier")
        scenario.hooks["running"] = hold_reset
        owner, result = self.worker(bridge.reset)
        self.assertTrue(entered.wait(1))
        try:
            with self.assertRaises(Exception):
                bridge.estop("new generation")
        finally:
            release.set()
            self.joined(owner)
        self.assertIn("error", result)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        bridge.safe_state()
        bridge.reset()
        self.assertEqual(scenario.counts("start"), 1)

    def test_terminal_history_rollover_keeps_admission_and_sticky_fault(self):
        scenario, bridge, store = self.make()
        for _ in range(70):
            self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 70)
        self.assertEqual(len(bridge._history), 64)
        self.assertEqual(bridge.safety_status()["pending_native"], [])
        def fail(*_):
            raise RuntimeError("sticky terminal stop fault")
        scenario.hooks["stop"] = fail
        with self.assertRaises(Exception):
            bridge.estop()
        scenario.hooks.pop("stop")
        for _ in range(70):
            with self.assertRaises(Exception):
                bridge.safe_state()
        self.assertEqual(len(bridge._history), 64)
        self.assertTrue(bridge.safety_status()["fault"])
        with self.assertRaises(Exception):
            bridge.reset()
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 70)

    def test_returned_manager_survives_failed_method_proof(self):
        scenario, bridge, store = self.make()
        scenario.hooks["manager_constructed"] = lambda: setattr(scenario.manager, "crop", lambda *args: None)
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertTrue(any(value is scenario.manager for value in bridge.lease.unresolved_values))
        self.assertIs(bridge.lease.core, scenario.core)
        bridge.close()
        self.assertFalse(bridge.safety_status()["closed"])
        self.assertEqual(scenario.counts("unload"), 0)
        self.assertEqual(scenario.counts("start"), 0)

    def test_failed_start_before_native_thread_has_no_permanent_native_owner(self):
        scenario, bridge, store = self.make()
        original = threading.Thread.start
        def fail(thread):
            if thread.name == "mhs-native-construction":
                raise RuntimeError("controlled failure before thread creation")
            return original(thread)
        with patch.object(threading.Thread, "start", fail):
            with self.assertRaises(Exception):
                self.capture(bridge, store)
        self.assertEqual(scenario.trace, [])
        self.assertEqual(bridge.safety_status()["pending_native"], [])
        self.assertIsNone(bridge.safety_status()["request_owner"])
        bridge.close()
        self.assertTrue(bridge.safety_status()["closed"])
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(scenario.trace, [])

    def test_failure_after_real_start_cannot_authorize_construction(self):
        scenario, bridge, store = self.make()
        original = threading.Thread.start
        construction_entered = threading.Event()
        scenario.hooks["core_creation"] = construction_entered.set
        handles = []
        def fail(thread):
            if thread.name == "mhs-native-construction":
                handles.append(thread)
                original(thread)
                construction_entered.wait(.05)
                raise RuntimeError("controlled injected failure after real start")
            return original(thread)
        with patch.object(threading.Thread, "start", fail):
            with self.assertRaises(Exception):
                self.capture(bridge, store)
        for handle in handles:
            handle.join(1)
            self.assertFalse(handle.is_alive())
        self.assertEqual(scenario.trace, [], "startup return is required before factory entry")
        self.settle(bridge)
        bridge.close()
        self.assertTrue(bridge.safety_status()["closed"])

    def test_delayed_start_does_not_hold_close_and_cannot_enter_factory_late(self):
        scenario, bridge, store = self.make()
        original = threading.Thread.start
        published, release = threading.Event(), threading.Event()
        handles = []
        def delayed(thread):
            if thread.name == "mhs-native-construction":
                handles.append(thread)
                published.set()
                if not release.wait(2):
                    raise TimeoutError("controlled startup release missing")
            return original(thread)
        with patch.object(threading.Thread, "start", delayed):
            owner, result = self.worker(lambda: self.capture(bridge, store))
            self.assertTrue(published.wait(1))
            closer, close_result = self.worker(bridge.close)
            try:
                closer.join(.3)
                bounded = not closer.is_alive()
            finally:
                release.set()
                owner.join(1)
                closer.join(1)
        self.assertTrue(bounded, "close must not wait for the startup lock")
        self.assertFalse(owner.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertNotIn("error", close_result)
        self.assertIn("error", result)
        self.settle(bridge)
        for handle in handles:
            handle.join(1)
            self.assertFalse(handle.is_alive())
        self.assertEqual(scenario.trace, [])
        self.assertTrue(bridge.safety_status()["closed"])
        bridge.close()

    def test_pending_start_blocks_second_owner_without_holding_bookkeeping_lock(self):
        scenario, bridge, store = self.make()
        original = threading.Thread.start
        published, release = threading.Event(), threading.Event()
        def delayed(thread):
            if thread.name == "mhs-native-construction":
                published.set()
                if not release.wait(2):
                    raise TimeoutError("controlled startup release missing")
            return original(thread)
        with patch.object(threading.Thread, "start", delayed):
            owner, result = self.worker(lambda: self.capture(bridge, store))
            self.assertTrue(published.wait(1))
            second, second_result = self.worker(lambda: self.capture(bridge, store))
            try:
                second.join(.3)
                bounded = not second.is_alive()
            finally:
                release.set()
                owner.join(1)
                second.join(1)
        self.assertTrue(bounded)
        self.assertIsInstance(second_result.get("error"), signals.Busy)
        self.assertIn("value", result)
        self.assertEqual(scenario.counts("core_creation"), 1)
        self.assertEqual(scenario.counts("start"), 1)

    def test_reset_reserves_authority_through_final_readback_reconciliation(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        bridge.safe_state()
        reconciled, release = threading.Event(), threading.Event()
        original = PymmcoreCameraBridge._run
        def hold_after_real_observation(receiver, kind, *args, **kwargs):
            result = original(receiver, kind, *args, **kwargs)
            if receiver is bridge and kind == "reset_observation":
                reconciled.set()
                if not release.wait(2):
                    raise TimeoutError("controlled reconciliation release missing")
            return result
        with patch.object(PymmcoreCameraBridge, "_run", hold_after_real_observation):
            resetter, result = self.worker(bridge.reset)
            self.assertTrue(reconciled.wait(1))
            before = list(scenario.trace)
            second_error = None
            try:
                self.capture(bridge, store)
            except BaseException as exc:
                second_error = exc
            finally:
                release.set()
                self.joined(resetter)
        self.assertIsInstance(second_error, signals.Busy)
        self.assertEqual(scenario.trace, before)
        self.assertEqual(result.get("value"), {"reset": True, "resumed": False})
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 2)

    def test_settled_cleanup_failure_can_retry_only_owned_cleanup(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        def fail(*args):
            raise RuntimeError("controlled unload failure before effect")
        scenario.hooks["unload"] = fail
        bridge.close()
        self.settle(bridge)
        self.assertFalse(bridge.safety_status()["closed"])
        self.assertIs(bridge.lease.core, scenario.core)
        self.assertIn("Camera", scenario.core.loaded)
        scenario.hooks.pop("unload")
        bridge.close()
        self.settle(bridge)
        self.assertTrue(bridge.safety_status()["closed"])
        self.assertNotIn("Camera", scenario.core.loaded)
        self.assertEqual(scenario.counts("unload"), 2)
        self.assertEqual(scenario.counts("start"), 1)
        before = list(scenario.trace)
        bridge.close()
        self.assertEqual(scenario.trace, before)
        with self.assertRaises(Exception):
            bridge.reset()


if __name__ == "__main__":
    unittest.main()
