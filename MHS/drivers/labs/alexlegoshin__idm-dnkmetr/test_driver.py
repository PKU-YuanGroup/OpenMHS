"""Acceptance run of the GPP-4323 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ACTION = "x-cap.alexlegoshin.enable_output.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverState(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_is_read_back_and_the_output_changes(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint": 12.0, "current_limit": 0.25})
        state = driver.read("main", ["voltage_setpoint", "current_limit"])
        self.assertEqual(state, {"voltage_setpoint": 12.0, "current_limit": 0.25})
        self.assertEqual(driver.read("main", ["voltage", "current"]), {"voltage": 0.0, "current": 0.0})
        self.assertEqual(driver.call(ACTION, {"enabled": True}), {"enabled": True})
        self.assertAlmostEqual(driver.read("main", ["voltage"])["voltage"], 12.0)
        self.assertAlmostEqual(driver.read("main", ["current"])["current"], 12.0 / driver.native.load_ohms)
        self.assertEqual(driver.call(ACTION, {"enabled": False}), {"enabled": False})
        self.assertEqual(driver.read("main", ["voltage"])["voltage"], 0.0)
        self.assertIn(("set_voltage", 12.0), driver.native.written)
        self.assertIn(("set_current_limit", 0.25), driver.native.written)

    def test_the_estop_opens_the_output(self) -> None:
        driver = self.driver()
        driver.call(ACTION, {"enabled": True})
        self.assertTrue(driver.native.output_on)
        driver.estop("test")
        self.assertFalse(driver.native.output_on)
        self.assertEqual(driver.read("main", ["voltage"])["voltage"], 0.0)

    def test_the_identity_is_the_profile_reply(self) -> None:
        driver = self.driver()
        identity = driver.read("main", ["identity"])["identity"]
        self.assertTrue(identity.startswith("GW INSTEK,GPP-"))


class Limits(unittest.TestCase):
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

    def test_the_bounds_of_the_clone(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint": -0.1}, {"voltage_setpoint": 64.1}, {"current_limit": 3.1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint": 0}, {"voltage_setpoint": 64.0}, {"current_limit": 0},
                      {"current_limit": 3.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage_setpoint": -0.1}, {"voltage_setpoint": 60.1}, {"current_limit": -0.01},
                      {"current_limit": 0.03}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint": 60.0}, {"current_limit": 0.02}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_action_reports_the_state_it_sent(self) -> None:
        client = self.serve()
        for enabled in (True, False):
            receipt = client.invoke(ACTION, {"enabled": enabled}, **self.ids)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"], {"enabled": enabled})


if __name__ == "__main__":
    unittest.main()
