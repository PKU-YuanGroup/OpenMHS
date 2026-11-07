"""Acceptance run of the gym-pybullet-drones package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym_pybullet_drones and
pybullet are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: placeholder-free: the CF2X hover RPM the clone's constants give (BaseAviary.py:116-119, cf2x.urdf:5-11)
HOVER_RPM = math.sqrt((9.8 * 0.027) / (4 * 3.16e-10))
MAX_RPM = math.sqrt((2.25 * 9.8 * 0.027) / (4 * 3.16e-10))


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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def observation(receipt):
        values = receipt["output"]["observation"]["values"]
        while isinstance(values, list) and values and isinstance(values[0], list):
            values = values[0]
        return values

    # -- the action space is the envelope -------------------------------------------------------------------
    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([-1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, MAX_RPM + 1.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    # -- the vertical model of the fake ---------------------------------------------------------------------
    def test_a_hover_command_holds_the_altitude(self) -> None:
        client = self.serve()
        receipt = self.step(client, [HOVER_RPM] * 4)
        self.assertEqual(receipt["status"], "completed")
        values = self.observation(receipt)
        self.assertEqual(len(values), 20)                        # BaseAviary.py:541-561
        self.assertEqual((values[0], values[1], values[2]), (0.0, 0.0, 0.0))
        self.assertEqual((values[3], values[4], values[5], values[6]), (0.0, 0.0, 0.0, 1.0))
        self.assertAlmostEqual(values[12], 0.0, places=9)        # the vertical velocity at hover
        self.assertEqual(values[16:], [HOVER_RPM] * 4)           # the clipped motor commands (CtrlAviary.py:121-140)
        self.assertEqual(receipt["output"]["reward"], -1.0)      # CtrlAviary.py:144-155
        self.assertFalse(receipt["output"]["terminated"])        # CtrlAviary.py:159-170
        self.assertFalse(receipt["output"]["truncated"])         # CtrlAviary.py:174-185
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_more_thrust_than_weight_lifts_the_drone(self) -> None:
        client = self.serve()
        receipt = self.step(client, [1.1 * HOVER_RPM] * 4)
        values = self.observation(receipt)
        self.assertGreater(values[2], 0.0)                       # the altitude grew
        self.assertGreater(values[12], 0.0)                      # and the drone is moving up
        self.assertEqual(values[16:], [1.1 * HOVER_RPM] * 4)

    def test_less_thrust_than_weight_stays_on_the_ground(self) -> None:
        client = self.serve()
        values = self.observation(self.step(client, [0.5 * HOVER_RPM] * 4))
        self.assertEqual((values[2], values[12]), (0.0, 0.0))    # the ground stops a falling drone

    # -- reset and seed -------------------------------------------------------------------------------------
    def test_the_reset_returns_the_initial_state(self) -> None:
        client = self.serve()
        self.step(client, [1.1 * HOVER_RPM] * 4)
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        values = self.observation(receipt)
        self.assertEqual(values[2], 0.0)                         # BaseAviary.py:451-470
        self.assertEqual(values[16:], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertIs(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    # -- the e-stop and the fidelity contract ---------------------------------------------------------------
    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [HOVER_RPM] * 4)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [HOVER_RPM] * 4), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:ctrl-aviary-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
