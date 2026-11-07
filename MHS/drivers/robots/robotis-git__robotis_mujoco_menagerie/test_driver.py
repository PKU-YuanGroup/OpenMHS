"""Acceptance run of the ROBOTIS FFW-BG2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the fake with the real engine.
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


class FfwBg2Cases(unittest.TestCase):
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

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 19)["status"], "completed")
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (25, 25, 19))
        self.assertEqual((state["tick"], state["timestep_ms"]), (1, 2.0))

    def test_controls_are_bounded_by_the_model(self) -> None:
        client = self.serve()
        for index, value in ((0, 0.1), (0, -0.6), (10, -0.1), (18, 1.2)):
            ctrl = [0.0] * 19
            ctrl[index] = value
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
        self.assertEqual(self.state(client)["tick"], 0)                       # a refusal actuated nothing

        ctrl = [0.0] * 19
        ctrl[0] = -0.4                                                       # lift_joint range -0.5 to 0.0
        ctrl[3] = 1.0                                                        # left arm joint 1, -3.14 to 3.14
        receipt = self.step(client, ctrl)
        self.assertEqual(receipt["status"], "completed")
        state = self.state(client)
        self.assertLess(state["qpos"][0], 0.0)
        self.assertGreater(state["qpos"][3], 0.0)
        self.assertEqual((state["ctrl"][0], state["ctrl"][3]), (-0.4, 1.0))

    def test_ticks_advance_the_model_clock(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * 19, ticks=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["observation"]["time"]), (5, 0.01))
        self.assertEqual((self.state(client)["tick"], self.state(client)["time_ms"]), (5, 10))

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        ctrl = [0.0] * 19
        ctrl[0] = -0.4
        self.assertEqual(self.step(client, ctrl)["status"], "completed")
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["time"], 0.0)
        self.assertEqual(receipt["output"]["observation"]["qpos"], [0.0] * 25)
        self.assertEqual((self.state(client)["tick"], self.state(client)["time_ms"]), (0, 0))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:ffw_bg2", "F1"))
        # MuJoCo reset has no seed-control contract; state API presence proves no determinism.
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 19)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 19), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
