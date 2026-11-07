"""Acceptance run of the K10CR1 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The gate case fails here: the package is blocked on the missing
native stop (the upstream class has no stop, abort or disable method), which is recorded in RESULT.json.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
MOVE_ABS = "x-cap.quantumquadrate.move_absolute.v1"
MOVE_REL = "x-cap.quantumquadrate.move_relative.v1"
HOME = "x-cap.quantumquadrate.home_stage.v1"
JOG = "x-cap.quantumquadrate.jog_stage.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability_id, payload=None):
        receipt = client.invoke(capability_id, payload or {}, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"], receipt.get("output")

    def test_the_stage_starts_at_its_reference_angle(self) -> None:
        client = self.serve()
        self.assertEqual(client.read("main", **self.ids)["state"], {"position": 0.0})

    def test_the_moves_reach_the_device_and_change_the_reported_angle(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.invoke(client, MOVE_ABS, {"angle": 45.0}), ("completed", {"angle": 45.0}))
        self.assertEqual(client.read("main", **self.ids)["state"], {"position": 45.0})
        self.assertEqual(self.invoke(client, MOVE_REL, {"delta": -10.0}), ("completed", {"delta": -10.0}))
        self.assertEqual(client.read("main", **self.ids)["state"], {"position": 35.0})
        self.assertEqual(self.invoke(client, HOME), ("completed", {"response": "#000000"}))
        self.assertEqual(client.read("main", **self.ids)["state"], {"position": 0.0})

    def test_the_angle_waits_for_the_site(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, MOVE_ABS, {"angle": 45.0}), LIMITS_UNSET)
        self.assertEqual(self.invoke(client, MOVE_REL, {"delta": 10.0}), LIMITS_UNSET)
        self.assertEqual(client.read("main", **self.ids)["state"], {"position": 0.0})


if __name__ == "__main__":
    unittest.main()
