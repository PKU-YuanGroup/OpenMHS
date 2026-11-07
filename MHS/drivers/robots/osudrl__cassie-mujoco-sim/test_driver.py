"""Acceptance run of the Cassie MuJoCo package: the gate, plus cases for what is specific to this driver.

The cases run on the package fake (fake.py); the upstream ctypes wrapper over MuJoCo 2.10 is not installed here, so
nothing compares the fake with the upstream library.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INITIAL_QPOS = [0.0, 0.0, 1.01, 1.0, 0.0, 0.0, 0.0]     # placeholder test data, as the fake starts
CONTROL = [1.0, -1.0, 2.0, -2.0, 0.5, -1.0, 1.0, -2.0, 2.0, -0.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CassieCases(unittest.TestCase):
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

    def step(self, client, ticks=1, ctrl=None):
        payload = {"ticks": ticks}
        if ctrl is not None:
            payload["action"] = {"ctrl": ctrl}
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_two_ticks_step_the_model_and_apply_the_control(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ticks=2, ctrl=CONTROL)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(len(output["state_hash"]), len("sha256:") + 64)
        self.assertEqual(len(output["observation"]["qpos"]), 35)
        self.assertEqual(len(output["observation"]["qvel"]), 32)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 1)                    # two 0.5 ms steps
        self.assertEqual(len(state["ctrl"]), 10)
        for applied, requested in zip(state["ctrl"], CONTROL):
            self.assertAlmostEqual(applied, requested, places=9)

    def test_an_out_of_envelope_control_is_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        refused = self.step(client, ctrl=[5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)          # nothing was stepped

    def test_a_reset_restores_the_initial_state(self) -> None:
        client = self.serve()
        before = self.state(client)
        self.assertEqual(before["qpos"][:7], INITIAL_QPOS)
        self.step(client, ticks=3, ctrl=CONTROL)
        self.assertNotEqual(self.state(client)["tick"], 0)
        receipt = self.reset(client, seed=9)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 9)
        after = self.state(client)
        self.assertEqual(after["tick"], 0)
        self.assertEqual(after["time_ms"], 0)
        self.assertEqual(after["qpos"], before["qpos"])
        self.assertEqual(after["qvel"], before["qvel"])
        self.assertEqual(after["seed"], 9)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.step(client)
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, not advanced

    def test_a_step_without_an_action_uses_zero_control(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * 10)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.5, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
