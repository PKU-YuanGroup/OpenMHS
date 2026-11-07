"""Acceptance run of the DexPoint package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): SAPIEN is not installed
where the gate runs, so nothing here compares the stand-in with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
DOF = 22          # the default robot's 6 arm + 16 hand joints (common_robot_utils.py:53-56)
ZERO_ACTION = {"values": [0.0] * DOF}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DexPointCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        too_high = {"values": [0.0] * DOF}
        too_high["values"][0] = 1.5
        refused = self.step(client, too_high)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        short = {"values": [0.0] * (DOF - 1)}
        malformed = self.step(client, short)
        self.assertEqual(malformed["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refusals changed nothing

    def test_a_seed_repeats_the_initial_pose(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]
        second = self.reset(client, seed=3)["output"]
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=4)["output"]
        self.assertNotEqual(first["observation"], other["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_step_advances_the_tick_and_the_palm(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 57)                          # dof + 3 + 7 + 12 + 5 + 3 + 4 + 1
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertTrue(receipt["output"]["reward"] >= 0.0)
        moved = {"values": [0.0] * DOF}
        moved["values"][0] = 1.0
        after = self.step(client, moved)["output"]["observation"]["values"]
        self.assertGreater(after[22], observation[22])                 # the palm x moved by the first action value
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_horizon_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        output = self.step(client, ticks=200)["output"]
        # relocate_env.py:155-157: the horizon is 200 control steps; base.py:214-217 sets done at the horizon.
        self.assertEqual((output["terminated"], output["tick"]), (True, 200))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "analytic:dexpoint-allegro-relocate-stand-in")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
