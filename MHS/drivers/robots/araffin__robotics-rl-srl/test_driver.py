"""Acceptance run of the OmniRobot package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the upstream simulator needs numpy, OpenCV, PyTorch, SciPy, ZMQ and
seaborn and is not importable where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

# fake.py placeholder marker colours (16 x 16 x 3 stand-in; the device returns 224 x 224 x 3)
TARGET = (255, 0, 0)
ROBOT = (0, 128, 0)
BOTH = (255, 128, 0)


def markers(image):
    """The placeholder target and robot pixels of an observation."""
    target = robot = None
    for y, row in enumerate(image):
        for x, pixel in enumerate(row):
            pixel = tuple(pixel)
            if pixel == TARGET or pixel == BOTH:
                target = (x, y)
            if pixel == ROBOT or pixel == BOTH:
                robot = (x, y)
    return robot, target


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OmniRobotCases(unittest.TestCase):
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
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_is_a_placeholder_image(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (16, 16, 3))
        robot, target = markers(values)
        self.assertIsNotNone(robot)
        self.assertIsNotNone(target)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (0, 1, 2, 3, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_greedy_step_reaches_the_target(self) -> None:
        # The clone pays +1 within 0.2 m of the target (real_robots/omnirobot_utils/omnirobot_manager_base.py:152-158).
        for seed in range(20):
            client = self.serve()
            observation = self.reset(client, seed=seed)["output"]["observation"]["values"]
            for _ in range(40):
                robot, target = markers(observation)
                self.assertIsNotNone(robot)
                self.assertIsNotNone(target)
                dx, dy = target[0] - robot[0], target[1] - robot[1]
                if abs(dx) >= abs(dy):
                    action = 0 if dx > 0 else 1                  # FORWARD raises x, BACKWARD lowers it
                else:
                    action = 2 if dy > 0 else 3                  # LEFT raises y, RIGHT lowers it
                output = self.step(client, action)["output"]
                observation = output["observation"]["values"]
                if output["reward"] == 1.0:
                    self.assertGreaterEqual(output["tick"], 1)
                    return
        self.fail("the fake reached no target within 40 greedy steps for 20 seeds")

    def test_a_wall_bump_pays_minus_one(self) -> None:
        # Moving away from the target and into the 0.85 boundary (real_robots/constants.py:92-93,121) pays -1
        # (real_robots/omnirobot_utils/omnirobot_manager_base.py:155-156).
        for seed in range(20):
            client = self.serve()
            observation = self.reset(client, seed=seed)["output"]["observation"]["values"]
            robot, target = markers(observation)
            if max(abs(target[0] - robot[0]), abs(target[1] - robot[1])) < 3:
                continue                                              # too close: the step may reach the target
            action = 1 if target[0] > robot[0] else 0                 # move away from the target in x
            for _ in range(15):
                reward = self.step(client, action)["output"]["reward"]
                if reward == -1.0:
                    return
        self.fail("the fake paid no wall bump within 15 steps for 20 seeds")

    def test_the_episode_ends_after_max_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, 0, ticks=251)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # MAX_STEPS is 250 and the native check is _env_step_counter > MAX_STEPS (omnirobot_env.py:294).
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 251))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "gymnasium:OmnirobotEnv-v0 (analytic fake of the in-process simulator)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
