"""Acceptance run of the pyagilis package: the gate, plus cases for this driver's native mapping.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativeMapping(unittest.TestCase):
    """The native calls of the fake, without the runtime's envelope (direct method calls)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_jog_moves_both_counters(self) -> None:
        driver = self.driver()
        before = driver.read("main")
        result = driver.jog(10, -10)
        after = driver.read("main")
        self.assertEqual(result["x_steps"], before["x_steps"] + 10)
        self.assertEqual(result["y_steps"], before["y_steps"] - 10)
        self.assertEqual(after["x_steps"], before["x_steps"] + 10)
        self.assertEqual(after["y_steps"], before["y_steps"] - 10)

    def test_go_to_zero_returns_both_counters_to_zero(self) -> None:
        driver = self.driver()
        driver.jog(7, -3)
        result = driver.go_to_zero()
        self.assertEqual((result["x_steps"], result["y_steps"]), (0, 0))
        self.assertEqual((driver.read("main")["x_steps"], driver.read("main")["y_steps"]), (0, 0))

    def test_set_zero_resets_both_counters(self) -> None:
        driver = self.driver()
        driver.jog(5, 5)
        result = driver.set_zero()
        self.assertEqual((result["x_steps"], result["y_steps"]), (0, 0))

    def test_the_estop_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        driver.stop()
        state = driver.read("main")
        self.assertEqual(state["x_last_operation"], "stopped")
        self.assertEqual(state["y_last_operation"], "stopped")


class OperatorOverlay(unittest.TestCase):
    """The example overlay fills the two operator_required jog paths and still refuses a wider step count."""

    def serve(self):
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_example_overlay_narrows_the_jog(self) -> None:
        client, device_id, session = self.serve()
        completed = client.invoke("x-cap.lando1784.jog.v1", {"x_steps": 50, "y_steps": -50},
                                  device_id=device_id, session_id=session)
        self.assertEqual(completed["status"], "completed")
        refused = client.invoke("x-cap.lando1784.jog.v1", {"x_steps": 101, "y_steps": 0},
                                device_id=device_id, session_id=session)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))


if __name__ == "__main__":
    unittest.main()
