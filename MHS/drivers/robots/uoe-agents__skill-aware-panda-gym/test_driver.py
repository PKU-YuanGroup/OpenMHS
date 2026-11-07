"""Acceptance run of the skill-aware Panda-gym package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream stack
(panda-gym, gymnasium, pybullet, numpy and scipy) is not installed where the gate runs, so nothing here compares
the fake with the upstream environment or a PyBullet run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def _clip(value, low, high):
    return min(high, max(low, value))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SkillAwareCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0], [0.0, -1.1, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        wrong_length = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(wrong_length["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused calls changed nothing

    def test_a_seed_repeats_the_reset(self) -> None:
        def start(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            return receipt["output"]["seed"], receipt["output"]["observation"]

        seed, first = start(17)
        self.assertEqual(seed, 17)
        self.assertEqual(start(17)[1], first)
        self.assertNotEqual(start(18)[1], first)                  # the object and goal draws follow the seed

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_moves_the_end_effector_and_reports_the_skill(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["terminated"], output["truncated"], output["reward"]), (False, False, -1.0))
        before = self.reset(client, seed=5)["output"]["observation"]
        after = self.step(client, [1.0, 0.0, 0.0, 0.0])["output"]["observation"]
        self.assertGreater(after["observation"]["values"][0], before["observation"]["values"][0])
        # the object rests above 0.019 and below 0.021, which get_state labels "push" (envs/__init__.py:150)
        self.assertEqual(self.state(client)["info"]["state"], "push")

    def test_a_grasp_and_lift_is_labelled_pick(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        object_xy = observation["achieved_goal"]["values"][:2]
        for _ in range(12):
            robot = observation["observation"]["values"]
            action = [_clip((object_xy[0] - robot[0]) / 0.05, -1.0, 1.0),
                      _clip((object_xy[1] - robot[1]) / 0.05, -1.0, 1.0),
                      _clip((0.0 - robot[2]) / 0.05, -1.0, 1.0), 1.0]
            observation = self.step(client, action)["output"]["observation"]
        lifted = self.step(client, [0.0, 0.0, 1.0, 1.0])
        self.assertEqual(lifted["status"], "completed")
        self.assertEqual(self.state(client)["info"]["state"], "pick")
        for _ in range(3):                                        # open the fingers above the table
            self.assertEqual(self.step(client, [0.0, 0.0, 0.0, -1.0])["status"], "completed")
        self.assertEqual(self.state(client)["info"]["state"], "roll")   # high and no finger contact

    def test_the_episode_is_truncated_at_50_steps(self) -> None:
        client = self.serve()
        output = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=50)["output"]
        # the TimeLimit that gymnasium.make adds from the registration (skill_aware_panda_gym/__init__.py:10)
        self.assertEqual((output["tick"], output["truncated"], output["terminated"]), (50, True, False))
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(fidelity["engine"], "python:skill_aware_panda_gym.fake:FakePandaPushEnv")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
