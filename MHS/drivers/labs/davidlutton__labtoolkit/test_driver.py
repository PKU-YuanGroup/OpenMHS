"""Acceptance run of the Agilent PSA package: the gate, plus cases for what is specific to this driver.

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


class AgilentPsaCases(unittest.TestCase):
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

    def test_the_analyser_reads_its_sweep_settings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["identification"], "Agilent Technologies,E4440A,US00000000,A.14.00")
        self.assertEqual((state["frequency_center"], state["frequency_span"]), (1.0e9, 10.0e6))
        self.assertEqual(state["sweep_points"], 1001)
        self.assertEqual((state["resolution_bandwidth"], state["video_bandwidth"]), (1.0e6, 1.0e6))
        self.assertTrue(state["continuous"])

    def test_the_sweep_points_are_bounded_by_the_class_comment(self) -> None:
        client = self.serve()
        for value in (100, 8193):
            refused = self.configure(client, sweep_points=value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["sweep_points"], 1001)              # untouched by the refusals
        applied = self.configure(client, sweep_points=2048)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"]["applied"], {"sweep_points": 2048})
        self.assertEqual(self.state(client)["sweep_points"], 2048)

    def test_the_frequency_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, frequency_center=950e6)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["frequency_center"], 1.0e9)         # the fake's value, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, frequency_center=950e6, frequency_span=5e6)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["frequency_center"], 950e6)
        self.assertEqual(self.state(client)["frequency_span"], 5e6)
        for patch in ({"frequency_center": 800e6}, {"frequency_span": 30e6}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["frequency_center"], 950e6)

    def test_the_stop_sweep_action_and_the_estop(self) -> None:
        client = self.serve()
        stopped = client.invoke("x-cap.davidlutton.stop_sweep.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"continuous": False})
        self.assertFalse(self.state(client)["continuous"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["continuous"])
        refused = self.configure(client, continuous=True)                        # latched
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
