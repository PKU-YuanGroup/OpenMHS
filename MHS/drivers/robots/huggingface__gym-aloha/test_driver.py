"""Acceptance run of the gym-aloha package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym_aloha itself is not
installed where the gate runs (it needs MuJoCo and a GL context), so nothing here compares the fake with the upstream
environment.  The fake models the interface and the start state of the environment and no physics, so these cases
check the contract, the joint-target effect, the seed, the 300-step truncation and the e-stop; they do not check a
reward, because the upstream reward is a contact predicate the fake cannot evaluate.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 14


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AlohaCases(unittest.TestCase):
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

    def test_aloha_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        too_high = list(ZERO_ACTION)
        too_high[3] = 1.5                                   # gym_aloha/env.py:86: the action space is -1 to 1
        refused = self.step(client, too_high)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        refused = self.step(client, ZERO_ACTION[:13])       # 13 values cannot fill the 14-element Box
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, refused)
        self.assertEqual(self.state(client)["tick"], 1)     # the refused steps changed nothing

    def test_aloha_a_step_follows_the_joint_targets(self) -> None:
        client = self.serve()
        action = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7, -0.1, 0.2, -0.3, 0.4, -0.5, 0.6, -0.7]
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        qpos = output["observation"]["agent_pos"]["values"]   # gym_aloha/env.py:143-147
        self.assertEqual(len(qpos), 14)
        # gym_aloha/tasks/sim.py:38-69: the arm joints are the commanded absolute targets and the gripper value is
        # unnormalized for the physics and normalized again for the observation, so it comes back unchanged
        for index in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12):
            self.assertAlmostEqual(qpos[index], action[index], places=9, msg=f"qpos[{index}]")
        self.assertAlmostEqual(qpos[6], action[6], places=9)
        self.assertAlmostEqual(qpos[13], action[13], places=9)
        self.assertEqual((output["tick"], output["reward"], output["terminated"], output["truncated"]),
                         (1, 0.0, False, False))
        self.assertEqual(self.state(client)["observation"]["agent_pos"]["values"], qpos)

    def test_aloha_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first)
        self.assertEqual(self.reset(client, seed=11)["output"]["seed"], 11)

    def test_aloha_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_aloha_the_episode_truncates_at_300_ticks(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, ZERO_ACTION, ticks=300)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # gym_aloha/__init__.py:6: max_episode_steps 300, applied by the TimeLimit that gymnasium.make adds
        self.assertEqual((output["tick"], output["truncated"], output["terminated"]), (300, True, False))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_aloha_the_reset_takes_no_named_scenario(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.reset.v1", {"scenario": "default"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, refused)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_aloha_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:gym_aloha/AlohaInsertion-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        self.assertTrue(any("480 x 640 x 3" in gap for gap in fidelity["gaps"]), fidelity["gaps"])

    def test_aloha_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
