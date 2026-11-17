"""Acceptance run of the LevyLab lock-in package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
FIELDS = "cap.sensing.read.v1"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LockinCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        self.native = driver.native
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def read_fields(self, client, fields=None):
        payload = {} if fields is None else {"fields": fields}
        return client.invoke(FIELDS, payload, **self.ids)

    def test_the_identity_and_status_are_read_from_the_native(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["identity"], "LevyLab MC Lock-in (firmware v2.15.4.4)")
        self.assertEqual(state["status"], "idle")

    def test_requested_measurement_fields_are_returned(self) -> None:
        client = self.serve()
        receipt = self.read_fields(client, ["source_X", "drain_Mean"])
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {"source_X": 1.0, "drain_Mean": 1.0})
        self.assertIn("sampled_at", receipt["output"])

    def test_an_omitted_field_list_reads_every_configured_measurement(self) -> None:
        client = self.serve()
        receipt = self.read_fields(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        values = receipt["output"]["values"]
        self.assertEqual(len(values), 15)
        self.assertEqual(values["gate_Theta"], 90.0)

    def test_an_unconfigured_field_is_refused_before_any_native_call(self) -> None:
        client = self.serve()
        receipt = self.read_fields(client, ["source_Q"])
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)

    def test_the_driver_serves_no_write(self) -> None:
        client = self.serve()
        with self.assertRaises(MHSError) as caught:
            client.write("main", {"status": "start"}, **self.ids)
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.NOT_WRITABLE")

    def test_every_requested_field_is_validated_before_measurement_io(self) -> None:
        client = self.serve()
        with patch.object(self.native, "_get_lockin", wraps=self.native._get_lockin) as measure:
            receipt = self.read_fields(client, ["source_X", "source_Q"])
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)
        measure.assert_not_called()

    def test_a_missing_measurement_is_a_fault_without_a_substitute_value(self) -> None:
        client = self.serve()
        with patch.object(self.native, "_get_lockin", return_value=None):
            receipt = self.read_fields(client, ["source_X"])
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")


if __name__ == "__main__":
    unittest.main()
