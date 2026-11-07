"""Acceptance run of the Unitree GO2 parkour MuJoCo package: the gate, plus cases for this driver.

The cases run on the fake backend (``fake.py``): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine.  The served model is the card's first model, ``core/go2/scene.xml``, which
includes ``core/go2/go2.xml``; the stand-in derives its shape from that text.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: One free base joint (7 qpos, 6 qvel) and twelve hinge joints (go2.xml:70, go2.xml:84-208).
NQ = 19
NV = 18
#: The actuator block has twelve motors, one per leg joint (go2.xml:224-237).
NU = 12
#: An in-range control vector: every actuator ctrlrange includes 0 (go2.xml:10, :24).
ZERO = [0.0] * NU
#: Actuator 0 is FR_hip (go2.xml:225); after the free base and the three FL joints its qpos slot is 10.
FR_HIP_QPOS = 10


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        # The free base starts at the body pos of go2.xml:64 with the identity quaternion.
        self.assertEqual(state["qpos"][:3], [-7.5, 0.0, 0.5])
        self.assertEqual(state["qpos"][3], 1.0)
        # The model states no option timestep (go2.xml:4); the stand-in uses MuJoCo's library default of 2 ms as a
        # placeholder (fake.py), and the bridge publishes the stand-in's value.
        self.assertEqual(state["timestep_ms"], 2.0)
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # abduction and hip motors are -23.7..23.7 (go2.xml:10); knee motors are -45.43..45.43 (go2.xml:24).
        for index, value in ((0, 23.8), (0, -23.8), (1, 23.8), (1, -23.8), (2, 45.5), (2, -45.5)):
            refused = self.step(client, ZERO[:index] + [value] + ZERO[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        target = list(ZERO)
        target[0] = 1.0
        first = self.step(client, target)["output"]["observation"]
        second = self.step(client, target)["output"]["observation"]
        self.assertEqual(second["time"], 0.004)                # two ticks of the 2 ms step
        self.assertGreater(second["qpos"][FR_HIP_QPOS], first["qpos"][FR_HIP_QPOS])
        self.assertGreater(second["qpos"][FR_HIP_QPOS], 0.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        target = list(ZERO)
        target[0] = 1.0
        self.step(client, target, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][:3], [-7.5, 0.0, 0.5])
        self.assertEqual(output["observation"]["qpos"][FR_HIP_QPOS], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:go2_parkour", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
