"""Class-aligned Gymnasium and MuJoCo bridges (SIM-03), end to end.

Ported reviewer repros (each failed before WP-05):

* fit-robots-sim/gym_e2e.py: with the class schemas ``step {"ticks": 1,
  "action": 1}`` is INPUT_INVALID, ``{"action": {"value": 1}}`` is
  DEVICE.FAULTED, and ``ticks`` is ignored; seed returns ``{seed,
  noise_seed}``; snapshot misses ``get_state`` behind a wrapper;
* fit-robots-sim/mj_e2e.py: ``MujocoBridge(prebuilt=...)`` crashes with
  "'NoneType' object has no attribute 'mj_step'", step reads ``n_steps``
  instead of ``ticks``, there is no ctrl input and ``timestep_ms`` is None.
"""

from __future__ import annotations

import unittest
import warnings

from tests.bridges import support

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.mujoco import MujocoBridge
from mhs.schema import validate
from mhs.server import Resource

WORLD = [Resource("world", "world.sim")]


def class_output_errors(capability_id: str, output: dict) -> list[str]:
    return validate(output, support.class_schema(capability_id)["output_schema"])


def gym_device(bridge: GymnasiumBridge, capabilities: tuple[str, ...] = (
        "cap.world.reset.v1", "cap.world.step.v1", "cap.world.seed.v1")):
    return support.simulated_device(
        "mhs://localhost:7799/gym/cartpole",
        resources=list(WORLD),
        capabilities=[support.class_capability(cap, "world") for cap in capabilities],
        bridge=bridge,
        risk_class="R0",
    )


class GymnasiumTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = support.FakeCartPole(terminate_after=8)
        self.bridge = GymnasiumBridge(env=support.FakeWrapper(self.env), env_id="CartPole-v1", seed=3)
        self.harness = support.Harness(gym_device(self.bridge))

    def tearDown(self) -> None:
        self.bridge.close()

    def test_cartpole_step_with_index_action_advances_five_ticks(self) -> None:
        reset = self.harness.command("cap.world.reset.v1", {"seed": 3})
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(class_output_errors("cap.world.reset.v1", reset["output"]), [])
        self.assertEqual(reset["output"]["seed"], 3)
        step = self.harness.command("cap.world.step.v1", {"action": {"index": 1}, "ticks": 5})
        self.assertEqual(step["status"], "completed", step)
        output = step["output"]
        self.assertEqual(output["tick"], 5)
        self.assertEqual(self.env.native_steps, 5)
        self.assertEqual(output["reward"], 5.0)
        self.assertFalse(output["terminated"])
        self.assertAlmostEqual(output["observation"]["values"][0], 0.03 + 0.5)
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(class_output_errors("cap.world.step.v1", output), [])

    def test_out_of_range_discrete_action_is_rejected_without_a_native_step(self) -> None:
        self.harness.command("cap.world.reset.v1", {})
        receipt = self.harness.command("cap.world.step.v1", {"action": {"index": 2}, "ticks": 1})
        self.assertNotEqual(receipt["status"], "completed")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.env.native_steps, 0)

    def test_ticks_stop_at_a_terminal_state_unless_autoreset(self) -> None:
        self.harness.command("cap.world.reset.v1", {})
        step = self.harness.command("cap.world.step.v1", {"action": {"index": 0}, "ticks": 20})
        self.assertEqual(step["status"], "completed", step)
        self.assertTrue(step["output"]["terminated"])
        self.assertEqual(step["output"]["tick"], 8)
        self.assertEqual(self.env.native_steps, 8)
        again = self.harness.command("cap.world.step.v1", {"action": {"index": 0}, "ticks": 1})
        self.assertEqual(again["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(self.env.native_steps, 8)

        env = support.FakeCartPole(terminate_after=8)
        auto = GymnasiumBridge(env=env, autoreset=True)
        try:
            auto.call("cap.world.reset.v1", {})
            out = auto.call("cap.world.step.v1", {"action": {"index": 0}, "ticks": 20})
            self.assertEqual(env.native_steps, 20)
            self.assertEqual(out["tick"], 4)
        finally:
            auto.close()

    def test_seed_returns_seed_and_accepted(self) -> None:
        seeded = self.harness.command("cap.world.seed.v1", {"seed": 11})
        self.assertEqual(seeded["output"], {"seed": 11, "accepted": True})
        self.harness.command("cap.world.reset.v1", {})
        self.assertEqual(self.env.seeds[-1], 11)

    def test_snapshot_and_restore_through_explicit_wrapper_paths(self) -> None:
        self.assertFalse(self.bridge.snapshot_supported)  # method presence is not a profile
        env = support.FakeCartPole(terminate_after=8)
        bridge = GymnasiumBridge(env=support.FakeWrapper(env), checkpoint={
            "profile": "json_state_v1", "getter": "env.get_state", "setter": "env.set_state"})
        self.addCleanup(bridge.close)
        self.assertTrue(bridge.snapshot_supported)
        bridge.call("cap.world.reset.v1", {"seed": 1})
        bridge.call("cap.world.step.v1", {"action": {"index": 1}, "ticks": 2})
        snapshot = bridge.snapshot()
        before = bridge.read("world")
        bridge.call("cap.world.step.v1", {"action": {"index": 1}, "ticks": 3})
        bridge.restore(snapshot)
        self.assertEqual(bridge.read("world"), before)
        self.assertEqual(env.steps, 2)
        determinism = {item["capability_id"]: item.get("determinism") for item in bridge.capabilities()}
        self.assertEqual(determinism["cap.world.step.v1"], "seeded")

    def test_snapshot_is_refused_and_not_exact_when_unsupported(self) -> None:
        bridge = GymnasiumBridge(env=support.FakeBoxEnv())
        try:
            self.assertFalse(bridge.snapshot_supported)
            with self.assertRaises(Exception):
                bridge.snapshot()
            determinism = {item["capability_id"]: item.get("determinism") for item in bridge.capabilities()}
            self.assertEqual(determinism["cap.world.step.v1"], "seeded")
        finally:
            bridge.close()

    def test_render_is_left_unbound(self) -> None:
        bridge = GymnasiumBridge(env=support.FakeCartPole(), render_mode="rgb_array")
        try:
            ids = [item["capability_id"] for item in bridge.capabilities()]
            self.assertNotIn("cap.world.render.v1", ids)
            with self.assertRaises(Exception):
                bridge.call("cap.world.render.v1", {"width": 64, "height": 64})
        finally:
            bridge.close()

    def test_cancel_event_stops_the_tick_loop(self) -> None:
        self.bridge.call("cap.world.reset.v1", {})
        context = BridgeContext()
        context.cancel_event = type("Set", (), {"is_set": staticmethod(lambda: True)})()
        with self.assertRaises(signals.Cancelled):
            self.bridge.call("cap.world.step.v1", {"action": {"index": 1}, "ticks": 3}, context)
        self.assertEqual(self.env.native_steps, 0)


class GymnasiumSpacesTests(unittest.TestCase):
    def test_box_action_values_with_element_limits_and_dict_observation(self) -> None:
        env = support.FakeBoxEnv()
        bridge = GymnasiumBridge(env=env)
        try:
            step_entry = {item["capability_id"]: item for item in bridge.capabilities()}["cap.world.step.v1"]
            limits = step_entry["limits"]["action.values"]
            self.assertEqual(limits["min"], [-1.0, -2.0])
            self.assertEqual(limits["max"], [1.0, 2.0])
            action_schema = step_entry["input_schema"]["properties"]["action"]
            self.assertEqual(action_schema["required"], ["values"])
            bridge.call("cap.world.reset.v1", {})
            out = bridge.call("cap.world.step.v1", {"action": {"values": [0.5, -1.5]}})
            self.assertEqual(out["observation"], {"position": {"values": [0.5]}, "mode": {"index": 1}})
            self.assertEqual(env.actions, [[0.5, -1.5]])
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"action": {"values": [0.5, 2.5]}})
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(caught.exception.data["details"]["path"], "action.values[1]")
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"action": {"values": [0.5]}})
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.CAPABILITY.INPUT_INVALID")
            self.assertEqual(len(env.actions), 1)
        finally:
            bridge.close()

    def test_dict_action_space_maps_named_fields(self) -> None:
        env = support.FakeBoxEnv()
        env.action_space = support.Dict({"thrust": support.Box([-1.0], [1.0]), "gear": support.Discrete(3)})
        received = []
        env.step = lambda action: (received.append(action) or ({"position": [0.0], "mode": 0}, 0.0, False, False, {}))
        bridge = GymnasiumBridge(env=env)
        try:
            bridge.call("cap.world.reset.v1", {})
            bridge.call("cap.world.step.v1", {"action": {"thrust": [0.25], "gear": 2}})
            self.assertEqual(received, [{"thrust": [0.25], "gear": 2}])
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"action": {"thrust": [0.25], "gear": 3}})
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.ENVELOPE_VIOLATION")
        finally:
            bridge.close()


class MujocoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = support.FakeMjModel()
        self.data = support.FakeMjData(self.model)
        self.mj = support.fake_mujoco()
        self.bridge = MujocoBridge(prebuilt=(self.model, self.data), mujoco=self.mj)

    def tearDown(self) -> None:
        self.bridge.close()

    def test_ctrl_outside_ctrlrange_is_rejected_without_stepping(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.5, 0.9]}})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(caught.exception.data["details"]["path"], "action.ctrl[1]")
        self.assertNotIn("mj_step", self.mj.calls)
        self.assertEqual(self.data.ctrl, [0.0, 0.0])

    def test_ctrl_limits_come_from_the_model(self) -> None:
        entry = {item["capability_id"]: item for item in self.bridge.capabilities()}["cap.world.step.v1"]
        self.assertEqual(entry["limits"]["action.ctrl"]["min"], [-1.0, -0.5])
        self.assertEqual(entry["limits"]["action.ctrl"]["max"], [1.0, 0.5])

    def test_ticks_and_ctrl_actuate(self) -> None:
        out = self.bridge.call("cap.world.step.v1", {"ticks": 5, "action": {"ctrl": [1.0, -0.5]}})
        self.assertEqual(self.mj.calls.count("mj_step"), 5)
        self.assertEqual(self.data.ctrl, [1.0, -0.5])
        self.assertEqual(out["tick"], 5)
        self.assertGreater(out["observation"]["qvel"][0], 0)
        self.assertEqual(class_output_errors("cap.world.step.v1", out), [])

    def test_timestep_from_model_opt_on_the_prebuilt_path(self) -> None:
        self.assertEqual(self.bridge.read("world")["timestep_ms"], 2.0)

    def test_integration_state_snapshot_restore(self) -> None:
        self.bridge.call("cap.world.step.v1", {"ticks": 3, "action": {"ctrl": [0.5, 0.25]}})
        snapshot = self.bridge.snapshot()
        self.assertIn("mj_getState", self.mj.calls)
        before = self.bridge.read("world")
        self.bridge.call("cap.world.step.v1", {"ticks": 4, "action": {"ctrl": [1.0, 0.5]}})
        self.bridge.restore(snapshot)
        self.assertIn("mj_setState", self.mj.calls)
        self.assertEqual(self.bridge.read("world"), before)

    def test_prebuilt_without_mujoco_is_not_ready_not_attribute_error(self) -> None:
        bridge = MujocoBridge(prebuilt=(self.model, self.data))
        try:
            if MujocoBridge.available():  # pragma: no cover - real mujoco installed
                self.skipTest("mujoco is installed")
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"ticks": 1})
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.NOT_READY")
        finally:
            bridge.close()

    def test_legacy_n_steps_alias_warns(self) -> None:
        with self.assertWarns(DeprecationWarning):
            out = self.bridge.call("cap.world.step.v1", {"n_steps": 2})
        self.assertEqual(out["tick"], 2)

    def test_mujoco_end_to_end_through_the_server(self) -> None:
        device = support.simulated_device(
            "mhs://localhost:7799/mujoco/arm",
            resources=list(WORLD),
            capabilities=[support.class_capability(cap, "world")
                          for cap in ("cap.world.reset.v1", "cap.world.step.v1")],
            bridge=self.bridge,
            risk_class="R0",
        )
        harness = support.Harness(device)
        reset = harness.command("cap.world.reset.v1", {})
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(class_output_errors("cap.world.reset.v1", reset["output"]), [])
        step = harness.command("cap.world.step.v1", {"ticks": 2, "action": {"ctrl": [0.1, 0.1]}})
        self.assertEqual(step["status"], "completed", step)
        bad = harness.command("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [2.0, 0.0]}})
        self.assertEqual(bad["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.mj.calls.count("mj_step"), 2)


if __name__ == "__main__":
    warnings.simplefilter("default")
    unittest.main()
