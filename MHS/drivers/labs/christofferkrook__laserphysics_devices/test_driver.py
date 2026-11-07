"""Acceptance run of the Ando OSA package: the gate, plus cases for what is specific to this driver.

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


class AndoOSACases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["start_wl"], 400.0)
        self.assertEqual(state["stop_wl"], 1600.0)
        self.assertEqual(state["center_wl"], 1000.0)
        self.assertEqual(state["span"], 1200.0)
        self.assertEqual(state["averages"], 2)
        self.assertEqual(state["resolution"], 0.1)
        self.assertEqual(state["scale"], "LOG")
        self.assertEqual(state["current_trace"], "B")
        self.assertEqual((state["display_on"], state["write_enabled"]), (False, False))
        self.assertEqual(state["sweep_status"], "SINGLE")

    def test_the_sourced_writes_reach_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, scale="LIN")["status"], "completed")
        self.assertEqual(self.configure(client, current_trace="A")["status"], "completed")
        self.assertEqual(self.configure(client, resolution=0.05)["status"], "completed")
        self.assertEqual(self.configure(client, sweep_status="AUTO")["status"], "completed")
        self.assertEqual(self.configure(client, display_on=True, write_enabled=True)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["scale"], "LIN")
        self.assertEqual(state["current_trace"], "A")
        self.assertEqual(state["resolution"], 0.05)
        self.assertEqual(state["sweep_status"], "AUTO")
        self.assertEqual((state["display_on"], state["write_enabled"]), (True, True))

    def test_the_wavelength_and_average_ranges_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, start_wl=600)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["start_wl"], 400.0)
        self.assertEqual(self.configure(client, averages=10)["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, start_wl=600)["status"], "completed")
        self.assertEqual(self.configure(client, stop_wl=1550, center_wl=1000, span=500)["status"], "completed")
        self.assertEqual(self.configure(client, averages=20)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["start_wl"], state["stop_wl"]), (600.0, 1550.0))
        self.assertEqual((state["center_wl"], state["span"], state["averages"]), (1000.0, 500.0, 20))
        for value in (2000, 200):
            self.assertEqual(self.configure(client, start_wl=value)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["start_wl"], 600.0)

    def test_the_estop_stops_the_sweep_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, sweep_status="AUTO")["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["sweep_status"], "STOP")
        refused = self.configure(client, scale="LIN")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
