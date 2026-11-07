"""A retained stop observation must postdate every earlier ordinary owner.

Only the controlled peer supplies delays and a swallowed selected-route stop
error. No production bridge method or upstream constructor is replaced.
"""
import threading
import time
import unittest

import numpy as np

from mhs.artifacts import LocalArtifactStore
from mhs.bridge.base import BridgeContext
from mhs.bridge.pymmcore_camera import CameraFactory, PymmcoreCameraBridge
from tests.bridges.pymmcore_fixture import CameraCore, CameraManager, CameraScenario
from tests.bridges import test_pymmcore_camera as camera_tests


class ObservedCore(CameraCore):
    def getROI(self, label):
        self.scenario.hit("roi_after_running", label)
        return CameraCore.getROI(self, label)


class ObservedScenario(CameraScenario):
    def create(self, lease):
        self.hit("core_creation")
        self.core = ObservedCore(self)
        lease.register_core(self.core)
        self.hit("registered")
        self.core.loadDevice(lease.camera, "DemoCamera", "DCam")
        self.core.initializeDevice(lease.camera)
        self.manager = CameraManager(self.core, lease.camera)
        self.hit("manager_constructed")
        return self.manager

    def factory(self):
        return CameraFactory(self.create, ObservedCore, CameraManager)


class CameraStopFreshnessTests(unittest.TestCase):
    context = camera_tests.CameraLifecycleTests.context
    capture = camera_tests.CameraLifecycleTests.capture
    worker = camera_tests.CameraLifecycleTests.worker
    joined = camera_tests.CameraLifecycleTests.joined
    settle = camera_tests.CameraLifecycleTests.settle

    def make(self):
        scenario = ObservedScenario(np.arange(6, dtype="u1").reshape(2, 3))
        bridge = PymmcoreCameraBridge(scenario.profile(stop_timeout_ms=150), scenario.factory())
        store = LocalArtifactStore()
        store.bind("mhs://camera-freshness-tests")
        self.addCleanup(store.close)
        self.addCleanup(bridge.close)
        return scenario, bridge, store

    def barrier(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def wait():
            entered.set()
            if not release.wait(3):
                raise TimeoutError("controlled freshness barrier was not released")
        return entered, release, wait

    def wait_safety(self, bridge):
        until = time.monotonic() + 1
        while time.monotonic() < until:
            with bridge._activity:
                if bridge._safety_requests:
                    return
            time.sleep(.001)
        self.fail("safe-state caller did not enter")

    def stale_stop(self, terminal="done"):
        scenario, bridge, store = self.make()
        scenario.status = terminal
        started, release_start, wait_start = self.barrier()
        observed, release_stop, wait_stop = self.barrier()
        scenario.hooks["start"] = lambda *_: wait_start()
        def hold_observation(*_):
            if threading.current_thread().name == "mhs-native-stop":
                wait_stop()
        def swallow_final_stop(label=None):
            if label is None and threading.current_thread().name == "mhs-native-acquisition":
                raise OSError("selected manager catches its final adapter stop failure")
        scenario.hooks.update(roi_after_running=hold_observation, stop=swallow_final_stop)
        caller, result = self.worker(lambda: self.capture(bridge, store, deadline_ms=30))
        self.assertTrue(started.wait(1))
        self.assertTrue(observed.wait(1))
        self.joined(caller)
        self.assertIn("error", result)
        with bridge._activity:
            acquisition, stop = bridge._jobs["acquisition"], bridge._jobs["stop"]
        release_start.set()
        self.assertTrue(acquisition.done.wait(1))
        status = bridge.safety_status()
        self.assertIsNone(status["request_owner"])
        self.assertEqual(status["pending_native"], ["stop"])
        self.assertTrue(scenario.core.running)
        self.assertIsNotNone(bridge._claim)
        self.assertFalse(stop.done.is_set())
        return scenario, bridge, store, stop, release_stop

    def test_old_stop_cannot_acknowledge_later_success_or_timeout(self):
        for terminal in ("done", "timeout"):
            with self.subTest(terminal=terminal):
                scenario, bridge, store, stop, release = self.stale_stop(terminal)
                before = scenario.trace.count(("stop", "Camera"))
                caller, result = self.worker(bridge.safe_state)
                self.wait_safety(bridge)
                release.set()
                self.joined(caller)
                self.assertIn("error", result)
                self.assertTrue(stop.done.is_set())
                self.assertTrue(scenario.core.running)
                self.assertEqual(scenario.trace.count(("stop", "Camera")), before)
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                self.assertIsNotNone(bridge._claim)
                self.assertEqual(scenario.counts("release"), 0)
                with self.assertRaises(Exception):
                    bridge.reset()
                with self.assertRaises(Exception):
                    self.capture(bridge, store)
                self.assertEqual(bridge.safe_state(), {"achieved": True})
                self.assertEqual(scenario.trace.count(("stop", "Camera")), before + 1)
                self.assertFalse(scenario.core.running)
                self.assertEqual(bridge.reset(), {"reset": True, "resumed": False})
                self.assertEqual(scenario.counts("start"), 1)
                self.assertEqual(store._grants, {})

    def test_late_error_keeps_debt_but_allows_new_protective_stop(self):
        scenario, bridge, store, stop, release = self.stale_stop("error")
        caller, result = self.worker(bridge.safe_state)
        self.wait_safety(bridge)
        release.set()
        self.joined(caller)
        self.assertIn("error", result)
        self.assertTrue(bridge.safety_status()["fault"])
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        before = scenario.trace.count(("stop", "Camera"))
        with self.assertRaises(Exception):
            bridge.safe_state()
        self.assertEqual(scenario.trace.count(("stop", "Camera")), before + 1)
        self.assertFalse(scenario.core.running)
        with self.assertRaises(Exception):
            bridge.reset()
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 1)

    def test_fresh_pending_stop_is_reused_without_replacement(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        observed, release, wait = self.barrier()
        scenario.hooks["roi_after_running"] = lambda *_: wait()
        before = scenario.trace.count(("stop", "Camera"))
        begun = time.monotonic()
        with self.assertRaises(Exception):
            bridge.safe_state(BridgeContext(deadline_ms=25))
        self.assertLess(time.monotonic() - begun, .5)
        self.assertTrue(observed.is_set())
        pending = bridge._jobs["stop"]
        caller, result = self.worker(bridge.safe_state)
        self.wait_safety(bridge)
        self.assertIs(bridge._jobs["stop"], pending)
        release.set()
        self.joined(caller)
        self.assertEqual(result, {"value": {"achieved": True}})
        self.assertEqual(scenario.trace.count(("stop", "Camera")), before + 1)
        self.assertEqual(bridge.reset(), {"reset": True, "resumed": False})
        self.assertEqual(scenario.counts("start"), 1)

    def committing_stop(self):
        scenario, bridge, store, old_stop, release_old = self.stale_stop()
        release_old.set()
        self.assertTrue(old_stop.done.wait(1))
        released, allow_release, wait_release = self.barrier()
        scenario.hooks["release"] = lambda *_: wait_release()
        caller, result = self.worker(bridge.safe_state)
        self.assertTrue(released.wait(1))
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        return scenario, bridge, store, caller, result, allow_release

    def test_new_stop_wins_during_previous_claim_release(self):
        scenario, bridge, store, caller, result, release = self.committing_stop()
        with self.assertRaises(Exception):
            bridge.estop("new safety generation")
        release.set()
        self.joined(caller)
        self.assertIn("error", result)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception):
            bridge.reset()
        self.assertEqual(bridge.safe_state(), {"achieved": True})
        bridge.reset()
        self.assertEqual(scenario.counts("start"), 1)

    def test_close_wins_during_claim_release_without_late_achievement(self):
        scenario, bridge, store, caller, result, release = self.committing_stop()
        begun = time.monotonic()
        bridge.close()
        self.assertLess(time.monotonic() - begun, .5)
        release.set()
        self.joined(caller)
        self.assertIn("error", result)
        self.settle(bridge)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.assertTrue(bridge.safety_status()["closed"])
        self.assertEqual(scenario.counts("start"), 1)
        with self.assertRaises(Exception):
            bridge.reset()

    def test_ordinary_admission_is_reserved_until_safe_commit(self):
        scenario, bridge, store, caller, result, release = self.committing_stop()
        with self.assertRaises(Exception):
            self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 1)
        release.set()
        self.joined(caller)
        self.assertEqual(result, {"value": {"achieved": True}})
        self.assertTrue(bridge.safety_status()["safe_state"]["achieved"])
        bridge.reset()
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.assertEqual(scenario.counts("start"), 1)


if __name__ == "__main__":
    unittest.main()
