"""Acceptance run of the LeCroy package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values and canned replies are test data, not
device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class State(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"coupling": "A1M", "trigger_mode": "NORM", "attenuation": 100})
        state = driver.read("main", ["coupling", "trigger_mode", "attenuation"])
        self.assertEqual(state, {"coupling": "A1M", "trigger_mode": "NORM", "attenuation": 100.0})

    def test_the_identity_and_profile_read_the_fake(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["identity", "family", "channels"])
        self.assertIn("LECROY", state["identity"])
        self.assertEqual(state["family"], "Fake WaveSurfer")
        self.assertEqual(state["channels"], 4)

    def test_setup_selects_headerless_unitless_replies(self) -> None:
        self.assertEqual(self.driver().native._header_mode, "OFF")

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertTrue(driver.read("main", ["stopped"])["stopped"])


class Actions(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, "fake")
        self.native = driver.native
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_an_ignored_stop_does_not_confirm_the_safe_state(self) -> None:
        client, device_id, session = self.serve()
        self.native.stop = lambda: None  # placeholder: no acquisition state change
        receipt = client.estop("ignored stop", device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(receipt["output"]["latched"])
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_a_nonzero_calibration_diagnostic_fails_the_receipt(self) -> None:
        client, device_id, session = self.serve()
        self.native.calibrate = lambda: "*CAL 4"  # placeholder: manual's C3 calibration failure
        payload = {}
        permit = client.permit("cap.device.calibrate.v1", payload,
                               device_id=device_id, session_id=session)
        receipt = client.invoke("cap.device.calibrate.v1", payload, permit_id=permit["permit_id"],
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")

    def test_failed_setting_query_is_not_a_successful_write(self) -> None:
        client, device_id, session = self.serve()
        original = self.native.get_trigger_info
        self.native.get_trigger_info = lambda: dict(original(), mode="N/A")
        receipt = client.invoke("cap.device.configure.v1", {"trigger_mode": "NORM"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")

    def test_a_malformed_stop_mode_does_not_confirm_stopping(self) -> None:
        client, device_id, session = self.serve()
        original = self.native.query
        self.native.query = lambda cmd: "NOT_STOPPED" if cmd == "TRMD?" else original(cmd)
        receipt = client.estop("malformed mode", device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(receipt["output"]["latched"])

    def test_the_measurement_action_returns_the_pava_reply(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.lucasgerads.measure.v1", {"parameter": "PKPK"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("PKPK", receipt["output"]["reply"])

    def test_the_arm_action_completes(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.lucasgerads.arm.v1", {},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["armed"])

    def test_the_calibration_maps_the_diagnostic_code(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.calibrate()
        self.assertTrue(output["calibrated"])
        self.assertIn("CAL", output["calibration_ref"])


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def configure(self, client, device_id, session, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, device_id=device_id, session_id=session)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_an_operator_required_setting_is_refused_without_an_overlay(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, vdiv=0.5), UNSET)

    def test_the_example_overlay_supplies_the_operator_bound(self) -> None:
        client, device_id, session = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, device_id, session, vdiv=0.5), "completed")
        self.assertEqual(self.configure(client, device_id, session, vdiv=100.0), ENVELOPE)

    def test_an_unknown_coupling_is_refused(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, coupling="BOGUS"), ENVELOPE)


if __name__ == "__main__":
    unittest.main()
