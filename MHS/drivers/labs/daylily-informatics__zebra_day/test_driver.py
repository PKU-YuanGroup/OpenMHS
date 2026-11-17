"""Acceptance run of the zebra_day package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZebraPrinterCases(unittest.TestCase):
    def serve(self):
        self.driver = load_driver(HERE, backend="fake")
        self.addCleanup(self.driver.close)
        server = build_server(self.driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, configuration):
        return client.invoke("cap.device.configure.v1", {"configuration": configuration}, **self.ids)

    def test_the_status_snapshot_is_served(self) -> None:
        client = self.serve()
        status = self.state(client)["status"]
        self.assertTrue(status["online"])
        self.assertEqual(status["model"], "ZD620-203dpi ZPL")          # fake placeholder
        self.assertEqual(status["serial"], "SIM1001")                  # fake placeholder
        self.assertEqual(status["label_count"], 12345)                 # fake placeholder
        self.assertFalse(status["paused"])
        self.assertEqual(status["errors"], [])

    def test_the_configuration_write_has_no_acknowledged_outcome(self) -> None:
        client = self.serve()
        before = self.state(client)["configuration"]
        self.assertNotIn("WRITTEN CONFIGURATION", before)
        receipt = self.configure(client, "^XA^MD10^XZ")
        self.assertEqual(receipt["status"], "unknown", receipt)
        after = self.state(client)["configuration"]
        self.assertIn("WRITTEN CONFIGURATION: ^XA^MD10^XZ", after)
        self.assertNotEqual(before, after)

    def test_an_unverified_cancel_cannot_confirm_the_estop(self) -> None:
        client = self.serve()
        self.assertFalse(self.driver.native.cancelled)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(self.driver.native.cancelled)
        refused = self.configure(client, "^XA^MD20^XZ")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_silent_configuration_transport_cannot_report_success(self) -> None:
        client = self.serve()
        self.driver.native.set_configuration = lambda _value: None
        receipt = self.configure(client, "^XA^MD10^XZ")
        self.assertEqual(receipt["status"], "unknown", receipt)


if __name__ == "__main__":
    unittest.main()
