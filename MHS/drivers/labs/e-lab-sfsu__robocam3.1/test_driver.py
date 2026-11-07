"""Acceptance run of the RoboCam camera package: the gate, plus cases for this driver.

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


class RoboCamCases(unittest.TestCase):
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

    def test_the_operator_limits_and_the_sourced_usb_range(self) -> None:
        client = self.serve()
        for field in ("exposure_us", "gain", "offset", "sensor_mode_index"):
            refused = self.configure(client, **{field: 1})
            self.assertEqual(refused["status"], "rejected", field)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, field)

        applied = self.configure(client, usb_bandwidth_percent=80)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["usb_bandwidth_percent"], 80)
        for value in (34, 101):
            refused = self.configure(client, usb_bandwidth_percent=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["usb_bandwidth_percent"], 80)

        enabled = self.configure(client, ae_enabled=True, hqi=True)
        self.assertEqual(enabled["status"], "completed")
        state = self.state(client)
        self.assertTrue(state["ae_enabled"])
        self.assertTrue(state["hqi"])

    def test_the_example_overlay_supplies_the_operator_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, exposure_us=9000, gain=150, offset=-5, sensor_mode_index=2)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["exposure_us"], 9000)
        self.assertEqual(state["gain"], 150)
        self.assertEqual(state["offset"], -5)
        self.assertEqual(state["sensor_mode_index"], 2)
        for value in (0, 100001):
            refused = self.configure(client, exposure_us=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["exposure_us"], 9000)

    def test_the_capture_counters_reset(self) -> None:
        client = self.serve()
        before = self.state(client)
        self.assertGreater(before["capture_lock_timeouts"], 0)       # placeholder test data
        reset = client.invoke("x-cap.e-lab-sfsu.reset_capture_stats.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"], {"lock_timeout": 0, "sdk_timeout_or_error": 0})
        after = self.state(client)
        self.assertEqual(after["capture_lock_timeouts"], 0)
        self.assertEqual(after["capture_sdk_errors"], 0)

    def test_the_estop_stops_the_camera_and_latches(self) -> None:
        client = self.serve()
        self.assertTrue(self.state(client)["running"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = self.configure(client, usb_bandwidth_percent=80)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
