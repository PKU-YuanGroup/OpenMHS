"""Acceptance run of the Anritsu MS2830A package: the gate, plus cases for what is specific to this driver.

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


class AnritsuMS2830ACases(unittest.TestCase):
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

    def test_the_analyser_reads_its_scalar_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["identification"], "Anritsu,MS2830A,0000000000,1.00")
        self.assertEqual((state["power_marker_1"], state["power_marker_2"], state["power_marker_3"]),
                         (-30.0, -40.0, -50.0))
        self.assertEqual((state["frequency_start"], state["frequency_stop"]), (0.1, 1.0))
        self.assertEqual((state["frequency_span"], state["frequency_center"]), (0.9, 0.55))
        self.assertEqual(state["frequency_step"], 1000000.0)
        self.assertEqual(state["sweep_points"], 1001)
        self.assertEqual(state["timeout"], 3000.0)

    def test_the_numeric_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"frequency_center": 1.0}, {"sweep_points": 501}, {"timeout": 5.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        state = self.state(client)
        self.assertEqual((state["frequency_center"], state["sweep_points"], state["timeout"]),
                         (0.55, 1001, 3000.0))

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, frequency_center=1.0, sweep_points=501, timeout=5.0)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["frequency_center"], state["sweep_points"], state["timeout"]), (1.0, 501, 5.0))
        for patch in ({"frequency_center": 1.2}, {"sweep_points": 100}, {"timeout": 61.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual((state["frequency_center"], state["sweep_points"], state["timeout"]), (1.0, 501, 5.0))

    def test_the_estop_latches_and_reaches_the_native_write(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, frequency_center=1.0)["status"], "completed")
        client.estop("test", **self.ids)
        refused = self.configure(client, frequency_center=1.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
