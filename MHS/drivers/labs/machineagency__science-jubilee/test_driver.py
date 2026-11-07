"""Acceptance run of the Science Jubilee package: the gate, plus cases for what is specific to this driver.

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
POSE = "cap.motion.cartesian_pose.v1"
HOME = "cap.motion.home.v1"
TOOL_OFFSET = "x-cap.machineagency.set_tool_offset.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ScienceJubileeCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def example_overlay(self):
        return str(HERE / "site-limits.example.json")

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_position_reads_are_mm(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_position"], state["y_position"], state["z_position"]), (0.0, 0.0, 0.0))

    def test_a_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke(POSE, {"position": {"x": 100, "y": 50, "z": 20}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_position"], 0.0)

    def test_the_example_overlay_moves_and_bounds_the_pose(self) -> None:
        client = self.serve(self.example_overlay())
        moved = client.invoke(POSE, {"position": {"x": 100, "y": 50, "z": 20}}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(self.state(client)["x_position"], 100.0)
        refused = client.invoke(POSE, {"position": {"x": 314, "y": 50, "z": 20}}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["x_position"], 100.0)

    def test_home_of_the_named_axes_and_of_all_axes(self) -> None:
        client = self.serve(self.example_overlay())
        client.invoke(POSE, {"position": {"x": 100, "y": 50, "z": 20}}, **self.ids)
        named = client.invoke(HOME, {"axes": ["x", "y"]}, **self.ids)
        self.assertEqual(named["status"], "completed", named)
        self.assertEqual((self.state(client)["x_position"], self.state(client)["y_position"]), (0.0, 0.0))
        all_axes = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(all_axes["output"]["axes"], ["x", "y", "z", "u"])

    def test_the_tool_offset_needs_the_site_and_returns_what_it_applied(self) -> None:
        without = self.serve()
        refused = without.invoke(TOOL_OFFSET, {"tool_index": 0, "x": -1.4, "y": 49.88, "z": -8.8}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        with_overlay = self.serve(self.example_overlay())
        applied = with_overlay.invoke(TOOL_OFFSET, {"tool_index": 0, "x": -1.4, "y": 49.88, "z": -8.8}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"],
                         {"tool_index": 0, "x": -1.4, "y": 49.88, "z": -8.8})

    def test_the_estop_latches_every_actuation(self) -> None:
        client = self.serve(self.example_overlay())
        client.estop("test", **self.ids)
        refused = client.invoke(POSE, {"position": {"x": 100, "y": 50, "z": 20}}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
