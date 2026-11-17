"""Acceptance run of the Evogym Walker-v0 driver: the gate plus cases for this package.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py); the upstream evogym
stack is not installed, so no case compares the analytic fake with the compiled simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# walk.py:36: Box(low=0.6, high=1.6); one placeholder actuator in the fake's body.
LOW, HIGH = 0.6, 1.6
# walk.py:36-37 and the fake constants: one actuator, velocity gain 12.0, timestep 3 ms.
STEP_DISPLACEMENT = 12.0 * (HIGH - 1.0) * 0.003


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WalkerCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, [LOW])["status"], "completed")
        self.assertEqual(self.step(client, [HIGH])["status"], "completed")
        for values in ([LOW - 0.1], [HIGH + 0.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 2)   # the refused steps changed nothing

    def test_the_reward_is_the_centre_of_mass_displacement(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [HIGH])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertAlmostEqual(output["reward"], STEP_DISPLACEMENT, places=9)
        self.assertAlmostEqual(output["observation"]["values"][0], 12.0 * (HIGH - 1.0), places=9)
        # base.py:260-262 flattens a (2, n) array: all x offsets precede all y offsets.
        self.assertEqual(output["observation"]["values"][2:], [-0.10, 0.10, -0.10, 0.10,
                                                                -0.05, -0.05, 0.05, 0.05])
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_a_low_target_moves_backwards(self) -> None:
        client = self.serve()
        self.reset(client)
        output = self.step(client, [LOW])["output"]
        self.assertLess(output["reward"], 0.0)
        self.assertAlmostEqual(output["observation"]["values"][0], 12.0 * (LOW - 1.0), places=9)

    def test_the_upstream_reset_ignores_the_seed(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], second["observation"])   # base.py:65-69 ignores the seed
        self.assertEqual((first["seed"], second["seed"]), (11, 12))      # the receipt echoes the requested seed
        self.assertEqual(self.reset(client)["output"]["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_a_standing_command_is_truncated_at_500_steps(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [1.0], ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # walk.py:72 returns truncated=False; the 500-step TimeLimit is the gymnasium.make wrapper
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 500))
        self.assertEqual(output["reward"], 0.0)
        ended = self.step(client, [1.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")

    def test_a_forward_command_reaches_the_goal(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [HIGH], ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # walk.py:67-69: com_x > 99 * 0.1 terminates and adds 1.0; the fake reaches it at tick 459
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 459))
        self.assertGreater(output["reward"], 1.0)
        ended = self.step(client, [HIGH])
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:evogym Walker-v0 fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (3.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [HIGH])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [HIGH]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
