"""Acceptance run of the drone_sim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream clone is
never imported, so nothing here compares the fake with the upstream environment.
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


class SimpleDroneCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5, 0.5, 0.5])["status"], "completed")
        for values in ([1.1, 0.5, 0.5, 0.5], [-0.1, 0.5, 0.5, 0.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_a_reset_returns_the_fixed_upstream_state(self) -> None:
        client = self.serve()
        output = self.reset(client)["output"]
        # simple_drone_env.py:88 -> drone.py:104: position (0, 0, 0.5); acceleration, p, q and r stay zero
        self.assertEqual(output["observation"]["values"],
                         [[0.0, 0.0, 0.5], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        self.assertEqual(output["seed"], 0)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_hover_action_holds_the_altitude(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [1.0, 1.0, 1.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # K*4*NULL_ROT^2/0.468 = 9.800002 N/kg, so the net vertical acceleration is about -2.1e-6 m/s^2
        value = output["observation"]["values"]
        self.assertAlmostEqual(value[0][2], 0.5, places=9)
        self.assertAlmostEqual(value[1][2], -2.0900408532753545e-06, places=11)
        self.assertAlmostEqual(output["reward"], 1 - 1.5 / math.sqrt(34), places=9)
        self.assertFalse(output["terminated"])

    def test_a_zero_action_falls_until_z_is_negative(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=100)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # simple_drone_env.py:70-74: done once z < 0, the drone is reset and 5 is subtracted from the reward
        self.assertTrue(output["terminated"])
        self.assertLess(output["observation"]["values"][0][2], 0.0)
        self.assertLess(self.state(client)["reward"], -4.0)              # the reward of the terminal step
        self.assertLess(output["tick"], 100)
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")

    def test_an_asymmetric_action_ends_the_episode_at_the_tilt_limit(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0], ticks=20)
        self.assertEqual(receipt["status"], "completed")
        # drone.py:172-177 with w1 = NULL_ROT: torque x = L*K*NULL_ROT^2 and w_dot = torque/IXX = 53.13 rad/s^2;
        # the cross-coupling term then lifts the pitch, so the 60 degree limit (simple_drone_env.py:65) is passed
        # within the first few steps
        self.assertTrue(receipt["output"]["terminated"])
        self.assertTrue(1 <= receipt["output"]["tick"] <= 5, receipt["output"]["tick"])
        self.assertLess(self.state(client)["reward"], -4.0)              # the reward of the terminal step

    def test_the_seed_is_recorded_but_the_reset_is_fixed(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 7, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 7)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["observation"], first["observation"])
        # simple_drone_env.py:86: reset(self) has no seed; different seeds restore the same state
        other = self.reset(client, seed=8)["output"]
        self.assertEqual(other["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("custom:drone_sim.sim.drone", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (4.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5, 0.5, 0.5])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.5, 0.5, 0.5]), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
