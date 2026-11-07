"""Acceptance run of the caproto-rpi TagDriver: the gate, plus cases specific to the hat IOC's state PV.

Add cases, never remove the check_driver call.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, close_server, load, load_driver
from mhs.bridge.tag_fake import request_key
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
HAT_ON = "x-cap.danielballan.hat_on.v1"
ALL_OFF = "x-cap.danielballan.all_off.v1"
STATE_KEY = request_key({"profile": "epics-ca", "pv": "state"})
DEVICE = "mhs://localhost/caproto-rpi"
OVERLAY = {"openmhs": "0.9", "site": "test bench", "devices": {DEVICE: {
    "hat_state": {"min": 0, "max": 1, "unit": "1", "source": "operator", "reason": "test bench"}}}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CaprotoRpiCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def server(self, **options):
        server = load(HERE, backend="fake", **options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        return client, device, session

    def test_hat_on_and_all_off_write_the_declared_pv(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(HAT_ON, {}), {"hat_state": 1})
        self.assertEqual(driver.native.pvs, {"state": 1})
        self.assertEqual(driver.call(ALL_OFF, {}), {"hat_state": 0})
        self.assertEqual(driver.native.pvs, {"state": 0})

    def test_state_truthiness_is_normalized_like_write_state(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.write("main", {"hat_state": 7}), {"applied": {"hat_state": 7}})
        self.assertEqual(driver.native.pvs["state"], 1)
        self.assertEqual(driver.read("main")["hat_state"], 1)

    def test_the_rgb_color_pv_is_not_served(self) -> None:
        driver = self.driver()
        self.assertNotIn("color", driver.read("main"))
        with self.assertRaises(Exception):
            driver.write("main", {"color": "000000"})
        self.assertEqual(driver.native.pvs, {"state": 0})

    def test_operator_required_state_is_refused_without_an_overlay(self) -> None:
        client, device, session = self.server()
        receipt = client.write("main", {"hat_state": 1}, device_id=device, session_id=session)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_example_overlay_bounds_the_state_pv(self) -> None:
        client, device, session = self.server(site_limits=OVERLAY)
        inside = client.write("main", {"hat_state": 1}, device_id=device, session_id=session)
        self.assertEqual(inside["status"], "completed", inside)
        outside = client.write("main", {"hat_state": 2}, device_id=device, session_id=session)
        self.assertEqual(outside["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_an_unacknowledged_state_write_fences_commands_until_a_confirmed_stop(self) -> None:
        driver = self.driver()
        driver.native.silent.add(STATE_KEY)
        with self.assertRaises(Exception) as caught:
            driver.write("main", {"hat_state": 1})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")
        with self.assertRaises(Exception) as fenced:
            driver.call(HAT_ON, {})
        self.assertEqual(getattr(fenced.exception, "code", None), "MHS.DEVICE.PRECONDITION_UNMET")
        driver.native.silent.discard(STATE_KEY)
        self.assertEqual(driver.call(ALL_OFF, {}), {"hat_state": 0})
        self.assertEqual(driver.call(HAT_ON, {}), {"hat_state": 1})

    def test_a_refused_stop_never_reports_a_safe_state(self) -> None:
        driver = self.driver()
        driver.call(HAT_ON, {})
        driver.native.refuse.add(STATE_KEY)
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])

    def test_estop_through_the_stock_server_latches(self) -> None:
        client, device, session = self.server()
        invoked = client.invoke(HAT_ON, {}, device_id=device, session_id=session)
        self.assertEqual(invoked["status"], "completed", invoked)
        receipt = client.estop("test", device_id=device, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(HAT_ON, {}, device_id=device, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_hardware_backend_is_refused_without_a_human_hardware_review(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state,
                            options={"prefix": "hatpi:"})
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
