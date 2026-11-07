"""Acceptance run of the Mini-Circuits RCDAT package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RcdatCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, value):
        return client.invoke("cap.device.configure.v1", {"attenuation_setting": value}, **self.ids)

    def test_the_identity_and_the_starting_attenuation_are_read(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["attenuation_setting"], 0.0)          # the fake's placeholder start
        self.assertEqual(state["part_number"], "RCDAT-0000")         # placeholder
        self.assertEqual(state["serial_number"], "00000000000")      # placeholder

    def test_a_write_reports_the_quarter_decibel_value_the_device_stores(self) -> None:
        client = self.serve()
        done = self.configure(client, 0.3)
        self.assertEqual(done["status"], "completed", done)
        self.assertEqual(done["output"]["applied"]["attenuation_setting"], 0.25)
        self.assertEqual(self.state(client)["attenuation_setting"], 0.25)

    def test_the_upstream_range_is_enforced_before_the_native(self) -> None:
        client = self.serve()
        for value in (-0.01, 115.01):
            refused = self.configure(client, value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["attenuation_setting"], 0.0)   # untouched

    def test_the_estop_drives_maximum_attenuation_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, 10.0)["status"], "completed")
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(self.state(client)["attenuation_setting"], 115.0)
        refused = self.configure(client, 10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["attenuation_setting"], 115.0)


if __name__ == "__main__":
    unittest.main()
