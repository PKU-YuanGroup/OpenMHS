"""Acceptance run of the liquid-handling x-axis package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
MOVE = "x-cap.ethanjli.axis_move.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class XAxisCases(unittest.TestCase):
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

    def test_the_reads_are_the_axis_positions(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["physical_position"], 0.0)     # the fake start position
        self.assertEqual(state["sensor_position"], 0.0)       # the fake start position

    def test_a_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(MOVE, {"delta_cm": 0.5}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["physical_position"], 0.0)

    def test_the_example_overlay_supplies_the_travel_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(MOVE, {"delta_cm": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["moved_cm"], 0.5)
        self.assertEqual(receipt["output"]["physical_position"], 0.5)
        self.assertEqual(self.state(client)["physical_position"], 0.5)
        for value in (-1.01, 1.01):
            refused = client.invoke(MOVE, {"delta_cm": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["physical_position"], 0.5)

    def test_the_estop_latches_and_blocks_the_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.invoke(MOVE, {"delta_cm": 0.25}, **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        refused = client.invoke(MOVE, {"delta_cm": 0.25}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
