"""Recorder keeps native value/schema types while tracing nested actuators."""

from __future__ import annotations

import enum
import unittest
from types import SimpleNamespace

from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.testing import Recorder, log_of


class Discrete:
    def __init__(self, n=3, start=1):
        self.n, self.start, self.shape, self.dtype = n, start, (), "int64"

    def contains(self, value):
        return self.start <= value < self.start + self.n


class MultiDiscrete:
    def __init__(self):
        self.nvec, self.low, self.high = [3, 2], [0, 0], [2, 1]
        self.shape, self.dtype = (2,), "int64"


class MultiBinary:
    def __init__(self):
        self.n, self.shape, self.dtype = 2, (2,), "int8"


class Box:
    def __init__(self):
        self.low, self.high, self.shape, self.dtype = [-1.0], [1.0], (1,), "float32"


class Tuple:
    def __init__(self):
        self.spaces = (Discrete(), Box())


class Dict:
    def __init__(self):
        self.spaces = {"mode": Discrete(), "position": Box()}


class Env:
    def __init__(self, space):
        self.action_space = space
        self.observation_space = Box()
        self.received = []

    def reset(self, seed=None, options=None):
        return [0.0], {}

    def step(self, action):
        self.received.append(action)
        return [0.0], 0.0, False, False, {}


class ValueBoundaryTests(unittest.TestCase):
    def test_space_schemas_and_native_action_types_survive_recording(self):
        cases = [(Discrete(), {"index": 1}), (MultiDiscrete(), {"values": [1, 0]}),
                 (MultiBinary(), {"values": [0, 1]}), (Box(), {"values": [0.5]}),
                 (Tuple(), {"items": [1, [0.5]]}),
                 (Dict(), {"mode": 1, "position": [0.5]})]
        for space, action in cases:
            with self.subTest(space=type(space).__name__):
                plain, native = Env(space), Env(space)
                recorder = Recorder(native)
                before = GymnasiumBridge(env=plain, env_origin="the schema fixture")
                recorded = GymnasiumBridge(env=recorder, env_origin="the schema fixture")
                self.addCleanup(before.close)
                self.addCleanup(recorded.close)
                self.assertIs(recorder.action_space, space)
                self.assertEqual(recorded.capabilities(), before.capabilities())
                expected = before.call("cap.world.step.v1", {"action": action, "ticks": 1})
                actual = recorded.call("cap.world.step.v1", {"action": action, "ticks": 1})
                self.assertEqual(actual, expected)
                self.assertEqual(native.received, plain.received)
                self.assertEqual(type(native.received[0]), type(plain.received[0]))
                self.assertIn("step", [event.name for event in log_of(recorder).actuations()])

    def test_multidiscrete_with_bounds_keeps_integer_schema(self):
        bridge = GymnasiumBridge(env=Recorder(Env(MultiDiscrete())))
        self.addCleanup(bridge.close)
        step = next(item for item in bridge.capabilities() if item["capability_id"] == "cap.world.step.v1")
        schema = step["input_schema"]["properties"]["action"]["properties"]["values"]
        self.assertEqual(schema["items"]["type"], "integer")

    def test_invalid_discrete_input_has_zero_native_step_calls(self):
        native = Env(Discrete())
        recorder = Recorder(native)
        bridge = GymnasiumBridge(env=recorder)
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception):
            bridge.call("cap.world.step.v1", {"action": {"index": 99}, "ticks": 1})
        self.assertEqual(native.received, [])
        self.assertEqual(log_of(recorder).actuations(), [])

    def test_enum_and_ordered_quantity_keep_concrete_identity(self):
        class Direction(enum.Enum):
            INFUSE = 1
            WITHDRAW = 2

        class Angle:
            def __init__(self, radians):
                self.radians = radians

            def __lt__(self, other):
                return self.radians < other.radians

        angle = Angle(0.5)
        native = SimpleNamespace(direction=Direction.INFUSE, angle=angle)
        recorder = Recorder(native)
        self.assertIs(recorder.direction, Direction.INFUSE)
        self.assertIs(type(recorder.direction)["WITHDRAW"], Direction.WITHDRAW)
        self.assertIs(recorder.angle, angle)
        self.assertIs(type(recorder.angle), Angle)
        self.assertTrue(recorder.angle < type(recorder.angle)(1.0))

    def test_schema_subclass_is_preserved_and_selection_never_runs_properties(self):
        class Derived(Discrete):
            pass

        class DescriptorSpace:
            @property
            def n(self):
                raise AssertionError("type selection must not execute schema descriptors")

        DescriptorSpace.__name__ = "Discrete"
        values = [Derived(), DescriptorSpace()]
        recorder = Recorder(attributes={"value": None})
        for value in values:
            recorder.value = value
            self.assertIs(recorder.value, value)

    def test_sample_method_and_shape_do_not_hide_nested_actuation(self):
        class Sampler:
            shape = (1,)

            def __init__(self):
                self.count = 0

            def sample(self):
                self.count += 1

            def stop(self):
                self.count += 1

        native = SimpleNamespace(sensor=Sampler())
        recorder = Recorder(native)
        with log_of(recorder).fail(names=["sensor.sample", "sensor.stop"]):
            for method in (recorder.sensor.sample, recorder.sensor.stop):
                with self.assertRaises(RuntimeError):
                    method()
        self.assertEqual(native.sensor.count, 0)

    def test_schema_name_does_not_exempt_control_methods_or_missing_fields(self):
        class Control:
            n = 3

            def stop(self):
                raise AssertionError("injection must precede the native method")

        Control.__name__ = "Discrete"
        recorder = Recorder(attributes={"controller": Control()})
        with log_of(recorder).fail(names=["controller.stop"]):
            with self.assertRaises(RuntimeError):
                recorder.controller.stop()
        self.assertEqual([event.name for event in log_of(recorder).actuations()], ["controller.stop"])
        empty = type("Discrete", (), {})()
        recorder = Recorder(attributes={"value": empty})
        recorder.value.enabled = False
        self.assertFalse(empty.enabled)
        self.assertEqual([event.name for event in log_of(recorder).actuations()], ["value.enabled"])

    def test_native_numpy_values_dtype_and_shape_preserve_identity(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional; protocol boundaries also have dependency-free tests")
        values = [np.int64(3), np.float32(0.5), np.dtype("float32"), np.array([1, 2]), (2,)]
        recorder = Recorder(SimpleNamespace(value=None))
        for value in values:
            recorder.value = value
            self.assertIs(recorder.value, value)
            self.assertIs(type(recorder.value), type(value))

    def test_genuine_gym_spaces_keep_identity_when_dependency_is_available(self):
        try:
            from gymnasium import spaces
        except ImportError:
            self.skipTest("gymnasium is optional; all schema families have dependency-free tests")
        cases = [spaces.Discrete(3), spaces.MultiDiscrete([3, 2]), spaces.MultiBinary(2),
                 spaces.Box(-1, 1, shape=(2,)), spaces.Tuple((spaces.Discrete(2),)),
                 spaces.Dict({"mode": spaces.Discrete(2)})]
        recorder = Recorder(attributes={"space": None})
        for space in cases:
            recorder.space = space
            self.assertIs(recorder.space, space)


if __name__ == "__main__":
    unittest.main()
