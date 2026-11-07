"""Acceptance run of the CS285 obstacles package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the clone's gym and
mujoco-py are not installed where the gate runs and nothing here imports the clone, so nothing compares the fake
with the upstream environment.
"""

import importlib.util
import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
START = [-0.5, 0.75]
END = [0.7, -0.8]


def _fake_module():
    spec = importlib.util.spec_from_file_location("cs285_obstacles_fake", HERE / "fake.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ObstaclesCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([1.0, 0.0], [0.0, -1.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                     # the refused steps changed nothing

    def test_a_zero_action_keeps_the_position_and_pays_the_distance(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["values"]
        receipt = self.step(client, [0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["values"], observation)
        distance = math.hypot(observation[0] - observation[2], observation[1] - observation[3])
        self.assertAlmostEqual(output["reward"], -distance, places=12)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))
        self.assertEqual((observation[2], observation[3]), (END[0], END[1]))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                          # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([0.2, 0.1], [0.0, 0.0], [-0.3, 0.2], [0.1, -0.1])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_ticks_bound_is_enforced(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, [0.0, 0.0], ticks=ticks)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID), ticks)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:cs285.envs.obstacles", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


class FakeCases(unittest.TestCase):
    def test_the_fake_moves_and_blocks(self) -> None:
        fake = _fake_module().FakeObstacles(random_starts=False)
        self.assertEqual(fake.reset(), [START[0], START[1], END[0], END[1]])
        observation, _reward, _done, _info = fake.step([0.99, 0.0])
        self.assertAlmostEqual(observation[0], START[0] + 0.099, places=12)
        blocked, _reward, _done, _info = fake.step([0.99, 0.0])           # obstacle [-0.4, 0.8, 0.4, 0.3]
        self.assertEqual(blocked[:2], observation[:2])

    def test_the_fake_reports_done_near_the_end(self) -> None:
        fake = _fake_module().FakeObstacles(random_starts=False)
        fake.reset()
        fake.current = [0.7, -0.79]                                       # 0.01 from the configured end
        observation, reward, done, _info = fake.step([0.0, 0.0])
        self.assertEqual(observation[:2], fake.current)
        self.assertAlmostEqual(reward, -0.01, places=12)
        self.assertEqual(done, 1.0)

    def test_the_fake_seed_repeats_and_applies_zero(self) -> None:
        first = _fake_module().FakeObstacles()
        second = _fake_module().FakeObstacles()
        self.assertEqual(first.reset(seed=7), second.reset(seed=7))
        self.assertNotEqual(first.reset(seed=8), second.reset(seed=7))
        self.assertEqual(first.reset(seed=0), second.reset(seed=0))       # the fake applies seed 0


if __name__ == "__main__":
    unittest.main()
