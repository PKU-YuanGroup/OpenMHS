"""Acceptance run of the Ravens package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend; the upstream Environment is
never imported or run (the gate cannot install the PyBullet stack and the clone is read-only).
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION = {
    "pose0": [[0.5, 0.0, 0.05], [0.0, 0.0, 0.0, 1.0]],
    "pose1": [[0.5, 0.0, 0.05], [0.0, 0.0, 0.0, 1.0]],
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RavensCases(unittest.TestCase):
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

    def step(self, client, ticks=1, action=None):
        fields = {"ticks": ticks}
        if action is not None:
            fields["action"] = action
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_one_tick_and_returns_the_legacy_four_tuple(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, action=ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertIn("color", output["observation"])
        self.assertIn("depth", output["observation"])
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (1, 1))
        self.assertEqual(state["reward"], 0.0)

    def test_a_reset_starts_a_new_episode_and_echoes_the_seed(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 11)
        self.assertEqual(self.state(client)["tick"], 0)
        self.step(client, action=ACTION)
        second = self.reset(client, seed=12)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["output"]["seed"], 12)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 2))

    def test_the_seed_capability_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"], {"seed": 21, "accepted": True})
        reset = self.reset(client)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 21)

    def test_a_step_without_an_action_is_refused_without_advancing(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        refused = self.step(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_world(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        self.assertEqual(self.step(client, action=ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action=ACTION), self.reset(client, seed=4)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertAlmostEqual(fidelity["timestep_ms"], 4.166666666666667)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
