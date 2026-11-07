"""Where the limits the Gymnasium bridge derives from an action space say they come from (wave D, found not fixed).

Before the fix every derived bound was ``upstream_code`` with ``ref <env>:action_space``, whichever object supplied
the space, so a driver package's fake published its placeholder bounds as upstream code.
"""

from __future__ import annotations

import unittest

from mhs import limits as _limits
from mhs.bridge.gymnasium import GymnasiumBridge

from tests.bridges import support

FAKE_REF = "action_space of the fake backend .fake:FakeRover"


def code_of(exc: BaseException | None) -> str | None:
    return getattr(exc, "code", None)


class GymLimitProvenanceTests(unittest.TestCase):
    def bridge(self, **kwargs) -> GymnasiumBridge:
        bridge = GymnasiumBridge(**kwargs)
        self.addCleanup(bridge.close)
        return bridge

    def test_a_space_the_bridge_builds_itself_is_upstream_code(self) -> None:
        bridge = self.bridge(env_id="Box-v0", env_spec={"module": "tests.bridges.support", "attr": "FakeBoxEnv"})
        rule = bridge.action_limits()["action.values"]
        self.assertEqual(rule, {"min": [-1.0, -2.0], "max": [1.0, 2.0], "source": "upstream_code",
                                "ref": "Box-v0:action_space"})

    def test_a_prebuilt_env_publishes_its_bounds_without_a_source(self) -> None:
        env = support.FakeBoxEnv()
        bridge = self.bridge(env=env, env_id="Box-v0")
        rule = bridge.action_limits()["action.values"]
        self.assertEqual(rule, {"min": [-1.0, -2.0], "max": [1.0, 2.0],
                                "ref": "action_space of the FakeBoxEnv object passed to the bridge"})
        # still enforced, and the refusal claims no provenance
        bridge.call("cap.world.reset.v1", {})
        with self.assertRaises(Exception) as caught:
            bridge.call("cap.world.step.v1", {"action": {"values": [0.5, 2.5]}})
        self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertNotIn("provenance", caught.exception.data["details"])
        self.assertEqual(env.actions, [])

    def test_env_origin_names_the_backend_in_every_derived_rule(self) -> None:
        env = support.FakeBoxEnv()
        env.action_space = support.Dict({"thrust": support.Box([-1.0], [1.0]), "gear": support.Discrete(3)})
        bridge = self.bridge(env=support.FakeWrapper(env), env_id="Rover-v0",
                             env_origin="the fake backend .fake:FakeRover")
        limits = bridge.action_limits()
        self.assertEqual(sorted(limits), ["action.gear", "action.thrust"])
        for path, rule in limits.items():
            with self.subTest(path=path):
                self.assertNotIn("source", rule)
                self.assertNotIn("reason", rule)
                self.assertEqual(rule["ref"], FAKE_REF)
        step = {item["capability_id"]: item for item in bridge.capabilities()}["cap.world.step.v1"]
        self.assertEqual(step["limits"], limits)
        # the effective rule keeps the ref although it states no source
        effective = _limits.compile_limits(bridge.step_input_schema(), [_limits.LimitSource("bridge", limits)])
        self.assertEqual(effective.rule("action.thrust").to_json(), {"min": [-1.0], "max": [1.0], "ref": FAKE_REF})

    def test_action_space_ref_cites_the_upstream_definition(self) -> None:
        bridge = self.bridge(env=support.FakeBoxEnv(), env_origin="the fake backend .fake:FakeRover",
                             action_space_ref="rover/envs.py:42")
        rule = bridge.action_limits()["action.values"]
        self.assertEqual((rule["source"], rule["ref"]), ("upstream_code", "rover/envs.py:42"))
        self.assertNotIn("reason", rule)
        effective = _limits.compile_limits(bridge.step_input_schema(),
                                           [_limits.LimitSource("bridge", bridge.action_limits())])
        self.assertEqual(effective.rule("action.values").to_json()["ref"], "rover/envs.py:42")

    def test_a_blank_or_oversized_action_space_ref_is_refused(self) -> None:
        for bad in ("", "   ", 42, "x" * 501):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception) as caught:
                    GymnasiumBridge(env=support.FakeBoxEnv(), action_space_ref=bad)
                self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
