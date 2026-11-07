"""Acceptance run of the BipedRobot package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  All cases run on the fake backend (fake.py): MuJoCo, torch, numpy and
gymnasium are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 12}
PUSH_ACTION = {"values": [1.0] * 12}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BipedRobotCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_all_twelve_action_values_are_bounded(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for index in (0, 11):
            for bound in (1.5, -1.5):
                action = {"values": [0.0] * 12}
                action["values"][index] = bound
                refused = self.step(client, action)
                self.assertEqual(refused["status"], "rejected", (index, bound))
                self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, bound))
        malformed = self.step(client, {"values": [0.0] * 11})
        self.assertEqual(malformed["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 1)          # only the first, in-range step advanced

    def test_the_observation_uses_the_upstream_lengths(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual((len(observation["actor"]["values"]), len(observation["critic"]["values"])), (50, 60))
        stepped = self.step(client, ZERO_ACTION)["output"]["observation"]
        self.assertEqual((len(stepped["actor"]["values"]), len(stepped["critic"]["values"])), (50, 60))

    def test_a_seed_repeats_the_episode(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]
        second = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(self.reset(client, seed=4)["output"]["observation"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_ticks_must_be_positive(self) -> None:
        client = self.serve()
        refused = self.step(client, ZERO_ACTION, ticks=0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_episode_truncates_at_1000_steps(self) -> None:
        client = self.serve()
        receipt = self.step(client, ZERO_ACTION, ticks=1000)
        output = receipt["output"]
        self.assertEqual((receipt["status"], output["truncated"], output["terminated"], output["tick"]),
                         ("completed", True, False, 1000))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_long_push_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, PUSH_ACTION, ticks=51)
        output = receipt["output"]
        # the stand-in tilts 0.002 rad per unit action per joint (fake.py) and stops at the 0.784 rad boundary
        self.assertEqual((receipt["status"], output["terminated"], output["tick"]), ("completed", True, 33))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:MujocoV2-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 2}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
