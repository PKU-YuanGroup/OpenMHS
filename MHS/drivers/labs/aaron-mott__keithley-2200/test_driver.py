"""Acceptance run of the Keithley 2200 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
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

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {
            "voltage": 12.5,
            "current": 1.25,
            "overvoltage_protection": 20.0,
            "output": True,
            "overvoltage_protection_enabled": True,
        })
        self.assertEqual(driver.native.written[0], "*IDN?")          # the identity probe on connect
        self.assertEqual(driver.native.written[1:],
                         ["VOLT 12.5", "CURR 1.25", "VOLT:PROT 20", "OUTP ON", "VOLT:PROT:STAT ON"])

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:],
                         ["VOLT?", "CURR?", "OUTP?", "VOLT:PROT?", "VOLT:PROT:STAT?",
                          "MEAS:VOLT?", "MEAS:CURR?", "FETCh:POW?"])
        self.assertEqual(state["voltage"], 0.0)
        self.assertEqual(state["current"], 0.0)
        self.assertFalse(state["output"])
        self.assertEqual(state["overvoltage_protection"], 0.0)
        self.assertFalse(state["overvoltage_protection_enabled"])
        self.assertEqual((state["measured_voltage"], state["measured_current"], state["measured_power"]),
                         (0.0, 0.0, 0.0))

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage": 5.0, "current": 0.5, "output": True,
                              "overvoltage_protection": 25.0, "overvoltage_protection_enabled": True})
        state = driver.read("main", ["voltage", "current", "output", "overvoltage_protection",
                                     "overvoltage_protection_enabled",
                                     "measured_voltage", "measured_current", "measured_power"])
        self.assertEqual(state["voltage"], 5.0)
        self.assertEqual(state["current"], 0.5)
        self.assertTrue(state["output"])
        self.assertEqual(state["overvoltage_protection"], 25.0)
        self.assertTrue(state["overvoltage_protection_enabled"])
        self.assertAlmostEqual(state["measured_voltage"], 5.0)
        self.assertAlmostEqual(state["measured_current"], 0.05)      # placeholder 100 ohm modelled load
        self.assertAlmostEqual(state["measured_power"], 0.25)

    def test_the_estop_writes_outp_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "OUTP OFF")
        self.assertFalse(driver.read("main", ["output"])["output"])


class RuntimeLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    @staticmethod
    def configure(client, ids, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_every_numeric_write_is_operator_required(self) -> None:
        client, ids = self.serve()
        for patch in ({"voltage": 1.0}, {"current": 0.5}, {"overvoltage_protection": 2.0}):
            self.assertEqual(self.configure(client, ids, **patch), UNSET, patch)

    def test_the_example_overlay_bounds_the_three_numeric_writes(self) -> None:
        client, ids = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage": -1.0}, {"voltage": 30.001},
                      {"current": -0.001}, {"current": 5.001},
                      {"overvoltage_protection": -1.0}, {"overvoltage_protection": 30.001}):
            self.assertEqual(self.configure(client, ids, **patch), ENVELOPE, patch)
        for patch in ({"voltage": 0.0}, {"voltage": 30.0},
                      {"current": 0.0}, {"current": 5.0},
                      {"overvoltage_protection": 0.0}, {"overvoltage_protection": 30.0}):
            self.assertEqual(self.configure(client, ids, **patch), "completed", patch)

    def test_the_output_is_written_and_the_safe_state_action_disables_it(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.configure(client, ids, output=True), "completed")
        self.assertTrue(client.read(device_id=ids["device_id"], resource_id="main",
                                    session_id=ids["session_id"])["state"]["output"])
        receipt = client.invoke("x-cap.aaron-mott.output_off.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed")
        state = client.read(device_id=ids["device_id"], resource_id="main",
                            session_id=ids["session_id"])["state"]
        self.assertFalse(state["output"])

    def test_the_estop_disables_the_output_and_latches(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.configure(client, ids, output=True), "completed")
        client.estop("test", **ids)
        state = client.read(device_id=ids["device_id"], resource_id="main",
                            session_id=ids["session_id"])["state"]
        self.assertFalse(state["output"])
        self.assertEqual(self.configure(client, ids, output=True), ESTOP)


if __name__ == "__main__":
    unittest.main()
