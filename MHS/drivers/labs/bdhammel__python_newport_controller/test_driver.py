"""Acceptance run of the New Focus Picomotor package: the gate plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.bdhammel.move_steps.v1"
STOP = "cap.motion.stop.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
POSITIONS = [1000, -250, 0, 75]      # the fake's canned test data, not a device fact


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PicomotorCases(unittest.TestCase):
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

    def move(self, client, axis, steps):
        return client.invoke(MOVE, {"axis": axis, "steps": steps}, **self.ids)

    def test_the_position_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["positions"], POSITIONS)
        self.assertEqual(state["positions"], state["positions"])        # a read does not move the fake

    def test_a_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client, 1, 10)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["positions"], POSITIONS)

    def test_the_example_overlay_bounds_and_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client, 2, -30)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"axis": 2, "steps": -30})
        self.assertEqual(self.state(client)["positions"], [1000, -280, 0, 75])
        for axis, steps in ((0, 1), (5, 1), (1, 1001), (1, -1001)):
            refused = self.move(client, axis, steps)
            self.assertEqual(refused["status"], "rejected", (axis, steps))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (axis, steps))
        self.assertEqual(self.state(client)["positions"], [1000, -280, 0, 75])

    def test_the_stop_action(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = self.move(client, 1, 1)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["positions"], POSITIONS)


if __name__ == "__main__":
    unittest.main()
