"""Acceptance run of the Muller-Brown package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); the upstream package is not installed and is never imported.  The
potential helper below repeats the published formula only to check that the reward the protocol returns is the energy
decrease (muller_brown_discrete.py:75-87, :103-110); it is test data, not a second source of driver facts.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The upstream coefficients (muller_brown_discrete.py:75-80), used only to check the reward.
A = [-200, -100, -170, 15]
A_X = [-1, -1, -6.5, 0.7]
B = [0, 0, 11, 0.6]
C = [-10, -10, -6.5, 0.7]
X0 = [1, 0, -0.5, -1]
Y0 = [0, 0.5, 1.5, 1]


def potential(ix, iy):
    """The energy of a 5 by 5 grid state, computed from the published coefficients."""
    x = -1.5 + ix * (1.0 + 1.5) / 4.0
    y = -0.5 + iy * (2.0 + 0.5) / 4.0
    value = 0.0
    for k in range(4):
        value += A[k] * math.exp(A_X[k] * (x - X0[k]) ** 2 + B[k] * (x - X0[k]) * (y - Y0[k])
                                 + C[k] * (y - Y0[k]) ** 2)
    return value


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MullerBrownCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 4)["status"], "completed")
        for index in (-1, 5, 6):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_the_reward_is_the_energy_decrease(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=3)["output"]["observation"]["values"]
        ix, iy = values
        if ix < 4:
            action, expected = 3, [ix + 1, iy]
        elif iy < 4:
            action, expected = 0, [ix, iy + 1]
        elif ix > 0:
            action, expected = 2, [ix - 1, iy]
        else:
            action, expected = 4, [ix, iy]
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["values"], expected)
        self.assertAlmostEqual(output["reward"], potential(ix, iy) - potential(expected[0], expected[1]), places=9)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))

    def test_a_do_nothing_action_keeps_the_state(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=4)["output"]["observation"]["values"]
        output = self.step(client, 4)["output"]
        self.assertEqual(output["observation"]["values"], values)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))

    def test_an_off_grid_move_is_penalized(self) -> None:
        client = self.serve()
        for seed in range(50):
            values = self.reset(client, seed=seed)["output"]["observation"]["values"]
            ix, iy = values
            if ix == 0:
                action = 2
            elif ix == 4:
                action = 3
            elif iy == 0:
                action = 1
            elif iy == 4:
                action = 0
            else:
                continue
            output = self.step(client, action)["output"]
            self.assertEqual(output["observation"]["values"], [ix, iy], seed)   # the agent stays in place
            self.assertEqual((output["reward"], output["tick"]), (-100.0, 1), seed)
            return
        self.fail("no seed produced a boundary start state on the 5 by 5 grid")

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]["values"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"]["values"], first)
        starts = {tuple(self.reset(client, seed=seed)["output"]["observation"]["values"])
                  for seed in range(11, 21)}
        self.assertGreater(len(starts), 1)                               # different seeds are not all the same draw

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_ticks_advance_the_grid(self) -> None:
        client = self.serve()
        output = self.step(client, 4, ticks=3)["output"]
        self.assertEqual((output["tick"], output["reward"]), (3, 0.0))
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])

    def test_observations_stay_on_the_grid(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        for action in (0, 1, 2, 3, 4):
            values = self.step(client, action)["output"]["observation"]["values"]
            self.assertTrue(all(0 <= value <= 4 for value in values), values)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:MullerBrownDiscrete-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 4)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 4), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
