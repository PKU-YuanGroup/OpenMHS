"""Acceptance run of the Keysight DSOX1200 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
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
        driver.write("main", {"channel1_display": False, "channel1_coupling": "AC", "acquire_type": "PEAK"})
        state = driver.read("main", ["channel1_display", "channel1_coupling", "acquire_type"])
        self.assertEqual(state, {"channel1_display": False, "channel1_coupling": "AC", "acquire_type": "PEAK"})

    def test_the_identity_reads_the_fake_idn(self) -> None:
        driver = self.driver()
        self.assertIn("KEYSIGHT", driver.read("main", ["identity"])["identity"])

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.read("main", ["acquire_complete"])["acquire_complete"], 0)


class Actions(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_measurement_action_returns_a_scalar(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.jovanmarkov96.measure.v1", {"item": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["value"], 2.5)

    def test_the_run_and_single_actions_report_completion(self) -> None:
        client, device_id, session = self.serve()
        for capability_id, expected in (("x-cap.jovanmarkov96.run.v1", 0),
                                        ("x-cap.jovanmarkov96.single.v1", 100)):
            receipt = client.invoke(capability_id, {}, device_id=device_id, session_id=session)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"]["acquire_complete"], expected)


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
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=0.5), UNSET)

    def test_the_example_overlay_supplies_the_operator_bound(self) -> None:
        client, device_id, session = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=0.5), "completed")
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=10.0), ENVELOPE)

    def test_an_unknown_coupling_is_refused(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, channel1_coupling="BOGUS"), ENVELOPE)


if __name__ == "__main__":
    unittest.main()
