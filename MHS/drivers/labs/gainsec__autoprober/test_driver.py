"""Acceptance run of the AutoProber CNC package: the gate, plus cases for this driver.

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
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

MOVE_ABSOLUTE = "x-cap.gainsec.move_absolute.v1"
MOVE_RELATIVE = "x-cap.gainsec.move_relative.v1"
READ_SETTINGS = "x-cap.gainsec.read_settings.v1"
UNLOCK = "x-cap.gainsec.unlock.v1"
STOP = "cap.motion.stop.v1"
HOME = "x-cap.gainsec.home.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AutoProberCncCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def overlay(self):
        return self.serve(str(HERE / "site-limits.example.json"))

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_are_fresh_status_queries(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["state"], "Idle")
        self.assertEqual((state["position_x"], state["position_y"], state["position_z"]), (0.0, 0.0, 0.0))
        self.assertEqual(state["limit_pins"], [])
        self.assertIn("MPos:0.000,0.000,0.000", state["status_line"])

    def test_a_move_needs_the_site_travel_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke(MOVE_ABSOLUTE, {"x_mm": 1, "y_mm": 1, "z_mm": 0, "feed_mm_min": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position_x"], 0.0)

    def test_the_example_overlay_bounds_an_absolute_move(self) -> None:
        client = self.overlay()
        moved = client.invoke(MOVE_ABSOLUTE, {"x_mm": 5, "y_mm": -4, "z_mm": 1, "feed_mm_min": 500}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(
            (moved["output"]["x_mm"], moved["output"]["y_mm"], moved["output"]["z_mm"]),
            (5.0, -4.0, 1.0),
        )
        self.assertEqual(moved["output"]["state"], "Idle")
        refused = client.invoke(MOVE_ABSOLUTE, {"x_mm": 50, "y_mm": 0, "z_mm": 0, "feed_mm_min": 500}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        self.assertEqual(self.state(client)["position_x"], 5.0)

    def test_a_relative_move_reaches_the_fake_and_an_empty_move_is_refused(self) -> None:
        client = self.overlay()
        moved = client.invoke(MOVE_RELATIVE, {"dx_mm": 2, "dy_mm": 0, "dz_mm": 0, "feed_mm_min": 300}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["x_mm"], 2.0)
        empty = client.invoke(MOVE_RELATIVE, {"dx_mm": 0, "dy_mm": 0, "dz_mm": 0, "feed_mm_min": 300}, **self.ids)
        self.assertEqual(empty["status"], "failed", empty)
        self.assertEqual(empty["error"]["mhs_code"], PRECONDITION)

    def test_home_and_the_settings_read(self) -> None:
        client = self.overlay()
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"]["homed"], True)
        settings = client.invoke(READ_SETTINGS, {}, **self.ids)
        self.assertEqual(settings["status"], "completed", settings)
        self.assertEqual(settings["output"]["settings"]["110"], "500.000")

    def test_a_feed_hold_write_cannot_confirm_the_estop(self) -> None:
        client = self.overlay()
        stopped = client.estop("test feed hold", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(self.state(client)["state"], "Hold")
        for capability in (MOVE_ABSOLUTE, HOME, UNLOCK):
            refused = client.invoke(capability, {}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_stop_capability_does_not_report_sensed_standstill(self) -> None:
        client = self.overlay()
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(self.state(client)["state"], "Hold")

    def test_alarm_unlock_does_not_resume_the_fake_feed_hold(self) -> None:
        client = self.overlay()
        client.invoke(STOP, {}, **self.ids)
        unlocked = client.invoke(UNLOCK, {}, **self.ids)
        self.assertEqual(unlocked["status"], "completed", unlocked)
        self.assertEqual(unlocked["output"]["state"], "Hold")


if __name__ == "__main__":
    unittest.main()
