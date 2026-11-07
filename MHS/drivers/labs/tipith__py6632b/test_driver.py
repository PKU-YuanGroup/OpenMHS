"""Acceptance run of the HP 6632B package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HP6632BCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_source_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.tipith.set_source.v1",
                                {"voltage_v": 4.0, "current_ma": 50}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual((self.state(client)["voltage"], self.state(client)["current"]), (0.0, 0.0))

    def test_the_example_overlay_sets_the_source(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = client.invoke("x-cap.tipith.set_source.v1",
                                {"voltage_v": 5.0, "current_ma": 100}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"], {"voltage_v": 5.0, "current_ma": 100})
        state = self.state(client)
        self.assertEqual((state["voltage"], state["current"]), (5.0, 0.1))
        for payload in ({"voltage_v": 5.01, "current_ma": 100}, {"voltage_v": 5.0, "current_ma": 101}):
            refused = client.invoke("x-cap.tipith.set_source.v1", payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual((self.state(client)["voltage"], self.state(client)["current"]), (5.0, 0.1))

    def test_output_and_the_safe_state_action(self) -> None:
        client = self.serve()
        enabled = client.invoke("x-cap.tipith.set_output.v1", {"enabled": True}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertTrue(self.state(client)["output_enabled"])
        stopped = client.invoke("x-cap.tipith.stop_output.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"output_enabled": False})
        self.assertFalse(self.state(client)["output_enabled"])

    def test_the_estop_stops_the_output_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.tipith.set_output.v1", {"enabled": True}, **self.ids)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(self.state(client)["output_enabled"])
        refused = client.invoke("x-cap.tipith.set_output.v1", {"enabled": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
