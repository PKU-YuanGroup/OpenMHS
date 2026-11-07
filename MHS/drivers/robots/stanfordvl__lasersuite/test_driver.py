"""Acceptance run of the laser suite DoorOpen package: the gate plus cases for its world contract.

Add cases, never remove ``check_driver``.  The cases run on the fake backend (fake.py); MuJoCo, mujoco-py and the
upstream package are not installed or imported here.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: Test data, not a fact: a five-element zero action vector.
ACTION = {"values": [0.0] * 5}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DoorOpenCases(unittest.TestCase):
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

    def step(self, client, **fields):
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_echoes_the_seed_and_step_advances_the_tick(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["tick"], 0)
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(output["seed"], 7)
        self.assertEqual(self.state(client)["seed"], 7)
        self.assertIsInstance(output["observation"], dict)
        receipt = self.step(client, ticks=3, action=ACTION)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertRegex(receipt["output"]["state_hash"], r"^sha256:[0-9a-f]{64}$")
        receipt = self.step(client, ticks=2, action={"values": [0.5] * 5})
        self.assertEqual(receipt["output"]["tick"], 5)

    def test_a_step_changes_the_observation(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]
        receipt = self.step(client, ticks=1, action={"values": [1.0] * 5})
        self.assertEqual(receipt["status"], "completed")
        self.assertNotEqual(receipt["output"]["observation"], before)
        self.assertEqual(self.state(client)["observation"], receipt["output"]["observation"])
        self.assertEqual(self.state(client)["reward"], receipt["output"]["reward"])
        self.assertEqual(self.state(client)["terminated"], receipt["output"]["terminated"])

    def test_the_placeholder_observation_has_the_clone_keys(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        for key in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos", "task_state"):
            self.assertIn(key, observation)

    def test_ticks_is_bounded_by_the_class(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks, action=ACTION)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)                  # the refused steps changed nothing

    def test_seed_must_be_non_negative(self) -> None:
        client = self.serve()
        refused = self.reset(client, seed=-1)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_an_empty_action_vector_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, ticks=1, action={"values": []})
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("robosuite:DoorOpen", "F0"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["determinism"]["kind"]), (0.0, "none"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=1, action=ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ticks=1, action=ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, not advanced


if __name__ == "__main__":
    unittest.main()
