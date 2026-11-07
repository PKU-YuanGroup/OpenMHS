"""Acceptance run of the NEJE laser 2 package: the gate, plus cases for what is specific to this driver.

The package code is model-authored and unreviewed; every case runs on the fake backend and nothing here opens a
serial port. Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
MOVE = "x-cap.beniroquai.move_xy.v1"
LASER = "x-cap.beniroquai.set_laser.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativeFrames(unittest.TestCase):
    """The driver reaches the fake's pyGraver methods with the values it was given."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_move_reaches_move_xy(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.move_xy(10, 20), {"x": 10, "y": 20})
        self.assertEqual(driver.native.location, [10, 20])
        self.assertIn(("moveXY", 10, 20), driver.native.frames)

    def test_laser_settings_reach_set_pwd(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.set_laser(12, 34), {"power": 12, "idle": 34})
        self.assertEqual((driver.native.power, driver.native.idle), (12, 34))
        self.assertIn(("setPWD", 12, 34), driver.native.frames)

    def test_pause_and_stop_reach_their_frames(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.pause_carving(), {"paused": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.stop_carving(), {"stopped": True})
        self.assertTrue(driver.native.stopped)
        self.assertIn(("pauseCarving",), driver.native.frames)
        self.assertIn(("stopCarving",), driver.native.frames)

    def test_the_progress_read_is_the_native_value(self) -> None:
        driver = self.driver()
        driver.native.carvingPercentProgress = 42        # test data for this case only
        self.assertEqual(driver.read("main", ["carving_progress"]), {"carving_progress": 42})


class Limits(unittest.TestCase):
    """The operator bounds are enforced before a native frame is sent."""

    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def invoke(self, client, capability, payload):
        receipt = client.invoke(capability, payload, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt

    def test_without_an_overlay_every_setting_is_unset(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, MOVE, {"x": 10, "y": 20}), UNSET)
        self.assertEqual(self.invoke(client, LASER, {"power": 10, "idle": 20}), UNSET)

    def test_the_example_overlay_admits_its_range_and_refuses_outside_it(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        move = self.invoke(client, MOVE, {"x": 10, "y": 20})
        self.assertEqual(move["status"], "completed")
        self.assertEqual(move["output"], {"x": 10, "y": 20})
        self.assertEqual(self.invoke(client, MOVE, {"x": 70000, "y": 20}), ENVELOPE)
        laser = self.invoke(client, LASER, {"power": 10, "idle": 20})
        self.assertEqual(laser["status"], "completed")
        self.assertEqual(laser["output"], {"power": 10, "idle": 20})
        self.assertEqual(self.invoke(client, LASER, {"power": 256, "idle": 20}), ENVELOPE)


if __name__ == "__main__":
    unittest.main()
