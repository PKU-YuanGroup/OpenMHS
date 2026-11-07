"""Acceptance run of the InternUtopia package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); Isaac Sim is not
installed and cannot run where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PATH = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class InternUtopiaCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, action=None, ticks=1):
        fields = {"ticks": ticks}
        if action is not None:
            fields["action"] = action
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def move(self, client, path, ticks=1):
        return self.step(client, {"move_along_path": path}, ticks=ticks)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_fake_starts_at_the_identity_pose(self) -> None:
        client = self.serve()
        output = self.reset(client)["output"]
        self.assertEqual(output["observation"]["position"]["values"], [0.0, 0.0, 0.0])
        self.assertEqual(output["observation"]["orientation"]["values"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_path_point_moves_the_fake_and_advances_one_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.move(client, PATH)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["position"]["values"], PATH[0])
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        second = self.move(client, PATH, ticks=2)
        self.assertEqual(second["output"]["observation"]["position"]["values"], PATH[1])
        self.assertEqual(second["output"]["tick"], 3)

    def test_the_demo_wrapper_is_accepted(self) -> None:
        client = self.serve()
        self.reset(client)
        # tests/h1_locomotion.py:58-61 passes {name: [path]}; the fake accepts that wrapper as well
        receipt = self.step(client, {"move_along_path": [PATH]})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["position"]["values"], PATH[0])

    def test_an_action_outside_the_space_is_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        refused = self.step(client, {"unknown_controller": 1})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["seed"], 21)

    def test_reset_options_are_accepted_and_ignored(self) -> None:
        client = self.serve()
        receipt = self.reset(client, options={"note": "the upstream reset accepts options but never reads them"})
        self.assertEqual(receipt["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("internutopia:isaac_sim", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"move_along_path": PATH})["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, {"move_along_path": PATH}), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
