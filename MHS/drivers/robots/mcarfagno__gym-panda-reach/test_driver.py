"""Acceptance run of the gym-panda-reach package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the package's fake backend (fake.py); the
upstream PyBullet environment is not installed and is never imported, so no case compares the fake with it.
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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaReachCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [1.0, 1.0, 1.0, 1.0])["status"], "completed")
        for values in ([1.1, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, -2.0], [0.0, -1.0001, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_first_step_applies_the_upstream_control_law(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        receipt = self.step(client, [0.2, -0.4, 0.6, 0.5])
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 24)
        # panda_env.py:52-55: newPosition = current + [0.2, -0.4, 0.6] * dv with dv = 0.05; fingers = action[3]
        self.assertAlmostEqual(values[0], start[0] + 0.01, places=9)
        self.assertAlmostEqual(values[1], start[1] - 0.02, places=9)
        self.assertAlmostEqual(values[2], start[2] + 0.03, places=9)
        self.assertAlmostEqual(values[9], 0.5, places=9)                # mean of both finger joints
        self.assertEqual(values[10:14], [0.0, 0.0, 0.0, 1.0])          # fixed object orientation
        self.assertAlmostEqual(values[20], 0.01, places=9)              # grip velocity = action * dv
        self.assertAlmostEqual(values[21], -0.02, places=9)
        self.assertAlmostEqual(values[22], 0.03, places=9)
        self.assertAlmostEqual(values[23], 0.025, places=9)             # fingers * dv
        object_position = values[3:6]
        distance = math.dist(values[0:3], object_position)
        self.assertAlmostEqual(receipt["output"]["reward"], -distance, places=9)   # dense reward, panda_env.py:45
        self.assertFalse(receipt["output"]["terminated"])
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_object_start(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_run_stops_on_the_2001st_step(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        # panda_env.py:13,97-101: step_counter becomes 2001 and done is set when it is greater than MAX_EPISODE_LEN
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=2001)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 2001))
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:gym-panda-reach-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
