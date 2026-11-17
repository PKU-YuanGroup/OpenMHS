"""Acceptance run of the Isaac Lab Parkour package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the upstream package are not installed where the gate runs, so nothing here compares the fake with the simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_DIM = 12                                                              # the fake's placeholder action size
OBS_DIM = 753                                                                # 53 + 132 + 9 + 29 + 10 * 53


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ParkourTeacherCases(unittest.TestCase):
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
        values = [0.0] * ACTION_DIM if values is None else values
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_declared_single_environment_placeholder_shapes(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=7)
        self.assertEqual(reset["status"], "completed")
        observation = reset["output"]["observation"]["policy"]["values"]
        self.assertEqual(len(observation), 1)
        self.assertEqual(len(observation[0]), OBS_DIM)
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        stepped = receipt["output"]["observation"]["policy"]["values"]
        self.assertEqual((len(stepped), len(stepped[0])), (1, OBS_DIM))
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_action_reaches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        first = self.step(client, values=[1.0] * ACTION_DIM)["output"]["observation"]["policy"]["values"][0]
        second = self.step(client, values=[2.0] * ACTION_DIM)["output"]["observation"]["policy"]["values"][0]
        self.assertNotEqual(first, second)
        self.assertAlmostEqual(second[0] - first[0], 0.25)                   # scale 0.25; fake default offset is zero

    def test_repeating_an_absolute_joint_target_does_not_add_a_delta(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        first = self.step(client, values=[1.0] * ACTION_DIM)["output"]["observation"]["policy"]["values"][0]
        second = self.step(client, values=[1.0] * ACTION_DIM)["output"]["observation"]["policy"]["values"][0]
        self.assertEqual(first[:ACTION_DIM], second[:ACTION_DIM])

    def test_action_clip_interval_is_an_endpoint_envelope(self) -> None:
        client = self.serve()
        for index in range(ACTION_DIM):
            for value in (-4.8001, 4.8001):
                values = [0.0] * ACTION_DIM
                values[index] = value
                refused = self.step(client, values=values)
                self.assertEqual(refused["status"], "rejected", (index, value, refused))
                self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.state(client)["tick"], 0)
        for value in (-4.8, 4.8):
            self.assertEqual(self.step(client, values=[value] * ACTION_DIM)["status"], "completed")

    def test_the_seed_repeats_the_placeholder_start(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=21)["output"]["observation"]
        second = self.reset(client, seed=21)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, self.reset(client, seed=22)["output"]["observation"])

    def test_the_teacher_episode_truncates_at_its_length(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1000, False, True))
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["timestep_ms"], 20.0)
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "parameter"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertFalse(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced

    def test_the_action_values_must_have_the_space_width(self) -> None:
        client = self.serve()
        refused = self.step(client, values=[0.0] * (ACTION_DIM - 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
