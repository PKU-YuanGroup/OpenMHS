"""Acceptance run of the MS-2000 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.thedeanlab.move_axis_absolute.v1"
STOP_SCAN = "x-cap.thedeanlab.stop_scan.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MS2000Cases(unittest.TestCase):
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

    def test_the_reads_are_the_three_axes(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_position"], state["y_position"], state["z_position"]), (0.0, 0.0, 0.0))

    def test_a_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(MOVE, {"axis": "x", "position": 12.5}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_position"], 0.0)          # the placeholder start, untouched

    def test_the_example_overlay_supplies_the_travel_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(MOVE, {"axis": "x", "position": 12.5}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["axis"], "x")
        self.assertEqual(moved["output"]["position"], 12.5)
        self.assertEqual(self.state(client)["x_position"], 12.5)
        refused = client.invoke(MOVE, {"axis": "x", "position": 1000.5}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["x_position"], 12.5)

    def test_the_stop_scan_action_completes(self) -> None:
        client = self.serve()
        receipt = client.invoke(STOP_SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["stopped"], True)

    def test_the_estop_latches_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = client.invoke(MOVE, {"axis": "y", "position": 5.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
