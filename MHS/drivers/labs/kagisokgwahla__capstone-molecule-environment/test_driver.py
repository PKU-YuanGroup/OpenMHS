"""Acceptance run of the molecule-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``); RDKit and the
upstream environment are not installed where the gate runs, so nothing here compares the fake with upstream.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MoleculeCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, action_c="Add", pos="back", mol="O", ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"action_c": action_c, "pos": pos, "mol": mol}},
            **self.ids,
        )

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_carbon_start_state(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"], {"smiles": "C"})
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["observation"]["smiles"], state["tick"]), ("C", 0))

    def test_add_and_remove_at_the_front_and_back(self) -> None:
        client = self.serve()
        self.reset(client)
        back = self.step(client, "Add", "back", "O")
        self.assertEqual((back["status"], back["output"]["observation"]["smiles"]), ("completed", "CO"))
        self.assertEqual(back["output"]["tick"], 1)
        front = self.step(client, "Add", "front", "N")
        self.assertEqual(front["output"]["observation"]["smiles"], "NCO")
        removed = self.step(client, "Remove", "back")
        self.assertEqual(removed["output"]["observation"]["smiles"], "NC")
        self.assertEqual(removed["output"]["tick"], 3)
        self.assertTrue(removed["output"]["state_hash"].startswith("sha256:"))

    def test_reset_options_choose_the_start_smiles(self) -> None:
        client = self.serve()
        receipt = self.reset(client, options={"smiles": "O"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"], {"smiles": "O"})
        self.assertEqual(self.state(client)["observation"]["smiles"], "O")
        self.assertEqual(self.reset(client)["output"]["observation"], {"smiles": "C"})

    def test_ticks_apply_the_edit_once_per_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, "Add", "back", "O", ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["smiles"], "COOO")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_reset_restores_the_start_state_after_edits(self) -> None:
        client = self.serve()
        self.reset(client)
        self.step(client, "Add", "back", "O")
        self.assertEqual(self.state(client)["observation"]["smiles"], "CO")
        second = self.reset(client)["output"]
        self.assertEqual(second["observation"]["smiles"], "C")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_ticks_outside_the_class_bound_are_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # The class schema's minimum/maximum are enforced before the driver; the runtime reports a
            # schema refusal as INPUT_INVALID because no separate Limit is declared on ticks.
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_object_needs_the_three_upstream_fields(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"action_c": "Add"}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertEqual(self.state(client)["observation"]["smiles"], "CO")


if __name__ == "__main__":
    unittest.main()
