"""Acceptance run of the ISDS205B package: the gate, plus cases for what is specific to this driver.

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


class Isds205bCases(unittest.TestCase):
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

    def test_the_reads_come_from_the_fake(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["sample_rate_hz"], 1000000)            # placeholder
        self.assertEqual(state["memory_length_kb"], 64)               # placeholder
        self.assertFalse(state["ch1_coupling_ac"])
        self.assertFalse(state["ch2_coupling_ac"])
        self.assertFalse(state["generator_enabled"])
        self.assertFalse(state["has_hard_trigger"])
        self.assertTrue(state["has_dds"])
        self.assertFalse(state["has_io"])
        self.assertGreater(state["ch1_voltage_resolution_v"], 0)     # placeholder
        self.assertGreater(state["ch2_voltage_resolution_v"], 0)     # placeholder

    def test_the_sample_rate_write_and_its_envelope(self) -> None:
        client = self.serve()
        applied = self.configure(client, sample_rate_hz=4000000)     # placeholder
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["sample_rate_hz"], 4000000)  # placeholder
        refused = self.configure(client, sample_rate_hz=2000000)     # placeholder
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["sample_rate_hz"], 4000000)  # unchanged

    def test_the_capture_returns_scalar_measurements(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.gridinwork.capture.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["samples"], 4)                       # placeholder
        self.assertEqual(output["sample_rate_hz"], 1000000)          # placeholder
        self.assertAlmostEqual(output["ch1_v_pp"], 2.0)              # placeholder
        self.assertAlmostEqual(output["ch2_v_pp"], 2.0)              # placeholder
        self.assertFalse(output["ch1_out_of_range"])
        self.assertFalse(output["ch2_out_of_range"])

    def test_the_range_action_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.gridinwork.set_input_range.v1",
                                {"channel": 0, "min_mv": -5000, "max_mv": 5000}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = client.invoke("x-cap.gridinwork.set_input_range.v1",
                                {"channel": 0, "min_mv": -5000, "max_mv": 5000}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertAlmostEqual(applied["output"]["voltage_resolution_v"], 10000 / 256.0)  # placeholder
        self.assertEqual(self.state(client)["ch1_voltage_resolution_v"], 10000 / 256.0)    # placeholder

        outside = client.invoke("x-cap.gridinwork.set_input_range.v1",
                                {"channel": 0, "min_mv": -6000, "max_mv": 5000}, **self.ids)
        self.assertEqual(outside["status"], "rejected", outside)
        self.assertEqual(outside["error"]["mhs_code"], ENVELOPE)

    def test_the_generator_enable_and_the_estop(self) -> None:
        client = self.serve()
        enabled = client.invoke("x-cap.gridinwork.generator_enable.v1", {"enable": True}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"], {"generator_enabled": True})
        self.assertTrue(self.state(client)["generator_enabled"])

        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["generator_enabled"])
        refused = client.invoke("x-cap.gridinwork.generator_enable.v1", {"enable": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused_write = self.configure(client, sample_rate_hz=8000000)   # placeholder
        self.assertEqual(refused_write["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
