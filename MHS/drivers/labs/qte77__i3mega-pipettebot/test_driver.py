"""Acceptance run of the i3 Mega pipettebot package: the gate, plus cases for this driver.

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
MOVE = "cap.motion.cartesian_pose.v1"
HOME = "cap.motion.home.v1"
EMERGENCY_STOP = "x-cap.qte77.emergency_stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class I3megaPipettebotCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def move(self, client, x, y, z):
        return client.invoke(MOVE, {"position": {"x": x, "y": y, "z": z}}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_come_from_the_firmware_position(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x"], state["y"], state["z"]), (0.0, 0.0, 0.0))

    def test_the_workspace_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client, 50.0, 50.0, 50.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_moves_and_reads_back(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client, 100.0, 110.5, 5.25)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["reached"], True)
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 110.5, "z": 5.25})
        state = self.state(client)
        self.assertEqual((state["x"], state["y"], state["z"]), (100.0, 110.5, 5.25))

    def test_the_example_overlay_refuses_outside_the_envelope(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for position in ((220.5, 100.0, 50.0), (100.0, -0.5, 50.0), (100.0, 100.0, 180.5)):
            refused = self.move(client, *position)
            self.assertEqual(refused["status"], "rejected", position)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, position)
        state = self.state(client)
        self.assertEqual((state["x"], state["y"], state["z"]), (0.0, 0.0, 0.0))

    def test_home_references_x_and_y_and_leaves_z(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.move(client, 100.0, 110.5, 5.25)["status"], "completed")
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"], {"homed": True, "axes": ["x", "y"]})
        state = self.state(client)
        self.assertEqual((state["x"], state["y"], state["z"]), (0.0, 0.0, 5.25))

    def test_the_emergency_stop_action_halts(self) -> None:
        client = self.serve()
        halted = client.invoke(EMERGENCY_STOP, {}, **self.ids)
        self.assertEqual(halted["status"], "completed", halted)
        self.assertEqual(halted["output"], {"halted": True})

    def test_the_estop_latches_and_refuses_the_next_move(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.move(client, 50.0, 50.0, 50.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
