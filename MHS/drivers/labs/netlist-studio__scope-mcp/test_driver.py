"""Acceptance run of the MSOX2024A package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  Every number below that comes from fake.py is a placeholder, not a
fact from the clone or a record of an instrument.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverBehaviour(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_of_a_fresh_scope(self) -> None:
        state = self.driver().read("main")
        self.assertEqual(state["identity"],
                         "AGILENT TECHNOLOGIES,MSOX2024A,FAKE000000,02.43.2018020635")  # placeholder
        self.assertEqual(state["operation_condition"], 8)  # placeholder
        self.assertEqual(state["channel1_coupling"], "DC")  # placeholder
        self.assertTrue(state["channel1_enabled"])
        self.assertEqual(state["trigger_source_channel"], 1)  # placeholder
        self.assertEqual(state["trigger_slope"], "positive")  # placeholder
        self.assertEqual(state["timebase_scale_s_per_div"], 0.001)  # placeholder

    def test_a_write_changes_the_state_it_reports(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel1_coupling": "GND", "channel1_enabled": False,
                              "channel1_bwlimit": True})
        driver.write("main", {"trigger_source_channel": 2, "trigger_slope": "negative"})
        state = driver.read("main")
        self.assertEqual(state["channel1_coupling"], "GND")
        self.assertFalse(state["channel1_enabled"])
        self.assertTrue(state["channel1_bwlimit"])
        self.assertEqual(state["trigger_source_channel"], 2)
        self.assertEqual(state["trigger_slope"], "negative")

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main", ["operation_condition"]), {"operation_condition": 8})  # placeholder
        driver.estop("test")
        self.assertEqual(driver.read("main", ["operation_condition"]), {"operation_condition": 0})  # placeholder

    def test_closing_the_driver_closes_the_visa_session(self) -> None:
        driver = self.driver()
        native = driver.native
        driver.close()
        self.assertTrue(native.closed)


class Serving(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        self.native = driver.native
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def action(self, client, cap, payload):
        return client.invoke(cap, payload, **self.ids)

    def test_an_ignored_stop_does_not_confirm_the_safe_state(self) -> None:
        client = self.serve()
        self.native.stop = lambda: None  # placeholder: write returned but RUN remains set
        receipt = client.estop("ignored stop", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(receipt["output"]["latched"])
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_the_operator_supplies_the_numeric_ranges(self) -> None:
        client = self.serve()
        for patch in ({"channel1_scale_v_per_div": 0.5}, {"channel1_offset_v": 0.2},
                      {"timebase_scale_s_per_div": 0.001}, {"timebase_delay_s": 0.0002},
                      {"trigger_level_v": 1.0}):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)

        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"channel1_scale_v_per_div": 0.5}, {"channel1_offset_v": 0.2},
                      {"timebase_scale_s_per_div": 0.001}, {"timebase_delay_s": 0.0002},
                      {"trigger_level_v": 1.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        for patch in ({"channel1_scale_v_per_div": 0.0001}, {"channel1_offset_v": 20.0},
                      {"timebase_scale_s_per_div": 2.0}, {"timebase_delay_s": 0.01},
                      {"trigger_level_v": 20.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_enum_bounds_of_the_clone(self) -> None:
        client = self.serve()
        for patch in ({"channel1_coupling": "DIFFERENTIAL"}, {"trigger_source_channel": 5},
                      {"trigger_slope": "rising"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"channel1_coupling": "AC"}, {"trigger_source_channel": 3},
                      {"trigger_slope": "either"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_measurement_and_acquisition_actions(self) -> None:
        client = self.serve()
        measured = self.action(client, "x-cap.netlist-studio.measure.v1",
                               {"channel": 2, "parameter": "vpp"})
        self.assertEqual(measured["status"], "completed")
        self.assertEqual(measured["output"]["value"], 2.0)  # placeholder
        self.assertEqual(measured["output"]["channel"], 2)
        self.assertEqual(self.action(client, "x-cap.netlist-studio.stop.v1", {})["output"],
                         {"operation_condition": 0})  # placeholder
        self.assertEqual(self.action(client, "x-cap.netlist-studio.run.v1", {})["output"],
                         {"operation_condition": 8})  # placeholder
        self.assertEqual(self.action(client, "x-cap.netlist-studio.single.v1", {})["output"],
                         {"operation_condition": 8})  # placeholder
        refused = self.action(client, "x-cap.netlist-studio.measure.v1",
                              {"channel": 1, "parameter": "jitter"})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)


if __name__ == "__main__":
    unittest.main()
