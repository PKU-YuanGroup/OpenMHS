"""Acceptance run of the MSO5000 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every number below is a placeholder of fake.py, not a fact.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

#: The fake placeholders (fake.py): the state of a freshly opened in-memory scope.
START = {
    "identity": "RIGOL TECHNOLOGIES,MSO5074,FAKE000000,00.01.00",  # placeholder
    "trigger_status": "RUN",  # placeholder
    "acquisition_type": "NORMal",  # placeholder
    "average_count": 64,  # placeholder
    "sample_rate": 1000000.0,  # placeholder
    "memory_depth_points": 1000000,  # placeholder
    "channel1_enabled": True,  # placeholder
    "channel1_scale_per_div": 0.5,  # placeholder
    "channel1_offset": 0.0,  # placeholder
    "channel1_coupling": "DC",  # placeholder
    "channel1_probe_ratio": 10.0,  # placeholder
    "channel1_bandwidth_limit": "20M",  # placeholder
    "timebase_mode": "YT",  # placeholder
    "timebase_scale_s_per_div": 0.0001,  # placeholder
    "timebase_offset_s": 0.0,  # placeholder
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def configure_channel_input(self, client, **patch):
        """``completed``, or the code the channel-input action was refused with."""
        receipt = client.invoke("x-cap.mabl.scope_channel_input.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def state(self, client, fields=None):
        return client.read("main", fields=fields, **self.ids)["state"]

    def test_the_state_of_the_served_channel(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client), START)

    def test_a_write_changes_the_state_it_reports(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, acquisition_type="AVERages"), "completed")
        self.assertEqual(self.configure(client, memory_depth="1M"), "completed")
        self.assertEqual(self.configure_channel_input(client, channel1_coupling="AC"), "completed")
        self.assertEqual(self.configure_channel_input(client, channel1_probe_ratio=100.0), "completed")
        self.assertEqual(self.configure_channel_input(client, channel1_bandwidth_limit="20M"), "completed")
        self.assertEqual(self.configure_channel_input(client, channel1_enabled=False), "completed")
        state = self.state(client)
        self.assertEqual(state["acquisition_type"], "AVERages")
        self.assertEqual(state["memory_depth_points"], 1000000)  # placeholder
        self.assertEqual(state["channel1_coupling"], "AC")
        self.assertEqual(state["channel1_probe_ratio"], 100.0)
        self.assertEqual(state["channel1_bandwidth_limit"], "20M")
        self.assertFalse(state["channel1_enabled"])

    def test_the_envelope_of_the_upstream_enums(self) -> None:
        client = self.serve()
        for patch in (
            {"acquisition_type": "SINE"},
            {"memory_depth": "2M"},
        ):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in (
            {"acquisition_type": "PEAK"},
            {"memory_depth": "10M"},
        ):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        for patch in (
            {"channel1_coupling": "Differential"},
            {"channel1_probe_ratio": 3.0},
            {"channel1_bandwidth_limit": "ON"},
        ):
            self.assertEqual(self.configure_channel_input(client, **patch), ENVELOPE, patch)
        for patch in (
            {"channel1_coupling": "GND"},
            {"channel1_probe_ratio": 1.0},
            {"channel1_bandwidth_limit": "OFF"},
        ):
            self.assertEqual(self.configure_channel_input(client, **patch), "completed", patch)

    def test_the_operator_supplies_the_span_and_position_ranges(self) -> None:
        client = self.serve()
        for patch in (
            {"channel1_scale_per_div": 0.5},
            {"channel1_offset": 0.2},
            {"timebase_scale_s_per_div": 0.001},
            {"timebase_offset_s": 0.0002},
        ):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in (
            {"channel1_scale_per_div": 0.5},
            {"channel1_offset": 0.2},
            {"timebase_scale_s_per_div": 0.001},
            {"timebase_offset_s": 0.0002},
        ):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        state = self.state(client)
        self.assertEqual(state["channel1_scale_per_div"], 0.5)
        self.assertEqual(state["channel1_offset"], 0.2)
        self.assertEqual(state["timebase_scale_s_per_div"], 0.001)
        self.assertEqual(state["timebase_offset_s"], 0.0002)
        for patch in (
            {"channel1_scale_per_div": 0.0},
            {"channel1_scale_per_div": 20.0},
            {"channel1_offset": 5.0},
            {"timebase_scale_s_per_div": 0.0},
            {"timebase_offset_s": 1.0},
        ):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_measurement_action_returns_a_scalar(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.mabl.scope_measure.v1",
                                {"item": "VPP", "source": "CHANnel1"}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"value": 2.5})  # placeholder

    def test_the_run_action_starts_acquisition_and_the_estop_stops_it(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.mabl.scope_run.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"trigger_status": "RUN"})  # placeholder
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client, ["trigger_status"])["trigger_status"], "STOP")  # placeholder


class Safety(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_estop_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main", ["trigger_status"])["trigger_status"], "RUN")  # placeholder
        driver.estop("test")
        self.assertEqual(driver.read("main", ["trigger_status"])["trigger_status"], "STOP")  # placeholder

    def test_the_identity_is_the_scope_of_this_driver(self) -> None:
        driver = self.driver()
        self.assertTrue(driver.read("main", ["identity"])["identity"].startswith("RIGOL TECHNOLOGIES,MSO"))


if __name__ == "__main__":
    unittest.main()
