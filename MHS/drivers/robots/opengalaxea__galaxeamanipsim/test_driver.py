"""Acceptance run of the Galaxea R1Base-v0 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream Sapien
environment is not installed where the gate runs and is never imported by package code, so nothing here compares the
fake with an upstream run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
LEFT = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
RIGHT = [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6]
ACTION = LEFT + [0.7] + RIGHT + [0.8]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GalaxeaR1BaseCases(unittest.TestCase):
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

    def test_the_initial_state_is_the_upstream_base_state(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        observation = receipt["output"]["observation"]
        upper = observation["upper_body_observations"]
        self.assertEqual(upper["left_arm_joint_position"]["values"], [0.0] * 6)
        self.assertEqual(upper["right_arm_joint_position"]["values"], [0.0] * 6)
        self.assertEqual(upper["left_arm_gripper_position"]["values"], [0.0])
        self.assertEqual(upper["right_arm_gripper_position"]["values"], [0.0])
        self.assertEqual(upper["left_arm_joint_velocity"]["values"], [0.0] * 6)
        self.assertEqual(observation["lower_body_observations"]["torso_joint_position"]["values"], [0.0] * 4)
        self.assertEqual(observation["language_instruction"]["value"], "")
        self.assertEqual(observation["object_dict"], {})
        state = self.state(client)
        self.assertEqual((state["tick"], state["reward"], state["terminated"], state["truncated"]), (0, 0.0, False, False))

    def test_a_step_copies_the_commanded_targets(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        upper = observation["upper_body_observations"]
        self.assertEqual(upper["left_arm_joint_position"]["values"], LEFT)
        self.assertEqual(upper["right_arm_joint_position"]["values"], RIGHT)
        self.assertEqual(upper["left_arm_gripper_position"]["values"], [0.7])
        self.assertEqual(upper["right_arm_gripper_position"]["values"], [0.8])
        commands = observation["upper_body_action_dict"]
        self.assertEqual(commands["left_arm_joint_position_cmd"]["values"], LEFT)
        self.assertEqual(commands["right_arm_gripper_position_cmd"]["values"], [0.8])
        # The base environment reports reward 0, no termination and no truncation on every step.
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(state["observation"]["upper_body_observations"]["right_arm_joint_position"]["values"], RIGHT)

    def test_ticks_applies_the_action_more_than_once(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ACTION, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["reward"]), (3, 0.0))
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_action_length_is_the_envelope(self) -> None:
        client = self.serve()
        self.reset(client)
        for values in (ACTION[:-1], ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)  # the refused steps changed nothing

    def test_ticks_must_stay_inside_the_class_schema(self) -> None:
        client = self.serve()
        self.reset(client)
        for ticks in (0, 10001):
            refused = self.step(client, ACTION, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 9}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 9, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 9)
        self.assertEqual(self.reset(client, seed=4)["output"]["seed"], 4)

    def test_the_same_actions_repeat_the_state_hashes(self) -> None:
        def hashes():
            client = self.serve()
            self.reset(client, seed=5)
            return [self.step(client, ACTION)["output"]["state_hash"],
                    self.step(client, RIGHT + [0.1] + LEFT + [0.2])["output"]["state_hash"]]

        self.assertEqual(hashes(), hashes())

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(device["safety"]["estop"], {"kind": "software", "latching": True, "native": None})
        fidelity = device["fidelity"]
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sapien:BimanualManipulationEnv", "F0"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertTrue(any("NOT COVERED" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.step(client, ACTION)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
