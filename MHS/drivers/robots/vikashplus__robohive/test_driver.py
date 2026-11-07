"""Acceptance run of the robohive package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py): neither robohive nor
MuJoCo is installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0] * 9
PUSH = [1.0] * 9


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrankaReachCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ZERO}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, PUSH)["status"], "completed")
        for values in ([-1.5] + [0.0] * 8, [1.5] + [0.0] * 8):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_a_step_returns_the_reach_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # qp_robot (9) + qv_robot (9) + reach_err (3): the observation keys of ReachBaseV0
        self.assertEqual(len(output["observation"]["values"]), 21)
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["values"]
        again = self.reset(client, seed=7)["output"]["observation"]["values"]
        other = self.reset(client, seed=8)["output"]["observation"]["values"]
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_push_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, PUSH, ticks=20)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # reach_dist passes far_th = 1.0 before the 20 requested ticks, and the bridge stops at the terminal state
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 20)
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_zero_actions_are_truncated_at_fifty_ticks(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, ZERO, ticks=50)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 50))
        self.assertEqual(self.step(client)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("robohive:FrankaReachFixed-v0 (MuJoCo)", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (80.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
