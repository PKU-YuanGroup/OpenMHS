"""Acceptance run of the WarpAUV package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything here runs on the fake backend (fake.py): the upstream
IsaacSim/IsaacLab stack was not installed, so nothing compares the fake with the real environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = {"values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WarpAUVCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, ZERO["values"], ticks=2)["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, -1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        short = self.step(client, [0.0] * 5)                                    # the schema needs six values
        self.assertEqual((short["status"], short["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 2)                          # the refused steps changed nothing

    def test_the_observation_has_seventeen_values(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]
        self.assertEqual(len(observation["values"]), 17)
        receipt = self.step(client, ZERO["values"])
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["observation"]["values"]), 17)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_thruster_command_changes_the_state(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=2)["output"]["observation"]["values"]
        receipt = self.step(client, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        self.assertNotEqual(before, after)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertGreaterEqual(len(receipt["output"]["state_hash"]), 64)

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        second = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(first, second)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fake_episode_is_truncated_at_180_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ZERO["values"], ticks=180)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 180))
        ended = self.step(client, ZERO["values"])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Isaac-WarpAUV-Direct-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 120.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO["values"])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO["values"]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
