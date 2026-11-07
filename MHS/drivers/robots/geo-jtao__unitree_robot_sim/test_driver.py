"""Acceptance run of the unitree B2 MuJoCo package: the gate, plus model- and safety-specific cases.

Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
BAD_INPUT = "MHS.CAPABILITY.INPUT_INVALID"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

#: A twelve-element control vector for the selected scene's actuator order.
#: The values are test data for this package, not device limits.
CTRL = [0.0] * 12
#: MuJoCo's qpos0 for b2.xml: the free base at base_link's pos 0 0 0.8 with the identity quaternion
#: (b2.xml:52-54), then the twelve hinge joints at their ref 0.
QPOS0 = [0.0, 0.0, 0.8, 1.0, 0.0, 0.0, 0.0] + [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeB2Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def step(self, client, ticks=1, ctrl=None):
        payload = {"ticks": ticks}
        if ctrl is not None:
            payload["action"] = {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def test_model_shape_is_derived_from_the_mjcf(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.inner.world_state()
        self.assertEqual(len(state["qpos"]), 19)      # free base 7 + 12 hinge joints
        self.assertEqual(len(state["qvel"]), 18)      # free base 6 + 12 hinge joints
        self.assertEqual(len(state["ctrl"]), 12)      # twelve leg motors
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["timestep_ms"], 2.0)   # fake stand-in placeholder
        limits = driver.inner.action_limits()["action.ctrl"]
        self.assertEqual(len(limits["min"]), 12)
        self.assertEqual(limits["min"][:3], [-200.0, -200.0, -300.0])
        self.assertEqual(limits["max"][:3], [200.0, 200.0, 300.0])
        self.assertEqual(limits["min"][3:6], [-200.0, -200.0, -300.0])
        lows, highs = driver.inner.ctrl_limits()
        self.assertEqual(len(lows), 12)
        self.assertLess(lows[0], highs[0])

    def test_step_advances_ticks_and_applies_the_control(self) -> None:
        client = self.serve()
        ctrl = list(CTRL)
        ctrl[0] = 0.1       # FR_hip
        ctrl[1] = 0.2       # FR_thigh
        ctrl[2] = 0.3       # FR_calf
        receipt = self.step(client, ticks=3, ctrl=ctrl)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        observation = output["observation"]
        self.assertAlmostEqual(observation["time"], 0.006, places=9)
        # qpos is worldbody order (FL leg first); the actuator block is FR first.  The stand-in's motors are
        # torque-like placeholders (reviewer r20): a larger positive control accelerates its joint more.
        qpos, qvel = observation["qpos"], observation["qvel"]
        self.assertGreater(qvel[9], 0.0)
        self.assertGreater(qpos[10], 0.0)
        self.assertLess(qpos[10], qpos[11])
        self.assertLess(qpos[11], qpos[12])
        # Joints without control and the free base (not integrated by the stand-in) keep qpos0.
        self.assertEqual(qpos[:10], QPOS0[:10])
        self.assertEqual(qpos[13:], QPOS0[13:])
        state = self.state(client)
        self.assertEqual(state["tick"], 3)
        self.assertEqual(state["ctrl"], ctrl)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=2, ctrl=[1.0] * 12)["status"], "completed")
        receipt = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 0)
        # mj_resetData restores MuJoCo's qpos0, not zeros (reviewer r20).
        self.assertEqual(receipt["output"]["observation"]["qpos"], QPOS0)
        self.assertEqual(receipt["output"]["observation"]["qvel"], [0.0] * 18)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["ctrl"], [0.0] * 12)

    def test_a_malformed_action_is_rejected_before_the_state_changes(self) -> None:
        client = self.serve()
        for payload in ({"ticks": 1, "action": {"ctrl": [1.0]}},
                        {"ticks": 0},
                        {"ticks": 1, "action": {"other": 1}}):
            with self.subTest(payload=payload):
                receipt = client.invoke("cap.world.step.v1", payload, **self.ids)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], BAD_INPUT)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["time_ms"], 0)

    def test_out_of_envelope_control_is_refused_before_the_state_changes(self) -> None:
        client = self.serve()
        for index, value in ((0, 200.5), (2, 300.5), (11, -300.5)):
            with self.subTest(index=index, value=value):
                ctrl = list(CTRL)
                ctrl[index] = value
                receipt = self.step(client, ticks=1, ctrl=ctrl)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["time_ms"], 0)

    def test_estop_latches_step_and_reset_releases_it(self) -> None:
        client = self.serve()
        estop = client.estop("unitree-b2 test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "software_only")
        refused = self.step(client, ticks=1, ctrl=list(CTRL))
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The integration state stays readable during the latch.
        self.assertEqual(self.state(client)["tick"], 0)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(self.step(client, ticks=1, ctrl=list(CTRL))["status"], "completed")

    def test_the_placeholder_state_is_repeatable(self) -> None:
        client = self.serve()
        ctrl = list(CTRL)
        ctrl[0] = 0.1
        first = self.step(client, ticks=3, ctrl=ctrl)
        self.assertEqual(first["status"], "completed", first)
        client.invoke("cap.world.reset.v1", {}, **self.ids)
        second = self.step(client, ticks=3, ctrl=ctrl)
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(first["output"]["state_hash"], second["output"]["state_hash"])
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])


if __name__ == "__main__":
    unittest.main()
