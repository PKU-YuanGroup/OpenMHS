"""Literal native keys and nested input paths must never share a limit address."""
from __future__ import annotations

import copy
import unittest

from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.driver import GymnasiumDriver, build_manifest, close_server
from tests.bridges import support
from tests.bridges.test_gym_nested_spaces import Env, code_of
from tests.driver import support as driver_support


class CountingEnv(Env):
    def __init__(self, space):
        super().__init__(space)
        self.resets = 0

    def reset(self, seed=None, options=None):
        self.resets += 1
        return super().reset(seed=seed, options=options)


def mixed_space():
    return support.Dict({
        "action.x": support.Box([-1.0], [1.0]),
        "action": support.Dict({"x": support.Box([-2.0], [2.0])}),
        "mhs_key_0": support.Discrete(2),
    })


class LiteralKeyTests(unittest.TestCase):
    def make(self, space):
        env = CountingEnv(space)
        bridge = GymnasiumBridge(env=env)
        self.addCleanup(bridge.close)
        return env, bridge

    def test_literal_and_nested_keys_get_distinct_bounds_and_native_arguments(self):
        env, bridge = self.make(mixed_space())
        schema = bridge.action_schema()
        self.assertEqual(set(schema["properties"]), {"mhs_key_1", "action", "mhs_key_0"})
        self.assertEqual(schema["properties"]["mhs_key_1"]["description"], 'Native action key: "action.x".')
        limits = bridge.action_limits()
        self.assertEqual(limits["action.mhs_key_1"]["max"], [1.0])
        self.assertEqual(limits["action.action.x"]["max"], [2.0])
        good = {"mhs_key_1": [0.5], "action": {"x": [1.5]}, "mhs_key_0": 1}
        for key, bad_value in [("mhs_key_1", [1.5]), ("action", {"x": [2.5]})]:
            bad = copy.deepcopy(good)
            bad[key] = bad_value
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"action": bad, "ticks": 1})
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual((env.resets, env.actions), (0, []))
        bridge.call("cap.world.step.v1", {"action": good, "ticks": 1})
        self.assertEqual(env.actions, [{"action.x": [0.5], "action": {"x": [1.5]}, "mhs_key_0": 1}])

    def test_aliases_are_order_independent_and_preserve_all_literal_characters(self):
        keys = ["", "x.y", "x[y]", "1x", "a b", "\u00b5", "mhs_key_0"]
        spaces = [support.Dict({k: support.Discrete(2) for k in order}) for order in (keys, keys[::-1])]
        env, bridge = self.make(spaces[0])
        _, other = self.make(spaces[1])
        self.assertEqual(bridge.action_schema(), other.action_schema())
        action = {alias: 1 for alias in bridge.action_schema()["properties"]}
        bridge.call("cap.world.step.v1", {"action": action, "ticks": 1})
        self.assertEqual(env.actions, [{key: 1 for key in keys}])

    def test_nested_literal_alias_restores_native_key_at_each_level(self):
        env, bridge = self.make(support.Dict({"arm.joints": support.Dict({"q[0]": support.Box([-3], [3])})}))
        self.assertIn("action.mhs_key_0.mhs_key_0", bridge.action_limits())
        bridge.call("cap.world.step.v1", {"ticks": 1, "action": {"mhs_key_0": {"mhs_key_0": [2]}}})
        self.assertEqual(env.actions, [{"arm.joints": {"q[0]": [2]}}])

    def test_literal_payload_is_refused_instead_of_guessing_a_second_input_form(self):
        env, bridge = self.make(mixed_space())
        with self.assertRaises(Exception) as caught:
            bridge.call("cap.world.step.v1", {"ticks": 1, "action": {"action.x": [0], "action": {"x": [0]}, "mhs_key_0": 0}})
        self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual((env.resets, env.actions), (0, []))

    def test_non_string_keys_cannot_alias_each_other(self):
        env, bridge = self.make(support.Dict({1: support.Discrete(2), "1": support.Discrete(2)}))
        with self.assertRaises(Exception) as caught:
            bridge.action_schema()
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertEqual(env.actions, [])

    def test_ordinary_identifiers_and_reserved_spellings_stay_unchanged(self):
        _, bridge = self.make(support.Dict({"mhs_key_0": support.Discrete(2), "arm_2": support.Box([-1], [1])}))
        self.assertEqual(set(bridge.action_schema()["properties"]), {"mhs_key_0", "arm_2"})
        self.assertEqual(set(bridge.action_limits()), {"action.mhs_key_0", "action.arm_2"})
        self.assertNotIn("description", bridge.action_schema()["properties"]["mhs_key_0"])

    def test_stock_server_enforces_the_distinct_limits_and_preserves_native_keys(self):
        env = CountingEnv(mixed_space())
        class D(GymnasiumDriver):
            device_id, device_kind, mode, risk = "literal-keys", "world.sim", "simulated", "R0"
            backends = {"fake": lambda **kwargs: env}
            safe_state = "future fake steps are fenced"
        driver = D(backend="fake")
        manifest = build_manifest(driver)
        step = next(item for item in manifest["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        self.assertIn("action.mhs_key_1", step["limits"])
        server, client = driver_support.serve(driver)
        self.addCleanup(close_server, server)
        action = {"mhs_key_1": [1.1], "action": {"x": [0]}, "mhs_key_0": 0}
        refused = client.command("cap.world.step.v1", {"ticks": 1, "action": action})
        self.assertEqual(driver_support.code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION", refused)
        self.assertEqual(env.actions, [])
        action["mhs_key_1"] = [0.5]
        accepted = client.command("cap.world.step.v1", {"ticks": 1, "action": action})
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertEqual(env.actions[-1]["action.x"], [0.5])


if __name__ == "__main__":
    unittest.main()
