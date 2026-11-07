"""Acceptance run of the bcr_bot MuJoCo package: the gate, plus model- and safety-specific cases.

Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
BAD_INPUT = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BcrBotCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY)
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
        self.assertEqual(len(state["qpos"]), 9)       # free base 7 + two hinge joints
        self.assertEqual(len(state["qvel"]), 8)       # free base 6 + two hinge joints
        self.assertEqual(len(state["ctrl"]), 2)       # two velocity actuators
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["timestep_ms"], 2.0)   # mjcf/bcr_bot.xml:5
        # The actuator elements declare no ctrlrange, so the bridge leaves the bound to the operator.
        self.assertEqual(driver.inner.action_limits(), {"action.ctrl": "operator_required"})
        lows, highs = driver.inner.ctrl_limits()
        self.assertEqual(len(lows), 2)
        self.assertLess(lows[0], highs[0])

    def test_step_advances_ticks_and_applies_the_control(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=3, ctrl=[1.0, -2.0])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        observation = output["observation"]
        self.assertAlmostEqual(observation["time"], 0.006, places=9)
        self.assertAlmostEqual(observation["qpos"][7], 0.006, places=9)
        self.assertAlmostEqual(observation["qpos"][8], -0.012, places=9)
        self.assertEqual(observation["qvel"][6], 1.0)
        self.assertEqual(observation["qvel"][7], -2.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 3)
        self.assertEqual(state["ctrl"], [1.0, -2.0])

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=2, ctrl=[1.0, 0.0])["status"], "completed")
        receipt = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 0)
        self.assertEqual(receipt["output"]["observation"]["qpos"], [0.0] * 9)
        self.assertEqual(receipt["output"]["observation"]["qvel"], [0.0] * 8)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["ctrl"], [0.0, 0.0])

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

    def test_estop_latches_step_and_reset_releases_it(self) -> None:
        client = self.serve()
        estop = client.estop("bcr_bot test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "software_only")
        refused = self.step(client, ticks=1, ctrl=[0.0, 0.0])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The integration state stays readable during the latch.
        self.assertEqual(self.state(client)["tick"], 0)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(self.step(client, ticks=1, ctrl=[0.0, 0.0])["status"], "completed")

    def test_the_placeholder_state_is_repeatable(self) -> None:
        client = self.serve()
        first = self.step(client, ticks=3, ctrl=[1.0, -2.0])
        self.assertEqual(first["status"], "completed", first)
        client.invoke("cap.world.reset.v1", {}, **self.ids)
        second = self.step(client, ticks=3, ctrl=[1.0, -2.0])
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(first["output"]["state_hash"], second["output"]["state_hash"])
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])


    def test_a_control_step_needs_an_operator_bound(self) -> None:
        # The model gives no actuator a ctrlrange: without an operator overlay the endpoint refuses every step that
        # sets action.ctrl (LIMITS_UNSET) before the engine runs, and a step without an action still advances.
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        width = len(client.read("world", **ids)["state"]["ctrl"])
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.0] * width}}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 1)

if __name__ == "__main__":
    unittest.main()
