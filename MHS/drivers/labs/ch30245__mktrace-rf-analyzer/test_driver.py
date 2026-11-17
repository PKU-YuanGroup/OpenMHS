"""Acceptance run of the MKTrace driver package: the gate harness plus cases for this driver.

Add cases, never remove the ``check_driver`` call.  The cases exercise the fake through the stock in-process server:
the identity read, the allowed-port limit, the Keysight measurement setup, the Touchstone publication through the
SDK's native-file artifacts, and the e-stop latch.  The fake's numbers are placeholders, not instrument facts.
"""

from pathlib import Path
import unittest

from mhs.adapter import close_server, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "x-cap.ch30245.configure-measurements.v1"
CAPTURE = "x-cap.ch30245.capture-trace.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MktraceCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, artifact_store=LocalArtifactStore())
        self.addCleanup(close_server, server)
        self.server = server
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def invoke(self, client, capability, payload):
        return client.invoke(capability, payload, **self.ids)

    def test_identity_is_read_from_the_native(self) -> None:
        client, _fake = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertIn("identity", state)
        self.assertIn("N5247B", state["identity"])   # placeholder identity of the fake

    def test_invalid_port_count_is_refused_before_the_native(self) -> None:
        client, fake = self.serve()
        before = list(fake._parameters)
        refused = self.invoke(client, CAPTURE, {"port_count": 3})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(fake._parameters, before)
        refused = self.invoke(client, CONFIGURE, {"port_count": 0})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_configure_measurements_adds_only_the_missing_parameters(self) -> None:
        client, fake = self.serve()
        first = self.invoke(client, CONFIGURE, {"port_count": 2})
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual([item["parameter"] for item in first["output"]["created_measurements"]],
                         ["S21", "S12", "S22"])
        self.assertEqual(first["output"]["channel"], 1)             # placeholder channel
        second = self.invoke(client, CONFIGURE, {"port_count": 2})
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(second["output"]["created_measurements"], [])
        self.assertEqual(fake._parameters, ["S11", "S21", "S12", "S22"])

    def test_capture_publishes_a_touchstone_artifact(self) -> None:
        client, _fake = self.serve()
        self.assertEqual(self.invoke(client, CONFIGURE, {"port_count": 2})["status"], "completed")
        receipt = self.invoke(client, CAPTURE, {"port_count": 2})
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["port_count"], 2)
        self.assertTrue(output["file_name"].endswith(".s2p"), output["file_name"])
        descriptor = receipt["artifacts"][0]
        self.assertEqual(descriptor["uri"], output["artifact_ref"])
        self.assertEqual(descriptor["media_type"], "application/x-touchstone")
        data = self.server.read_artifact(output["artifact_ref"], session_id=self.ids["session_id"])["data"]
        self.assertTrue(data.startswith(b"! MKTrace fake capture"), data[:80])
        self.assertIn(b"# Hz S RI R 50", data)

    def test_capture_requires_all_of_the_requested_measurements(self) -> None:
        client, _fake = self.serve()
        receipt = self.invoke(client, CAPTURE, {"port_count": 2})
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_closing_io_does_not_confirm_an_analyzer_stop(self) -> None:
        client, fake = self.serve()
        receipt = client.estop("unit test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertGreaterEqual(fake._abort_calls, 1)
        refused = self.invoke(client, CAPTURE, {"port_count": 1})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LATCHED)


if __name__ == "__main__":
    unittest.main()
