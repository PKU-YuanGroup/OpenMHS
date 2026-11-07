"""Acceptance run of the gym_av_aloha package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py): mujoco and dm-control are not installed where the gate runs, so nothing
here compares the fake with the upstream MuJoCo environment.  Never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


def values(value):
    return [float(value)] * 21


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CubeTransferCases(unittest.TestCase):
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

    def step(self, client, action_values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": action_values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_step_applies_the_action_to_the_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, values(1.5))
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(observation["agent_pos"]["values"], values(1.5))
        self.assertEqual(observation["environment_state"]["values"][2], 0.0)
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["terminated"]), (1, False))
        self.assertEqual(receipt["output"]["reward"], 0.0)

    def test_ticks_advance_the_world_and_the_state(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        self.assertEqual(self.step(client, values(0.25), ticks=2)["output"]["tick"], 2)
        receipt = self.step(client, values(0.5))
        self.assertEqual(receipt["output"]["tick"], 3)
        state = self.state(client)
        self.assertEqual(state["tick"], 3)
        self.assertEqual(state["observation"]["agent_pos"]["values"], values(0.5))

    def test_a_wrong_action_length_is_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        refused = self.step(client, [0.0] * 20)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)                  # refused before the bridge call

    def test_a_seed_repeats_the_cube_pose(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=17)["output"]
        second = self.reset(client, seed=17)["output"]
        other = self.reset(client, seed=18)["output"]
        self.assertEqual((first["seed"], second["seed"]), (17, 17))
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"]["environment_state"], other["observation"]["environment_state"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["output"]["seed"], accepted["output"]["accepted"]), (21, True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_reset_clears_the_tick_and_the_arm_pose(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        self.step(client, values(2.0))
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["observation"]["agent_pos"]["values"], values(0.0))

    def test_the_observation_has_no_pixels(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        observation = self.state(client)["observation"]
        self.assertEqual(sorted(observation), ["agent_pos", "environment_state"])
        self.assertNotIn("pixels", observation)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        self.step(client, values(0.5))
        client.estop("test", **self.ids)
        for refused in (self.step(client, values(0.5)), self.reset(client, seed=7)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
