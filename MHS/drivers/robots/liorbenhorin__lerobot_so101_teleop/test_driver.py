"""Acceptance run of the lerobot_so101_teleop package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab,
torch and the clone's USD assets are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ACTION = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
CAMERA_VALUES = 18


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class So101RockAStackCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.device_id = device_id
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values=ACTION, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_held_joint_target_is_the_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # the fake holds the commanded joint positions (fake.py; the real task applies them through Isaac Lab)
        self.assertEqual(output["observation"]["policy"]["values"], ACTION)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertEqual(output["tick"], 1)
        self.assertEqual(self.state(client)["observation"]["policy"]["values"], ACTION)

    def test_ticks_advance_the_policy_step(self) -> None:
        client = self.serve()
        self.reset(client)
        output = self.step(client, ticks=3)["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(output["observation"]["policy"]["values"], ACTION)
        self.assertEqual(self.state(client)["tick"], 3)
        # cap.world.step.v1 bounds ticks to 1..10000 (the bridge's default max_ticks); the schema refuses the rest
        refused = self.step(client, ticks=10001)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))

    def test_the_episode_truncates_at_five_seconds(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=300)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # 5 s at the 1/60 s policy step (base_env_cfg.py:297-298 and :305) is 300 steps
        self.assertEqual((output["tick"], output["truncated"], output["terminated"]), (300, True, False))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_must_have_six_joint_values(self) -> None:
        client = self.serve()
        self.reset(client)
        for values in ([0.0], [0.0] * 5, [0.0] * 7):
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)                         # the refused steps changed nothing

    def test_the_action_space_is_unbounded(self) -> None:
        client = self.serve()
        self.reset(client)
        values = [1e6, -1e6, 0.0, 1e-6, -1e-6, 0.0]
        receipt = self.step(client, values=values)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["observation"]["policy"]["values"], values)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)

    def test_the_visual_groups_are_published(self) -> None:
        client = self.serve()
        self.reset(client)
        observation = self.reset(client)["output"]["observation"]
        self.assertEqual(sorted(observation), ["policy", "visual"])
        self.assertEqual(sorted(observation["visual"]), ["camera_ego", "camera_external"])
        self.assertEqual(len(observation["policy"]["values"]), 6)
        for name in ("camera_ego", "camera_external"):
            self.assertEqual(len(observation["visual"][name]["values"]), CAMERA_VALUES)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.device_id)
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "isaaclab:Lerobot-So101-Teleop-Rock-A-Stack-Simple")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.step(client)
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                         # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
