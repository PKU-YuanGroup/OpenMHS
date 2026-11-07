"""Acceptance run of the Temi package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py); ``_commands`` is what
reached the fake Temi.  Nothing here ran on a robot.
"""

import json
import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
FAULTED = "MHS.DEVICE.FAULTED"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SHIM_FAILED = "MHS.ADAPTER.SHIM_FAILED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TemiCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.robot = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.robot._commands[:]
        return self.client

    def sent(self, name=None):
        return [(command, args) for command, args in self.robot._commands
                if name is None or command == name]

    def invoke(self, capability_id, payload):
        return self.client.invoke(capability_id, payload, **self.ids)

    # -- the documented commands -------------------------------------------------------------------------------
    def test_goto_sends_the_location_and_reports_reached(self) -> None:
        self.serve()
        receipt = self.invoke("x-cap.tongji-cdi.goto.v1", {"location": "Front Door"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"location": "Front Door", "reached": True})
        self.assertEqual(self.sent("goto"), [("goto", {"location": "Front Door"})])

    def test_a_goto_that_did_not_reach_the_location_is_a_failure(self) -> None:
        self.serve()
        self.robot._set_goto_success(False)
        receipt = self.invoke("x-cap.tongji-cdi.goto.v1", {"location": "Front Door"})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))
        self.assertEqual(self.robot._location, "Front Door")       # the command did reach the fake
        self.assertEqual(len(self.sent("goto")), 1)

    def test_speak_sends_the_sentence(self) -> None:
        self.serve()
        receipt = self.invoke("x-cap.tongji-cdi.speak.v1", {"sentence": "Hello"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"sentence": "Hello"})
        self.assertEqual(self.sent("speak"), [("speak", {"sentence": "Hello"})])
        self.assertEqual(self.robot._spoken, ["Hello"])

    def test_ask_returns_the_recognized_answer(self) -> None:
        self.serve()
        receipt = self.invoke("x-cap.tongji-cdi.ask.v1", {"sentence": "What is your name?"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"question": "What is your name?", "answer": "yes"})
        self.assertEqual(self.sent("ask"), [("ask", {"sentence": "What is your name?"})])

    def test_an_ask_without_an_answer_is_a_failure(self) -> None:
        self.serve()
        self.robot._set_answer(None)
        receipt = self.invoke("x-cap.tongji-cdi.ask.v1", {"sentence": "Are you there?"})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))

    def test_interface_opens_the_url(self) -> None:
        self.serve()
        receipt = self.invoke("x-cap.tongji-cdi.interface.v1", {"url": "https://example.invalid/"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"url": "https://example.invalid/"})
        self.assertEqual(self.robot._url, "https://example.invalid/")

    def test_a_native_failure_is_not_hidden(self) -> None:
        self.serve()
        self.robot._fail_next_command("the WebSocket closed")
        receipt = self.invoke("x-cap.tongji-cdi.speak.v1", {"sentence": "Hello"})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", SHIM_FAILED))

    # -- stop and e-stop ----------------------------------------------------------------------------------------
    def test_the_stop_action_sends_the_stop_command(self) -> None:
        self.serve()
        receipt = self.invoke("x-cap.tongji-cdi.stop.v1", {})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True})
        self.assertEqual(self.sent("stop"), [("stop", {})])

    def test_the_estop_stops_temi_and_latches(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertGreaterEqual(len(self.sent("stop")), 1)          # the @estop and the safe-state action
        self.assertGreaterEqual(self.robot._stop_count, 1)
        before = len(self.robot._commands)
        refused = self.invoke("x-cap.tongji-cdi.speak.v1", {"sentence": "Hello"})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(len(self.robot._commands), before)         # the latched call reached no native code
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.invoke("x-cap.tongji-cdi.speak.v1", {"sentence": "Hello"})["status"], "completed")

    # -- declaration, reference and loader ---------------------------------------------------------------------
    def test_the_reference_declares_the_stop_action_and_command_native(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(safety["estop"]["native"], "command")
        self.assertIn("x-cap.tongji-cdi.stop.v1", safety["safe_state"]["achieved_by"])

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
