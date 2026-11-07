"""AsyncRunner: awaited, bounded and cancellable natives; Status-like returns.

Ported reviewer repros (each failed before WP-05):

* fit-lab-instruments/t_pyobj.py and fit-lab-automation/drv/try_bridge.py
  (FIT-09, LAB-02): an ``async def`` native gives "cannot serialise native
  value of type coroutine" and a never-awaited warning; an ophyd-like
  ``set()`` returning a Status object gives "cannot serialise ...
  StatusLike".
"""

from __future__ import annotations

import asyncio
import threading
import time
import unittest

from tests.bridges import support

from mhs import signals
from mhs.bridge.base import AsyncRunner, BridgeContext, is_status_like
from mhs.bridge.python import PythonObjectBridge
from mhs.server import Resource

BATH = "tests.bridges.support:AsyncBath"
AXIS = "tests.bridges.support:Axis"


def entry(native: str, result_map: dict, *, args: dict | None = None, timeout_ms: int = 2000, **extra) -> dict:
    binding = {"bridge": "python-object", "native": native, "result": {"map": result_map},
               "concurrency": "exclusive", "timeout_ms": timeout_ms}
    if args is not None:
        binding["args"] = args
    binding.update(extra)
    return binding


def bath_config() -> dict:
    return {
        "target": BATH,
        "setup": "setup",
        "close": "close",
        "capabilities": {
            "cap.measure.temperature.v1": entry("bath_temperature", {"temperature": "output.$"}),
            "x-cap.test.setpoint.v1": entry(
                "set_point_1", {"setpoint": "output.$"},
                args={"value": {"from": "input.setpoint", "type": "number"}}, invoke="await"),
            "x-cap.test.ramp.v1": entry(
                "ramp", {"setpoint": "output.setpoint"},
                args={"target": {"from": "input.target", "type": "number"},
                      "seconds": {"from": "input.seconds", "type": "number"}},
                timeout_ms=10000),
        },
        "reads": {"bath": {"fields": {"temperature": "bath_temperature", "setpoint": "setpoint"}}},
    }


class AsyncRunnerTests(unittest.TestCase):
    def test_runs_coroutines_on_one_persistent_loop(self) -> None:
        runner = AsyncRunner(name="test-loop")
        try:
            async def loop_id() -> int:
                return id(asyncio.get_running_loop())

            first = runner.run(loop_id(), timeout_ms=1000)
            second = runner.run(loop_id(), timeout_ms=1000)
            self.assertEqual(first, second)
        finally:
            runner.close()

    def test_timeout_cancels_the_task_and_reports_an_unknown_outcome(self) -> None:
        runner = AsyncRunner()
        cancelled = threading.Event()
        try:
            async def forever() -> None:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            with self.assertRaises(signals.OutcomeUnknown):
                runner.run(forever(), timeout_ms=50)
            self.assertTrue(cancelled.wait(1.0))
        finally:
            runner.close()

    def test_cancel_event_cancels_the_task(self) -> None:
        runner = AsyncRunner()
        event = threading.Event()
        cancelled = threading.Event()
        try:
            async def forever() -> None:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            threading.Timer(0.05, event.set).start()
            started = time.monotonic()
            with self.assertRaises(signals.Cancelled):
                runner.run(forever(), timeout_ms=5000, cancel_event=event)
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertTrue(cancelled.wait(1.0))
        finally:
            runner.close()

    def test_native_exceptions_propagate_unchanged(self) -> None:
        runner = AsyncRunner()
        try:
            async def boom() -> None:
                raise TimeoutError("the native's own timeout")

            with self.assertRaises(TimeoutError):
                runner.run(boom(), timeout_ms=1000)
        finally:
            runner.close()

    def test_status_detection(self) -> None:
        self.assertTrue(is_status_like(support.StatusLike(delay=0.0)))
        for value in (None, 1, "x", {"done": True, "success": True}, [1], 2.0):
            self.assertFalse(is_status_like(value))


class AsyncNativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = PythonObjectBridge(bath_config(), device_id="mhs://localhost:7799/lab/bath")
        self.native: support.AsyncBath = self.bridge._ensure_loaded()

    def tearDown(self) -> None:
        self.bridge.close()

    def test_async_setup_runs_and_natives_are_awaited_on_the_same_loop(self) -> None:
        self.assertTrue(self.native.setup_done)
        self.assertEqual(self.bridge.call("cap.measure.temperature.v1", {}), {"temperature": 22.0})
        self.assertEqual(self.bridge.call("x-cap.test.setpoint.v1", {"setpoint": 35}), {"setpoint": 35.0})
        self.assertEqual(self.bridge.read("bath"), {"temperature": 22.0, "setpoint": 35.0})
        self.assertEqual(len(self.native.loops), 1, "every coroutine must run on the bridge's one loop")

    def test_cancel_event_cancels_the_native_coroutine(self) -> None:
        context = BridgeContext(cancel_event=threading.Event(), deadline_ms=10000)
        threading.Timer(0.05, context.cancel_event.set).start()
        with self.assertRaises(signals.Cancelled):
            self.bridge.call("x-cap.test.ramp.v1", {"target": 80, "seconds": 5}, context)
        self.assertTrue(self.native.ramp_cancelled.wait(1.0))
        self.assertFalse(self.native.ramp_done)

    def test_deadline_bounds_the_await(self) -> None:
        context = BridgeContext(deadline_ms=100)
        with self.assertRaises(signals.OutcomeUnknown):
            self.bridge.call("x-cap.test.ramp.v1", {"target": 80, "seconds": 5}, context)
        self.assertTrue(self.native.ramp_cancelled.wait(1.0))

    def test_close_awaits_the_async_close_hook(self) -> None:
        self.bridge.close()
        self.assertTrue(self.native.closed)

    def test_invoke_await_refuses_a_non_awaitable(self) -> None:
        config = bath_config()
        config["capabilities"]["x-cap.test.sync.v1"] = entry("setpoint", {"v": "output.$"}, invoke="get")
        config["capabilities"]["x-cap.test.badawait.v1"] = entry(
            "model", {"v": "output.$"}, invoke="await")
        bridge = PythonObjectBridge(config)
        try:
            with self.assertRaises(signals.DriverFailed) as caught:
                bridge.call("x-cap.test.badawait.v1", {})
            self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        finally:
            bridge.close()


class AsyncEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = PythonObjectBridge(bath_config(), device_id="mhs://localhost:7799/lab/bath")
        self.native: support.AsyncBath = self.bridge._ensure_loaded()
        device = support.simulated_device(
            "mhs://localhost:7799/lab/bath",
            resources=[Resource("bath", "lab.thermal_block")],
            capabilities=[
                support.open_capability("cap.measure.temperature.v1", "bath", verb="read"),
                support.open_capability("x-cap.test.ramp.v1", "bath"),
            ],
            bridge=self.bridge,
        )
        self.harness = support.Harness(device)

    def tearDown(self) -> None:
        self.bridge.close()

    def test_async_native_awaited_through_the_server(self) -> None:
        receipt = self.harness.command("cap.measure.temperature.v1", {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"temperature": 22.0})

    def test_operation_cancel_reaches_the_native_coroutine(self) -> None:
        holder: dict = {}

        def run() -> None:
            holder["receipt"] = self.harness.command(
                "x-cap.test.ramp.v1", {"target": 80, "seconds": 5}, deadline_ms=8000)

        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(self.native.ramp_started.wait(2.0))
        operation = self.harness.wait_running()
        self.harness.cancel(operation["operation_id"])
        worker.join(5.0)
        self.assertFalse(worker.is_alive())
        self.assertTrue(self.native.ramp_cancelled.is_set())
        self.assertFalse(self.native.ramp_done)
        # the receipt is terminal and never claims completion (WP-04 records
        # "cancelled" from mhs.signals.Cancelled; the 0.9 compat server "failed")
        self.assertIn(holder["receipt"]["status"], ("cancelled", "failed"), holder["receipt"])
        self.assertEqual(self.native.setpoint, 20.0)


class StatusObjectTests(unittest.TestCase):
    def config(self, invoke: str = "status", timeout_ms: int = 2000) -> dict:
        return {
            "target": AXIS,
            "capabilities": {
                "x-cap.test.move.v1": entry(
                    "set", {"reached": "output.success"},
                    args={"value": {"from": "input.position", "type": "number"}},
                    invoke=invoke, timeout_ms=timeout_ms),
            },
            "reads": {"axis": {"fields": {"position": "position"}}},
        }

    def test_status_object_is_awaited(self) -> None:
        for invoke in ("status", "call"):
            with self.subTest(invoke=invoke):
                bridge = PythonObjectBridge(self.config(invoke))
                try:
                    native: support.Axis = bridge._ensure_loaded()
                    output = bridge.call("x-cap.test.move.v1", {"position": 12.5})
                    self.assertEqual(output, {"reached": True})
                    self.assertTrue(native.statuses[-1].done)
                    self.assertEqual(native.position, 12.5)
                finally:
                    bridge.close()

    def test_a_status_that_completes_inside_wait_is_awaited(self) -> None:
        # t_pyobj.py repro: done stays False until wait() is called
        config = self.config()
        config["target"] = "tests.bridges.support:LazyAxis"
        config["reads"] = {"axis": {"fields": {"position": "pos"}}}
        bridge = PythonObjectBridge(config)
        try:
            started = time.monotonic()
            self.assertEqual(bridge.call("x-cap.test.move.v1", {"position": 4}), {"reached": True})
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertEqual(bridge.read("axis"), {"position": 4.0})
        finally:
            bridge.close()

    def test_failed_status_is_a_driver_failure(self) -> None:
        bridge = PythonObjectBridge(self.config())
        try:
            with self.assertRaises(signals.DriverFailed) as caught:
                bridge.call("x-cap.test.move.v1", {"position": 500})
            self.assertIn(caught.exception.code, ("MHS.ADAPTER.SHIM_FAILED", "MHS.DEVICE.FAULTED"))
        finally:
            bridge.close()

    def test_status_wait_is_bounded(self) -> None:
        config = self.config(timeout_ms=30)
        config["factory"] = {"kind": "class", "kwargs": {"delay": 0.5}}
        bridge = PythonObjectBridge(config)
        try:
            with self.assertRaises(signals.OutcomeUnknown):
                bridge.call("x-cap.test.move.v1", {"position": 1})
        finally:
            bridge.close()

    def test_status_end_to_end(self) -> None:
        bridge = PythonObjectBridge(self.config())
        device = support.simulated_device(
            "mhs://localhost:7799/lab/axis",
            resources=[Resource("axis", "motion.axis")],
            capabilities=[support.open_capability("x-cap.test.move.v1", "axis")],
            bridge=bridge,
        )
        harness = support.Harness(device)
        try:
            receipt = harness.command("x-cap.test.move.v1", {"position": 3})
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"], {"reached": True})
            self.assertEqual(harness.read("axis")["state"], {"position": 3.0})
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
