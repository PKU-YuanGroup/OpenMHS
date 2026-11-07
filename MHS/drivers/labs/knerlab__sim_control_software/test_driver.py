"""Acceptance run of the knerlab motorized polarizer package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
TARGET_RAD = math.radians(90.0)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PolarizerCases(unittest.TestCase):
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

    def move(self, client, radians):
        return client.invoke("cap.motion.joint_position.v1", {"joint_positions": [radians]}, **self.ids)

    def test_the_position_is_read_in_degrees(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["position"], 0.0)      # the fake's placeholder start position

    def test_the_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = self.move(client, 0.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)

    def test_the_example_overlay_moves_the_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = self.move(client, TARGET_RAD)
        self.assertEqual(done["status"], "completed", done)
        self.assertTrue(done["output"]["reached"])
        self.assertAlmostEqual(done["output"]["joint_positions"][0], TARGET_RAD, places=9)
        self.assertAlmostEqual(self.state(client)["position"], 90.0, places=9)

    def test_a_negative_target_is_converted_to_degrees(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = self.move(client, math.radians(-45.0))
        self.assertEqual(done["status"], "completed", done)
        self.assertAlmostEqual(self.state(client)["position"], -45.0, places=9)

    def test_the_stop_action_reaches_the_native_stop(self) -> None:
        client = self.serve()
        # The class's optional deceleration is accepted and ignored: the native stop has no profile argument.
        stopped = client.invoke("cap.motion.stop.v1", {"deceleration": 2.0}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertTrue(stopped["output"]["stopped"])
        self.assertIn("position_deg", stopped["output"]["stopped_position"])

    def test_the_estop_stops_the_axis_and_latches(self) -> None:
        client = self.serve()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        refused = self.move(client, TARGET_RAD)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
