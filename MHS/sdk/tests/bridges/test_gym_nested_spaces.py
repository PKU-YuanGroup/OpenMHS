"""Nested ``Dict`` action spaces are bounded member by member (MERGE-B fix round; failed first).

Ported verifier probe ``scratch/verify-WP-05/round3/probes/r1_gym_nested.py``
(minor): the members of a ``Dict`` nested inside a ``Dict`` got no schema, no
limits and no native conversion, so ``{'arm': {'j': [500, 500]}}`` reached
``env.step`` although ``j`` is a ``Box([-1, -1], [1, 1])``.  A ``Tuple`` inside a
``Dict`` now gets its structure (item count) and native conversion; the
elements of a ``Tuple`` stay unbounded (the documented simulation-only
residual, the same as a top-level ``Tuple``).
"""

from __future__ import annotations

import unittest

from tests.bridges import support

from mhs.bridge.gymnasium import GymnasiumBridge


class Tuple:
    """Duck-typed ``gymnasium.spaces.Tuple``."""

    def __init__(self, spaces) -> None:
        self.spaces = tuple(spaces)


class Env:
    def __init__(self, space) -> None:
        self.action_space = space
        self.observation_space = support.Box([-1.0], [1.0])
        self.actions: list = []

    def reset(self, seed=None, options=None):
        return [0.0], {}

    def step(self, action):
        self.actions.append(action)
        return [0.0], 0.0, False, False, {}


def code_of(exc: BaseException | None) -> str | None:
    return getattr(exc, "code", None)


class NestedDictTests(unittest.TestCase):
    def _bridge(self, space):
        env = Env(space)
        return GymnasiumBridge(env=env), env

    def test_nested_dict_members_are_bounded(self) -> None:
        bridge, env = self._bridge(support.Dict({"arm": support.Dict({"j": support.Box([-1.0, -1.0], [1.0, 1.0])}),
                                                 "grip": support.Discrete(2)}))
        try:
            limits = bridge.action_limits()
            self.assertEqual(list(limits["action.arm.j"]["min"]), [-1.0, -1.0])
            self.assertEqual(list(limits["action.arm.j"]["max"]), [1.0, 1.0])
            for action in ({"arm": {"j": [500.0, 500.0]}, "grip": 0}, {"arm": {"j": [0.0, -1.5]}, "grip": 1}):
                with self.subTest(action=action):
                    with self.assertRaises(Exception) as caught:
                        bridge.call("cap.world.step.v1", {"action": action, "ticks": 1})
                    self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(env.actions, [])
            bridge.call("cap.world.step.v1", {"action": {"arm": {"j": [0.5, -0.5]}, "grip": 1}, "ticks": 1})
            self.assertEqual(env.actions[-1]["grip"], 1)
            self.assertEqual(list(env.actions[-1]["arm"]["j"]), [0.5, -0.5])
        finally:
            bridge.close()

    def test_nested_dict_structure_is_checked(self) -> None:
        bridge, env = self._bridge(support.Dict({"arm": support.Dict({"j": support.Box([-1.0], [1.0])})}))
        try:
            schema = bridge.action_schema()["properties"]["arm"]
            self.assertEqual(schema.get("type"), "object")
            self.assertEqual(schema.get("required"), ["j"])
            self.assertIs(schema.get("additionalProperties"), False)
            for action in ({"arm": {"x": [0.0]}}, {"arm": {"j": [0.0], "x": 1}}, {"arm": [0.0]}):
                with self.subTest(action=action):
                    with self.assertRaises(Exception) as caught:
                        bridge.call("cap.world.step.v1", {"action": action, "ticks": 1})
                    self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
            self.assertEqual(env.actions, [])
        finally:
            bridge.close()

    def test_a_tuple_inside_a_dict_gets_structure_and_native_conversion(self) -> None:
        bridge, env = self._bridge(support.Dict({"t": Tuple([support.Box([-1.0], [1.0]), support.Discrete(3)])}))
        try:
            schema = bridge.action_schema()["properties"]["t"]
            self.assertEqual((schema.get("type"), schema.get("minItems"), schema.get("maxItems")), ("array", 2, 2))
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"action": {"t": [[0.5]]}, "ticks": 1})
            self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
            bridge.call("cap.world.step.v1", {"action": {"t": [[0.5], 2]}, "ticks": 1})
            native = env.actions[-1]["t"]
            self.assertIsInstance(native, tuple)
            self.assertEqual((list(native[0]), native[1]), ([0.5], 2))
        finally:
            bridge.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
