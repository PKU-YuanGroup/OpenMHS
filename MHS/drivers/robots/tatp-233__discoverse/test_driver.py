"""Acceptance run of the DISCOVERSE MMK2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the MuJoCo engine or with a physical MMK2.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


def controls(**overrides):
    """A 19-value ctrl vector: the wheel and arm actuators at zero, overridden by name."""
    values = [0.0] * 19
    for index, value in overrides.items():
        values[int(index)] = value
    return values


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MMK2Cases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_is_the_scene_shape(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (28, 27, 19))
        self.assertEqual((state["tick"], state["time_ms"], state["timestep_ms"]), (0, 0, 2.0))
        self.assertEqual(state["qpos"][3], 1.0)                       # free-joint quaternion [x, y, z, qw, ...]

    def test_a_control_reaches_the_stand_in(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, controls(**{"2": 0.5}))           # lift, ctrlrange -0.04 to 0.87 m
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(receipt["output"]["observation"]["qpos"][9], 0.01)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (1, 2))
        self.assertEqual((state["ctrl"][2], state["qpos"][9], state["qvel"][8]), (0.5, 0.01, 5.0))

    def test_the_control_ranges_are_the_limits(self) -> None:
        client = self.serve()
        refused = self.step(client, controls(**{"2": 1.0}))           # above the lift's 0.87 m
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.step(client, controls(**{"0": -36.0}))         # below the wheel motor's -35
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))   # nothing was actuated or advanced

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, controls(**{"2": 0.5}), ticks=3)
        self.assertEqual(self.state(client)["tick"], 3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        qpos = receipt["output"]["observation"]["qpos"]
        self.assertEqual((len(qpos), qpos[:7]), (28, [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]))
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:mmk2", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, controls())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, controls()), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
