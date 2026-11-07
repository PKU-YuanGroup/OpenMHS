"""Acceptance run of the TacEx package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream Isaac Sim /
Isaac Lab stack was not available where the gate runs, so nothing here compares the fake with the upstream environment.
The observations are the 14 values of base_env.py:588-603: ee position 3, orientation 2, object 2, goal 2, actions 5.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = [0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TacExBallRollingCases(unittest.TestCase):
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

    def test_the_action_space_is_the_clamp_of_the_environment(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0, 0.0], [0.0, -1.0001, 0.0, 0.0, 0.0],
                       [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE if len(values) == 5 else INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_ticks_are_bounded_by_the_world_class(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for ticks in (0, 10001):
            refused = self.step(client, ZERO_ACTION, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)              # the refused steps changed nothing

    def test_the_fake_is_a_world_simulator(self) -> None:
        client = self.serve()
        hello = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        self.assertEqual((hello["mode"], hello["risk_class"]), ("simulated", "R0"))
        self.assertEqual([item["kind"] for item in device["resources"]], ["world.sim"])
        self.assertEqual(sorted(item["capability_id"] for item in device["capabilities"]),
                         ["cap.world.reset.v1", "cap.world.seed.v1", "cap.world.step.v1"])

    def test_a_step_returns_fourteen_observation_values(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 14)                      # base_env.py:224-226
        self.assertTrue(all(isinstance(value, float) for value in observation))
        receipt = self.step(client, [0.25, -0.25, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["values"]), 14)
        # the fake's kinematics is a placeholder 1 mm per action unit; the last five values echo the action
        self.assertGreater(output["observation"]["values"][0], observation[0])
        self.assertLess(output["observation"]["values"][1], observation[1])
        self.assertEqual(output["observation"]["values"][9:], [0.25, -0.25, 0.0, 0.0, 0.0])
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_success_reward_is_paid_at_the_goal(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=7)["output"]["observation"]["values"]
        goal_x, goal_y = observation[7], observation[8]
        reward = 0.0
        for _ in range(300):
            ball_x, ball_y = observation[5], observation[6]
            goal_x, goal_y = observation[7], observation[8]
            if ((goal_x - ball_x) ** 2 + (goal_y - ball_y) ** 2) ** 0.5 < 0.0005:
                break
            # the fake moves the ball 1 mm per action unit (placeholder), so the action is the remaining
            # distance divided by that gain and clamped to the box
            receipt = self.step(client, [max(-1.0, min(1.0, (goal_x - ball_x) / 0.001)),
                                         max(-1.0, min(1.0, (goal_y - ball_y) / 0.001)), 0.0, 0.0, 0.0])
            self.assertEqual(receipt["status"], "completed")
            observation = receipt["output"]["observation"]["values"]
            reward = max(reward, receipt["output"]["reward"])
            if receipt["output"]["terminated"] or receipt["output"]["truncated"]:
                break
        # base_env.py:199-203 and :480: below 0.005 m the success term pays 10
        self.assertEqual(reward, 10.0)

    def test_an_out_of_bounds_object_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        output = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0], ticks=300)["output"]
        # base_env.py:230-231 and :411-412: x_bounds end at 0.75 m and the ball starts at 0.5 m; the fake moves
        # 1 mm per action unit (placeholder), so 300 ticks are enough and the step loop stops at the terminal state
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertGreater(output["observation"]["values"][5], 0.75)
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")   # a reset starts the next episode

    def test_an_episode_is_truncated_at_the_configured_length(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = self.step(client, ZERO_ACTION, ticks=1000)["output"]
        # episode_length_s 8.3333/2 s at dt 0.01 s is 416.665 steps; the fake floors it to 416 (placeholder rounding)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 416))
        self.assertEqual(self.step(client, ZERO_ACTION)["error"]["mhs_code"], PRECONDITION)

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"], other["observation"])
        self.assertEqual((first["seed"], other["seed"]), (11, 12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_passed_through(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "gymnasium:TacEx-Ball-Rolling-Privileged-v0")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"]), ("F0", 10.0))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
