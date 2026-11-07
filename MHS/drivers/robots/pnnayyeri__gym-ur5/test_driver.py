"""Acceptance run of the gym-ur5 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything here runs on the fake backend (fake.py): CoppeliaSim,
legacy gym, the upstream package and the PyCopp remoteApi library are not installed where the gate runs, so nothing
here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymUR5Cases(unittest.TestCase):
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

    def test_the_action_space_bounds_the_step_input(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # refused steps changed nothing

    def test_the_observation_has_six_values_and_the_action_is_clipped(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [1.0, 1.0, 1.0])                      # clipped to +0.1 per axis (ur5_env.py:64)
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 6)
        for got in values[0:3]:
            self.assertAlmostEqual(got, 0.1, places=12)
        for got in values[3:6]:                                          # the fake's force vectors are placeholders
            self.assertEqual(got, 0.0)
        # Tip [0.1, 0.1, 0.1] to TargetObject [0.5, 0, 0]: 0.4**2 + 0.1**2 + 0.1**2 = 0.18
        self.assertAlmostEqual(receipt["output"]["reward"], -0.18, places=12)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_reward_accumulates_and_a_reset_clears_it(self) -> None:
        client = self.serve()
        self.reset(client)
        first = self.step(client, [0.1, 0.0, 0.0])["output"]["reward"]    # distance 0.4: -0.16
        second = self.step(client, [0.1, 0.0, 0.0])["output"]["reward"]   # distance 0.3: -0.16 - 0.09
        self.assertAlmostEqual(first, -0.16, places=12)
        self.assertAlmostEqual(second, -0.25, places=12)
        state = self.state(client)
        self.assertAlmostEqual(state["reward"], -0.25, places=12)         # step adds, it does not replace
        self.assertEqual(state["tick"], 2)
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["reward"], state["tick"]), (0.0, 0))
        self.assertEqual(state["observation"]["values"], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    def test_a_seed_is_echoed_but_the_start_does_not_depend_on_it(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]
        second = self.reset(client, seed=9)["output"]
        self.assertEqual((first["seed"], second["seed"]), (3, 9))
        self.assertEqual(first["observation"], second["observation"])     # UR5Env has no random start state

    def test_the_seed_class_sets_the_next_reset_seed(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("coppeliasim:UR5-Gripper-thread-pyapi.ttt", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
