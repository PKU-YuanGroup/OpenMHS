"""Acceptance run of the DexHand package: the gate, plus cases for what is specific to this driver.

All cases run on the package's fake backend (fake.py); Isaac Gym is not installed where the gate runs, so nothing here
compares the fake with an upstream simulation.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = [0.0] * 18


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DexHandCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values or ZERO_ACTION)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        pushed = list(ZERO_ACTION)
        pushed[0] = 1.5
        refused = self.step(client, pushed)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused_ticks = client.invoke("cap.world.step.v1",
                                      {"ticks": 0, "action": {"values": list(ZERO_ACTION)}}, **self.ids)
        self.assertEqual(refused_ticks["status"], "rejected")
        self.assertEqual(self.state(client)["tick"], 1)          # refused calls changed nothing

    def test_the_observation_is_the_flat_policy_vector(self) -> None:
        client = self.serve()
        observation = self.reset(client)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 224)                  # the 13 components of BaseTask.yaml:103-116
        # hand_pose is the 7-value component after 6+6+12+12 values; the default is [0,0,0.5] + identity
        self.assertEqual(observation[36:43], [0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0])
        self.assertTrue(all(value == 0.0 for value in observation[43:48]))  # no contact model in the fake

    def test_a_base_action_moves_the_model(self) -> None:
        client = self.serve()
        self.reset(client)
        action = list(ZERO_ACTION)
        action[0] = 1.0
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]["values"]
        # 1.0 * max_base_linear_velocity 0.5 m/s * physics timestep 0.005 s (BaseTask.yaml:10,44)
        self.assertAlmostEqual(observation[0], 0.0025, places=12)
        self.assertAlmostEqual(observation[6], 0.5, places=12)
        self.assertEqual(observation[48:66], action)             # prev_actions is the last action
        self.assertEqual(output["reward"], 0.1)                  # alive reward (BaseTask.yaml:62)
        self.assertEqual(output["tick"], 1)

    def test_the_episode_times_out_and_resets(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, ticks=299)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 299))
        self.assertAlmostEqual(output["reward"], 29.9, places=9)  # 299 alive rewards of 0.1
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((seeded["status"], seeded["output"]["accepted"]), ("completed", True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:dexhand021-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
