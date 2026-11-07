"""Acceptance run of the LPX 200 package: the gate, the wire lines, and the two kinds of limit.

The gate call stays first; add cases, never remove it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The lines the driver leaves on the fake transport (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(set(driver.native.sent),
                         {"OPMODE?", "TRIGGER?", "MODE?", "REPRATE?", "HV?", "EGY?", "PRESSURE?", "Menu?"})
        self.assertEqual(state["operating_mode"], "OFF")
        self.assertEqual(state["trigger_mode"], "INT")
        self.assertEqual(state["mode"], "HV")
        self.assertEqual(state["repetition_rate"], 100.0)
        self.assertEqual(state["high_voltage"], 20.0)
        self.assertEqual(state["energy"], 10.0)
        self.assertEqual(state["pressure"], 1500.0)
        self.assertEqual(state["gas_mix"], "RARE")

    def test_a_number_is_appended_to_the_prefix_of_the_key(self) -> None:
        driver = self.driver()
        driver.write("main", {"repetition_rate": 50.0, "high_voltage": 21.5, "energy": 8.0})
        self.assertEqual(driver.native.sent[-6:], ["REPRATE=50", "REPRATE?", "HV=21.5", "HV?",
                                                   "EGY=8", "EGY?"])
        state = driver.read("main", ["repetition_rate", "high_voltage", "energy"])
        self.assertEqual(state, {"repetition_rate": 50.0, "high_voltage": 21.5, "energy": 8.0})

    def test_the_mode_and_trigger_are_sent_with_their_names(self) -> None:
        driver = self.driver()
        driver.write("main", {"mode": "EGY PGR", "trigger_mode": "EXT"})
        self.assertEqual(set(driver.native.sent[-4:]),
                         {"MODE=EGY PGR", "MODE?", "TRIGGER=EXT", "TRIGGER?"})
        self.assertEqual(driver.write("main", {"mode": "HV", "trigger_mode": "INT"}),
                         {"applied": {"mode": "HV", "trigger_mode": "INT"}})

    def test_the_actions_and_the_estop_send_opmode(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.emission_on(), {"operating_mode": "ON"})
        self.assertEqual(driver.emission_off(), {"operating_mode": "OFF"})
        driver.emission_on()
        driver.estop("test")
        self.assertEqual(driver.native.sent[-1], "OPMODE=OFF")
        self.assertEqual(driver.native.sent.count("OPMODE=OFF"), 2)
        self.assertEqual(driver.read("main", ["operating_mode"]), {"operating_mode": "OFF"})


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

    def test_the_three_numeric_settings_need_an_operator_bound(self) -> None:
        client = self.serve()
        for patch in ({"repetition_rate": 50.0}, {"high_voltage": 20.0}, {"energy": 10.0}):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)

    def test_the_allowed_mode_and_trigger_sets(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"mode": "EGY"}, {"mode": "hv"}, {"trigger_mode": "BOTH"}, {"trigger_mode": "ext"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"mode": "EGY PGR"}, {"mode": "EGY NGR"}, {"trigger_mode": "EXT"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"repetition_rate": 0.5}, {"repetition_rate": 101.0}, {"high_voltage": 14.9},
                      {"high_voltage": 30.1}, {"energy": 0.5}, {"energy": 101.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"repetition_rate": 50.0}, {"repetition_rate": 100.0}, {"high_voltage": 20.0},
                      {"energy": 10.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
