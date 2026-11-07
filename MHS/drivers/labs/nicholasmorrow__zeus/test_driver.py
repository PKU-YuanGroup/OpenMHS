"""Acceptance run of the ZEUS package: the gate, plus cases for what is specific to this driver.

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


class ZeusCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def test_the_read_and_the_initialization(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["z_position"], 0)      # placeholder: the fake's start position
        started = self.invoke(client, "x-cap.nicholasmorrow.initialize.v1", {})
        self.assertEqual(started["output"], {"initialized": True})
        self.assertEqual(self.state(client)["z_position"], 1800)   # placeholder: fake maxZPosition after initZDrive

    def test_the_operator_must_supply_the_z_range(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.nicholasmorrow.move_z.v1", {"position": 500, "speed": "fast"})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["z_position"], 0)      # placeholder: untouched

    def test_the_example_overlay_moves_the_z_drive(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.invoke(client, "x-cap.nicholasmorrow.move_z.v1", {"position": 250, "speed": "slow"})
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"z_position": 250, "speed": "slow"})
        self.assertEqual(self.state(client)["z_position"], 250)
        refused = self.invoke(client, "x-cap.nicholasmorrow.move_z.v1", {"position": 1801, "speed": "fast"})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_dosing_drive_actions(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = self.invoke(client, "x-cap.nicholasmorrow.aspirate.v1", {
            "volume": 50, "container_geometry": 1, "deck_geometry": 2, "liquid_class": 3})
        self.assertEqual(aspirated["output"], {"commanded_volume": 50, "container_geometry": 1,
                                              "deck_geometry": 2, "liquid_class": 3})
        dispensed = self.invoke(client, "x-cap.nicholasmorrow.dispense.v1", {
            "volume": 25, "container_geometry": 1, "deck_geometry": 2, "liquid_class": 3})
        self.assertEqual(dispensed["output"], {"commanded_volume": 25, "container_geometry": 1,
                                              "deck_geometry": 2, "liquid_class": 3})

    def test_the_tip_actions(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        picked = self.invoke(client, "x-cap.nicholasmorrow.pick_tip.v1", {"tip_type": 1, "deck_geometry": 2})
        self.assertEqual(picked["output"], {"tip_type": 1, "deck_geometry": 2})
        discarded = self.invoke(client, "x-cap.nicholasmorrow.discard_tip.v1", {"deck_geometry": 2})
        self.assertEqual(discarded["output"], {"deck_geometry": 2})

    def test_the_safe_state_action_and_the_estop_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = self.invoke(client, "x-cap.nicholasmorrow.emergency_stop.v1", {})
        self.assertEqual(stopped["output"], {"emergency_stop": True})
        client.estop("test", **self.ids)
        refused = self.invoke(client, "x-cap.nicholasmorrow.initialize.v1", {})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
