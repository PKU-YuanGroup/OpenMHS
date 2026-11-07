"""Acceptance run of the HP 89400 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HP89400Cases(unittest.TestCase):
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

    def test_the_scalar_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["center_frequency"], 2_500_000.0)
        self.assertEqual(state["span"], 5_000_000.0)
        self.assertEqual((state["x_units"], state["y_units"]), ("HZ", "VRMS/RTHZ"))
        self.assertEqual((state["data_points"], state["average_count"]), (8, 16))
        self.assertEqual((state["operating_condition"], state["error_code"]), (0, 0))
        self.assertEqual(state["errors"], '0,"No error"')

    def test_the_trace_action_reports_values_and_axis_metadata(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.snhobbs.acquire_spectrum.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["values"]), 8)
        self.assertEqual(output["points"], 8)
        self.assertEqual((output["x_units"], output["y_units"]), ("HZ", "VRMS/RTHZ"))
        self.assertEqual((output["center_frequency"], output["span"]), (2_500_000.0, 5_000_000.0))
        self.assertIn("sampled_at", output)                    # stamped by the runtime

    def test_abort_and_autorange_reach_the_native(self) -> None:
        client = self.serve()
        aborted = client.invoke("x-cap.snhobbs.abort_measurement.v1", {}, **self.ids)
        self.assertEqual(aborted["output"], {"aborted": True})
        enabled = client.invoke("x-cap.snhobbs.enable_autorange.v1", {"enabled": True}, **self.ids)
        self.assertEqual(enabled["output"], {"enabled": True})
        disabled = client.invoke("x-cap.snhobbs.enable_autorange.v1", {"enabled": False}, **self.ids)
        self.assertEqual(disabled["output"], {"enabled": False})

    def test_the_extension_input_is_closed(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.snhobbs.enable_autorange.v1", {"bogus": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
