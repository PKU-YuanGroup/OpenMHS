"""Acceptance run of the pumpy3 package: the gate, plus cases for what is specific to this driver.

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


class Pumpy3Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def start(self, client, direction):
        return client.invoke("x-cap.iridiumwastaken.start_pump.v1", {"direction": direction}, **self.ids)

    def stop_pump(self, client):
        return client.invoke("x-cap.iridiumwastaken.stop_pump.v1", {}, **self.ids)

    def test_the_sourced_diameter_and_the_operator_required_writes(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, diameter=24)["status"], "completed")
        self.assertEqual(self.state(client)["diameter"], 24.0)
        refused = self.configure(client, diameter=40)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["diameter"], 24.0)
        for patch in ({"rate": 600}, {"target_volume": 2.5}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, rate=600)["status"], "completed")
        self.assertEqual(self.state(client)["rate"], 600.0)
        self.assertEqual(self.configure(client, target_volume=2.5)["status"], "completed")
        self.assertEqual(self.state(client)["target_volume"], 2.5)

    def test_start_and_safe_state_actions(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.start(client, "forward")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"running": True, "direction": "forward"})
        self.assertTrue(self.state(client)["running"])
        receipt = self.stop_pump(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"running": False})
        self.assertFalse(self.state(client)["running"])

    def test_reverse_direction(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.start(client, "reverse")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"running": True, "direction": "reverse"})
        self.stop_pump(client)

    def test_the_estop_latches_writes_and_actions(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = self.start(client, "forward")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = self.configure(client, diameter=24)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
