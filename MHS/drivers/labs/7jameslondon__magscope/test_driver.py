"""Acceptance run of the MagScope focus driver: the gate, plus cases specific to this package.

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


class MagscopeFocusCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_target_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.write("main", {"target_z": 10.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["current_z"], 0.0)          # the fake's placeholder start, untouched

    def test_the_example_overlay_supplies_the_travel_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        written = client.write("main", {"target_z": 12.5}, **self.ids)
        self.assertEqual(written["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["current_z"], 12.5)                       # micrometres, converted from the native nm
        self.assertEqual(state["target_z"], 12.5)
        for value in (-100.01, 100.01):
            refused = client.write("main", {"target_z": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["current_z"], 12.5)

    def test_the_manual_focus_action_moves_the_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("cap.imaging.focus.v1",
                              {"method": "manual", "target_z": 20.0}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"focused": True, "z_um": 20.0})
        self.assertEqual(self.state(client)["current_z"], 20.0)
        read_only = client.invoke("cap.imaging.focus.v1", {"method": "none"}, **self.ids)
        self.assertEqual(read_only["output"], {"focused": True, "z_um": 20.0})

    def test_the_estop_holds_the_reported_position_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.write("main", {"target_z": 7.0}, **self.ids)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual(state["current_z"], 7.0)
        self.assertEqual(state["target_z"], 7.0)                         # the stop commanded the axis to its position
        refused = client.write("main", {"target_z": 8.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
