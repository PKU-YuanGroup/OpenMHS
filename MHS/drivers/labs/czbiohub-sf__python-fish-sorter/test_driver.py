"""Acceptance run of the Fish Sorter pneumatics package: the gate, plus the package's own cases.

Add cases, never remove the check_driver call.  The numeric values asserted here are the fake's
test data (marked ``# placeholder`` in fake.py), not facts about the instrument.  The fake stands
in for the controller program of the clone's CoDeSys project (see fake.py): it takes a valid code
from the function register, echoes it and writes 0 back.  Nothing here ran on a real controller.
"""

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PRESSURE = "x-cap.czbiohub-sf.set_pressure.v1"
VACUUM = "x-cap.czbiohub-sf.set_vacuum.v1"
IDLE = "x-cap.czbiohub-sf.idle_atmospheric.v1"
SAFE = "x-cap.czbiohub-sf.safe_pneumatics.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FishSorterPneumaticsCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.valves = driver.native                     # the fake ValveController
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return self.client

    def configure(self, **patch):
        return self.client.invoke("cap.device.configure.v1", patch, **self.ids)

    def invoke(self, capability, payload=None):
        return self.client.invoke(capability, payload or {}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def taken(self, code):
        """The controller took ``code``: the function register is back at 0 and the echo holds the code."""
        state = self.state()
        self.assertEqual((state["function_code"], state["function_echo"]), (0, code))

    # -- limits ---------------------------------------------------------------------------------------------
    def test_the_timing_writes_wait_for_the_site(self) -> None:
        self.serve()
        refused = self.configure(draw_time_ms=75)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state()["draw_time_ms"], 50)                # fake placeholder, untouched

    def test_the_example_overlay_supplies_the_timing_range(self) -> None:
        self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(draw_time_ms=75)["status"], "completed")
        self.assertEqual(self.state()["draw_time_ms"], 75)
        refused = self.configure(expel_time_ms=5001)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state()["expel_time_ms"], 150)              # fake placeholder, untouched

    # -- the pneumatic functions --------------------------------------------------------------------------------
    def test_each_action_completes_only_once_the_controller_took_its_code(self) -> None:
        self.serve()
        cases = (
            (PRESSURE, {"state": True}, {"pressure": True, "function_code": 9}, {"press": True, "vacuum": False}),
            (VACUUM, {"state": True}, {"vacuum": True, "function_code": 16}, {"press": True, "vacuum": True}),
            (PRESSURE, {"state": False}, {"pressure": False, "function_code": 8}, {"press": False, "vacuum": True}),
            (VACUUM, {"state": False}, {"vacuum": False, "function_code": 17}, {"press": False, "vacuum": False}),
            (VACUUM, {"state": True}, {"vacuum": True, "function_code": 16}, {"press": False, "vacuum": True}),
            (IDLE, {}, {"idle": True, "function_code": 128}, {"press": False, "vacuum": False}),
        )
        for capability, payload, output, outputs in cases:
            receipt = self.invoke(capability, payload)
            self.assertEqual((receipt["status"], receipt["output"]), ("completed", output), receipt)
            self.assertEqual(self.valves._outputs(), outputs, capability)
            self.taken(output["function_code"])

    def test_the_safe_state_action_confirms_the_idle_code(self) -> None:
        self.serve()
        self.invoke(PRESSURE, {"state": True})
        safe = self.invoke(SAFE)
        self.assertEqual((safe["status"], safe["output"]), ("completed", {"idle": True, "function_code": 128}))
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})
        self.taken(128)

    def test_the_estop_leaves_both_outputs_off_and_latches(self) -> None:
        self.serve()
        self.invoke(PRESSURE, {"state": True})
        self.invoke(VACUUM, {"state": True})
        self.assertEqual(self.valves._outputs(), {"press": True, "vacuum": True})
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})
        self.taken(128)
        refused = self.invoke(PRESSURE, {"state": True})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})

    # -- native replies (pymodbus returns an exception reply; it does not raise: valve_test.py:88-96) ----------------
    def test_a_modbus_exception_reply_is_a_failure_with_the_native_code(self) -> None:
        self.serve(str(HERE / "site-limits.example.json"))
        self.valves._reply_with_errors(1, writes_only=True)
        failed = self.invoke(PRESSURE, {"state": True})
        self.assertEqual((failed["status"], failed["error"]["mhs_code"]), ("failed", FAULTED), failed)
        self.assertEqual(failed["error"]["details"]["native_code"], 4)
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})    # nothing was written
        self.valves._reply_with_errors(1, writes_only=True)
        refused_write = self.configure(draw_time_ms=75)
        self.assertEqual((refused_write["status"], refused_write["error"]["mhs_code"]), ("failed", FAULTED))
        self.assertEqual(self.state()["draw_time_ms"], 50)                # fake placeholder, untouched
        self.assertEqual(self.invoke(PRESSURE, {"state": True})["status"], "completed")   # the hook was one-shot

    def test_a_read_back_that_fails_after_the_write_is_unknown_not_failed(self) -> None:
        self.serve()
        original = self.valves.read_register
        calls = []

        def failing_read(add_offset, count=1):
            calls.append(add_offset)
            self.valves._reply_with_errors(1)
            return original(add_offset, count)

        self.valves.read_register = failing_read
        try:
            receipt = self.invoke(PRESSURE, {"state": True})
        finally:
            self.valves.read_register = original
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN), receipt)
        self.assertTrue(calls)
        self.assertEqual(self.valves._outputs(), {"press": True, "vacuum": False})     # the write did land

    def test_a_write_that_raises_is_unknown_not_failed(self) -> None:
        self.serve()

        def lost_reply(add_offset, value):
            raise ConnectionError("no reply")                           # the request may have reached the controller

        self.valves.write_register = lost_reply
        try:
            receipt = self.invoke(PRESSURE, {"state": True})
        finally:
            del self.valves.write_register
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN), receipt)
        self.assertEqual(self.invoke(PRESSURE, {"state": True})["status"], "completed")

    def test_a_code_the_controller_does_not_take_is_unknown(self) -> None:
        self.serve()
        self.valves._stall()
        receipt = self.invoke(PRESSURE, {"state": True})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN), receipt)
        self.assertEqual(receipt["error"]["details"]["native_code"], 9)  # still waiting in the function register
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})

    def test_a_code_lost_to_a_running_sequence_is_a_failure(self) -> None:
        self.serve()
        self.valves._end_sequence_on_next_code(2)                          # placeholder: a draw sequence
        receipt = self.invoke(PRESSURE, {"state": True})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED), receipt)
        self.assertEqual(receipt["error"]["details"]["native_code"], 2)
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})

    # -- e-stop failures keep the latch ---------------------------------------------------------------------------
    def test_an_estop_whose_idle_write_is_refused_fails_and_keeps_the_latch(self) -> None:
        self.serve()
        self.invoke(PRESSURE, {"state": True})
        self.valves._reply_with_errors(1000)
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.valves._reply_with_errors(0)
        refused = self.invoke(PRESSURE, {"state": False})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))

    def test_an_estop_the_controller_does_not_take_fails_and_keeps_the_latch(self) -> None:
        self.serve()
        self.invoke(VACUUM, {"state": True})
        self.valves._stall()
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": True})       # nothing confirmed it off
        refused = self.invoke(VACUUM, {"state": False})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))

    def test_a_command_waiting_for_the_controller_when_the_estop_lands_is_not_sent(self) -> None:
        self.serve()
        written, checked, receipts = [], [], {}
        inside, go = threading.Event(), threading.Event()
        original_write, original_check = self.valves.write_register, self.driver.check_cancelled
        original_function = self.driver._function

        def recording_write(add_offset, value):
            written.append(int(value))
            return original_write(add_offset, value)

        def recording_check():
            checked.append(threading.current_thread().name)
            return original_check()

        def held_function(key):                         # holds the command inside its method, past the latch check
            if key == "press_on" and not inside.is_set():
                inside.set()
                go.wait(5)
            return original_function(key)

        self.valves.write_register = recording_write
        self.driver.check_cancelled = recording_check
        self.driver._function = held_function
        action = threading.Thread(name="action", daemon=True, target=lambda: receipts.__setitem__(
            "action", self.invoke(PRESSURE, {"state": True})))
        action.start()
        self.assertTrue(inside.wait(5))
        transaction = self.driver._io()
        transaction.acquire()                           # a transaction of another caller is in flight
        try:
            stop = threading.Thread(name="estop", daemon=True, target=lambda: receipts.__setitem__(
                "estop", self.client.estop("test", **self.ids)))
            stop.start()
            time.sleep(0.2)                             # the runtime cancelled the command; its native stop waits
            go.set()
            time.sleep(0.1)                             # the command now waits for the transaction too
        finally:
            transaction.release()
        action.join(5)
        stop.join(5)
        del self.valves.write_register
        del self.driver.check_cancelled
        del self.driver._function
        self.assertTrue(checked)                        # the command checked its cancellation under the lock
        self.assertEqual(receipts["action"]["status"], "cancelled", receipts["action"])
        self.assertNotIn(9, written)                    # press_on never reached the controller
        self.assertEqual(receipts["estop"]["status"], "completed", receipts["estop"])
        self.assertEqual(self.valves._outputs(), {"press": False, "vacuum": False})
        self.taken(128)

    # -- recovery, reference and loader -----------------------------------------------------------------------
    def test_the_driver_declares_no_reset_hook_no_reenable_and_no_terminal_stop(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        self.assertIsNone(driver.reset_hook)
        estop = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))["safety"]["estop"]
        self.assertEqual(estop["native"], "stop")
        self.assertNotIn("reenable", estop)
        self.assertNotIn("terminal", estop)

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
