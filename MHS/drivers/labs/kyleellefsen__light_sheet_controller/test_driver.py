"""Acceptance run of the light sheet controller package: the gate, plus cases for this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LightSheetCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_scan_starts_and_stops(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["stopped"])
        self.assertEqual(state["sample_rate"], 5000.0)             # the fake's placeholder sample rate
        started = client.invoke("x-cap.kyleellefsen.start_scan.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"running": True})
        self.assertFalse(self.state(client)["stopped"])
        stopped = client.invoke("x-cap.kyleellefsen.stop_scan.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"stopped": True, "blue_laser_on": False})
        self.assertTrue(self.state(client)["stopped"])

    def test_numeric_settings_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, n_steps=8)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, n_steps=8, step_duration=12.5)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["n_steps"], 8)
        self.assertEqual(state["step_duration"], 12.5)
        refused = self.configure(client, n_steps=2000)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_laser_selection_and_the_estop(self) -> None:
        client = self.serve()
        selected = client.invoke("x-cap.kyleellefsen.select_laser.v1", {"laser": "blue"}, **self.ids)
        self.assertEqual(selected["output"], {"blue_laser_on": True})
        self.assertTrue(self.state(client)["blue_laser_on"])
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        state = self.state(client)
        self.assertTrue(state["stopped"])
        self.assertFalse(state["blue_laser_on"])
        refused = client.invoke("x-cap.kyleellefsen.start_scan.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_goto_zero_and_goto_end_stop_the_scan(self) -> None:
        client = self.serve()
        client.invoke("x-cap.kyleellefsen.start_scan.v1", {}, **self.ids)
        zeroed = client.invoke("x-cap.kyleellefsen.goto_zero.v1", {}, **self.ids)
        self.assertEqual(zeroed["output"], {"stopped": True})
        client.invoke("x-cap.kyleellefsen.start_scan.v1", {}, **self.ids)
        ended = client.invoke("x-cap.kyleellefsen.goto_end.v1", {}, **self.ids)
        self.assertEqual(ended["output"], {"stopped": True})
        self.assertTrue(self.state(client)["stopped"])

    def test_the_scan_mode_action_sets_both_flags(self) -> None:
        client = self.serve()
        applied = client.invoke("x-cap.kyleellefsen.set_scan_mode.v1",
                                {"triangle_scan": True, "alternate_lasers": False}, **self.ids)
        self.assertEqual(applied["output"],
                         {"triangle_scan": True, "alternate_lasers": False})
        state = self.state(client)
        self.assertTrue(state["triangle_scan"])
        self.assertFalse(state["alternate_lasers"])


if __name__ == "__main__":
    unittest.main()
