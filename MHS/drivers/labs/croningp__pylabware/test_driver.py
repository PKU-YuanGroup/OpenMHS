"""Acceptance run of the C3000 package: the gate, plus cases for what is specific to this driver.

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


class C3000Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def configure(self, client, **patch):
        return self.invoke(client, "cap.device.configure.v1", patch)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_start_from_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["plunger_position"], 0)
        self.assertEqual(state["valve_position"], "I")
        self.assertTrue(state["initialized"])
        self.assertTrue(state["idle"])
        self.assertTrue(state["connected"])

    def test_the_valve_write_reaches_the_fake_and_reads_back(self) -> None:
        client = self.serve()
        receipt = self.configure(client, valve_position="O")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["valve_position"], "O")

    def test_the_speed_bound_is_enforced(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.croningp.set_speed.v1", {"speed": 48001})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        completed = self.invoke(client, "x-cap.croningp.set_speed.v1", {"speed": 48000})
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"], {"speed": 48000})

    def test_the_plunger_actions_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.croningp.transfer.v1",
                              {"increments": 10, "direction": "dispense"})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["plunger_position"], 0)

    def test_the_example_overlay_supplies_the_travel(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        filled = self.invoke(client, "x-cap.croningp.transfer.v1",
                             {"increments": 10, "direction": "dispense"})
        self.assertEqual(filled["status"], "completed")
        self.assertEqual(filled["output"]["plunger_position"], -10)
        withdrawn = self.invoke(client, "x-cap.croningp.transfer.v1",
                                {"increments": 4, "direction": "withdraw"})
        self.assertEqual(withdrawn["output"]["plunger_position"], -6)
        homed = self.invoke(client, "x-cap.croningp.move_home.v1", {})
        self.assertEqual(homed["output"]["plunger_position"], 0)
        self.assertEqual(self.state(client)["plunger_position"], 0)

    def test_the_relative_and_absolute_moves_use_the_overlay(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        relative = self.invoke(client, "x-cap.croningp.move_plunger.v1",
                               {"position": 5, "mode": "relative"})
        self.assertEqual(relative["output"]["plunger_position"], 5)
        absolute = self.invoke(client, "x-cap.croningp.move_plunger.v1",
                               {"position": 2, "mode": "absolute"})
        self.assertEqual(absolute["output"]["plunger_position"], 2)

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertTrue(self.state(client)["idle"])
        refused = self.invoke(client, "x-cap.croningp.move_home.v1", {})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
