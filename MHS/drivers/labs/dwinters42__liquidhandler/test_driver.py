"""Acceptance run of the dwinters42 liquidhandler driver: the gate, plus cases for this driver.

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


class LiquidhandlerCases(unittest.TestCase):
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

    def test_the_operator_bounds_are_required(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.dwinters42.move_arm.v1",
                                {"arm": 1, "x": 100, "y": 100, "z": 50}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["arm1_position"], [0, 0, 0])

    def test_the_example_overlay_allows_moves_and_locations(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.dwinters42.move_arm.v1",
                              {"arm": 1, "x": 100, "y": 100, "z": 50}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], [100, 100, 50])
        self.assertEqual(self.state(client)["arm1_position"], [100, 100, 50])
        added = client.invoke("x-cap.dwinters42.add_position.v1",
                              {"name": "wash", "x": 100, "y": 100, "z": 50}, **self.ids)
        self.assertEqual(added["status"], "completed")
        self.assertIn("wash", self.state(client)["location_names"])

    def test_draw_and_dispense_track_the_syringe(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.state(client)["syringe_contents"], [1000])
        drawn = client.invoke("x-cap.dwinters42.draw.v1",
                              {"pump": 1, "units": 100, "source": "bottle", "speed": 10}, **self.ids)
        self.assertEqual(drawn["status"], "completed")
        self.assertEqual(drawn["output"]["syringe_contents"], [1100])
        dispensed = client.invoke("x-cap.dwinters42.dispense.v1",
                                  {"pump": 1, "units": 100, "speed": 10}, **self.ids)
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"]["syringe_contents"], [1000])

    def test_the_protocol_speed_bound_is_enforced(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = client.invoke("x-cap.dwinters42.pump.v1",
                                {"pump": 1, "speed": 21, "position": 100, "direction": "out"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["syringe_contents"], [1000])
        accepted = client.invoke("x-cap.dwinters42.pump.v1",
                                 {"pump": 1, "speed": 1, "position": 100, "direction": "out"}, **self.ids)
        self.assertEqual(accepted["status"], "completed")

    def test_the_estop_stops_the_pumps_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.dwinters42.move_arm.v1",
                      {"arm": 1, "x": 100, "y": 100, "z": 50}, **self.ids)
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.dwinters42.move_arm.v1",
                                {"arm": 1, "x": 200, "y": 200, "z": 50}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
