"""Acceptance run of the oscilloscope_mcp package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OscilloscopeCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_exposes_the_settings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["initialized"])
        self.assertFalse(state["acquisition_active"])
        self.assertGreater(state["channel_count"], 0)
        self.assertGreater(state["sample_rate_hz"], 0)
        self.assertEqual(state["coupling"], "DC")
        self.assertEqual(state["impedance"], "1M")
        self.assertEqual(state["trigger_type"], "edge")

    def test_a_write_reaches_the_fake_and_reads_back(self) -> None:
        client = self.serve()
        receipt = self.configure(client, voltage_range_v=2.5)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["voltage_range_v"], 2.5)
        receipt = self.configure(client, sample_rate_hz=1.0e6)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["sample_rate_hz"], 1.0e6)

    def test_an_out_of_envelope_write_is_refused(self) -> None:
        client = self.serve()
        refused = self.configure(client, sample_rate_hz=2.0e9)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertNotEqual(self.state(client)["sample_rate_hz"], 2.0e9)

    def test_the_example_overlay_fills_the_trigger_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(
            "x-cap.manasp21.setup_trigger.v1",
            {"source": "channel0", "trigger_type": "edge", "level": 1.5, "edge": "rising", "holdoff": 0.1},
            **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["level"], 1.5)
        state = self.state(client)
        self.assertEqual((state["trigger_source"], state["trigger_type"]), ("channel0", "edge"))
        self.assertEqual(state["trigger_level_v"], 1.5)

    def test_the_timeout_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.manasp21.acquire_waveform.v1",
                                {"channel": 0, "timeout": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_acquisition_reports_scalar_measurements(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.manasp21.acquire_waveform.v1",
                                {"channel": 0, "timeout": 1.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["channel"], 0)
        self.assertGreater(output["sample_count"], 0)
        self.assertGreater(output["sample_rate_hz"], 0)
        self.assertLessEqual(output["minimum_voltage_v"], output["maximum_voltage_v"])
        self.assertGreaterEqual(output["rms_voltage_v"], 0)
        self.assertFalse(self.state(client)["acquisition_active"])

    def test_the_safe_state_action_stops_the_acquisition(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.manasp21.stop_acquisition.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["acquisition_active"])

    def test_the_estop_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.configure(client, voltage_range_v=2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
