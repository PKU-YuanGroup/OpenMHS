"""Acceptance run of the CubOS gantry package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

HOME = "x-cap.ursa-laboratories.home_axes.v1"
STOP = "x-cap.ursa-laboratories.stop_motion.v1"
RESUME = "x-cap.ursa-laboratories.resume_motion.v1"
MOVE = "cap.motion.cartesian_pose.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CubosGantryCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_driver(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def move(self, client, x=100.0, y=50.0, z=20.0):
        return client.invoke(MOVE, {"position": {"x": x, "y": y, "z": z}}, **self.ids)

    def test_the_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_enables_the_envelope(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 50.0, "z": 20.0})
        self.assertEqual(self.state(client)["position"], {"x": 100.0, "y": 50.0, "z": 20.0})

    def test_a_target_outside_the_envelope_is_refused(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.move(client, x=900.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_home_sets_the_reference(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.move(client)["status"], "completed")
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertTrue(homed["output"]["homed"])
        self.assertEqual(self.state(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_stop_halts_and_the_estop_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertTrue(stopped["output"]["stopped"])
        self.assertEqual(self.state(client)["status"], "Hold")

        client.estop("test", **self.ids)
        refused = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_reset_rearms_nothing_and_names_the_reenable(self) -> None:
        driver, client = self.serve_driver(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        self.assertGreaterEqual(driver.native._stops, 1)

        refused = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(driver.native._resumes, 0)

        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["reenable"], RESUME)
        self.assertIs(reset["output"]["resumed"], False)
        self.assertEqual(driver.native._resumes, 0)
        self.assertEqual(self.state(client)["status"], "Hold")
        moved = self.move(client)
        self.assertEqual(moved["status"], "failed", moved)

        resumed = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertTrue(resumed["output"]["resumed"])
        self.assertEqual(driver.native._resumes, 1)
        self.assertEqual(self.move(client)["status"], "completed")

    def test_the_manifest_declares_the_independent_stop_and_the_reenable(self) -> None:
        client = self.serve()
        manifest = next(item for item in client.devices() if item["device_id"] == self.ids["device_id"])
        safety = manifest["safety"]
        self.assertEqual(safety["estop"]["reenable"], RESUME)
        self.assertIn(STOP, safety["safe_state"]["achieved_by"])
        self.assertNotIn(RESUME, safety["safe_state"]["achieved_by"])
        self.assertTrue(safety["estop"].get("physical_ref"))

    def test_motion_is_not_queued_while_held_after_reset(self) -> None:
        driver, client = self.serve_driver(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        calls = []
        # The real methods send commands before discovering Hold. An accepting
        # stand-in exposes a missing driver guard without copying the planner.
        driver.native.move_to = lambda *args: calls.append(("move_to", args))
        driver.native.home = lambda: calls.append(("home", ()))
        for capability, payload in ((MOVE, {"position": {"x": 1, "y": 2, "z": 3}}), (HOME, {})):
            with self.subTest(capability=capability):
                receipt = client.invoke(capability, payload, **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
                self.assertEqual(calls, [])

    def test_motion_requires_a_recognized_controller_state(self) -> None:
        driver, client = self.serve_driver(str(HERE / "site-limits.example.json"))
        calls = []
        driver.native.get_status = lambda: ""
        driver.native.move_to = lambda *args: calls.append(args)
        receipt = self.move(client)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        self.assertEqual(calls, [])

    def test_idle_status_frames_allow_moves_and_alarm_allows_homing(self) -> None:
        driver, client = self.serve_driver(str(HERE / "site-limits.example.json"))
        driver.native.get_status = lambda: "<Idle|WPos:0,0,0>"  # placeholder coordinates
        self.assertEqual(self.move(client)["status"], "completed")
        driver.native.get_status = lambda: "<Alarm|WPos:0,0,0>"  # placeholder coordinates
        self.assertEqual(client.invoke(HOME, {}, **self.ids)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
