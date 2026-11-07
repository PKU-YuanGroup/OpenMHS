"""safety_bindings: e-stop, reset, interlocks and safe state reach the native API.

Ported reviewer repro (failed before WP-05): drv-verify/estop_probe.py and
driver-authoring/driver_v1.py (DRV-03) -- a declarative PythonObjectBridge has
no way to bind an e-stop, so ``mhs.safety.estop`` leaves the native heater on
("native heater_on after MHS estop: True") and the bridge has no reset or
interlock hooks at all.
"""

from __future__ import annotations

import threading
import time
import unittest

from tests.bridges import support

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.python import PythonObjectBridge
from mhs.bridge.serial import FakeSerial, SerialBridge
from mhs.server import Resource

HEATER = "tests.bridges.support:Heater"


def heater_config(**safety: object) -> dict:
    bindings = {
        "estop": {"native": "emergency_stop"},
        "reset": {"native": "clear_fault"},
        "safe_state": {"native": "emergency_stop", "description": "heater off"},
        "interlocks": [{"id": "lid", "native": "lid_closed", "invoke": "get", "description": "lid closed"}],
    }
    bindings.update(safety)
    return {
        "target": HEATER,
        "capabilities": {
            "cap.thermal.setpoint.v1": {
                "bridge": "python-object", "native": "set_point",
                "args": {"celsius": {"from": "input.target_temperature", "type": "number"}},
                "result": {"map": {"setpoint": "output.setpoint"}},
                "concurrency": "exclusive", "timeout_ms": 2000,
            },
            "x-cap.test.slow.v1": {
                "bridge": "python-object", "native": "slow",
                "args": {"seconds": {"from": "input.seconds", "type": "number"}},
                "result": {"map": {"slept": "output.slept"}},
                "concurrency": "exclusive", "timeout_ms": 5000,
            },
        },
        "reads": {"heater": {"method": "state"}},
        "safety_bindings": bindings,
    }


class PythonObjectSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = PythonObjectBridge(heater_config(), device_id="mhs://localhost:7799/lab/heater")
        self.native: support.Heater = self.bridge._ensure_loaded()

    def tearDown(self) -> None:
        self.bridge.close()

    def test_estop_calls_the_native_stop_and_reports_safe_state(self) -> None:
        result = self.bridge.estop("test")
        self.assertIn(("emergency_stop", None), self.native.calls)
        self.assertFalse(self.native.heating)
        self.assertEqual(result["native"], "emergency_stop")
        self.assertTrue(result["safe_state_achieved"])
        status = self.bridge.safety_status()
        self.assertTrue(status["safe_state"]["achieved"])
        self.assertEqual(status["safe_state"]["description"], "heater off")
        self.assertEqual(self.bridge.estop_native, "emergency_stop")

    def test_estop_does_not_wait_for_a_running_call(self) -> None:
        worker = threading.Thread(target=self.bridge.call, args=("x-cap.test.slow.v1", {"seconds": 0.8}))
        worker.start()
        time.sleep(0.1)  # the slow call now holds the bridge lock
        started = time.monotonic()
        with self.assertRaises(signals.DriverFailed) as caught:
            self.bridge.estop("preempt")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(self.bridge.safety_status()["safe_state"]["achieved"])
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertTrue(worker.is_alive(), "the e-stop must not wait for the running call")
        worker.join(2.0)
        self.assertTrue(self.bridge.estop("settled")['safe_state_achieved'])

    def test_interlocks_read_the_native_state(self) -> None:
        self.assertEqual(self.bridge.interlocks(),
                         [{"id": "lid", "state": "closed", "description": "lid closed"}])
        self.native.lid_closed = False
        self.assertEqual(self.bridge.interlocks()[0]["state"], "open")
        self.native.lid_closed = "maybe"   # not a boolean: never treated as closed
        self.assertEqual(self.bridge.interlocks()[0]["state"], "unknown")

    def test_reset_is_refused_while_an_interlock_is_open(self) -> None:
        self.native.lid_closed = False
        with self.assertRaises(Exception) as caught:
            self.bridge.reset()
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertNotIn(("clear_fault", None), self.native.calls)
        self.native.lid_closed = True
        self.bridge.reset()
        self.assertIn(("clear_fault", None), self.native.calls)

    def test_failing_estop_native_is_safe_state_unreached(self) -> None:
        bridge = PythonObjectBridge(heater_config(estop={"native": "does_not_exist"}), load=True)
        try:
            with self.assertRaises(signals.DriverFailed) as caught:
                bridge.estop("boom")
            self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
        finally:
            bridge.close()

    def test_unknown_safety_binding_keys_are_refused(self) -> None:
        for bad in ({"estopp": {"native": "emergency_stop"}},
                    {"estop": {"native": "emergency_stop", "colour": "red"}},
                    {"interlocks": [{"native": "lid_closed"}]}):
            with self.subTest(bad=bad):
                config = heater_config()
                config["safety_bindings"] = bad
                with self.assertRaises(Exception) as caught:
                    PythonObjectBridge(config)
                self.assertEqual(getattr(caught.exception, "code", None), "MHS.ADAPTER.MANIFEST_INVALID")


class PythonObjectSafetyEndToEndTests(unittest.TestCase):
    def test_server_estop_reaches_the_native_api(self) -> None:
        bridge = PythonObjectBridge(heater_config(), device_id="mhs://localhost:7799/lab/heater")
        device = support.simulated_device(
            "mhs://localhost:7799/lab/heater",
            resources=[Resource("heater", "thermal.zone")],
            capabilities=[support.open_capability("cap.thermal.setpoint.v1", "heater")],
            bridge=bridge,
        )
        harness = support.Harness(device)
        try:
            native: support.Heater = bridge._ensure_loaded()
            self.assertEqual(harness.command("cap.thermal.setpoint.v1", {"target_temperature": 70})["status"],
                             "completed")
            receipt = harness.estop("operator pressed stop")
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertTrue(receipt["output"]["safe_state_achieved"])
            self.assertFalse(native.heating, "the native heater must be off after mhs.safety.estop")
            blocked = harness.command("cap.thermal.setpoint.v1", {"target_temperature": 80})
            self.assertEqual(blocked["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
            self.assertEqual(native.setpoint, 70)
            status = harness.safety_status()
            self.assertIn({"id": "lid", "state": "closed", "description": "lid closed"}, status["interlocks"])
            self.assertEqual(harness.reset()["status"], "completed")
            self.assertIn(("clear_fault", None), native.calls)
        finally:
            bridge.close()


class AsyncSafetyTests(unittest.TestCase):
    def test_async_estop_runs_while_an_async_call_is_in_flight(self) -> None:
        config = {
            "target": "tests.bridges.support:AsyncBath",
            "capabilities": {
                "x-cap.test.ramp.v1": {
                    "bridge": "python-object", "native": "ramp",
                    "args": {"target": {"from": "input.target"}, "seconds": {"from": "input.seconds"}},
                    "result": {"map": {"setpoint": "output.setpoint"}},
                    "concurrency": "exclusive", "timeout_ms": 5000,
                },
            },
            "safety_bindings": {"estop": {"native": "stop", "invoke": "await", "timeout_ms": 500}},
        }
        bridge = PythonObjectBridge(config)
        native: support.AsyncBath = bridge._ensure_loaded()
        context = BridgeContext(cancel_event=threading.Event(), deadline_ms=5000)
        holder: dict = {}

        def run() -> None:
            try:
                bridge.call("x-cap.test.ramp.v1", {"target": 90, "seconds": 2}, context)
            except BaseException as exc:  # noqa: BLE001
                holder["error"] = exc

        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(native.ramp_started.wait(2.0))
            started = time.monotonic()
            with self.assertRaises(signals.DriverFailed) as caught:
                bridge.estop("stop now")
            self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
            self.assertLess(time.monotonic() - started, 0.4)
            self.assertTrue(native.stopped)
            context.cancel_event.set()   # what the server does to running operations
            worker.join(2.0)
            self.assertIsInstance(holder.get("error"), signals.Cancelled)
            self.assertFalse(native.ramp_done)
        finally:
            context.cancel_event.set()
            worker.join(2.0)
            bridge.close()


class SerialSafetyTests(unittest.TestCase):
    def bridge(self, serial: FakeSerial) -> SerialBridge:
        return SerialBridge(
            {
                "port": "/dev/fake",
                "timeout_s": 0.3,
                "capabilities": {
                    "x-cap.test.query.v1": {"resource": "instrument", "command": "SLOW?",
                                             "parse": {"kind": "float", "field": "value"}},
                },
                "safety_bindings": {
                    "estop": {"command": "STOP"},
                    "safe_state": {"command": "HEAT 0", "description": "heater output off"},
                    "reset": {"command": "RST"},
                    "interlocks": [{"id": "door", "command": "DOOR?", "parse": {"kind": "int"},
                                    "closed_when": 1, "description": "door closed"}],
                },
            },
            serial_factory=lambda **kwargs: serial,
        )

    def test_estop_safe_state_reset_and_interlocks_are_commands(self) -> None:
        serial = FakeSerial({"DOOR?": "1\n", "RST": "OK\n"})
        bridge = self.bridge(serial)
        try:
            self.assertEqual(bridge.interlocks(), [{"id": "door", "state": "closed", "description": "door closed"}])
            result = bridge.estop("stop")
            self.assertTrue(result["safe_state_achieved"])
            self.assertIn(b"STOP\n", serial.written)
            self.assertIn(b"HEAT 0\n", serial.written)
            self.assertLess(serial.written.index(b"STOP\n"), serial.written.index(b"HEAT 0\n"))
            bridge.reset()
            self.assertIn(b"RST\n", serial.written)
            serial.responses["DOOR?"] = "0\n"
            self.assertEqual(bridge.interlocks()[0]["state"], "open")
            with self.assertRaises(Exception) as caught:
                bridge.reset()
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.INTERLOCK_OPEN")
            self.assertEqual(bridge.estop_native, "STOP")
        finally:
            bridge.close()

    def test_estop_is_written_while_a_transaction_waits(self) -> None:
        serial = FakeSerial(default="")   # SLOW? never answers: the call waits for its timeout
        bridge = self.bridge(serial)
        holder: dict = {}

        def run() -> None:
            try:
                bridge.call("x-cap.test.query.v1", {})
            except BaseException as exc:  # noqa: BLE001
                holder["error"] = exc

        worker = threading.Thread(target=run)
        worker.start()
        try:
            time.sleep(0.05)
            started = time.monotonic()
            bridge.estop("now")
            self.assertLess(time.monotonic() - started, 0.15)
            self.assertIn(b"STOP\n", serial.written)
            worker.join(2.0)
            self.assertIsInstance(holder.get("error"), signals.OutcomeUnknown)
        finally:
            worker.join(2.0)
            bridge.close()


if __name__ == "__main__":
    unittest.main()
