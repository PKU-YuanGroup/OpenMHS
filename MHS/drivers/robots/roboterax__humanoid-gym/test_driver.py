"""Acceptance run of the humanoid-gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
used here, so nothing compares the stand-in's placeholder motion with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_CTRL = [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class XBotLCases(unittest.TestCase):
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

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_is_the_mjcf_shape(self) -> None:
        client = self.serve()
        state = self.state(client)
        # XBot-L.xml:165-168 is three base slides plus one ball joint, and :394-481 is twelve leg hinges:
        # 3 + 4 + 12 qpos and 3 + 3 + 12 qvel; :497-510 is twelve motors.
        self.assertEqual(len(state["qpos"]), 19)
        self.assertEqual(len(state["qvel"]), 18)
        self.assertEqual(len(state["ctrl"]), 12)
        self.assertEqual((state["time_ms"], state["tick"], state["timestep_ms"]), (0, 0, 1.0))
        self.assertEqual(state["qpos"][:4], [0.0, 0.0, 0.0, 1.0])       # base slides and the ball's w
        self.assertEqual(state["qvel"], [0.0] * 18)
        self.assertEqual(state["ctrl"], ZERO_CTRL)

    def test_the_control_envelope_is_the_model_ctrlrange(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [200.0] * 12)["status"], "completed")
        for bad in ([200.5] * 12, [0.0] * 11 + [-200.5]):
            refused = self.step(client, bad)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        # the three refused steps never reached mj_step
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_advances_the_integration_and_keeps_the_control(self) -> None:
        client = self.serve()
        ctrl = [100.0] + [0.0] * 11
        receipt = self.step(client, ctrl, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertAlmostEqual(output["observation"]["time"], 0.003, places=9)
        state = self.state(client)
        self.assertEqual((state["time_ms"], state["tick"]), (3, 3))
        self.assertEqual(state["ctrl"], ctrl)
        # the stand-in moves the first actuated hinge (qpos offset 7, qvel offset 6) in the control's direction
        self.assertGreater(state["qvel"][6], 0.0)
        self.assertGreater(state["qpos"][7], 0.0)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, [100.0] + [0.0] * 11, ticks=5)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        # a MuJoCo reset does not use the class seed; the bridge echoes its configured seed (0)
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["time_ms"], state["tick"]), (0, 0))
        self.assertEqual(state["qpos"][:4], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(state["qvel"], [0.0] * 18)
        self.assertEqual(state["ctrl"], ZERO_CTRL)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:XBot-L", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (1.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_CTRL), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced
        self.assertTrue(client.safety_status(self.ids["device_id"])["estop"]["engaged"])


if __name__ == "__main__":
    unittest.main()
