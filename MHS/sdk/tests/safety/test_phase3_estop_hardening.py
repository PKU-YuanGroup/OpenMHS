"""Hardening of the composed phase-2 e-stop path (review s10, S10-1 to S10-5; verification safety lens, F1 to F4).

Each case pins one item so that a regression of it fails here:

* S10-1: the SDK ROS route rejects a driver class that overrides ``inner``, ``estop``, ``safety_status`` or
  ``_run_safe_state``, and an inner bridge that is not exactly ``RosBridge``;
* S10-2: a run of the stop path takes its settle budget from its own start;
* S10-3: the latch is set (and persisted) while the settle hook runs;
* S10-4: looking up the settle hook imports nothing;
* S10-5 / F2: ``command_in_flight`` and ``awaiting_operations`` come from the operations still in flight;
* F1: a restore admission seen at the first sample keeps the e-stop unachieved even if it is gone at the second;
* F3: a restore after the latch is refused before any bridge call, on a bridge without ``restore_admission``;
* F4: the wait for a command in flight ends when its worker thread is gone without settling.
"""

from __future__ import annotations

import builtins
import json
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import mhs.server as server_module
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.driver import GymnasiumDriver, build_server, close_server
from mhs.server import _EstopAttempt, _await_settled, _sdk_ros_route, _sdk_settle_hook

from tests.bridges.test_gym_sync_safety import ACTION, STEP, BlockingCartPole, in_thread
from tests.driver import support
from tests.safety import test_estop_recovery_declarations as recovery
from tests.safety import test_estop_stop_once as stop_once
from tests.safety._support import conveyor, error_code


class RouteTests(unittest.TestCase):
    """S10-1: CORE-074's report list goes only to a route that is the SDK's from the class down to the bridge."""

    def driver(self, name="Uav", **body):
        uav = stop_once._Uav()
        driver, _transport = stop_once._ros_driver(uav, estop_spec=stop_once.LAND_SERVICE,
                                                   safe_spec=stop_once.LAND_SERVICE, name=name, body=body)
        self.addCleanup(driver.close)
        return driver

    def test_the_sdk_driver_is_the_route(self):
        self.assertTrue(_sdk_ros_route(self.driver()))

    def test_a_class_level_override_of_inner_or_the_safety_methods_is_not(self):
        wrapper = property(lambda self: self.__dict__.get("_inner_bridge"))
        for name, value in (("inner", wrapper), ("estop", lambda self, reason="", ctx=None: {}),
                            ("safety_status", lambda self: {}), ("_run_safe_state", lambda self, ctx=None: {})):
            with self.subTest(member=name):
                self.assertFalse(_sdk_ros_route(self.driver(name=f"Override{name}", **{name: value})))

    def test_an_inner_bridge_of_another_class_is_not(self):
        driver = self.driver()
        _ = driver.inner

        class Sub(RosBridge):
            pass

        driver.__dict__["_inner_bridge"] = Sub(
            {"timeout_s": 1.0, "resources": [{"resource_id": "main", "kind": "instrument"}]},
            transport=RecordingRosTransport(lambda message: None))
        self.addCleanup(driver.__dict__["_inner_bridge"].close)
        self.assertFalse(_sdk_ros_route(driver))

    def test_an_instance_safety_status_is_not(self):
        driver = self.driver()
        driver.safety_status = lambda: {}
        self.assertFalse(_sdk_ros_route(driver))


class SettleTests(unittest.TestCase):
    def test_s10_2_a_run_takes_its_settle_budget_from_its_own_start(self):
        server, _rpc, device, _session = conveyor()
        self.addCleanup(server.close)
        attempt = _EstopAttempt()
        attempt.started = time.monotonic() - 30.0          # the first run started long ago
        budgets: list[float] = []
        with mock.patch.object(server_module, "_settle_native_work",
                               side_effect=lambda bridge, timeout: budgets.append(timeout)):
            server._run_estop_attempt(device, "s10-2", attempt)
        self.assertEqual(len(budgets), 1)
        self.assertGreater(budgets[0], 0.5 * server._estop_budget_ms(device) / 1000.0, budgets)

    def test_s10_3_the_latch_is_set_and_persisted_while_the_settle_hook_runs(self):
        env = BlockingCartPole()

        class Blocking(GymnasiumDriver):
            device_id = "hardening/cartpole"
            backends = {"fake": lambda: env}
            safe_state = "no new step after the e-stop; a native call already running completes first"

        holder = tempfile.TemporaryDirectory(prefix="mhs-s10-3-")
        self.addCleanup(holder.cleanup)
        state_dir = Path(holder.name)
        driver = Blocking(backend="fake")
        server = build_server(driver, state_dir=state_dir)
        self.addCleanup(close_server, server)
        self.addCleanup(env.release.set)
        client = support.Client(server)
        client.command(STEP, {"ticks": 1, "action": ACTION})
        env.block_steps = True
        worker, _ = in_thread(lambda: client.command(STEP, {"ticks": 1, "action": ACTION}))
        self.assertTrue(env.entered.wait(2))
        seen: list[tuple[bool, bool]] = []
        original = server_module._settle_native_work

        def observed(bridge, timeout):
            # Other tests may still have a bounded background stop finishing.
            # Only this device's settle hook witnesses this server's latch.
            if bridge is not driver:
                return original(bridge, timeout)
            latch = state_dir / "latch.json"
            persisted = latch.exists() and json.loads(latch.read_text()).get("devices", {}) != {}
            seen.append((bool(server._latched.get(client.device_id)), persisted))
            threading.Timer(0.1, env.release.set).start()
            return original(bridge, timeout)

        with mock.patch.object(server_module, "_settle_native_work", side_effect=observed):
            stop = client.estop("s10-3")
        worker.join(3)
        self.assertEqual(seen, [(True, True)], seen)
        self.assertTrue(stop["output"]["latched"])

    def test_s10_4_looking_up_the_settle_hook_imports_nothing(self):
        env = BlockingCartPole()
        from mhs.bridge.gymnasium import GymnasiumBridge

        bridge = GymnasiumBridge(env=env)
        self.addCleanup(bridge.close)
        real_import = builtins.__import__

        def refuse(name, *args, **kwargs):
            raise AssertionError(f"import of {name} on the e-stop path")

        with mock.patch.object(builtins, "__import__", side_effect=refuse):
            hook = _sdk_settle_hook(bridge)
            none = _sdk_settle_hook(types.SimpleNamespace(settle_native_work=lambda timeout: True))
        self.assertIs(builtins.__import__, real_import)
        self.assertIsNotNone(hook)
        self.assertIsNone(none)


class InFlightLabelTests(unittest.TestCase):
    """S10-5 / F2: once the commands in flight settled, a stop that has not answered is a timeout."""

    def test_settled_commands_and_a_hanging_second_run_report_timeout_without_a_stale_list(self):
        class HangingDrive(recovery.SlowFakeDrive):
            def __init__(self, **options):
                super().__init__(**options)
                self.hang = threading.Event()
                self.offs = 0

            def switch_off(self):
                self.offs += 1
                if self.offs > 2:                         # the second run of the stop path hangs
                    self.hang.wait(10)
                super().switch_off()

        class Hanging(recovery.Drive):
            backends = {"fake": HangingDrive}
            estop_latency_ms = 400

        driver, server, client = recovery.served(Hanging)
        self.addCleanup(close_server, server)
        self.addCleanup(driver.native.hang.set)
        self.addCleanup(driver.native.release.set)
        driver.native.slow_move = True
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: sender.command(recovery.MOVE, {"position": 0.5}, deadline_ms=5000),
                                  daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.assertTrue(driver.native.entered.wait(5))
        threading.Timer(0.05, driver.native.release.set).start()   # the move settles early in the budget
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(recovery.details(receipt)["reason"], "timeout", receipt)
        self.assertNotIn("awaiting_operations", recovery.details(receipt))

    def test_a_command_still_in_flight_is_listed(self):
        driver, server, client = recovery.served(recovery.SlowDrive)
        self.addCleanup(close_server, server)
        driver.native.slow_move = True
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: sender.command(recovery.MOVE, {"position": 0.5}, deadline_ms=5000),
                                  daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(driver.native.release.set)
        self.assertTrue(driver.native.entered.wait(5))
        receipt = client.estop()
        self.assertEqual(recovery.details(receipt)["reason"], "command_in_flight", receipt)
        self.assertEqual(len(recovery.details(receipt)["awaiting_operations"]), 1)


class RestoreTests(unittest.TestCase):
    def test_f1_a_restore_seen_at_the_first_sample_keeps_the_estop_unachieved(self):
        server, _rpc, device, _session = conveyor()
        self.addCleanup(server.close)
        bridge = device.bridge
        server._restore_admissions[device.device_id] = 0

        def status_and_drop():
            server._restore_admissions.pop(device.device_id, None)   # the restore ends between the two samples
            return {"safe_state": {"description": "stopped", "achieved": True}}

        bridge.safety_status = status_and_drop
        attempt = _EstopAttempt()
        server._run_estop_attempt(device, "f1", attempt)
        self.assertIs(attempt.bridge_safe_state, False)
        self.assertEqual(attempt.reason, "bridge_reports_unsafe")

    def test_f3_a_restore_after_the_latch_reaches_no_bridge_method(self):
        server, rpc, device, session = conveyor()
        self.addCleanup(server.close)
        bridge = device.bridge
        self.assertFalse(hasattr(bridge, "restore_admission"))
        snapshot = rpc("mhs.snapshot", session_id=session, deadline_ms=2000)
        rpc("mhs.safety.estop", session_id=session, reason="f3", deadline_ms=1000)
        calls: list[str] = []
        original_snapshot, original_restore = bridge.snapshot, bridge.restore

        def counted_snapshot(*args, **kwargs):
            calls.append("snapshot")
            return original_snapshot(*args, **kwargs)

        def counted_restore(*args, **kwargs):
            calls.append("restore")
            return original_restore(*args, **kwargs)

        bridge.snapshot, bridge.restore = counted_snapshot, counted_restore
        receipt = rpc("mhs.restore", session_id=session, snapshot=snapshot, deadline_ms=2000)
        self.assertEqual((receipt["status"], error_code(receipt)), ("rejected", "MHS.SAFETY.ESTOP_ENGAGED"))
        self.assertEqual(calls, [])


class SettledWaitTests(unittest.TestCase):
    def test_f4_the_wait_ends_when_the_worker_died_without_settling(self):
        worker = threading.Thread(target=lambda: None, daemon=True)
        worker.start()
        worker.join()
        operation = types.SimpleNamespace(done=threading.Event(), thread=worker)
        waiter = threading.Thread(target=_await_settled, args=(operation,), daemon=True)
        waiter.start()
        waiter.join(2.0)
        self.assertFalse(waiter.is_alive(), "the wait never ends for a worker that is gone without settling")
        self.assertFalse(operation.done.is_set())

    def test_f4_a_live_worker_is_still_waited_for(self):
        release = threading.Event()
        operation = types.SimpleNamespace(done=threading.Event(), thread=None)

        def work():
            release.wait(5)
            operation.done.set()

        operation.thread = threading.Thread(target=work, daemon=True)
        operation.thread.start()
        threading.Timer(0.2, release.set).start()
        started = time.monotonic()
        _await_settled(operation)
        self.assertGreaterEqual(time.monotonic() - started, 0.15)
        self.assertTrue(operation.done.is_set())


if __name__ == "__main__":
    unittest.main()
