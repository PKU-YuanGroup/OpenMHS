"""Acceptance run of the AWG33220A package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StateAndSafety(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_boolean_write_changes_the_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": False, "burst_enabled": True})
        state = driver.read("main", ["output", "burst_enabled"])
        self.assertEqual(state, {"output": False, "burst_enabled": True})

    def test_a_function_write_changes_the_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"function": "square", "burst_mode": "gate"})
        state = driver.read("main", ["function", "burst_mode"])
        self.assertEqual(state, {"function": "square", "burst_mode": "gate"})

    def test_the_estop_disables_the_output(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.estop("test")
        self.assertFalse(driver.native.get_output())
        self.assertEqual(driver.read("main", ["output"]), {"output": False})


class OperatorLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_a_numeric_write_is_refused(self) -> None:
        client = self.serve()
        for patch in ({"frequency": 10.0}, {"amplitude": 0.1}, {"phase": 10.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_admits_its_range_and_refuses_outside_it(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, frequency=10.0), "completed")
        self.assertEqual(self.configure(client, amplitude=0.5), "completed")
        self.assertEqual(self.configure(client, frequency=1000.1), ENVELOPE)
        self.assertEqual(self.configure(client, amplitude=1.1), ENVELOPE)
        state = client.read("main", **self.ids)["state"]
        self.assertEqual((state["frequency"], state["amplitude"]), (10.0, 0.5))


if __name__ == "__main__":
    unittest.main()
