"""Acceptance run of the mano_pybullet package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym, pybullet, numpy, chumpy and the MANO model files, so nothing here compares the fake with a real run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ANGLES = [0.0] * 20


def action(x=0.0, y=0.0, z=0.0):
    """The joint-mode action the default HandLiftEnv expects: one hand of position, quaternion, angles."""
    return {"items": [[[x, y, z], [0.0, 0.0, 0.0, 1.0], ANGLES]]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HandLiftCases(unittest.TestCase):
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

    def step(self, client, action_value, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action_value}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_world(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, action())
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertFalse(output["terminated"] or output["truncated"])
        # the observation is (hand state, (object position, object orientation)) in the spaces of hand_env.py:81-89
        # and hand_object_env.py:32-37; the object stays on the ground for a zero action
        item = output["observation"]["items"]
        self.assertEqual(item[1]["items"][0]["values"], [0.0, 0.0, 0.0])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_object_follows_a_lift_and_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, action(z=0.3))
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertAlmostEqual(output["reward"], 0.3, places=7)
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["tick"], 1)
        # hand_lift_env.py:56-57: done when the object is above target_height (0.25 by default)
        ended = self.step(client, action())
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_a_horizontal_move_does_not_end_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, action(x=0.5))
        self.assertEqual(receipt["status"], "completed")
        self.assertFalse(receipt["output"]["terminated"])
        self.assertEqual(receipt["output"]["observation"]["items"][1]["items"][0]["values"][0], 0.5)

    def test_the_seed_is_echoed_and_used_by_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)
        self.assertEqual(first["output"]["seed"], 7)
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        second = self.reset(client)
        self.assertEqual(second["output"]["seed"], 21)
        self.assertEqual(second["output"]["observation"], first["output"]["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("pybullet:mano_pybullet HandLiftEnv-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=7)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
