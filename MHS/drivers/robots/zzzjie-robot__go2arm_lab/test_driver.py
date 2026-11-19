"""Acceptance run of the Go2Arm package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Lab and Isaac Sim
are not installed where the gate runs, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 18}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2ArmCases(unittest.TestCase):
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

    def test_the_action_bounds_are_enforced(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 18)["status"], "completed")
        for values in ([1.5] + [0.0] * 17, [0.0] * 17 + [-1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_a_step_advances_ticks_and_keeps_the_policy_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [0.25] * 18, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(len(output["observation"]["values"]), 727)
        self.assertLess(output["reward"], 0.0)
        self.assertIn("arm_reward", self.state(client)["info"])

    def test_a_seed_repeats_the_synthetic_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            first = self.step(client, [0.1 * (index % 3) for index in range(18)])
            second = self.step(client, [-0.1 * (index % 2) for index in range(18)])
            return [first["output"]["observation"], second["output"]["observation"]]

        self.assertEqual(trajectory(11), trajectory(11))
        self.assertNotEqual(trajectory(11), trajectory(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        direct = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], direct["observation"])

    def test_the_configured_timeout_truncates_at_1000_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [0.0] * 18, ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client, [0.0] * 18)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:go2arm-manager-env-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 18)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 18), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
