"""MuJoCo actuators without a control range (MHS/changes/MUJOCO-UNBOUNDED-ACTUATORS.md).

Ported reviewer repro (wave C, tenfoldpaper/multipanda_ros2): the MuJoCo bridge published an actuator without a
``ctrlrange`` inside the derived ``action.ctrl`` limit as ``-/+sys.float_info.max``.  The gate's envelope probe could
not exceed that value, the probe was accepted and the integration turned non-finite (G6.ENVELOPE_NOT_ENFORCED for 56
bounds, G8 SAFE-014), the 44-element literals made the step tool 2,576 bytes (G8.TOOL_SIZE), and a model without
any range was served unbounded with only G8.SAFE014_NOT_APPLICABLE.  Such a control is now ``operator_required``
(one path for a model without any range, one per element for a mixed model): the endpoint refuses a step that sets
it before the native step until the operator's overlay bounds it, gate G6 exercises that refusal, and the MCP
description groups per-element bounds by value.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import random
import sys
import types
import unittest

from mhs.bridge.mujoco import MujocoBridge
from mhs.conformance.inprocess import Harness, client_for
from mhs.driver import Action, DriverDefinitionError, GymnasiumDriver, Limit, MujocoDriver, build_manifest, close_server
from mhs.driver.behaviour import BehaviourRun, Endpoint, Session
from mhs.driver.build import build_reference, build_server
from mhs.driver.check import Gate, _g8_tool
from mhs.mcp import MCPProjection, _describe_property, _limit_texts, _number, _rule_text

from tests.bridges import support
from tests.driver.support import Client

_UNSET = "MHS.SAFETY.LIMITS_UNSET"
_ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
_FLOAT_MAX = sys.float_info.max


def model_with(ranges: list[list[float]], limited: list[int] | None) -> support.FakeMjModel:
    """The test model with one actuator per range (``limited`` None: the model has no ctrllimited array)."""
    model = support.FakeMjModel()
    model.nu = len(ranges)
    model.nq = model.nv = max(2, len(ranges))
    model.actuator_ctrlrange = [list(pair) for pair in ranges]
    if limited is None:
        del model.actuator_ctrllimited
    else:
        model.actuator_ctrllimited = list(limited)
    return model


def bridge_for(model: support.FakeMjModel) -> tuple[MujocoBridge, types.SimpleNamespace, support.FakeMjData]:
    data = support.FakeMjData(model)
    module = support.fake_mujoco()
    return MujocoBridge(prebuilt=(model, data), mujoco=module, model_name="models/arm.xml"), module, data


def module_for(ranges: list[list[float]], limited: list[int] | None):
    """A ``backends["fake"]`` factory: a stand-in mujoco module that loads the given test model."""

    def factory(**_options) -> types.SimpleNamespace:
        module = support.fake_mujoco()

        class MjModel:
            @staticmethod
            def from_xml_string(_xml: str) -> support.FakeMjModel:
                return model_with(ranges, limited)

            from_xml_path = from_xml_string

        module.MjModel = MjModel
        module.MjData = support.FakeMjData
        return module

    return factory


#: Actuator 0 has the model range -1..1, actuator 1 none (a position servo without ctrlrange, as in multipanda).
MIXED = ([[-1.0, 1.0], [0.0, 0.0]], [1, 0])
#: No actuator has a range (MuJoCo's ctrllimited default, or ctrllimited="false").
UNRANGED = ([[0.0, 0.0], [0.0, 0.0]], [0, 0])


class MixedArm(MujocoDriver):
    device_id = "mujoco/mixed-arm"
    model_xml = "<mujoco/>"
    backends = {"fake": module_for(*MIXED)}
    safe_state = "simulation paused"


class UnrangedArm(MujocoDriver):
    device_id = "mujoco/unranged-arm"
    model_xml = "<mujoco/>"
    backends = {"fake": module_for(*UNRANGED)}
    safe_state = "simulation paused"


def overlay(device_id: str, rules: dict) -> dict:
    return {"openmhs": "0.9", "site": "test bench", "devices": {
        f"mhs://localhost/{device_id}": {"cap.world.step.v1": rules}}}


def operator_rule(low: float, high: float) -> dict:
    return {"min": low, "max": high, "source": "operator", "reason": "test bench envelope"}


class BridgeLimitTests(unittest.TestCase):
    def test_a_fully_ranged_model_keeps_its_one_per_element_rule(self) -> None:
        bridge, _module, _data = bridge_for(support.FakeMjModel())
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.action_limits(), {"action.ctrl": {
            "min": [-1.0, -0.5], "max": [1.0, 0.5], "source": "upstream_code",
            "ref": "models/arm.xml:actuator_ctrlrange", "reason": "actuator ctrlrange of the model"}})
        self.assertEqual(bridge.action_limit_reasons(), {})

    def test_a_model_without_any_range_is_one_operator_required_path(self) -> None:
        bridge, _module, _data = bridge_for(model_with(*UNRANGED))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.action_limits(), {"action.ctrl": "operator_required"})
        reasons = bridge.action_limit_reasons()
        self.assertEqual(sorted(reasons), ["action.ctrl"])
        self.assertIn("no control range", reasons["action.ctrl"])

    def test_a_mixed_model_gets_one_rule_per_element_and_no_placeholder_bound(self) -> None:
        bridge, _module, _data = bridge_for(model_with(*MIXED))
        self.addCleanup(bridge.close)
        limits = bridge.action_limits()
        self.assertEqual(limits["action.ctrl[1]"], "operator_required")
        self.assertEqual((limits["action.ctrl[0]"]["min"], limits["action.ctrl[0]"]["max"]), (-1.0, 1.0))
        self.assertEqual(limits["action.ctrl[0]"]["source"], "upstream_code")
        self.assertNotIn("action.ctrl", limits)
        self.assertNotIn(repr(_FLOAT_MAX)[:10], json.dumps(limits))
        self.assertEqual(sorted(bridge.action_limit_reasons()), ["action.ctrl[1]"])

    def test_a_range_that_is_not_finite_or_is_inverted_counts_as_none(self) -> None:
        bridge, _module, _data = bridge_for(model_with([[-math.inf, 1.0], [2.0, 1.0], [-3.0, 3.0]], [1, 1, 1]))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.ctrl_ranges(), [None, None, (-3.0, 3.0)])
        self.assertEqual(sorted(path for path, rule in bridge.action_limits().items() if rule == "operator_required"),
                         ["action.ctrl[0]", "action.ctrl[1]"])

    def test_without_ctrllimited_a_range_counts_when_min_is_below_max(self) -> None:
        bridge, _module, _data = bridge_for(model_with([[-1.0, 1.0], [0.0, 0.0]], None))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.ctrl_ranges(), [(-1.0, 1.0), None])

    def test_the_legacy_ctrl_limits_keep_their_placeholder(self) -> None:
        # Package tests call ctrl_limits(); it keeps its lists, documented as a placeholder that is never published.
        bridge, _module, _data = bridge_for(model_with(*MIXED))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.ctrl_limits(), ([-1.0, -_FLOAT_MAX], [1.0, _FLOAT_MAX]))

    def test_a_direct_call_still_checks_the_model_range_and_refuses_a_non_finite_control(self) -> None:
        bridge, module, data = bridge_for(model_with(*MIXED))
        self.addCleanup(bridge.close)
        for ctrl, code in (([1.5, 0.0], _ENVELOPE), ([0.0, math.nan], "MHS.CAPABILITY.INPUT_INVALID"),
                           ([0.0, math.inf], "MHS.CAPABILITY.INPUT_INVALID"),
                           ([0.0, 10 ** 400], "MHS.CAPABILITY.INPUT_INVALID")):
            with self.subTest(ctrl=ctrl), self.assertRaises(Exception) as caught:
                bridge.call("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": ctrl}})
            self.assertEqual(getattr(caught.exception, "code", None), code)
        self.assertNotIn("mj_step", module.calls)
        self.assertEqual(data.ctrl, [0.0, 0.0])


class ServedLimitTests(unittest.TestCase):
    def serve(self, driver_class: type, site_limits: dict | None = None) -> Client:
        driver = driver_class(backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.module = driver.inner._mujoco
        return Client(server)

    def test_a_step_that_sets_an_unranged_control_is_refused_before_the_engine(self) -> None:
        client = self.serve(MixedArm)
        refused = client.command("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.5, 0.0]}})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", _UNSET), refused)
        self.assertNotIn("mj_step", self.module.calls)
        ticked = client.command("cap.world.step.v1", {"ticks": 2})
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(self.module.calls.count("mj_step"), 2)

    def test_an_operator_overlay_bounds_the_unranged_control_and_the_model_range_still_applies(self) -> None:
        client = self.serve(MixedArm, overlay("mujoco/mixed-arm", {"action.ctrl[1]": operator_rule(-2.0, 2.0)}))
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 1.5]}})["status"], "completed")
        for ctrl, path, source in (([0.5, 3.0], "action.ctrl[1]", "operator"),
                                   ([1.5, 0.0], "action.ctrl[0]", "upstream_code")):
            refused = client.command("cap.world.step.v1", {"action": {"ctrl": ctrl}})
            self.assertEqual(refused["error"]["mhs_code"], _ENVELOPE, refused)
            self.assertEqual(refused["error"]["details"]["path"], path)
            self.assertEqual(refused["error"]["details"]["provenance"]["source"], source)
        self.assertEqual(self.module.calls.count("mj_step"), 1)

    def test_an_overlay_cannot_widen_the_model_range(self) -> None:
        wide = overlay("mujoco/mixed-arm", {"action.ctrl[0]": operator_rule(-5.0, 5.0),
                                            "action.ctrl[1]": operator_rule(-1.0, 1.0)})
        with self.assertRaises(Exception) as caught:  # the strict server refuses the overlay at load
            self.serve(MixedArm, wide)
        self.assertIn("action.ctrl[0]: max 5.0 widens 1.0", str(caught.exception))
        self.assertIn("MHS.ADAPTER.MANIFEST_INVALID", str(caught.exception))

    def test_a_model_without_any_range_takes_one_scalar_or_per_element_overlay(self) -> None:
        client = self.serve(UnrangedArm)
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [0.0, 0.0]}})
        self.assertEqual(refused["error"]["mhs_code"], _UNSET, refused)
        client = self.serve(UnrangedArm, overlay("mujoco/unranged-arm", {"action.ctrl": operator_rule(-1.0, 1.0)}))
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [1.0, -1.0]}})["status"], "completed")
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [0.0, -1.5]}})
        self.assertEqual((refused["error"]["mhs_code"], refused["error"]["details"]["path"]),
                         (_ENVELOPE, "action.ctrl[1]"))

    def test_the_manifest_and_reference_say_which_control_has_no_bound_and_why(self) -> None:
        for driver_class, path in ((MixedArm, "action.ctrl[1]"), (UnrangedArm, "action.ctrl")):
            with self.subTest(driver=driver_class.__name__):
                driver = driver_class(backend="fake")
                self.addCleanup(driver.close)
                step = next(item for item in build_manifest(driver)["capabilities"]
                            if item["capability_id"] == "cap.world.step.v1")
                self.assertEqual(step["limits"][path], "operator_required")
                entries = build_reference(driver)["safety"]["operator_required"]
                entry = next(item for item in entries if item.get("path") == path)
                self.assertIn("no control range", entry["reason"])


def declaring(ranges_limited: tuple, limits: dict, name: str = "declared-arm") -> type:
    """A MujocoDriver over the given test model whose step action declares ``limits`` itself."""

    class Arm(MujocoDriver):
        device_id = f"mujoco/{name}"
        model_xml = "<mujoco/>"
        backends = {"fake": module_for(*ranges_limited)}
        safe_state = "simulation paused"
        actions = {"cap.world.step.v1": Action(name="step", limits=limits)}

    return Arm


def cited(low: float | None = None, high: float | None = None) -> Limit:
    return Limit(min=low, max=high, source="upstream_code", ref="models/arm.xml:12", reason="the upstream clamp")


#: Every actuator ranged (-1..1 and -0.5..0.5), as support.FakeMjModel.
RANGED = ([[-1.0, 1.0], [-0.5, 0.5]], [1, 1])


class DeclaredLimitTests(unittest.TestCase):
    """S5-1: a rule the driver declares on action.ctrl takes precedence; uncovered controls still fail closed."""

    def step_limits(self, driver_class: type) -> dict:
        driver = driver_class(backend="fake")
        self.addCleanup(driver.close)
        return next(item for item in build_manifest(driver)["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")["limits"]

    def serve(self, driver_class: type, site_limits: dict | None = None) -> Client:
        server = build_server(driver_class(backend="fake"), site_limits=site_limits)
        self.addCleanup(close_server, server)
        return Client(server)

    def test_a_declared_whole_vector_bound_replaces_operator_required(self) -> None:
        arm = declaring(UNRANGED, {"action.ctrl": cited(-2.0, 2.0)})
        limits = self.step_limits(arm)
        self.assertEqual(sorted(limits), ["action.ctrl"])
        self.assertEqual((limits["action.ctrl"]["min"], limits["action.ctrl"]["source"]), (-2.0, "upstream_code"))
        client = self.serve(arm)
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [1.5, -1.5]}})["status"], "completed")
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [2.5, 0.0]}})
        self.assertEqual(refused["error"]["mhs_code"], _ENVELOPE, refused)
        self.assertEqual(refused["error"]["details"]["provenance"]["source"], "upstream_code")

    def test_a_control_no_declared_rule_covers_still_fails_closed(self) -> None:
        arm = declaring(UNRANGED, {"action.ctrl[0]": cited(-2.0, 2.0)})
        limits = self.step_limits(arm)
        self.assertEqual(limits["action.ctrl[1]"], "operator_required")
        self.assertEqual(limits["action.ctrl[0]"]["max"], 2.0)
        self.assertNotIn("action.ctrl", limits)
        refused = self.serve(arm).command("cap.world.step.v1", {"action": {"ctrl": [0.5, 0.0]}})
        self.assertEqual((refused["error"]["mhs_code"], refused["error"]["details"]["paths"]),
                         (_UNSET, ["action.ctrl[1]"]))
        client = self.serve(arm, overlay("mujoco/declared-arm", {"action.ctrl[1]": operator_rule(-1.0, 1.0)}))
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [1.5, 0.5]}})["status"], "completed")
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [2.5, 0.0]}})
        self.assertEqual((refused["error"]["mhs_code"], refused["error"]["details"]["path"]),
                         (_ENVELOPE, "action.ctrl[0]"))

    def test_declared_bounds_inside_the_model_ranges_take_precedence(self) -> None:
        arm = declaring(MIXED, {"action.ctrl[0]": cited(-0.5, 0.5), "action.ctrl[1]": cited(-3.0, 3.0)})
        limits = self.step_limits(arm)
        self.assertEqual(sorted(limits), ["action.ctrl[0]", "action.ctrl[1]"])
        self.assertEqual((limits["action.ctrl[0]"]["max"], limits["action.ctrl[1]"]["max"]), (0.5, 3.0))
        client = self.serve(arm)
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [0.4, 2.0]}})["status"], "completed")
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [0.7, 0.0]}})
        self.assertEqual((refused["error"]["mhs_code"], refused["error"]["details"]["bound"]), (_ENVELOPE, 0.5))
        # every actuator ranged: the model's ranges stay one rule next to a narrower declared element rule
        limits = self.step_limits(declaring(RANGED, {"action.ctrl[1]": cited(-0.4, 0.4)}))
        self.assertEqual((limits["action.ctrl"]["max"], limits["action.ctrl[1]"]["max"]), ([1.0, 0.5], 0.4))

    def test_a_declared_rule_may_not_widen_a_model_range(self) -> None:
        for ranges, limits in ((MIXED, {"action.ctrl[0]": cited(-5.0, 5.0)}),
                               (RANGED, {"action.ctrl": cited(-5.0, 5.0)}),
                               (RANGED, {"action.ctrl[1]": cited(high=0.9)}),
                               # the min side alone (review mutant D1): the max sides are inside the ranges
                               (MIXED, {"action.ctrl[0]": cited(-5.0, 0.5)}),
                               (RANGED, {"action.ctrl[1]": cited(low=-0.9)}),
                               (RANGED, {"action.ctrl": cited(-5.0, 0.4)})):
            with self.subTest(limits=sorted(limits)), self.assertRaises(DriverDefinitionError) as caught:
                self.step_limits(declaring(ranges, limits))
            self.assertIn("widens the model's ctrlrange", str(caught.exception))

    def test_a_declaration_that_would_drop_a_bound_or_leave_a_side_open_is_refused(self) -> None:
        for limits, words in (({"action.ctrl[0]": Limit.operator_required("the site decides")}, "would drop it"),
                              ({"action.ctrl[1]": cited(high=1.0)}, "declare both min and max, or"),
                              ({"action.ctrl[0]": cited(high=0.5)}, "declare both min and max inside"),
                              ({"action.ctrl[5]": cited(-1.0, 1.0)}, "the model has 2 actuators")):
            with self.subTest(limits=sorted(limits)), self.assertRaises(DriverDefinitionError) as caught:
                self.step_limits(declaring(MIXED, limits))
            self.assertIn(words, str(caught.exception))
        # a declared operator_required on an actuator without a range is the declaration itself
        limits = self.step_limits(declaring(MIXED, {"action.ctrl[1]": Limit.operator_required("the site decides")}))
        self.assertEqual((limits["action.ctrl[1]"], limits["action.ctrl[0]"]["max"]), ("operator_required", 1.0))

    def test_an_allowed_set_bounds_a_control_on_both_sides(self) -> None:
        # review mutant D12: an allowed set counts as a declared bound (its smallest and largest number)
        allowed = Limit(allowed=[-1.0, 0.0, 1.0], source="upstream_code", ref="models/arm.xml:12")
        arm = declaring(MIXED, {"action.ctrl[1]": allowed})
        limits = self.step_limits(arm)
        self.assertEqual(sorted(limits), ["action.ctrl[0]", "action.ctrl[1]"])
        self.assertEqual((limits["action.ctrl[1]"]["allowed"], limits["action.ctrl[0]"]["max"]), ([-1.0, 0.0, 1.0], 1.0))
        client = self.serve(arm)  # no overlay: the declared set covers the unranged control
        self.assertEqual(client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 1.0]}})["status"], "completed")
        refused = client.command("cap.world.step.v1", {"action": {"ctrl": [0.5, 0.5]}})
        self.assertEqual((refused["error"]["mhs_code"], refused["error"]["details"]["kind"]), (_ENVELOPE, "allowed"))
        # an allowed set with a member outside a model range widens it
        with self.assertRaises(DriverDefinitionError) as caught:
            self.step_limits(declaring(MIXED, {"action.ctrl[0]": Limit(allowed=[0.0, 2.0], source="upstream_code",
                                                                       ref="models/arm.xml:12")}))
        self.assertIn("widens the model's ctrlrange", str(caught.exception))

    def test_a_whole_vector_operator_required_defers_only_what_the_model_leaves_open(self) -> None:
        deferred = Limit.operator_required("the site decides")
        with self.assertRaises(DriverDefinitionError) as caught:  # every actuator ranged: nothing to defer
            self.step_limits(declaring(RANGED, {"action.ctrl": deferred}))
        self.assertIn("every actuator has the model's ctrlrange", str(caught.exception))
        limits = self.step_limits(declaring(MIXED, {"action.ctrl": deferred}))  # one group; the range stays below
        self.assertEqual((limits["action.ctrl"], limits["action.ctrl[0]"]["max"]), ("operator_required", 1.0))
        self.assertNotIn("action.ctrl[1]", limits)

    def test_another_simulator_family_keeps_a_declared_rule_only_when_it_narrows(self) -> None:
        def gym(limits: dict) -> type:
            class Boxed(GymnasiumDriver):
                device_id = "gym/boxed"
                env_id = "Boxed-v0"
                backends = {"fake": lambda: support.FakeBoxEnv()}
                safe_state = "simulation paused"
                actions = {"cap.world.step.v1": Action(name="step", limits=limits)}

            return Boxed

        narrow = gym({"action.values": Limit(min=[-0.5, -1.0], max=[0.5, 1.0], source="upstream_code",
                                             ref="env.py:3")})
        limits = self.step_limits(narrow)
        self.assertEqual((limits["action.values"]["max"], limits["action.values"]["source"]), ([0.5, 1.0], "upstream_code"))
        with self.assertRaises(DriverDefinitionError) as caught:
            self.step_limits(gym({"action.values": Limit(min=[-5.0, -5.0], max=[5.0, 5.0], source="upstream_code",
                                                         ref="env.py:3")}))
        self.assertIn("does not narrow the bound the gymnasium bridge derives", str(caught.exception))


class GateBehaviourTests(unittest.TestCase):
    """G6 builds a step that carries the unranged control and checks the refusal, then the overlay."""

    @staticmethod
    def endpoints(driver_class: type, lie=None):
        def factory(site_limits=None, **_options) -> Endpoint:
            server = build_server(driver_class(backend="fake"), site_limits=site_limits)
            harness = Harness(server, allow_actuation=True)
            session = Session(server, next(iter(server.devices)))
            if lie is not None:
                original = session.command

                def command(capability_id, payload, **kwargs):
                    return lie(original(capability_id, payload, **kwargs))

                session.command = command

            def close() -> None:
                try:
                    harness.restore()
                finally:
                    close_server(server)

            return Endpoint(server, harness, session, None, close)

        return factory

    def run_g6(self, driver_class: type, lie=None) -> tuple[list, list]:
        seen: list[tuple[str, str | None]] = []

        def record(receipt):
            seen.append((receipt.get("status"), (receipt.get("error") or {}).get("mhs_code")))
            return lie(receipt) if lie is not None else receipt

        driver = driver_class(backend="fake")
        self.addCleanup(driver.close)
        run = BehaviourRun(endpoint=self.endpoints(driver_class, record), model=driver._driver_model(),
                           hardware_view=None, recorded=False)
        return run.run(), seen

    def test_g6_exercises_the_refusal_and_the_overlay_of_an_unranged_control(self) -> None:
        for driver_class in (MixedArm, UnrangedArm):
            with self.subTest(driver=driver_class.__name__):
                findings, seen = self.run_g6(driver_class)
                codes = sorted(code for code, _message, severity, _path in findings if severity == "error")
                self.assertEqual(codes, [])
                self.assertNotIn("G6.NO_INPUT", [code for code, *_rest in findings])
                self.assertIn(("rejected", _UNSET), seen)
                self.assertIn(("completed", None), seen)

    def test_g6_notices_an_endpoint_that_accepts_an_unranged_control_without_an_overlay(self) -> None:
        def accept(receipt):
            if (receipt.get("error") or {}).get("mhs_code") == _UNSET:
                return {"status": "completed", "output": {}}
            return receipt

        findings, _seen = self.run_g6(MixedArm, accept)
        self.assertIn("G6.OPERATOR_REQUIRED_NOT_ENFORCED", [code for code, *_rest in findings])


class ToolDescriptionTests(unittest.TestCase):
    @staticmethod
    def positional(path: str, low: list, high: list) -> str:
        """The rendering before the change: one ``min..max`` per element, by position."""
        return f"{path} [" + ", ".join(f"{_number(a)}..{_number(b)}" for a, b in zip(low, high)) + "]"

    def test_equal_element_bounds_are_one_group(self) -> None:
        rule = {"min": [-1] * 126, "max": [1] * 126, "reason": "actuator ctrlrange of the model"}
        self.assertEqual(_rule_text("action.ctrl", rule), "action.ctrl[*] -1..1 (actuator ctrlrange of the model)")

    def test_repeating_bounds_are_grouped_by_value_with_index_ranges(self) -> None:
        rule = {"min": [-200, -200, -300] * 4, "max": [200, 200, 300] * 4}
        self.assertEqual(_rule_text("action.ctrl", rule),
                         "action.ctrl[0-1,3-4,6-7,9-10] -200..200, [2,5,8,11] -300..300")

    def test_distinct_bounds_stay_positional_and_grouping_is_never_longer(self) -> None:
        self.assertEqual(_rule_text("a", {"min": [-1, -2], "max": [1, 2]}), "a [-1..1, -2..2]")
        rng = random.Random(7)
        for _trial in range(300):
            size = rng.randint(1, 60)
            pool = [(-rng.randint(1, 9), rng.randint(1, 9)) for _ in range(rng.randint(1, 6))]
            pairs = [rng.choice(pool) for _ in range(size)]
            low, high = [a for a, _b in pairs], [b for _a, b in pairs]
            unit = rng.choice([None, "rad", "N.m"])
            rule = {"min": low, "max": high, **({"unit": unit} if unit else {})}
            before = self.positional("action.ctrl", low, high) + (f" {unit}" if unit else "")
            self.assertLessEqual(len(_rule_text("action.ctrl", rule)), len(before), (low, high, unit))

    def test_in_the_grouped_form_every_group_carries_the_unit(self) -> None:
        # S5-3: "[0-2] -1..1, [3-5] -2..2 rad" left the first group without its unit.
        rule = {"min": [-1, -1, -1, -2, -2, -2], "max": [1, 1, 1, 2, 2, 2], "unit": "rad"}
        self.assertEqual(_rule_text("a", rule), "a[0-2] -1..1 rad, [3-5] -2..2 rad")
        self.assertEqual(_rule_text("a", {"min": [-1] * 8, "max": [1] * 8, "unit": "rad"}), "a[*] -1..1 rad")
        self.assertEqual(_rule_text("a", {"min": [-1, -2], "max": [1, 2], "unit": "rad"}), "a [-1..1, -2..2] rad")
        merged = _limit_texts({"a[0]": {"min": -1, "max": 1, "unit": "rad"}, "a[1]": {"min": -2, "max": 2, "unit": "rad"},
                               "a[2]": {"min": -1, "max": 1, "unit": "rad"}}, [])
        self.assertEqual(merged, ["a[0,2] -1..1 rad, [1] -2..2 rad"])

    def test_element_rules_are_merged_by_reason_and_value(self) -> None:
        rules = {f"action.ctrl[{index}]": {"min": -87, "max": 87, "source": "upstream_code", "reason": "model"}
                 for index in (0, 1, 2, 3, 22, 23, 24, 25)}
        rules.update({f"action.ctrl[{index}]": {"min": 0, "max": 255, "reason": "model"} for index in (21, 43)})
        rules.update({f"action.ctrl[{index}]": "operator_required" for index in list(range(7, 21)) + [29]})
        rules["ticks"] = {"min": 1, "max": 10000}
        texts = _limit_texts(rules, [f"action.ctrl[{index}]" for index in list(range(7, 21)) + [29]])
        self.assertEqual(texts, [
            "action.ctrl[0-3,22-25] -87..87, [21,43] 0..255 (model)",
            "action.ctrl[7-20,29]: no limit set yet (refused with MHS.SAFETY.LIMITS_UNSET until the operator "
            "sets one)",
            "ticks 1..10000"])

    def test_a_property_description_lists_its_element_rules(self) -> None:
        schema = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
        rules = {"ctrl[0]": {"min": -1, "max": 1, "reason": "model"}, "ctrl[1]": "operator_required"}
        _describe_property("ctrl", schema, required=False, rules=rules, unset={"ctrl[1]"})
        self.assertIn("Endpoint-enforced limits by element: [0] -1..1 (model); [1]: no limit set yet",
                      schema["description"])

    def test_a_huge_bound_prints_as_a_float(self) -> None:
        self.assertEqual(_number(_FLOAT_MAX), "1.7976931348623157e+308")
        self.assertEqual(_number(87.0), "87")

    def test_a_44_channel_mixed_step_tool_fits_the_bound_with_and_without_an_overlay(self) -> None:
        ranges = ([[-87.0, 87.0]] * 4 + [[-12.0, 12.0]] * 3 + [[0.0, 0.0]] * 14 + [[0.0, 255.0]]) * 2
        limited = ([1] * 7 + [0] * 14 + [1]) * 2

        class Dual(MujocoDriver):
            device_id = "mujoco/dual"
            model_xml = "<mujoco/>"
            backends = {"fake": module_for(ranges, limited)}
            safe_state = "simulation paused"

        servo = {f"action.ctrl[{index}]": operator_rule(-2.9, 2.9)
                 for index, flag in enumerate(limited) if not flag}
        for site_limits in (None, overlay("mujoco/dual", servo)):
            with self.subTest(overlay=site_limits is not None):
                server = build_server(Dual(backend="fake"), site_limits=site_limits)
                self.addCleanup(close_server, server)
                projection = MCPProjection(client_for(server))
                with contextlib.redirect_stderr(io.StringIO()):
                    projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                step = next(tool for tool in listed["result"]["tools"] if tool["name"].endswith("__world_step"))
                gate = Gate("G8", "Protocol and surface")
                _g8_tool(gate, step, hardware=False)
                self.assertNotIn("G8.TOOL_SIZE", [item.code for item in gate.findings])
                self.assertIn("action.ctrl[0-3,22-25] -87..87", step["description"])


if __name__ == "__main__":
    unittest.main()
