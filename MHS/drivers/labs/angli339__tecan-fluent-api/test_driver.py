"""Acceptance run of the Tecan Fluent package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ASPIRATE = "x-cap.angli339.liha_aspirate.v1"
DISPENSE = "x-cap.angli339.mca_dispense.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TecanCases(unittest.TestCase):
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

    def payload(self):
        return {"volume_ul": 10, "tip": 0, "labware": "SrcPlate", "well": "A1", "liquid_class": "Water"}

    def test_the_fake_starts_with_an_open_channel(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["fluent_status"], "Idle")          # placeholder status word of the fake
        self.assertTrue(state["channel_open"])

    def test_the_volume_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(ASPIRATE, self.payload(), **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertTrue(self.state(client)["channel_open"])

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = client.invoke(ASPIRATE, self.payload(), **self.ids)
        self.assertEqual(aspirated["status"], "completed")
        self.assertEqual(aspirated["output"], {"aspirated_volume": 10})
        dispensed = client.invoke(DISPENSE, {"volume_ul": 20, "labware": "DestPlate",
                                             "liquid_class": "Water"}, **self.ids)
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"], {"dispensed_volume": 20})
        refused = client.invoke(ASPIRATE, {**self.payload(), "well": "H13"}, **self.ids)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_estop_stops_and_detaches_the_channel(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.invoke(ASPIRATE, self.payload(), **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["channel_open"])
        self.assertEqual(state["fluent_status"], "Stopped")       # placeholder status word of the fake
        refused = client.invoke(ASPIRATE, self.payload(), **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
