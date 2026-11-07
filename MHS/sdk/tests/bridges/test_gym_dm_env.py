"""dm_env / composer environments behind the Gymnasium bridge (dm_env_v1): synthetic dm_env peers only."""
from __future__ import annotations

import enum
import unittest
from typing import Any, NamedTuple

from mhs.bridge.dm_env_adapter import DmEnvAdapter, DmEnvError, DmEnvProfile, is_timestep_like, space_from_spec
from mhs.bridge.gymnasium import GymnasiumBridge
from tests.bridges.support import FakeCartPole

STEP, RESET, SEED = "cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"
DM = {"profile": "dm_env_v1", "source_refs": ["synthetic-peer.py:1"]}


class StepType(enum.IntEnum):   # dm_env.StepType
    FIRST = 0
    MID = 1
    LAST = 2


class TimeStep(NamedTuple):    # dm_env.TimeStep: four fields
    step_type: Any
    reward: Any
    discount: Any
    observation: Any


class Array:                    # dm_env.specs.Array (unbounded)
    def __init__(self, shape, dtype="float64", name=None):
        self.shape, self.dtype, self.name = tuple(shape), dtype, name

    def validate(self, value):
        if tuple(getattr(value, "shape", ())) != self.shape:
            raise ValueError("shape")
        return value


class BoundedArray(Array):      # dm_env.specs.BoundedArray
    def __init__(self, shape, dtype, minimum, maximum, name=None):
        super().__init__(shape, dtype, name)
        self.minimum, self.maximum = minimum, maximum
        self.validated = 0

    def validate(self, value):
        super().validate(value)
        if str(value.dtype) != str(self.dtype):
            raise ValueError("dtype")
        self.validated += 1
        return value


class DiscreteArray(BoundedArray):
    def __init__(self, num_values, name=None):
        super().__init__((), "int64", 0, num_values - 1, name)
        self.num_values = num_values


class PianoLike:
    """A composer-style episode: MID steps, then LAST with a discount the test chooses."""

    def __init__(self, *, horizon=3, final_discount=0.0):
        self.spec = BoundedArray((3,), "float32", [-1.0, -0.5, 0.0], 1.0, name="action")
        self.horizon, self.final_discount = horizon, final_discount
        self.t = 0
        self.actions: list[Any] = []
        self.reset_args: list[tuple] = []
        self.closed = False
        self.override: Any = None

    def action_spec(self):
        return self.spec

    def observation_spec(self):
        return {"keys": BoundedArray((2,), "float64", 0.0, 1.0), "time": Array(())}

    def control_timestep(self):
        return 0.05

    def reset(self, *args, **kwargs):
        self.reset_args.append((args, kwargs))
        self.t = 0
        return TimeStep(StepType.FIRST, None, None, {"keys": [0.0, 0.0], "time": 0.0})

    def step(self, action):
        self.actions.append(action)
        if self.override is not None:
            return self.override
        self.t += 1
        last = self.t >= self.horizon
        return TimeStep(StepType.LAST if last else StepType.MID, 0.25, self.final_discount if last else 1.0,
                        {"keys": [1.0, 0.0], "time": 0.05 * self.t})

    def close(self):
        self.closed = True


def make(**options):
    env = PianoLike(**options)
    return env, GymnasiumBridge(env=env, dm_env=dict(DM), device_id="sim/dm")


def code(exc):
    return getattr(exc, "code", None)


class TimeStepGuardTests(unittest.TestCase):
    """Without the profile, a TimeStep is refused on the tuple path; it is never read as (obs, r, done, info)."""

    def test_legacy_step_and_reset_refuse_a_timestep(self):
        class Legacy(FakeCartPole):
            def step(self, action):
                return TimeStep(StepType.MID, 1.0, 1.0, [0.0] * 4)
        bridge = GymnasiumBridge(env=Legacy())
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": {"index": 1}})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertIn("TimeStep", str(caught.exception))
        self.assertEqual(bridge.world_state()["tick"], 0)

        class LegacyReset(FakeCartPole):
            def reset(self, seed=None, options=None):
                return TimeStep(StepType.FIRST, None, None, [0.0] * 4)
        bridge = GymnasiumBridge(env=LegacyReset())
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertEqual(bridge.world_state()["observation"], {})   # step_type never became the observation

    def test_detection(self):
        self.assertTrue(is_timestep_like(TimeStep(0, None, None, None)))
        for value in ((1, 2, 3, 4), ([0.0], 1.0, False, {}), {"step_type": 0, "discount": 1}, "step_type", None):
            self.assertFalse(is_timestep_like(value), value)


class AdapterMappingTests(unittest.TestCase):
    def test_termination_truncation_and_discount(self):
        for final, terminated, truncated in ((0.0, True, False), (1.0, False, True), (0.5, False, True)):
            with self.subTest(final=final):
                env, bridge = make(horizon=2, final_discount=final)
                self.addCleanup(bridge.close)
                out = bridge.call(STEP, {"ticks": 5, "action": {"values": [0.0, 0.0, 0.5]}})
                self.assertEqual((out["terminated"], out["truncated"], out["tick"]), (terminated, truncated, 2))
                self.assertEqual(out["reward"], 0.5)
                self.assertEqual(len(env.actions), 2)          # stopped at LAST; never stepped past it
                info = bridge.world_state()["info"]["dm_env"]
                self.assertEqual((info["step_type"], info["discount"]), ("LAST", final))
                with self.assertRaises(Exception) as caught:
                    bridge.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.5]}})
                self.assertEqual(code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")

    def test_malformed_timesteps_are_faults(self):
        cases = {
            "first from step": TimeStep(StepType.FIRST, 0.0, 1.0, {"keys": [0, 0], "time": 0.0}),
            "reward none": TimeStep(StepType.MID, None, 1.0, {"keys": [0, 0], "time": 0.0}),
            "discount none on last": TimeStep(StepType.LAST, 0.0, None, {"keys": [0, 0], "time": 0.0}),
            "discount above one": TimeStep(StepType.LAST, 0.0, 1.5, {"keys": [0, 0], "time": 0.0}),
            "bad step type": TimeStep(7, 0.0, 1.0, {"keys": [0, 0], "time": 0.0}),
            "nan reward": TimeStep(StepType.MID, float("nan"), 1.0, {"keys": [0, 0], "time": 0.0}),
            "not a timestep": ([0.0], 0.0, False, {}),
        }
        for name, value in cases.items():
            with self.subTest(case=name):
                env, bridge = make()
                self.addCleanup(bridge.close)
                env.override = value
                with self.assertRaises(Exception) as caught:
                    bridge.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}})
                self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")

    def test_step_type_must_be_an_exact_integer(self):
        import numpy
        observation = {"keys": [0, 0], "time": 0.0}
        for value in (1.9, 2.7, "2", b"1", True, numpy.float64(1.0), None):
            with self.subTest(step_type=value):
                env, bridge = make()
                self.addCleanup(bridge.close)
                env.override = TimeStep(value, 0.0, 1.0, observation)
                with self.assertRaises(Exception) as caught:
                    bridge.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}})
                self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        for value in (1, StepType.MID, numpy.int64(1)):
            with self.subTest(step_type=value):
                env, bridge = make()
                self.addCleanup(bridge.close)
                env.override = TimeStep(value, 0.0, 1.0, observation)
                self.assertFalse(bridge.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}})["terminated"])

    def test_an_integer_action_spec_never_truncates(self):
        env = PianoLike()
        env.spec = BoundedArray((2,), "int32", 0, 5)
        bridge = GymnasiumBridge(env=env, dm_env=dict(DM))
        self.addCleanup(bridge.close)
        items = bridge.step_input_schema()["properties"]["action"]["properties"]["values"]["items"]
        self.assertEqual(items["type"], "integer")
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": {"values": [1.9, 2.5]}})
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual((env.actions, env.reset_args), ([], []))          # refused before any native call
        bridge.call(STEP, {"ticks": 1, "action": {"values": [1, 2]}})
        self.assertEqual((env.actions[0].tolist(), str(env.actions[0].dtype)), ([1, 2], "int32"))
        with self.assertRaises(Exception) as caught:                         # the adapter's own check, too
            bridge._env._native_action([1.0, 2.5])
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        float_env = PianoLike()
        float_bridge = GymnasiumBridge(env=float_env, dm_env=dict(DM))
        self.addCleanup(float_bridge.close)
        self.assertEqual(float_bridge.step_input_schema()["properties"]["action"]["properties"]["values"]["items"],
                         {"type": "number"})

    def test_reset_must_be_first(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        env.reset = lambda: TimeStep(StepType.MID, 0.0, 1.0, {"keys": [0, 0], "time": 0.0})
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")

    def test_action_spec_is_the_step_envelope(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        limits = bridge.action_limits()
        self.assertEqual(limits["action.values"]["min"], [-1.0, -0.5, 0.0])
        self.assertEqual(limits["action.values"]["max"], [1.0, 1.0, 1.0])   # scalar maximum broadcast
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": {"values": [0.0, -0.6, 0.0]}})
        self.assertEqual(code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(env.actions, [])
        bridge.call(STEP, {"ticks": 1, "action": {"values": [0.25, -0.5, 1.0]}})
        sent = env.actions[0]
        self.assertEqual((tuple(sent.shape), str(sent.dtype)), ((3,), "float32"))   # converted to the spec
        self.assertEqual(env.spec.validated, 1)                                     # and validated by it

    def test_observation_spec_and_seedless_reset(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        out = bridge.call(RESET, {})
        self.assertEqual(out["observation"], {"keys": {"values": [0.0, 0.0]}, "time": {"values": 0.0}})
        self.assertEqual(env.reset_args, [((), {})])       # the dm_env reset takes nothing
        caps = bridge.capabilities()
        self.assertEqual([item["capability_id"] for item in caps], [STEP, RESET])
        self.assertEqual({item["determinism"] for item in caps}, {"none"})
        self.assertEqual(bridge.call(RESET, {"seed": 1})["seed"], 0)   # accepted, never passed to dm_env
        self.assertEqual(env.reset_args, [((), {}), ((), {})])
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {"options": {"a": 1}})
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(bridge._env_attr("dt"), 0.05)     # control_timestep reaches the bridge

    def test_spec_conversion(self):
        self.assertEqual(space_from_spec(DiscreteArray(4)).n, 4)
        unbounded = space_from_spec(Array((2,)))
        self.assertEqual((unbounded.low, unbounded.high), ([float("-inf")] * 2, [float("inf")] * 2))
        for bad in (BoundedArray((2,), "float32", [0.0, 0.0, 0.0], 1.0), BoundedArray((1,), "float32", 2.0, 1.0),
                    BoundedArray((1,), "float32", float("nan"), 1.0)):
            with self.assertRaises(DmEnvError):
                space_from_spec(bad)
        env = PianoLike()
        env.spec = Array((3,), "float32")
        bridge = GymnasiumBridge(env=env, dm_env=dict(DM))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.action_limits(), {})       # an unbounded spec derives no limits

    def test_discrete_action_spec(self):
        env = PianoLike()
        env.spec = DiscreteArray(5)
        bridge = GymnasiumBridge(env=env, dm_env=dict(DM))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.action_limits()["action.index"]["max"], 4)
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": {"index": 5}})
        self.assertIn(code(caught.exception), ("MHS.SAFETY.ENVELOPE_VIOLATION", "MHS.CAPABILITY.INPUT_INVALID"))
        bridge.call(STEP, {"ticks": 1, "action": {"index": 4}})
        self.assertEqual((int(env.actions[0]), str(env.actions[0].dtype)), (4, "int64"))

    def test_profile_and_combinations(self):
        with self.assertRaises(DmEnvError):
            DmEnvProfile.resolve({"profile": "dm_env_v2"})
        with self.assertRaises(DmEnvError):
            DmEnvProfile.resolve({"profile": "dm_env_v1", "seed": 1})
        for extra in ({"checkpoint": {"profile": "json_state_v1", "getter": "a", "setter": "b"}},):
            with self.assertRaises(Exception) as caught:
                GymnasiumBridge(env=PianoLike(), dm_env=dict(DM), **extra)
            self.assertEqual(code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        with self.assertRaises(Exception) as caught:
            GymnasiumBridge(env=None, env_id="X-v0", dm_env=dict(DM))
        self.assertEqual(code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        env = PianoLike()
        adapter = DmEnvAdapter(env)
        self.assertIs(adapter.unwrapped, env)
        bridge = GymnasiumBridge(env=env, dm_env=dict(DM))
        bridge.call(RESET, {})
        bridge.close()
        self.assertTrue(env.closed)


if __name__ == "__main__":
    unittest.main()
