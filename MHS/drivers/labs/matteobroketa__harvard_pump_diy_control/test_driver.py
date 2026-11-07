"""Acceptance run of the Harvard PHD 2000 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The fake numbers are test data, not device facts.
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


class HarvardPHD2000Cases(unittest.TestCase):
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

    def test_the_fake_starts_stopped_with_a_reported_rate_and_diameter(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 1.0)              # placeholder value of the fake
        self.assertEqual(state["direction"], "infuse")
        self.assertFalse(state["running"])
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["syringe_diameter_mm"], 12.0)   # placeholder value of the fake
        self.assertEqual(state["address"], 0)                  # placeholder value of the fake

    def test_the_numeric_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"flow_rate": 5.0}, {"syringe_diameter_mm": 12.5}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        self.assertEqual(self.state(client)["flow_rate"], 1.0)
        self.assertEqual(self.state(client)["syringe_diameter_mm"], 12.0)

    def test_the_example_overlay_supplies_the_numeric_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, flow_rate=5.0, syringe_diameter_mm=12.5)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 5.0)
        self.assertEqual(state["syringe_diameter_mm"], 12.5)
        for patch in ({"flow_rate": 0.5}, {"flow_rate": 700.0},
                      {"syringe_diameter_mm": 0.05}, {"syringe_diameter_mm": 60.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["flow_rate"], 5.0)
        self.assertEqual(self.state(client)["syringe_diameter_mm"], 12.5)

    def test_the_direction_write_and_the_run_pause_resume_actions(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, direction="withdraw")["status"], "completed")
        self.assertEqual(self.state(client)["direction"], "withdraw")
        started = client.invoke("x-cap.matteobroketa.run_pump.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"status": "withdrawing"})
        self.assertTrue(self.state(client)["running"])
        paused = client.invoke("x-cap.matteobroketa.pause_pump.v1", {}, **self.ids)
        self.assertEqual(paused["output"], {"status": "stopped"})
        self.assertFalse(self.state(client)["running"])
        resumed = client.invoke("x-cap.matteobroketa.resume_pump.v1", {}, **self.ids)
        self.assertEqual(resumed["output"], {"status": "withdrawing"})
        stopped = client.invoke("x-cap.matteobroketa.stop_pump.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"status": "stopped"})
        self.assertFalse(self.state(client)["running"])

    def test_the_estop_stops_the_pump_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.matteobroketa.run_pump.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        self.assertEqual(self.state(client)["status"], "stopped")
        refused = client.invoke("x-cap.matteobroketa.run_pump.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
