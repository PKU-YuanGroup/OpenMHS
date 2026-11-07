"""Acceptance and behaviour cases for the APO 1m Ash Dome rotation TagDriver.

Keep the check_driver call: it runs the full fake-backend gate. The extra cases exercise the declared Alpaca members
through the fake transport, the sourced SlewToAzimuth envelope, the started-rotation confirmation of slew, park and
find-home, the AbortSlew stop path (including refused and malformed replies), the excluded shutter methods, and the
human hardware-review gate. No server or hardware is contacted.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, close_server, load, load_driver
from mhs.bridge.tag_fake import request_key
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SLEW = "x-cap.holtzmanjon.slew_azimuth.v1"
PARK = "x-cap.holtzmanjon.park.v1"
HOME = "x-cap.holtzmanjon.find_home.v1"
ABORT = "x-cap.holtzmanjon.abort_slew.v1"
SETPARK = "x-cap.holtzmanjon.set_park.v1"
ABORTSLEW = {"profile": "alpaca", "device_type": "dome", "device_number": 0,
             "member": "abortslew", "method": True}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DomeCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def code(self, call):
        with self.assertRaises(Exception) as caught:
            call()
        return getattr(caught.exception, "code", None)

    def test_state_reads_the_five_seeded_alpaca_properties(self) -> None:
        state = self.driver().read("main")
        self.assertEqual(state["azimuth"], 200.0)
        self.assertEqual(state["shutterstatus"], 1)
        self.assertFalse(state["slewing"])
        self.assertFalse(state["athome"])
        self.assertFalse(state["atpark"])

    def test_slew_completes_on_a_started_rotation_and_abort_clears_the_slewing_flag(self) -> None:
        driver = self.driver()
        receipt = driver.call(SLEW, {"azimuth": 90})
        self.assertEqual(receipt["target_azimuth"], 90)
        self.assertTrue(receipt["slewing"])
        self.assertTrue(driver.native.properties["slewing"])
        stopped = driver.call(ABORT, {})
        self.assertFalse(stopped["slewing"])
        self.assertFalse(driver.native.properties["slewing"])

    def test_a_worker_that_has_not_started_rotating_ends_unknown_and_fences_commands(self) -> None:
        driver = self.driver()
        driver.native.start_delayed = True
        self.assertEqual(self.code(lambda: driver.call(SLEW, {"azimuth": 90})), "MHS.OUTCOME.UNKNOWN")
        driver.native.start_delayed = False
        self.assertEqual(self.code(lambda: driver.call(SLEW, {"azimuth": 90})), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertFalse(driver.call(ABORT, {})["slewing"])
        self.assertTrue(driver.call(SLEW, {"azimuth": 90})["slewing"])

    def test_a_target_within_tolerance_starts_no_rotation_and_ends_unknown(self) -> None:
        driver = self.driver()
        self.assertEqual(self.code(lambda: driver.call(SLEW, {"azimuth": 201})), "MHS.OUTCOME.UNKNOWN")
        self.assertFalse(driver.native.properties["slewing"])

    def test_park_when_already_parked_and_home_when_already_home_end_unknown(self) -> None:
        driver = self.driver()
        self.assertTrue(driver.call(SETPARK, {})["atpark"])
        self.assertEqual(self.code(lambda: driver.call(PARK, {})), "MHS.OUTCOME.UNKNOWN")
        self.assertFalse(driver.call(ABORT, {})["slewing"])
        driver.native.properties["athome"] = True
        self.assertEqual(self.code(lambda: driver.call(HOME, {})), "MHS.OUTCOME.UNKNOWN")

    def test_shutter_methods_are_not_served(self) -> None:
        driver = self.driver()
        for capability in ("x-cap.holtzmanjon.open_shutter.v1", "x-cap.holtzmanjon.close_shutter.v1"):
            with self.assertRaises(Exception):
                driver.call(capability, {})
        self.assertEqual(driver.native.properties["shutterstatus"], 1)

    def test_slew_azimuth_outside_the_responder_range_is_refused_without_a_native_call(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        fake = server.devices[device].bridge.native
        invokes = []
        original = fake.invoke_point

        def record(request, args, *, timeout_s):
            invokes.append(request)
            return original(request, args, timeout_s=timeout_s)

        fake.invoke_point = record
        before = dict(fake.properties)
        refused = client.invoke(SLEW, {"azimuth": 361}, device_id=device, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(invokes, [])
        self.assertEqual(fake.properties, before)

    def test_estop_reaches_abortslew_and_latches_until_an_operator_reset(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        started = client.invoke(SLEW, {"azimuth": 90}, device_id=device, session_id=session)
        self.assertEqual(started["status"], "completed", started)
        receipt = client.estop("test", device_id=device, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(SLEW, {"azimuth": 90}, device_id=device, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_refused_abortslew_never_reports_a_safe_state(self) -> None:
        driver = self.driver()
        driver.call(SLEW, {"azimuth": 90})
        driver.native.refuse.add(request_key(ABORTSLEW))
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])

    def test_a_malformed_abortslew_reply_is_not_taken_for_a_stop(self) -> None:
        driver = self.driver()
        driver.call(SLEW, {"azimuth": 90})
        driver.native.silent.add(request_key(ABORTSLEW))
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])

    def test_hardware_backend_is_refused_without_a_human_hardware_review(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state,
                            options={"host": "127.0.0.1", "port": 5555})
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
