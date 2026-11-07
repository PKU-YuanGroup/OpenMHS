"""Acceptance run of the pyzaber package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MOVE = "cap.motion.cartesian_pose.v1"
HOME = "x-cap.hgomersall.home_axes.v1"
STOP = "x-cap.hgomersall.stop_motion.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PyzaberCases(unittest.TestCase):
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

    def move(self, client, x, y, z):
        return client.invoke(MOVE, {"position": {"x": x, "y": y, "z": z}}, **self.ids)

    def test_the_reads_show_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"], state["z_mm"]), (10.0, 20.0, 30.0))

    def test_a_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client, 100.0, 50.0, 20.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_mm"], 10.0)

    def test_the_example_overlay_supplies_the_workspace(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client, 100.0, 50.0, 20.0)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 50.0, "z": 20.0})
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"], state["z_mm"]), (100.0, 50.0, 20.0))
        for payload in ((-1.0, 50.0, 20.0), (301.0, 50.0, 20.0),
                        (100.0, -1.0, 20.0), (100.0, 301.0, 20.0),
                        (100.0, 50.0, -1.0), (100.0, 50.0, 201.0)):
            refused = self.move(client, *payload)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"], state["z_mm"]), (100.0, 50.0, 20.0))

    def test_home_returns_the_axes_to_the_reference(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"]["homed"], True)
        self.assertEqual(homed["output"]["axes"], ["x", "y", "z"])
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"], state["z_mm"]), (0.0, 0.0, 0.0))

    def test_the_stop_and_the_estop_reach_the_native_stop_and_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["stopped"], True)
        client.estop("test", **self.ids)
        refused = self.move(client, 100.0, 50.0, 20.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_estop_calls_the_native_emergency_stop(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.native._stop_calls, 0)
        driver.estop("test")
        self.assertGreaterEqual(driver.native._stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
