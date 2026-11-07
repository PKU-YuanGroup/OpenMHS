"""Acceptance run of the star-sim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
TRANSFER = "x-cap.oelemento.transfer.v1"
MIX = "x-cap.oelemento.mix.v1"
VOLUMES = "x-cap.oelemento.tracked_volumes.v1"
COLUMN = [f"{row}1" for row in "ABCDEFGH"]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StarSimCases(unittest.TestCase):
    def setUp(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}

    def invoke(self, capability, payload):
        return self.client.invoke(capability, payload, **self.ids)

    def volumes(self, labware, wells):
        receipt = self.invoke(VOLUMES, {"labware": labware, "wells": wells})
        self.assertEqual(receipt["status"], "completed", receipt)
        return receipt["output"]["volumes"]

    def transfer(self, volume, source_wells, target_wells):
        return self.invoke(TRANSFER, {"tip_rack": "tip_rack", "source": "source_plate", "source_wells": source_wells,
                                      "target": "dest_plate", "target_wells": target_wells, "volume": volume})

    def test_a_column_transfer_moves_tracked_liquid_and_uses_one_tip_column(self) -> None:
        before = self.client.read("main", **self.ids)["state"]["tips_remaining_columns"]
        receipt = self.transfer(250, COLUMN, COLUMN)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tips"], COLUMN)                     # the first full column, rows A to H
        self.assertEqual(self.volumes("dest_plate", COLUMN), [250.0] * 8)
        source = self.volumes("source_plate", COLUMN)
        self.assertEqual(len(set(source)), 1)
        self.assertLess(source[0], self.volumes("source_plate", ["A2"])[0])     # drained by exactly one transfer
        after = self.client.read("main", **self.ids)["state"]["tips_remaining_columns"]
        self.assertEqual(after, before - 1)

    def test_fresh_tips_for_every_operation(self) -> None:
        first = self.transfer(10, ["A3"], ["A3"])
        second = self.transfer(10, ["A3"], ["A3"])
        self.assertEqual([first["status"], second["status"]], ["completed", "completed"])
        self.assertNotEqual(first["output"]["tips"], second["output"]["tips"])

    def test_the_upstream_volume_bounds_are_enforced_before_any_step(self) -> None:
        for volume in (0.5, 1000.5):
            receipt = self.transfer(volume, ["A4"], ["A4"])
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", volume)
        self.assertEqual(self.volumes("dest_plate", ["A4"]), [0.0])

    def test_well_lists_must_pair_up(self) -> None:
        receipt = self.transfer(10, ["A5", "B5"], ["A5"])
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.volumes("dest_plate", ["A5"]), [0.0])

    def test_too_little_liquid_fails_after_the_tips_were_picked_up(self) -> None:
        receipt = self.transfer(1000, ["A6"], ["A6"])
        self.assertEqual(receipt["status"], "completed", receipt)
        receipt = self.transfer(1000, ["A6"], ["B6"])                           # only the placeholder rest remains
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(receipt["error"]["details"]["completed_steps"], ["pick_up_tips"])
        self.assertEqual(self.volumes("dest_plate", ["B6"]), [0.0])

    def test_mix_returns_the_liquid_to_its_wells(self) -> None:
        before = self.volumes("source_plate", ["C7", "D7"])
        receipt = self.invoke(MIX, {"tip_rack": "tip_rack", "labware": "source_plate", "wells": ["C7", "D7"],
                                    "volume": 100, "cycles": 3})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["cycles"], 3)
        self.assertEqual(self.volumes("source_plate", ["C7", "D7"]), before)


if __name__ == "__main__":
    unittest.main()
