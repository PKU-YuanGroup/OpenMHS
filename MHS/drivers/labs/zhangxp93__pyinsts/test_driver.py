"""Acceptance run of the FSV3030 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_identity_and_the_reads_use_the_upstream_commands(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[0], "*IDN?")
        self.assertEqual(driver.native.written[1:],
                         ["FREQ:CENT?", "CALC:MARK1:X?", "CALC:MARK1:Y?", "CALC:DELT1:X?", "CALC:DELT1:Y?"])
        self.assertEqual(state["center_frequency"], 1.0e9)  # placeholder
        self.assertEqual(state["marker_frequency"], 9.5e8)  # placeholder
        self.assertEqual((state["marker_level"], state["delta_marker_frequency"], state["delta_marker_level"]),
                         (-12.5, 1.0e6, -3.0))  # placeholder

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"center_frequency": 2.0e9, "span": 5.0e6, "marker_frequency": 1.5e9,
                              "error_display": "OFF", "continuous_peak": "ON"})
        self.assertEqual(driver.native.written[1:],
                         ["SENSE:FREQ:CENT 2000000000Hz", "FREQ:SPAN 5000000Hz", "CALC:MARK1:X 1500000000",
                          "SYST:ERR:DISP OFF", "CALCulate1:MARKer1:MAXimum:AUTO ON"])
        state = driver.read("main", ["center_frequency", "marker_frequency"])
        self.assertEqual((state["center_frequency"], state["marker_frequency"]), (2.0e9, 1.5e9))  # placeholder

    def test_the_estop_aborts_the_measurement(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "ABOR")
        self.assertTrue(driver.native.aborted)


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_without_an_overlay_the_numeric_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"center_frequency": 1e8}, {"span": 1e6}, {"marker_frequency": 1e8}):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)

    def test_the_example_overlay_supplies_the_numeric_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, center_frequency=5e8, span=1e6, marker_frequency=5.5e8),
                         "completed")
        state = self.state(client)
        self.assertEqual((state["center_frequency"], state["marker_frequency"]), (5e8, 5.5e8))
        for patch in ({"center_frequency": 2e9}, {"span": 1e9}, {"marker_frequency": 2e9}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_two_on_off_settings_are_sourced_and_checked(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, error_display="OFF", continuous_peak="ON"), "completed")
        refused = client.invoke("cap.device.configure.v1", {"error_display": "MAYBE"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"))

    def test_the_estop_latches_the_configure_capability(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertEqual(self.configure(client, error_display="ON"), ESTOP)


if __name__ == "__main__":
    unittest.main()
