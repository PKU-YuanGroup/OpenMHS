"""Acceptance run of the Flamingo stage package: the gate, plus cases for this driver.

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
MOVE = "x-cap.uw-loci.move_stage.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlamingoStageCases(unittest.TestCase):
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

    def move(self, client, x=2.5, y=3.5, z=4.5, r=30.0):
        return client.invoke(MOVE, {"x": x, "y": y, "z": z, "r": r}, **self.ids)

    def test_the_tracked_position_and_home_are_read(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position_x"], 0.0)      # the fake's placeholder start position
        self.assertEqual(state["position_y"], 0.0)
        self.assertEqual(state["position_z"], 0.0)
        self.assertEqual(state["rotation"], 0.0)
        self.assertEqual(state["home_x"], 5.0)          # the fake's placeholder home position
        self.assertEqual(state["home_y"], 5.0)
        self.assertEqual(state["home_z"], 5.0)
        self.assertEqual(state["home_rotation"], 45.0)

    def test_the_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position_x"], 0.0)

    def test_the_example_overlay_moves_all_axes(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"x": 2.5, "y": 3.5, "z": 4.5, "r": 30.0})
        state = self.state(client)
        self.assertEqual(state["position_x"], 2.5)
        self.assertEqual(state["position_y"], 3.5)
        self.assertEqual(state["position_z"], 4.5)
        self.assertEqual(state["rotation"], 30.0)

    def test_a_target_outside_the_overlay_is_refused(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.move(client, x=11.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position_x"], 0.0)

    def test_a_home_write_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = client.write("main", {"home_x": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["home_x"], 5.0)

    def test_the_example_overlay_writes_the_home(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        written = client.write("main", {"home_x": 2.0}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(self.state(client)["home_x"], 2.0)
        self.assertEqual(self.state(client)["home_y"], 5.0)

    def test_the_stop_action_reaches_the_native_stop(self) -> None:
        client = self.serve()
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_latches_and_blocks_a_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["position_x"], 0.0)


if __name__ == "__main__":
    unittest.main()
