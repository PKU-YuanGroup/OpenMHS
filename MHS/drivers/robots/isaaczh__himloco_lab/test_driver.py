"""Acceptance run of the HimLoco Lab driver: the gate, plus cases for what is specific to this package.

The cases run on the fake backend (fake.py).  gymnasium, torch, Isaac Lab and Isaac Sim are not installed where the
gate runs, so nothing here compares the fake with the upstream environment; the fidelity ``gaps`` say so.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = {"values": [0.5] * 12}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HimlocoCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_contract_and_the_action_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        policy = output["observation"]["policy"]["values"]
        self.assertEqual(len(policy), 45)                                  # 3 + 3 + 3 + 12 + 12 + 12
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(output["reward"], 0.0)                            # the fake reports no reward
        # JointPositionActionCfg: scale=0.25 (velocity_env_cfg.py:248), so the relative joint block is scale * action.
        self.assertEqual(policy[9:21], [0.125] * 12)
        self.assertEqual(policy[33:45], [0.5] * 12)                        # last_action block
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_the_action_space_refuses_out_of_range_values(self) -> None:
        client = self.serve()
        self.step(client, {"values": [0.0] * 12})
        for replacement in (-101.0, 101.0):
            values = [0.0] * 12
            values[4] = replacement
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", replacement)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, replacement)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refusals changed nothing

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            return receipt["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_episode_truncates_at_1000_ticks(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, {"values": [0.0] * 12}, ticks=1000)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed", receipt)
        # 20 s episode / (4 * 0.005 s step) = 1000 ticks (velocity_env_cfg.py:488-492)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1000, False, True))
        ended = self.step(client, {"values": [0.0] * 12})
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Unitree-Go2-Velocity", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
