"""Acceptance run of the Humanoid-Base-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab,
torch, gymnasium and the Hugging Face assets are not installed where the gate runs, so nothing here compares the fake
with the upstream environment.  The fake is a kinematic stub; the cases check the bridge contract, the seed, the
timeout, the observation key set and the fidelity claim, not physics.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

#: The action dimension the clone states (base_env.py:120, :124).
NUM_ACTIONS = 50
#: The episode length in control steps, derived from episode_length_s 0.5 s (base_env.py:117) and
#: dt = (1/120 s) * 4 (base_env.py:32, :118, :142); it is derived, not a device fact.
EPISODE_STEPS = 15
OBSERVATION_KEYS = {
    "rgb", "fixed_rgb", "fixed_d", "left_hand_rgb", "right_hand_rgb", "qpos", "qvel", "action",
    "left_ee_pose", "right_ee_pose", "left_target_ee_pose", "right_target_ee_pose",
    "left_finger_tip_pos", "right_finger_tip_pos", "left_hand_contact_force", "right_hand_contact_force",
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HumanoidBaseCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        action = {"values": [0.0] * NUM_ACTIONS if values is None else list(values)}
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_is_a_50_element_vector(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        for length in (0, NUM_ACTIONS - 1, NUM_ACTIONS + 1):
            refused = self.step(client, values=[0.0] * length)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, length)
            self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing
        missing = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(missing["error"]["mhs_code"], INPUT_INVALID)

    def test_a_step_echoes_the_action_and_pays_no_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        values = [0.25] * NUM_ACTIONS
        receipt = self.step(client, values=values)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(observation["action"]["values"], values)
        self.assertEqual(observation["qpos"]["values"], values)                 # kinematic stand-in
        self.assertEqual(output["reward"], 0.0)                                 # base_env.py:297-298
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_the_observation_has_the_sixteen_base_keys(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        self.assertEqual(set(observation), OBSERVATION_KEYS)
        self.assertEqual(len(observation["qpos"]["values"]), NUM_ACTIONS)

    def test_a_seed_repeats_the_initial_state(self) -> None:
        def initial(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]["qpos"]["values"]

        first = initial(11)
        self.assertEqual(initial(11), first)
        self.assertNotEqual(initial(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_base_episode_times_out_after_the_control_interval(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, ticks=EPISODE_STEPS)
        output = receipt["output"]
        # base_env.py:217-219 returns the timeout as both terminated and truncated.
        self.assertEqual((output["terminated"], output["truncated"]), (True, True))
        self.assertEqual(output["tick"], EPISODE_STEPS)
        self.assertEqual(output["reward"], 0.0)
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Humanoid-Base-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
