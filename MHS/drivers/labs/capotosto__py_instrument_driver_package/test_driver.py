"""Acceptance run of the Keysight E4980A package: the gate, plus cases for this driver's command map.

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


class WireCommands(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_sends_the_command_words_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.0, "alc": True, "cable_length": 2})
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity probe on connect
        self.assertIn(":FREQuency 2500.0", driver.native.written)
        self.assertIn(":AMPLitude:ALC ON", driver.native.written)
        self.assertIn(":CORRection:LENGth 2", driver.native.written)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.5, "cable_length": 4})
        state = driver.read("main", ["frequency", "cable_length", "data_format"])
        self.assertEqual(state["frequency"], 2500.5)
        self.assertEqual(state["cable_length"], 4.0)
        self.assertEqual(state["data_format"], "ASCii")

    def test_the_aperture_action_writes_both_fields(self) -> None:
        driver = self.driver()
        driver.call("x-cap.capotosto.set_aperture.v1", {"mode": "LONG", "averages": 8})
        self.assertIn(":APERture LONG,8", driver.native.written)
        state = driver.read("main", ["aperture_mode", "aperture_averages"])
        self.assertEqual(state, {"aperture_mode": "LONG", "aperture_averages": 8})

    def test_the_fetch_actions_return_the_scalar_fields(self) -> None:
        driver = self.driver()
        formatted = driver.call("x-cap.capotosto.fetch_formatted.v1", {})
        self.assertEqual(set(formatted), {"primary", "secondary", "status"})
        impedance = driver.call("x-cap.capotosto.fetch_impedance.v1", {})
        self.assertEqual(set(impedance), {"resistance", "reactance"})
        self.assertEqual(driver.call("x-cap.capotosto.fetch_vac.v1", {}), {"voltage": 1.0})
        self.assertEqual(driver.call("x-cap.capotosto.fetch_iac.v1", {}), {"current": 0.01})

    def test_the_estop_removes_the_bias_and_aborts(self) -> None:
        driver = self.driver()
        driver.estop("package test")
        self.assertIn(":BIAS:STATe OFF", driver.native.written)
        self.assertIn(":ABORt", driver.native.written)


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_an_operator_bound_is_refused_until_an_overlay_fills_it(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, frequency=1000.0), UNSET)

    def test_the_example_overlay_fills_and_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, frequency=1000.0), "completed")
        self.assertEqual(self.configure(client, frequency=10.0), ENVELOPE)
        self.assertEqual(self.configure(client, cable_length=3.0), ENVELOPE)
        self.assertEqual(self.configure(client, cable_length=2.0), "completed")


if __name__ == "__main__":
    unittest.main()
