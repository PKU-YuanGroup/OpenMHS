"""Acceptance run of the Webots Gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py): Webots is not installed
where the gate runs, so nothing here compares the fake with the upstream Webots environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WebotsStickCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 2):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_follows_the_wheel_direction(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["output"]["observation"]["values"], ZERO)
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # The fake's per-step increments are placeholders (fake.py); the direction is the upstream rule at
        # controllers/gym_controller/gym_controller.py:77.
        self.assertEqual(output["observation"]["values"], [0.00005, 0.00005, 0.00005, 0.00005])
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (1.0, False, False, 1))
        self.reset(client)
        self.assertEqual(self.step(client, 0)["output"]["observation"]["values"],
                         [-0.00005, -0.00005, -0.00005, -0.00005])

    def test_one_action_repeats_for_every_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, 1, ticks=2)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (2, 2.0))
        for value, expected in zip(output["observation"]["values"],
                                   [0.0001, 0.00005, 0.000150005, 0.000100005]):
            self.assertAlmostEqual(value, expected, places=12)

    def test_a_falling_pole_ends_the_episode_with_reward_zero(self) -> None:
        client = self.serve()
        self.reset(client)
        ticks = 0
        while True:
            receipt = self.step(client, 1)
            self.assertEqual(receipt["status"], "completed", receipt)
            ticks += 1
            output = receipt["output"]
            if output["terminated"]:
                break
            self.assertEqual((output["truncated"], output["reward"]), (False, 1.0), ticks)
            self.assertLess(ticks, 500, "the fake never reaches its threshold")
        # The placeholder fall reaches the 0.2 rad threshold in tens of transitions (fake.py); the termination rule
        # is the upstream one at controllers/gym_controller/gym_controller.py:87-92.
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(output["reward"], 0.0)
        self.assertGreater(ticks, 10)
        self.assertGreater(output["observation"]["values"][2], 0.2)
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")               # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_time_limit_is_never_enforced(self) -> None:
        client = self.serve()
        observation = self.reset(client)["output"]["observation"]["values"]
        total = 0.0
        output = None
        for expected_tick in range(1, 1001):
            action = 1 if observation[2] + observation[3] < 0 else 0               # keeps the fake near zero
            receipt = self.step(client, action)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            self.assertFalse(output["terminated"], expected_tick)
            total += output["reward"]
            observation = output["observation"]["values"]
        # The constructor's max_episode_steps=1000 is only stored in EnvSpec; reset/step never truncate
        # (controllers/gym_controller/gym_controller.py:17-35).
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1000))
        self.assertEqual(total, 1000.0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"]["values"], ZERO)                     # upstream reset is fixed at zero
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"]["values"], ZERO)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 0, 1, 1)]

        first = trajectory(11)
        self.assertEqual(len(set(first)), len(first))               # every transition is observable in the hash
        self.assertEqual(trajectory(11), first)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:webots-gym-example", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
