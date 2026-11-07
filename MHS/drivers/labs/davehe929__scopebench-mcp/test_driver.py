"""Acceptance run of the DHO804D package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
MEASURE = "x-cap.davehe929.scope_measure.v1"


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
        driver.write("main", {"channel_coupling": "GND"})
        self.assertEqual(driver.native.written[0], "*IDN?")                     # the identity check on connect
        self.assertEqual(driver.native.written[1], ":CHANnel1:COUPling GND")
        driver.write("main", {"channel_offset": -0.2, "timebase_scale": 0.001})
        self.assertEqual(driver.native.written[-4:-1], [":CHANnel1:OFFSet -0.2", ":SYSTem:ERRor?",
                                                      ":TIMebase:MAIN:SCALe 0.001"])

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel_coupling": "AC", "trigger_level": 0.25})
        state = driver.read("main", ["channel_coupling", "trigger_level"])
        self.assertEqual(state, {"channel_coupling": "AC", "trigger_level": 0.25})

    def test_the_state_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        driver.read("main")
        self.assertEqual(driver.native.written[1:4], [":TRIGger:STATus?", ":CHANnel1:COUPling?",
                                                      ":CHANnel1:SCALe?"])

    def test_the_measurement_action_builds_the_item_query(self) -> None:
        driver = self.driver()
        output = driver.call(MEASURE, {"channel": 2, "measurement": "vpp"})
        self.assertEqual(output, {"value": 2.964})
        self.assertIn(":MEASure:ITEM? VPP,CHANnel2", driver.native.written)


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

    def test_the_coupling_is_the_sourced_allowed_set(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel_coupling="DIFF"), ENVELOPE)
        for value in ("AC", "DC", "GND"):
            self.assertEqual(self.configure(client, channel_coupling=value), "completed", value)

    def test_a_numeric_setting_is_operator_required_without_the_overlay(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel_offset=1.0), LIMITS_UNSET)
        self.assertEqual(self.configure(client, timebase_scale=0.001), LIMITS_UNSET)

    def test_the_example_overlay_fills_and_narrows_every_numeric_setting(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, channel_offset=10.1), ENVELOPE)
        self.assertEqual(self.configure(client, channel_offset=1.0), "completed")
        self.assertEqual(self.configure(client, timebase_scale=11.0), ENVELOPE)
        self.assertEqual(self.configure(client, trigger_level=-1.0), "completed")

    def test_the_measurement_inputs_are_bounded(self) -> None:
        client = self.serve()
        for payload in ({"channel": 0, "measurement": "vpp"}, {"channel": 5, "measurement": "vpp"},
                        {"channel": 1, "measurement": "bogus"}):
            receipt = client.invoke(MEASURE, payload, **self.ids)
            self.assertEqual(receipt["status"], "rejected", payload)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, payload)
        receipt = client.invoke(MEASURE, {"channel": 1, "measurement": "vpp"}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"value": 2.964})


class Safety(unittest.TestCase):
    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":STOP")
        self.assertEqual(driver.read("main", ["trigger_status"]), {"trigger_status": "STOP"})


if __name__ == "__main__":
    unittest.main()
