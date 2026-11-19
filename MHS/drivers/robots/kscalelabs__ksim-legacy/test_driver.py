"""Acceptance run of the K-Scale Stompy package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine or with the upstream MJX
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StompyCases(unittest.TestCase):
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

    def step(self, client, ctrl=None, ticks=1):
        action = {} if ctrl is None else {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_contract_is_the_bridge_world_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        # 31 motor actuators (stompy.xml:230-262); the root is three slides plus a ball, so 38 qpos and 37 qvel
        self.assertEqual(len(state["qpos"]), 38)
        self.assertEqual(len(state["qvel"]), 37)
        self.assertEqual(len(state["ctrl"]), 31)
        self.assertEqual((state["tick"], state["timestep_ms"], state["time_ms"]), (0, 1.0, 0))
        self.assertEqual(state["native_checkpoint"]["profile"], "mujoco_basic_v1")

    def test_a_tick_applies_the_control_and_advances_the_model_time(self) -> None:
        client = self.serve()
        self.reset(client)
        before = self.state(client)
        receipt = self.step(client, [1.0] * 31, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        after = self.state(client)
        self.assertEqual(after["tick"], 3)
        self.assertEqual(after["time_ms"], 3)
        # the stand-in gives each actuated joint 0.01 rad/s per control unit (placeholder) and the model step is
        # 0.001 s (stompy.xml:16); the left shoulder pitch sits at its ref -0.534 (stompy.xml:69)
        self.assertAlmostEqual(after["qpos"][7] - before["qpos"][7], 3 * 1.0 * 0.01 * 0.001, places=12)
        self.assertEqual(receipt["output"]["observation"]["qpos"], after["qpos"])
        self.assertEqual(receipt["output"]["tick"], 3)

    def test_the_control_range_is_the_models_ctrlrange(self) -> None:
        client = self.serve()
        self.reset(client)
        for value in (200.0, -200.0):
            self.assertEqual(self.step(client, [value] * 31)["status"], "completed", value)
        tick = self.state(client)["tick"]
        for value in (200.0001, -200.0001):
            refused = self.step(client, [value] * 31)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), value)
        self.assertEqual(self.state(client)["tick"], tick)                 # the refused steps changed nothing

    def test_a_wrong_control_count_is_refused_before_the_engine(self) -> None:
        client = self.serve()
        self.reset(client)
        refused = self.step(client, [0.0] * 30)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.reset(client)
        original = self.state(client)
        self.assertEqual(self.step(client, [5.0] * 31, ticks=2)["status"], "completed")
        self.assertNotEqual(self.state(client)["qpos"], original["qpos"])
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        restored = self.state(client)
        self.assertEqual((restored["time_ms"], restored["tick"]), (0, 0))
        self.assertEqual(restored["qpos"], original["qpos"])
        self.assertEqual(restored["qvel"], original["qvel"])
        self.assertEqual(restored["ctrl"], [0.0] * 31)
        self.assertEqual(receipt["output"]["seed"], 0)                    # the bridge publishes no seed control

    def test_one_control_sequence_repeats_the_stand_in(self) -> None:
        client = self.serve()
        self.reset(client)
        first = self.step(client, [0.5] * 31, ticks=2)["output"]["state_hash"]
        self.reset(client)
        second = self.step(client, [0.5] * 31, ticks=2)["output"]["state_hash"]
        self.assertEqual(first, second)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:stompy", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (1.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client, [0.0] * 31)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 31), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
