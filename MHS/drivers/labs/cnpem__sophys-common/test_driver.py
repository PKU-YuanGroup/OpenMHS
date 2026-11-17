"""Acceptance run of the CompactERAS package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
import logging
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CompactErasCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_reads_the_four_channels(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(state["version"], "1.0.0")                 # placeholder test data of the fake
        self.assertEqual(state["supported_devices"], "ERAS1 ERAS2") # placeholder test data of the fake
        for index in range(1, 5):
            self.assertAlmostEqual(state[f"voltage_ch{index}"], float(index))
            self.assertAlmostEqual(state[f"current_ch{index}"], float(index) * 1.0e-9)

    def test_the_voltage_capability_selects_one_channel(self) -> None:
        client, _fake = self.serve()
        first = client.invoke("cap.measure.voltage.v1", {"channel": "CH1"}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertAlmostEqual(first["output"]["voltage"], 1.0)     # placeholder test data of the fake
        second = client.invoke("cap.measure.voltage.v1", {"channel": "CH3"}, **self.ids)
        self.assertEqual(second["status"], "completed", second)
        self.assertAlmostEqual(second["output"]["voltage"], 3.0)   # placeholder test data of the fake

    def test_the_current_capability_selects_one_channel(self) -> None:
        client, _fake = self.serve()
        measured = client.invoke("cap.measure.current.v1", {"channel": "CH4"}, **self.ids)
        self.assertEqual(measured["status"], "completed", measured)
        self.assertAlmostEqual(measured["output"]["current"], 4.0e-9)  # placeholder test data of the fake

    def test_a_channel_outside_the_class_is_refused(self) -> None:
        client, fake = self.serve()
        before = fake.CH1.voltage.get()
        refused = client.invoke("cap.measure.voltage.v1", {"channel": "CH5"}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(fake.CH1.voltage.get(), before)

    def test_there_is_no_write(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"voltage_ch1": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertIn(refused["error"]["mhs_code"],
                      ("MHS.CAPABILITY.UNKNOWN", "MHS.CAPABILITY.NOT_BOUND"))

    def test_the_estop_latch_leaves_reads_available(self) -> None:
        # This R0 integration has no native stop and no physical effect: the e-stop is the endpoint's
        # software latch, and the read-only state stays readable because it actuates nothing.
        client, _fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertAlmostEqual(self.state(client)["voltage_ch1"], 1.0)  # placeholder test data

    def test_an_incompatible_version_warns_but_still_verifies_connectivity(self) -> None:
        _client, fake = self.serve()
        logger = logging.getLogger("compacteras-version-test")
        with self.assertLogs(logger, level="WARNING"):
            verified = fake.verifyVersion("2.0.0", logger=logger)
        self.assertTrue(verified)


if __name__ == "__main__":
    unittest.main()
