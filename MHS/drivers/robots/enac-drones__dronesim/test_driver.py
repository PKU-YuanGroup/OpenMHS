"""Acceptance run of the dronesim CtrlAviary package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  Nothing here compares the fake with the upstream PyBullet
environment: pybullet and gym are not importable where the gate runs, so the fake's contract is what is checked.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
START_Z = 0.1205                                  # placeholder: the fake's start height


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CtrlAviaryCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def observation_values(receipt):
        return receipt["output"]["observation"]["0"]["state"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5, 0.5, 0.5])["status"], "completed")
        for values in ([-0.1, 0.0, 0.0, 0.0], [1.1, 1.0, 1.0, 1.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing
        wrong_size = self.step(client, [0.5, 0.5, 0.5])
        self.assertEqual(wrong_size["status"], "rejected")
        self.assertEqual(wrong_size["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_reset_returns_the_twenty_value_state(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        observation = receipt["output"]["observation"]
        state = observation["0"]["state"]["values"]
        self.assertEqual(len(state), 20)                                  # BaseAviary.py:764-783
        self.assertEqual(state[2], START_Z)
        self.assertEqual(state[3:7], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(observation["0"]["neighbors"]["values"], [1])    # the identity adjacency
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_applies_the_pwm_command(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [1.0, 1.0, 1.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (-1.0, False, False, 1))                        # CtrlAviary.py:278 and :293
        state = output["observation"]["0"]["state"]["values"]
        self.assertEqual(state[16:20], [1.0, 1.0, 1.0, 1.0])             # the last motor command
        self.assertGreater(state[2], START_Z)                            # placeholder kinematics lift the drone
        self.assertEqual(self.state(client)["info"], {"answer": 42})     # CtrlAviary.py:308-310

    def test_several_ticks_advance_the_tick_counter(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, [0.5, 0.5, 0.5, 0.5], ticks=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 5)
        self.assertEqual(receipt["output"]["reward"], -5.0)              # -1 per tick

    def test_the_fake_is_deterministic_across_seeds(self) -> None:
        def trajectory(seed):
            client = self.serve()                                        # a fresh world: the hash counts episodes
            self.reset(client, seed=seed)
            return [self.step(client, [1.0, 0.0, 1.0, 0.0])["output"]["state_hash"]
                    for _ in range(3)]

        first = trajectory(1)
        self.assertEqual(trajectory(1), first)
        self.assertEqual(trajectory(2), first)                           # the upstream reset takes no seed

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        first = self.reset(client, seed=21)["output"]["observation"]
        second = self.reset(client, seed=21)["output"]["observation"]
        self.assertEqual(first, second)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        summary = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(summary["mode"], "simulated")
        self.assertEqual(summary["risk_class"], "R0")
        self.assertTrue(fidelity["engine"].startswith("dronesim:"))
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5, 0.5, 0.5])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.5, 0.5, 0.5]), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 2}, **self.ids)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
