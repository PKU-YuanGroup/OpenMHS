"""Acceptance run of the RoboDesk package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream
environment cannot be imported where the gate runs, so nothing here compares the fake with MuJoCo.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboDeskCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.25, -0.5, 0.75, -1.0, 1.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, -1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_a_step_moves_the_end_effector_and_keeps_the_six_keys(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(sorted(before), ["end_effector", "image", "qpos_objects", "qpos_robot",
                                          "qvel_objects", "qvel_robot"])
        self.assertEqual(len(before["image"]["values"]), 4 * 4 * 3)   # fake stand-in, upstream default 64x64x3
        self.assertEqual(len(before["qpos_robot"]["values"]), 9)
        self.assertEqual(len(before["end_effector"]["values"]), 3)
        self.assertEqual(len(before["qpos_objects"]["values"]), 26)
        # upstream fills qpos_objects from qvel (robodesk/robodesk.py:385); the fake mirrors that
        self.assertEqual(before["qpos_objects"], before["qvel_objects"])
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]
        self.assertGreater(after["end_effector"]["values"][0], before["end_effector"]["values"][0])
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["reward"]), (1, 0.0))
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))
        self.assertEqual(self.state(client)["info"], {"discount": 1.0})

    def test_the_default_time_limit_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=500)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the fake stands in for the upstream default episode_length of 500 (robodesk/robodesk.py:19-20)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 500))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")   # a reset starts the next episode

    def test_a_reset_seed_is_recorded_but_does_not_control_the_environment(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        # upstream reset() takes no seed argument and draws from numpy's global generator
        # (robodesk/robodesk.py:207-229), so the fidelity contract declares statistical determinism
        self.assertIn("qpos_robot", first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(device["safety"]["estop"]["kind"], "software")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("kinematic fake", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
