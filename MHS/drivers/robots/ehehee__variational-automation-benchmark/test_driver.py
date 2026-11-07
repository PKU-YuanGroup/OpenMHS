"""Acceptance run of the VAB package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``); robosuite, MuJoCo
and numpy are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
PUSH = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VABCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=0):
        return client.invoke("cap.world.reset.v1", {"seed": seed}, **self.ids)

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values or ZERO)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_strict_observation_and_the_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), {"images", "proprio"})
        self.assertEqual(set(observation["proprio"]),
                         {"joint_pos", "joint_vel", "eef_pos", "eef_quat", "gripper_qpos"})
        state = self.state(client)
        self.assertEqual((state["tick"], state["init_index"], state["episode"]), (0, 3, 1))

    def test_a_step_advances_the_tick_and_changes_the_observation(self) -> None:
        client = self.serve()
        self.reset(client)
        first = self.step(client, values=PUSH, ticks=1)["output"]
        second = self.step(client, values=PUSH, ticks=2)["output"]
        self.assertEqual(second["tick"], 3)
        self.assertNotEqual(first["observation"]["proprio"]["joint_pos"],
                            second["observation"]["proprio"]["joint_pos"])
        self.assertTrue(second["state_hash"].startswith("sha256:"))
        self.assertEqual(second["reward"], 0.0)
        self.assertFalse(second["terminated"])
        self.assertFalse(second["truncated"])
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_zero_action_still_advances_the_clock(self) -> None:
        client = self.serve()
        self.reset(client)
        before = self.state(client)["observation"]["images"]
        output = self.step(client, values=ZERO)["output"]
        self.assertEqual(output["tick"], 1)
        self.assertNotEqual(before, output["observation"]["images"])

    def test_reset_seed_selects_the_initial_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=0)["output"]["observation"]["proprio"]["joint_pos"]
        second = self.reset(client, seed=1)["output"]["observation"]["proprio"]["joint_pos"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.state(client)["init_index"], 1)

    def test_ticks_outside_the_class_bound_are_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_values_are_required(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_reset_seed_is_required(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_an_out_of_range_seed_is_a_failed_native_call(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=50)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("robosuite:libero.vab.env/VABEnv", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["timestep_ms"], 50.0)
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client, values=ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, values=ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
