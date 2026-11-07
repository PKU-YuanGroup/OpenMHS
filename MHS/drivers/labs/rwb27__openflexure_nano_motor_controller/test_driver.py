"""Acceptance run of the OpenFlexure stage package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data (see fake.py), so the cases
assert what a move changes, not the canned numbers themselves.
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


class OpenFlexureStageCases(unittest.TestCase):
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

    def test_the_reads_describe_the_fake_stage(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(len(state["position"]), 3)
        self.assertEqual(len(state["endstop_status"]), 3)
        self.assertEqual(len(state["endstop_maxima"]), 3)
        self.assertIsInstance(state["step_time"], int)
        self.assertIsInstance(state["ramp_time"], int)
        self.assertIn("OpenFlexure", state["firmware"])

    def test_motion_waits_for_the_site(self) -> None:
        client = self.serve()
        before = self.state(client)["position"]
        refused = client.invoke("x-cap.rwb27.move_relative.v1", {"displacement": [10, 0, 0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], before)

    def test_the_example_overlay_allows_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        start = self.state(client)["position"]
        moved = client.invoke("x-cap.rwb27.move_relative.v1", {"displacement": [10, 0, 0]}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], [start[0] + 10, start[1], start[2]])
        absolute = client.invoke("x-cap.rwb27.move_absolute.v1", {"target_position": [0, 0, 0]}, **self.ids)
        self.assertEqual(absolute["status"], "completed")
        self.assertEqual(self.state(client)["position"], [0, 0, 0])
        focused = client.invoke("x-cap.rwb27.focus_relative.v1", {"z": 5}, **self.ids)
        self.assertEqual(focused["status"], "completed")
        self.assertEqual(self.state(client)["position"][2], 5)
        outside = client.invoke("x-cap.rwb27.move_relative.v1", {"displacement": [1001, 0, 0]}, **self.ids)
        self.assertEqual(outside["error"]["mhs_code"], ENVELOPE)

    def test_homing_sets_the_selected_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.rwb27.move_relative.v1", {"displacement": [10, 20, 30]}, **self.ids)
        homed = client.invoke("x-cap.rwb27.home.v1", {"direction": "min", "axes": ["x"]}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertTrue(homed["output"]["homed"])
        self.assertEqual(self.state(client)["position"][0], 0)
        self.assertEqual(self.state(client)["position"][1:], [20, 30])

    def test_release_is_the_safe_state_action(self) -> None:
        client = self.serve()
        released = client.invoke("x-cap.rwb27.release_motors.v1", {}, **self.ids)
        self.assertEqual(released["status"], "completed")
        self.assertTrue(released["output"]["released"])

    def test_the_estop_latches_and_refuses_motion(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.rwb27.move_relative.v1", {"displacement": [10, 0, 0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
