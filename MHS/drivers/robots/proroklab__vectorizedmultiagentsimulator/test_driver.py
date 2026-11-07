"""Acceptance run of the VMAS balance package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the clone is never imported and torch, gymnasium and shimmy are not
installed where the gate runs, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
AGENTS = ("agent_0", "agent_1", "agent_2")
ACTION = {"agent_0": [0.5, 0.0], "agent_1": [0.0, 0.5], "agent_2": [-0.5, -0.5]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VMASBalanceCases(unittest.TestCase):
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

    def step(self, client, action=ACTION, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        before = self.state(client)["tick"]
        for agent, bad in (("agent_0", [2.0, 0.0]), ("agent_1", [0.0, -1.5]), ("agent_2", [-2.0, 2.0])):
            action = {"agent_0": [0.0, 0.0], "agent_1": [0.0, 0.0], "agent_2": [0.0, 0.0]}
            action[agent] = bad
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", agent)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, agent)
        self.assertEqual(self.state(client)["tick"], before)                    # the refused steps changed nothing

    def test_a_step_advances_the_world(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        start = self.state(client)["observation"][AGENTS[0]]["values"]
        receipt = self.step(client, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(set(output["observation"]), set(AGENTS))
        for name in AGENTS:
            self.assertEqual(len(output["observation"][name]["values"]), 16)
        moved = output["observation"][AGENTS[0]]["values"]
        self.assertNotEqual(moved[:4], start[:4])                                # the action changed the world
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_seed_repeats_the_start_state(self) -> None:
        def start(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["seed"], seed)
            return receipt["output"]["observation"]

        first = start(11)
        self.assertEqual(start(11), first)
        self.assertNotEqual(start(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_reset_options_are_accepted_and_unused(self) -> None:
        client = self.serve()
        plain = self.reset(client, seed=5)["output"]["observation"]
        with_options = self.reset(client, seed=5, options={"low": 0.9, "high": 0.9})["output"]["observation"]
        self.assertEqual(with_options, plain)                                  # GymnasiumWrapper ignores options

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("vmas:balance", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
