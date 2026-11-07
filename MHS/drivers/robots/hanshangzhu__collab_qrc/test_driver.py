"""Acceptance run of the collab_qrc MuJoCo package: the gate, plus model- and safety-specific cases.

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

#: The actuator order of the selected scene (vlm_exploration_scene.xml:361-381).
#: The values are test data for this package, not device limits.
CTRL = [0.0] * 16
#: MuJoCo's qpos0 for the scene: the free base at its body pos 4.0 0 0.6 with an identity quaternion
#: (vlm_exploration_scene.xml:158-161), then the 16 leg and foot joints at their default ref of 0.
QPOS0 = [4.0, 0.0, 0.6, 1.0, 0.0, 0.0, 0.0] + [0.0] * 16


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CollabQrcCases(unittest.TestCase):
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
        action = {} if ctrl is None else {"ctrl": list(ctrl)}
        payload = {"ticks": ticks}
        if action:
            payload["action"] = action
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def test_model_shape_is_derived_from_the_mjcf(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.inner.world_state()
        self.assertEqual(len(state["qpos"]), 23)      # free base 7 + 16 leg and foot joints
        self.assertEqual(len(state["qvel"]), 22)      # free base 6 + 16 leg and foot joints
        self.assertEqual(len(state["ctrl"]), 16)      # 12 leg motors + 4 wheel velocities
        self.assertEqual(state["qpos"], QPOS0)        # the model's default pose, not zeros
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["timestep_ms"], 2.0)   # vlm_exploration_scene.xml:4
        limits = driver.inner.action_limits()["action.ctrl"]
        self.assertEqual(len(limits["min"]), 16)
        self.assertEqual(limits["min"][0], -23.7)     # go2 motor ctrlrange
        self.assertEqual(limits["max"][2], 45.43)     # knee motor ctrlrange
        self.assertEqual(limits["min"][12], -15.0)    # wheel velocity ctrlrange
        self.assertEqual(limits["max"][15], 15.0)
        lows, highs = driver.inner.ctrl_limits()
        self.assertEqual(len(lows), 16)
        self.assertLess(lows[0], highs[0])

    def test_step_advances_ticks_and_applies_the_control(self) -> None:
        client = self.serve()
        ctrl = list(CTRL)
        ctrl[0] = 0.1       # FL_hip: a motor (force) actuator
        ctrl[12] = 1.0      # FL_wheel: a velocity actuator
        receipt = self.step(client, ticks=3, ctrl=ctrl)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        observation = output["observation"]
        self.assertAlmostEqual(observation["time"], 0.006, places=9)
        # Stand-in placeholder dynamics, not MuJoCo: each actuator's force accelerates only its own
        # joint, so the commanded hip and wheel turn in the commanded direction, the wheel's velocity
        # stays below its target, and the free base and the other joints keep qpos0.
        self.assertGreater(observation["qvel"][6], 0.0)
        self.assertGreater(observation["qpos"][7], 0.0)
        self.assertGreater(observation["qvel"][9], 0.0)
        self.assertLess(observation["qvel"][9], 1.0)
        self.assertGreater(observation["qpos"][10], 0.0)
        self.assertEqual(observation["qpos"][:7], QPOS0[:7])
        state = self.state(client)
        self.assertEqual(state["tick"], 3)
        self.assertEqual(state["ctrl"], ctrl)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=2, ctrl=[1.0] * 16)["status"], "completed")
        receipt = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 0)
        # mj_resetData restores qpos0 (base at 4.0 0 0.6, identity quaternion), not zeros.
        self.assertEqual(receipt["output"]["observation"]["qpos"], QPOS0)
        self.assertEqual(receipt["output"]["observation"]["qvel"], [0.0] * 22)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["ctrl"], [0.0] * 16)

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
        for index, value in ((0, 23.8), (2, 46.0), (12, 15.1)):
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
        estop = client.estop("collab_qrc test", **self.ids)
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
