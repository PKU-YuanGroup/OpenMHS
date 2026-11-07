"""The synchronous simulator e-stop is honest: a native call in flight is never reported as the safe state.

Synthetic peers only (a blocking CartPole-like environment and the fake MuJoCo module); no simulator runs.
"""
from __future__ import annotations

import threading
import time
import unittest

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.mujoco import MujocoBridge
from mhs.client import MHSClient
from mhs.driver import GymnasiumDriver, build_server, close_server
from tests.bridges import support
from tests.bridges.support import FakeCartPole

STEP, RESET = "cap.world.step.v1", "cap.world.reset.v1"
ACTION = {"index": 1}
NOT_ACHIEVED = {"safe_state": {"achieved": False}}


class BlockingCartPole(FakeCartPole):
    """Blocks inside a native step or reset until released (a long physics call)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.release = threading.Event()
        self.entered = threading.Event()
        self.block_steps = self.block_resets = False

    def _hold(self):
        self.entered.set()
        if not self.release.wait(10):
            raise AssertionError("test never released the native call")

    def step(self, action):
        if self.block_steps:
            self._hold()
        return super().step(action)

    def reset(self, seed=None, options=None):
        if self.block_resets:
            self._hold()
        return super().reset(seed=seed, options=options)


def in_thread(fn, *args):
    outcome = {}

    def run():
        try:
            outcome["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 - the test inspects it
            outcome["error"] = exc
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    return worker, outcome


class GymBridgeTests(unittest.TestCase):
    def make(self):
        env = BlockingCartPole()
        bridge = GymnasiumBridge(env=env)
        self.addCleanup(env.release.set)
        self.addCleanup(bridge.close)
        return env, bridge

    def test_an_in_flight_step_is_never_reported_safe(self):
        env, bridge = self.make()
        bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(bridge.safety_status(), {})
        env.block_steps = True
        worker, outcome = in_thread(bridge.call, STEP, {"ticks": 1, "action": ACTION})
        self.assertTrue(env.entered.wait(2))
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        started = time.monotonic()
        self.assertFalse(bridge.settle_native_work(0.1))
        self.assertLess(time.monotonic() - started, 1.0)          # bounded: never waits for the native call
        with self.assertRaises(Exception) as caught:
            bridge.reset()
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.RESET_REFUSED")
        threading.Timer(0.1, env.release.set).start()
        self.assertTrue(bridge.settle_native_work(5))
        worker.join(2)
        self.assertIn("value", outcome)                            # the native call completed undisturbed
        self.assertEqual(bridge.safety_status(), {})
        bridge.reset()

    def test_an_in_flight_reset_is_never_reported_safe(self):
        env, bridge = self.make()
        env.block_resets = True
        worker, _outcome = in_thread(bridge.call, RESET, {})
        self.assertTrue(env.entered.wait(2))
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        self.assertFalse(bridge.settle_native_work(0.05))
        env.release.set()
        worker.join(2)
        self.assertTrue(bridge.settle_native_work(1))
        self.assertEqual(bridge.safety_status(), {})

    def test_a_call_cancelled_while_queued_dispatches_nothing(self):
        env, bridge = self.make()
        env.block_resets = True
        first, _ = in_thread(bridge.call, RESET, {})
        self.assertTrue(env.entered.wait(2))
        cancel = threading.Event()
        queued_step, step_outcome = in_thread(bridge.call, STEP, {"ticks": 1, "action": ACTION},
                                              BridgeContext(cancel_event=cancel))
        queued_reset, reset_outcome = in_thread(bridge.call, RESET, {}, BridgeContext(cancel_event=cancel))
        time.sleep(0.05)
        cancel.set()                      # the endpoint cancels running operations when the e-stop engages
        env.release.set()
        for worker in (first, queued_step, queued_reset):
            worker.join(2)
        self.assertIsInstance(step_outcome.get("error"), signals.Cancelled)
        self.assertIsInstance(reset_outcome.get("error"), signals.Cancelled)
        self.assertEqual((len(env.seeds), env.native_steps), (1, 0))   # only the first, admitted reset ran


class MujocoBridgeTests(unittest.TestCase):
    def test_settle_waits_for_an_in_flight_step(self):
        model = support.FakeMjModel()
        data = support.FakeMjData(model)
        mj = support.fake_mujoco()
        release, entered = threading.Event(), threading.Event()
        original = mj.mj_step

        def blocking_step(m, d):
            entered.set()
            release.wait(10)
            original(m, d)
        mj.mj_step = blocking_step
        bridge = MujocoBridge(prebuilt=(model, data), mujoco=mj)
        self.addCleanup(bridge.close)
        self.addCleanup(release.set)
        worker, _ = in_thread(bridge.call, STEP, {"ticks": 1})
        self.assertTrue(entered.wait(2))
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        self.assertFalse(bridge.settle_native_work(0.05))
        threading.Timer(0.1, release.set).start()
        self.assertTrue(bridge.settle_native_work(5))
        worker.join(2)
        self.assertEqual(bridge.safety_status(), {"safe_state": {"achieved": True}})


class StockServerEstopTests(unittest.TestCase):
    """Through the endpoint: the software-only e-stop waits (bounded) for the native call, or says it could not."""

    def serve(self):
        env = BlockingCartPole()

        class Blocking(GymnasiumDriver):
            device_id = "sync-safety/cartpole"
            backends = {"fake": lambda: env}
            safe_state = ("no new step or reset after the e-stop; a native call already running completes first "
                          "and the e-stop waits for it, bounded")
        driver = Blocking(backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.addCleanup(env.release.set)
        client = MHSClient(server)
        client.hello()
        device = next(iter(server.devices.values())).device_id
        client.open_session([device], mode="simulated")
        client.invoke(STEP, {"ticks": 1, "action": ACTION}, device_id=device)
        env.block_steps = True
        return env, client, device

    def test_estop_waits_for_a_native_step_that_ends_within_the_budget(self):
        env, client, device = self.serve()
        worker, outcome = in_thread(lambda: client.invoke(STEP, {"ticks": 3, "action": ACTION}, device_id=device))
        self.assertTrue(env.entered.wait(2))
        threading.Timer(0.2, env.release.set).start()
        started = time.monotonic()
        stop = client.estop("in-flight step", device_id=device)
        self.assertGreaterEqual(time.monotonic() - started, 0.15)    # it waited for the native call
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"])
        worker.join(3)
        self.assertEqual(outcome["value"]["status"], "cancelled", outcome)   # the remaining ticks never ran
        self.assertEqual(env.native_steps, 2)                               # the setup step and the in-flight one

    def test_estop_reports_unreached_when_the_native_step_outlives_the_budget(self):
        env, client, device = self.serve()
        worker, _ = in_thread(lambda: client.invoke(STEP, {"ticks": 1, "action": ACTION}, device_id=device))
        self.assertTrue(env.entered.wait(2))
        started = time.monotonic()
        stop = client.estop("long native step", device_id=device)
        self.assertLess(time.monotonic() - started, 3.0)                    # bounded, no deadlock
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"))
        self.assertTrue(stop["error"]["details"]["retrying"])
        self.assertFalse(stop["output"]["safe_state_achieved"])
        self.assertTrue(stop["output"]["latched"])
        env.release.set()
        worker.join(3)
        deadline = time.monotonic() + 8.0
        confirmed = False
        while time.monotonic() < deadline and not confirmed:
            confirmed = bool(client.safety_status(device).get("estop", {}).get("confirmed"))
            time.sleep(0.05)
        self.assertTrue(confirmed, "the background retry (SAFE-040) confirms once the native call settled")


class FaultyWaitLock:
    """Wraps the bridge's lock: ordinary use is unchanged, a timed wait (the settle hook's) raises or hangs."""

    def __init__(self, lock, mode):
        self._inner, self.mode = lock, mode

    def acquire(self, blocking=True, timeout=-1):
        if timeout != -1:
            if self.mode == "raise":
                raise RuntimeError("the settle wait failed")
            time.sleep(3.0)                 # ignores its own bound: only the endpoint's bound can end it
            return False
        return self._inner.acquire(blocking)

    def release(self):
        self._inner.release()

    def __enter__(self):
        self._inner.acquire()
        return self

    def __exit__(self, *exc):
        self._inner.release()
        return False


class SettleHookTrustTests(unittest.TestCase):
    """The endpoint consults only the SDK's own hook, bounds the call itself, and lets safety_status decide."""

    def serve(self, driver_class=None):
        env = BlockingCartPole()
        base = driver_class or GymnasiumDriver

        class Served(base):
            device_id = "sync-safety/trust"
            backends = {"fake": lambda: env}
            safe_state = "no new step or reset after the e-stop; a running native call completes first"
        driver = Served(backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.addCleanup(env.release.set)
        client = MHSClient(server)
        client.hello()
        device = next(iter(server.devices.values())).device_id
        client.open_session([device], mode="simulated")
        client.invoke(STEP, {"ticks": 1, "action": ACTION}, device_id=device)
        return env, driver, client, device

    def test_a_raising_sdk_hook_leaves_the_decision_to_safety_status(self):
        env, driver, client, device = self.serve()
        driver.inner._lock = FaultyWaitLock(driver.inner._lock, "raise")
        stop = client.estop("idle, hook raises", device_id=device)
        self.assertEqual(stop["status"], "completed", stop)          # nothing in flight: safety_status says so
        client.reset(device_id=device)
        env.block_steps = True
        worker, _ = in_thread(lambda: client.invoke(STEP, {"ticks": 1, "action": ACTION}, device_id=device))
        self.assertTrue(env.entered.wait(2))
        started = time.monotonic()
        stop = client.estop("in flight, hook raises", device_id=device)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"))
        env.release.set()
        worker.join(3)

    def test_the_endpoint_bounds_a_hook_that_does_not_return(self):
        from mhs import server as server_module
        env, driver, client, device = self.serve()
        driver.inner._lock = FaultyWaitLock(driver.inner._lock, "hang")
        started = time.monotonic()
        server_module._settle_native_work(driver, 0.2)
        self.assertLess(time.monotonic() - started, 1.0)             # joined for the budget, not for 3 s
        started = time.monotonic()
        stop = client.estop("hook hangs", device_id=device)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertIn(stop["status"], ("completed", "failed"))       # decided by safety_status or the budget

    def test_package_supplied_hooks_are_never_called(self):
        calls = []

        class Overriding(GymnasiumDriver):
            def settle_native_work(self, timeout_s):
                calls.append(("driver", timeout_s))
                time.sleep(5)
                return True
        env, driver, client, device = self.serve(Overriding)
        driver.inner.settle_native_work = lambda timeout_s: calls.append(("instance", timeout_s)) or time.sleep(5)
        from mhs import server as server_module
        self.assertIsNone(server_module._sdk_settle_hook(driver))
        plain = GymnasiumBridge(env=FakeCartPole())
        self.addCleanup(plain.close)
        self.assertIsNotNone(server_module._sdk_settle_hook(plain))
        plain.settle_native_work = lambda timeout_s: True
        self.assertIsNone(server_module._sdk_settle_hook(plain))     # an instance attribute is not the SDK method
        started = time.monotonic()
        stop = client.estop("package hooks", device_id=device)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(calls, [])

    def test_the_family_driver_delegates_only_to_the_sdk_bridge_method(self):
        calls = []
        env, driver, client, device = self.serve()
        driver.inner.settle_native_work = lambda timeout_s: calls.append(timeout_s) or time.sleep(5)
        started = time.monotonic()
        self.assertTrue(driver.settle_native_work(0.2))             # the instance attribute is not delegated to
        stop = client.estop("instance hook on the inner bridge", device_id=device)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(calls, [])


class RestoreIsNeverWaitedForTests(unittest.TestCase):
    """A checkpoint restore owns the device: the e-stop answers at once (unachieved), never waits on its lock."""

    def test_estop_during_a_held_restore_answers_promptly_and_the_restore_keeps_its_deadline(self):
        from mhs import canonical
        from tests.driver import support as driver_support
        from tests.driver.test_families import Pendulums

        driver = Pendulums(backend="fake")
        server, client = driver_support.serve(driver)
        self.addCleanup(close_server, server)
        ids = {"session_id": client.session_id, "device_id": client.device_id, "deadline_ms": 1000}
        saved = client.rpc("mhs.snapshot", ids)
        self.assertEqual(client.command("cap.world.step.v1", {"ticks": 2, "action": {"ctrl": [0.3, 0.1]}})["status"],
                         "completed")
        release, entered = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = driver.native

        class HeldSetter:                       # the restore's native setter blocks while holding the bridge lock
            def __getattr__(self, name):
                if name == "mj_setState":
                    entered.set()
                    release.wait(5)
                return getattr(original, name)
        driver.inner._mujoco = HeldSetter()
        worker, outcome = in_thread(lambda: client.rpc("mhs.restore", {**ids, "snapshot": saved,
                                                                      "command_id": canonical.ulid()}))
        self.assertTrue(entered.wait(2))
        started = time.monotonic()
        stop = client.rpc("mhs.safety.estop", {**ids, "command_id": canonical.ulid(), "reason": "held restore"})
        self.assertLess(time.monotonic() - started, 0.5)          # no settle wait on a restore's lock
        self.assertFalse(stop["output"]["safe_state_achieved"], stop)
        release.set()
        worker.join(3)
        self.assertNotIn("error", outcome)                       # the restore answered within its own deadline
        self.assertNotEqual(outcome["value"]["status"], "completed", outcome)
        deadline = time.monotonic() + 8.0                         # the restore's end re-asserts the stop path
        while time.monotonic() < deadline and not client.rpc("mhs.safety.status", ids).get("estop", {}).get("confirmed"):
            time.sleep(0.05)
        self.assertTrue(client.rpc("mhs.safety.status", ids)["estop"]["confirmed"])


if __name__ == "__main__":
    unittest.main()
