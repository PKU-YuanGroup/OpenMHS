"""Acceptance run of the Cetus PCR package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ACTION = "x-cap.cetuspcr.run_protocol.v1"


def payload(**changes):
    values = {"temperature": 60, "duration_s": 1, "cycles": 1, "name": "test hold"}
    values.update(changes)
    return values


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, overlay=None):
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return server, client, ids

    def test_the_action_runs_the_upstream_loop(self) -> None:
        server, client, ids = self.serve(OVERLAY)
        receipt = client.invoke(ACTION, payload(), wait=True, wait_timeout_s=30, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["completed"])
        self.assertEqual(receipt["output"]["cycles_completed"], 1)
        self.assertEqual(receipt["output"]["actual_temperature"], 60.0)
        fake = server.devices[ids["device_id"]].bridge.native
        self.assertFalse(fake.is_running)
        self.assertEqual(fake.current_step, "hold")
        self.assertIn(b"<peltier 0 0>", fake.serial_device.written)

    def test_the_operator_bound_is_required_without_an_overlay(self) -> None:
        server, client, ids = self.serve()
        receipt = client.invoke(ACTION, payload(), **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        fake = server.devices[ids["device_id"]].bridge.native
        self.assertEqual(fake.serial_device.written, [])

    def test_the_estop_writes_the_zero_pwm_command(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertFalse(driver.native.is_running)
        self.assertIn(b"<peltier 0 0>", driver.native.serial_device.written)

    def test_the_example_overlay_narrows_the_operator_bounds(self) -> None:
        server, client, ids = self.serve(OVERLAY)
        for bad in (payload(temperature=101), payload(duration_s=86401), payload(cycles=0)):
            receipt = client.invoke(ACTION, bad, **ids)
            self.assertEqual(receipt["status"], "rejected", (bad, receipt))
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, bad)
        receipt = client.invoke(ACTION, payload(temperature=0, cycles=1000), wait=True, wait_timeout_s=30, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
