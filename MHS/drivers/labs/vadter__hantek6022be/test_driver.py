"""Acceptance run of the Hantek package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HantekCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_the_defaults_and_the_acquisition_summary(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["sample_rate"], 16_000_000)                 # the upstream default
        self.assertEqual((state["ch1_vdiv"], state["ch2_vdiv"]), (1.0, 1.0))
        summary = state["acquisition"]
        self.assertGreater(summary["sample_count"], 0)
        self.assertAlmostEqual(summary["duration_s"],
                               summary["sample_count"] / state["sample_rate"], places=12)
        for channel in (1, 2):
            minimum = summary[f"channel{channel}_min_v"]
            maximum = summary[f"channel{channel}_max_v"]
            rms = summary[f"channel{channel}_rms_v"]
            self.assertLessEqual(minimum, maximum)
            self.assertGreaterEqual(rms, 0.0)
            self.assertLessEqual(rms, max(abs(minimum), abs(maximum)))

    def test_the_sample_rate_write_reaches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, sample_rate=8_000_000)["status"], "completed")
        self.assertEqual(self.state(client)["sample_rate"], 8_000_000)
        # 3 MS/s is not in the samplerate table, and 50 kS/s is in get_rates() but not in dictN_SR.
        for value in (3_000_000, 50_000):
            refused = self.configure(client, sample_rate=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["sample_rate"], 8_000_000)

    def test_the_vertical_division_write_reaches_the_fake(self) -> None:
        client = self.serve()
        before = self.state(client)["acquisition"]["channel1_max_v"]
        self.assertEqual(self.configure(client, ch1_vdiv=0.5)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["ch1_vdiv"], state["ch2_vdiv"]), (0.5, 1.0))
        self.assertLess(state["acquisition"]["channel1_max_v"], before)
        refused = self.configure(client, ch2_vdiv=2.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["ch2_vdiv"], 1.0)

    def test_the_estop_reaches_the_fake_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.configure(client, sample_rate=8_000_000)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["sample_rate"], 16_000_000)   # the fake keeps the last acquisition


if __name__ == "__main__":
    unittest.main()
