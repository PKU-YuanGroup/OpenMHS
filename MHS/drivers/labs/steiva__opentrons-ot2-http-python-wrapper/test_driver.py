"""Acceptance run of the OT-2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpentronsOT2Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability, payload=None):
        return client.invoke(capability, payload or {}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_and_run_setup(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["robot_model"], "OT-2 fake")
        self.assertEqual(state["run_count"], 0)

        created = self.invoke(client, "x-cap.steiva.create_run.v1")
        self.assertEqual(created["status"], "completed")
        self.assertEqual(created["output"]["run_id"], "run-1")
        self.assertEqual(self.state(client)["run_count"], 1)

        pipette = self.invoke(client, "x-cap.steiva.load_pipette.v1", {"mount": "left"})
        self.assertEqual(pipette["output"]["pipette_id"], "pipette-left")

        labware = self.invoke(client, "x-cap.steiva.load_labware.v1",
                              {"labware_api_name": "opentrons_96_tiprack_300ul", "slot_name": 1})
        self.assertEqual(labware["output"]["labware_id"], "labware-1")

        self.assertEqual(self.invoke(client, "x-cap.steiva.home.v1")["output"], {"homed": True})
        self.assertEqual(self.invoke(client, "x-cap.steiva.control_run.v1",
                                     {"action": "play"})["output"], {"action": "play"})

    def test_aspirate_and_dispense(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.steiva.create_run.v1")
        self.invoke(client, "x-cap.steiva.load_pipette.v1", {"mount": "left"})

        aspirated = self.invoke(client, "cap.fluid.aspirate.v1",
                                {"volume": 50, "source": {"labware": "labware-1", "well": "A1"}})
        self.assertEqual(aspirated["status"], "completed")
        self.assertEqual(aspirated["output"], {"aspirated_volume": 50})

        dispensed = self.invoke(client, "cap.fluid.dispense.v1",
                                {"volume": 25, "target": {"labware": "labware-1", "well": "A1"}})
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"], {"dispensed_volume": 25})

    def test_the_class_volume_envelope(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.steiva.create_run.v1")
        refused = self.invoke(client, "cap.fluid.aspirate.v1",
                              {"volume": 1001, "source": {"labware": "labware-1", "well": "A1"}})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_slot_limit(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.steiva.create_run.v1")
        refused = self.invoke(client, "x-cap.steiva.load_labware.v1",
                              {"labware_api_name": "labware", "slot_name": 12})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        accepted = self.invoke(client, "x-cap.steiva.load_labware.v1",
                               {"labware_api_name": "labware", "slot_name": 11})
        self.assertEqual(accepted["status"], "completed")

    def test_the_estop_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.steiva.create_run.v1")
        client.estop("test", **self.ids)
        refused = self.invoke(client, "x-cap.steiva.create_run.v1")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_safe_state_action_stops_the_run(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.steiva.create_run.v1")
        stopped = self.invoke(client, "x-cap.steiva.stop_run.v1")
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})


if __name__ == "__main__":
    unittest.main()
