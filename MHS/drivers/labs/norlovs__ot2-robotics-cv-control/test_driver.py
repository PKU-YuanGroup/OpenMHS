"""Acceptance run of the OT-2 twin package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): neither gymnasium nor
pybullet is installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# src/ot2/ot2_gym_wrapper.py:16-17: the goal sampling bounds of the upstream environment
LOW = (-0.1875, -0.1705, 0.1196)
HIGH = (0.2535, 0.2195, 0.2895)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OT2TwinCases(unittest.TestCase):
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

    def test_the_action_space_bounds_the_velocities(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([-1.0001, 0.0, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_reset_draws_the_goal_inside_the_working_envelope(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 6)
        for value, low, high in zip(observation[3:], LOW, HIGH):
            self.assertGreaterEqual(value, low)
            self.assertLessEqual(value, high)

    def test_a_seed_repeats_the_reset_and_a_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            reset = self.reset(client, seed=seed)["output"]
            step = self.step(client, [0.5, -0.4, 0.3])["output"]
            return reset["seed"], reset["observation"]["values"], step["observation"]["values"], step["state_hash"]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12)[1][3:], first[1][3:])                # another goal draw

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_success_terminates_with_the_bonus(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["values"]
        output = None
        for _ in range(300):
            position, goal = observation[:3], observation[3:]
            distance = math.dist(position, goal)
            if distance < 0.01:                                                 # already inside the threshold
                break
            direction = [(target - current) / distance for current, target in zip(position, goal)]
            receipt = self.step(client, direction)
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            observation = output["observation"]["values"]
            if output["terminated"]:
                break
        else:
            self.fail("the episode did not terminate")
        if output is None or not output["terminated"]:
            self.fail("the episode did not terminate")
        distance = math.dist(observation[:3], observation[3:])
        self.assertLess(distance, 0.01)                                          # ot2_gym_wrapper.py:69
        self.assertAlmostEqual(output["reward"], -distance + 10.0, places=9)     # ot2_gym_wrapper.py:66-71
        self.assertFalse(output["truncated"])

    def test_the_episode_truncates_at_max_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=1000)                # max_steps defaults to 1000
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")      # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_info_reports_the_distance_to_the_goal(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        observation = self.step(client, [0.5, 0.0, 0.0])["output"]["observation"]["values"]
        info = self.state(client)["info"]
        self.assertEqual(info["current_position"], observation[:3])
        self.assertEqual(info["target_position"], observation[3:])
        self.assertAlmostEqual(info["distance_to_goal"], math.dist(observation[:3], observation[3:]), places=12)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:OT-2-digital-twin", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
