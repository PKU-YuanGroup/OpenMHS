"""Acceptance run of the robopal DianaMed package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py), which is a stand-in for
the ``mujoco`` module: its placeholder integration is checked here, not MuJoCo's.  Nothing here ran in MuJoCo.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class World(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_contract_comes_from_the_clauses_of_the_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["time_ms"], 0)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["qpos"], [0.0] * 7)              # seven hinge joints
        self.assertEqual(state["ctrl"], [0.0] * 7)              # seven motors
        self.assertAlmostEqual(state["timestep_ms"], 0.5, places=9)

    def test_a_step_writes_the_ctrl_and_advances_the_model(self) -> None:
        client = self.serve()
        ctrl = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        receipt = self.step(client, ctrl, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        observation = receipt["output"]["observation"]
        self.assertAlmostEqual(observation["time"], 3 * 0.0005, places=9)
        self.assertGreater(observation["qpos"][0], 0.0)
        state = self.state(client)
        self.assertEqual(state["ctrl"], ctrl)
        self.assertEqual(state["tick"], 3)

    def test_the_ctrl_is_bounded_by_the_actuator_ctrlrange_of_the_model(self) -> None:
        client = self.serve()
        for ctrl, path in (([81.0, 0, 0, 0, 0, 0, 0], "action.ctrl[0]"), ([-80.5, 0, 0, 0, 0, 0, 0], "action.ctrl[0]"),
                           ([0, 0, 0, 0, 0, 0, -81.0], "action.ctrl[6]")):
            refused = self.step(client, ctrl)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), ctrl)
            self.assertEqual(refused["error"]["details"]["path"], path)
        self.assertEqual(self.state(client)["tick"], 0)          # nothing was stepped
        self.assertEqual(self.step(client, [80.0, -80.0, 0, 0, 0, 0, 0])["status"], "completed")

    def test_a_reset_clears_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0, 0, 0, 0, 0, 0], ticks=5)["status"], "completed")
        reset = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"], state["qpos"]), (0, 0, [0.0] * 7))

    def test_the_placeholder_model_is_deterministic(self) -> None:
        def trajectory():
            client = self.serve()
            for ticks in (1, 2, 3):
                self.assertEqual(self.step(client, [0.5, -0.5, 0.0, 0.0, 0.0, 0.0, 0.0], ticks=ticks)["status"],
                                 "completed")
            return self.state(client)["qpos"]

        self.assertEqual(trajectory(), trajectory())


if __name__ == "__main__":
    unittest.main()
