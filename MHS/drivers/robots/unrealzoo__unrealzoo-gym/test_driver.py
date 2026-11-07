"""Acceptance run of the UnrealZoo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package needs
gym 0.10.9, unrealcv and a running Unreal Engine process (pyproject.toml:10-15), so nothing here compares the fake with
the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_DIM = 12  # gym_unrealcv/envs/mujoco.py:14
OBSERVATION_DIM = 48  # gym_unrealcv/envs/mujoco.py:13


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnrealMujocoGo1Cases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_step_returns_the_upstream_contract(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * ACTION_DIM, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), OBSERVATION_DIM)
        # mujoco.py:388: the reward is always 0.0 and the environment never terminates or truncates
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertEqual(output["tick"], 3)
        state = self.state(client)
        self.assertEqual((state["tick"], state["info"]["steps"]), (3, 3))

    def test_an_action_outside_the_box_is_refused_before_the_environment(self) -> None:
        client = self.serve()
        for element, value in ((0, 1.5), (ACTION_DIM - 1, -1.5)):
            values = [0.0] * ACTION_DIM
            values[element] = value
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", (element, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (element, value))
        self.assertEqual(self.state(client)["tick"], 0)  # no refused step advanced the environment
        self.assertEqual(self.step(client, [0.0] * ACTION_DIM)["status"], "completed")

    def test_a_seed_repeats_the_reset_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        again = self.reset(client, seed=7)["output"]
        other = self.reset(client, seed=8)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(again["observation"], first["observation"])
        self.assertNotEqual(other["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("unrealzoo-gym:UnrealMujoco-Go1-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_DIM)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION_DIM), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
