"""SAFE-031 for a permit-gated capability whose input schema admits only the empty object (suite 1.4.1).

Suite 1.4.0 skipped SAFE-031 (required at CL3) when it could build no second valid input for the gated
binding, so a permit-gated action without inputs (a declared re-enable, CORE-086, such as the brake
release of gh.ad-sdl/ur_module) capped every such endpoint at CL2.  Such a binding has no second valid
input: another input is refused by the structure check (CORE-060 step 7) before the permit check (step
10).  The suite now records the distinct-input presentation as not applicable and tests what applies
(``mhs.conformance.tests_core._safe_031_input_free``); every other binding is tested as before.

Positive cases show the decorated shapes passing; negative cases are endpoints that break one property
each (a reusable permit, a refusal that consumes the permit, an undeclared field that reaches the permit
with the empty input's digest, a permit honoured for another capability or resource) and fail; the
counterfactual shows the 1.4.0 skip; the schema cases pin what counts as "admits only the empty object".
"""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest import mock

from mhs.conformance import SUITE_VERSION
from mhs.conformance import synth as conformance_synth
from mhs.conformance import tests_core
from mhs.conformance.inprocess import Harness, client_for, run_suite_inprocess
from mhs.conformance.synth import UNDECLARED_FIELD, Binding, only_empty_input
from mhs.conformance.tests_core import RunOptions, SuiteContext
from mhs.driver import Driver, DriverFailed, Field, Limit, action, build_server, estop, read
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from tests.conformance import support

MOVE = "x-cap.test.safe031-move.v1"
HALT = "x-cap.test.safe031-halt.v1"
UNLOCK = "x-cap.test.safe031-unlock.v1"
RELEASE = "x-cap.test.safe031-release.v1"
PING = "x-cap.test.safe031-ping.v1"
SWITCH_ON = "x-cap.test.safe031-switch-on.v1"
EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}
NOT_APPLICABLE = "distinct-input check not applicable"


# ---------------------------------------------------------------------------
# drivers
# ---------------------------------------------------------------------------


class FakeArm:
    def __init__(self, **_options):
        self.enabled = True
        self.position = 0.0
        self.calls: list[object] = []

    def halt(self):
        self.calls.append("halt")  # stops motion; the arm stays enabled

    def disable(self):
        self.calls.append("disable")
        self.enabled = False

    def enable(self):
        self.calls.append("enable")
        self.enabled = True

    def move(self, position):
        self.calls.append(("move", position))
        if not self.enabled:
            return False
        self.position = float(position)
        return True


class GatedArm(Driver):
    """An input-free permit-gated action that is not the re-enable (an unlock), plus an ungated one."""

    device_id, device_kind, mode, risk = "test/safe031-arm", "motion.axis", "hardware", "R1"
    backends = {"fake": FakeArm}
    safe_state = "the arm is halted"

    @read("position", unit="m", description="arm position")
    def position(self):
        return self.native.position

    @action(name=MOVE, input={"position": Field("number", unit="m", description="target position",
                                                limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                                            ref="arm.py:10"))},
            output={"reached": Field("boolean", description="the target was reached")})
    def move(self, position):
        if not self.native.move(position):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the arm is disabled")
        return {"reached": True}

    @action(name=HALT, safe_state=True, output={"enabled": Field("boolean", description="arm enabled")})
    def halt(self):
        self.native.halt()
        return {"enabled": self.native.enabled}

    @action(name=UNLOCK, requires_permit=True, output={"unlocked": Field("boolean", description="unlocked")})
    def unlock(self):
        self.native.calls.append("unlock")
        return {"unlocked": True}

    @action(name=PING, output={"ok": Field("boolean", description="answered")})
    def ping(self):
        self.native.calls.append("ping")
        return {"ok": True}

    @estop
    def stop(self):
        self.native.halt()


class TwoGatedArm(GatedArm):
    """Two input-free permit-gated actions: the permit of one must not open the other."""

    @action(name=RELEASE, requires_permit=True, output={"released": Field("boolean", description="released")})
    def release(self):
        self.native.calls.append("release")
        return {"released": True}


class GatedReenableArm(Driver):
    """The ur_module shape: the declared re-enable (CORE-086) needs a permit for every call."""

    device_id, device_kind, mode, risk = "test/safe031-reenable", "motion.axis", "hardware", "R1"
    backends = {"fake": FakeArm}
    safe_state = "the arm is disabled; only the permit-gated re-enable enables it again"

    @read("position", unit="m", description="arm position")
    def position(self):
        return self.native.position

    @action(name=MOVE, input={"position": Field("number", unit="m", description="target position",
                                                limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                                            ref="arm.py:10"))},
            output={"reached": Field("boolean", description="the target was reached")})
    def move(self, position):
        if not self.native.move(position):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the arm is disabled")
        return {"reached": True}

    @action(name=HALT, safe_state=True, output={"enabled": Field("boolean", description="arm enabled")})
    def halt(self):
        self.native.disable()
        return {"enabled": self.native.enabled}

    @action(name=SWITCH_ON, reenable=True, requires_permit=True,
            output={"enabled": Field("boolean", description="arm enabled")})
    def switch_on(self):
        self.native.enable()
        return {"enabled": self.native.enabled}

    @estop
    def stop(self):
        self.native.disable()


# ---------------------------------------------------------------------------
# endpoints that break one property each (patched on the server instance)
# ---------------------------------------------------------------------------


def _wrap_commands(server, hook):
    """Route every ``mhs.command`` through ``hook(params, forward)``; other methods go straight through."""

    original = server.handle

    def handle(message):
        message = dict(message)
        if message.get("method") != "mhs.command":
            return original(message)
        return hook(dict(message.get("params") or {}), lambda params: original(dict(message, params=params)),
                    message)

    server.handle = handle


def reusable_permits(server):
    """Not single-use: the permit is marked unused again after every consumption."""

    original = server._consume_permit

    def consume(session, device, capability, payload, input_digest, permit_id, **kwargs):
        original(session, device, capability, payload, input_digest, permit_id, **kwargs)
        server._permits[permit_id].used = False

    server._consume_permit = consume


def refusal_consumes_permit(server):
    """A presentation refused before any effect still spends the permit."""

    def hook(params, forward, _message):
        if UNDECLARED_FIELD in (params.get("input") or {}) and params.get("permit_id") in server._permits:
            server._permits[params["permit_id"]].used = True
        return forward(params)

    _wrap_commands(server, hook)


def ignores_undeclared_fields(server):
    """Drops an undeclared field before the checks, so the permit of ``{}`` is honoured for another input."""

    def hook(params, forward, _message):
        given = dict(params.get("input") or {})
        if UNDECLARED_FIELD in given:
            given.pop(UNDECLARED_FIELD)
            params = dict(params, input=given)
        return forward(params)

    _wrap_commands(server, hook)


def lenient_permit_scope(server):
    """Checks only that the permit exists and is unused: no capability, digest, session, device or resource."""

    from mhs.errors import MHSError

    def check(session, device, capability, payload, input_digest, permit_id, *, consume=False, resource_id=None):
        if capability is None or not server._permit_required(device, capability):
            return
        permit = server._permits.get(permit_id) if permit_id else None
        if permit is None or permit.used:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "no usable permit")
        if consume:
            permit.used = True

    server._check_permit = check


def dispatched_failure_for_undeclared(server):
    """Answers the undeclared-field presentation with a *failed* receipt that names INPUT_INVALID."""

    def hook(params, forward, message):
        if UNDECLARED_FIELD in (params.get("input") or {}):
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": {
                "status": "failed", "command_id": params.get("command_id"),
                "error": {"mhs_code": "MHS.CAPABILITY.INPUT_INVALID", "message": "driver refused the field"}}}
        return forward(params)

    _wrap_commands(server, hook)


def interlocked_unlock(params, forward, message):
    """Command hook: UNLOCK presented with a permit is refused with another code than the permit check's."""

    if params.get("capability_id") == UNLOCK and params.get("permit_id"):
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": {
            "status": "rejected", "command_id": params.get("command_id"),
            "error": {"mhs_code": "MHS.SAFETY.INTERLOCK_OPEN", "message": "door open"}}}
    return forward(params)


def suite(driver_class, patch=None, **options):
    def factory():
        server = build_server(driver_class(backend="fake"))
        if patch is not None:
            patch(server)
        return server

    return run_suite_inprocess(factory, profile="MHS-Sim", level="CL3", **options)


def entry(report, test_id):
    return next(item for item in report["tests"] if item["id"] == test_id)


def blockers(report):
    return [(item["id"], item["status"], item.get("detail")) for item in report["tests"]
            if item["required"] and item["status"] != "pass"]


# ---------------------------------------------------------------------------
# a hand-built device: one input-free gated capability bound to two resources
# ---------------------------------------------------------------------------


class TwoSidedBridge(support.NullBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.called: list[tuple[str, Any]] = []

    def call(self, capability_id, args, ctx=None):
        self.called.append((capability_id, getattr(ctx, "resource", None)))
        return {"done": True}


TWO_SIDED_ID = support.ENDPOINT_ID + "/two-sided"
#: Sorts after UNLOCK, so UNLOCK on ``left`` stays the gated binding SAFE-031 picks.
LATE_HALT = "x-cap.test.safe031-zz-halt.v1"


def two_sided_server(*, gated_halt: bool = False) -> MHSServer:
    capabilities = [
        Capability(UNLOCK, "left", title="unlock left", verb="invoke", input_schema=copy.deepcopy(EMPTY),
                   output_schema={"type": "object"}, requires_permit=True),
        Capability(UNLOCK, "right", title="unlock right", verb="invoke", input_schema=copy.deepcopy(EMPTY),
                   output_schema={"type": "object"}, requires_permit=True),
        Capability(LATE_HALT, "left", title="halt", verb="invoke", input_schema=copy.deepcopy(EMPTY),
                   output_schema={"type": "object"}, requires_permit=gated_halt),
    ]
    device = Device(
        TWO_SIDED_ID, "Two-sided clamp", mode="simulated",
        resources=[Resource("left", "actuator", state_schema={"type": "object"}),
                   Resource("right", "actuator", state_schema={"type": "object"})],
        capabilities=capabilities,
        safety=SafetyEnvelope(risk_class="R1", envelope={}, estop={"kind": "software", "latching": True},
                              safe_state={"description": "halted", "achieved_by": [LATE_HALT]}),
        fidelity=copy.deepcopy(support.FAKE_FIDELITY),
        bridge=TwoSidedBridge(device_id=TWO_SIDED_ID),
    )
    return MHSServer(endpoint_id=support.ENDPOINT_ID, devices=[device], log_ready=False)


def direct(server, **options) -> tuple[Any, SuiteContext]:
    """SAFE-031 alone on ``server``, with the in-process harness (as a group endpoint of the runner)."""

    harness = Harness(server)
    ctx = SuiteContext(client_for(server), profile="MHS-Sim", requested_level="CL3",
                       options=RunOptions(**options), harness=harness)
    ctx.load()
    ctx.ensure_session()
    ctx.current_test = "SAFE-031"
    try:
        return tests_core.safe_004(ctx), ctx
    finally:
        ctx.current_test = None
        harness.restore()


# ---------------------------------------------------------------------------
# what counts as "admits only the empty object"
# ---------------------------------------------------------------------------


def binding(schema, *, declared=None, class_schema=None) -> Binding:
    capability = {"capability_id": UNLOCK, "resource": "main",
                  "input_schema": copy.deepcopy(schema if declared is None else declared)}
    return Binding(manifest={"device_id": "test/x", "mode": "simulated"}, capability=capability, verb="invoke",
                   schema=copy.deepcopy(schema),
                   class_entry=None if class_schema is None else {"input_schema": copy.deepcopy(class_schema)},
                   requires_permit=True)


class OnlyEmptyInputTests(unittest.TestCase):
    def test_closed_empty_object_schemas_are_shown(self):
        for schema, keyword in ((EMPTY, "additionalProperties: false"),
                                ({"type": "object", "additionalProperties": False}, "additionalProperties: false"),
                                ({"type": "object", "maxProperties": 0}, "maxProperties: 0")):
            with self.subTest(schema=schema):
                reason = only_empty_input(binding(schema))
                self.assertIsNotNone(reason)
                self.assertIn("admits only the empty object", reason)
                self.assertIn(keyword, reason)
                self.assertIn("CORE-060 step 7", reason)

    def test_anything_else_shows_nothing(self):
        cases = {
            "open object": {"type": "object"},
            "empty schema": {},
            "declared property": {"type": "object", "properties": {"x": {"type": "number"}},
                                  "additionalProperties": False},
            "pattern property": {"type": "object", "patternProperties": {"^a": {}}, "additionalProperties": False},
            "top-level $ref": {"$ref": "#/$defs/empty", "$defs": {"empty": {"type": "object"}},
                               "additionalProperties": False},
            "required field": {"type": "object", "required": ["x"], "additionalProperties": False},
            "minProperties": {"type": "object", "minProperties": 1, "additionalProperties": False},
            "boolean maxProperties": {"type": "object", "maxProperties": False},
            "maxProperties 1": {"type": "object", "maxProperties": 1},
            "not an object": {"type": "array", "additionalProperties": False},
            "additionalProperties schema": {"type": "object", "additionalProperties": {"type": "number"}},
            # refuses the probe's long name but admits {"ab": 1}: the probe alone shows nothing
            "propertyNames only": {"type": "object", "propertyNames": {"maxLength": 3}},
        }
        for name, schema in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(only_empty_input(binding(schema)))

    def test_every_applied_schema_must_be_closed(self):
        # The suite synthesizes from one schema; the endpoint serves the declared one (binding ∩ class).
        self.assertIsNone(only_empty_input(binding(EMPTY, declared={"type": "object"})))
        self.assertIsNone(only_empty_input(binding(EMPTY, class_schema={
            "type": "object", "properties": {"speed": {"type": "number"}}})))
        self.assertIsNotNone(only_empty_input(binding(EMPTY, class_schema=EMPTY)))

    def test_a_keyword_the_validator_ignores_never_counts(self):
        def lenient(instance, schema):
            return []  # accepts everything, the undeclared field included

        with mock.patch("mhs.schema.validate", lenient):
            self.assertIsNone(only_empty_input(binding(EMPTY)))

    def test_a_schema_the_validator_cannot_evaluate_shows_nothing(self):
        def broken(instance, schema):
            raise ValueError("cannot evaluate")

        with mock.patch("mhs.schema.validate", broken):
            self.assertIsNone(only_empty_input(binding(EMPTY)))

    # Integrator-v3 edit (Claude Sonnet review of p3-safe031, F4): a closed schema without ``type: object``
    # also admits a string, a number, null or a list, each a second valid input.

    def test_a_schema_without_type_object_shows_nothing(self):
        cases = {
            "typeless closed": {"additionalProperties": False},
            "typeless maxProperties 0": {"maxProperties": 0},
            "typeless anyOf": {"additionalProperties": False, "anyOf": [{"type": "string"}, {"maxProperties": 0}]},
            "type list with string": {"type": ["object", "string"], "additionalProperties": False},
            "type list with null": {"type": ["object", "null"], "properties": {}, "additionalProperties": False},
            "type list of one": {"type": ["object"], "additionalProperties": False},
        }
        for name, schema in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(only_empty_input(binding(schema)))
                # the declared schema and the class schema are held to the same rule
                self.assertIsNone(only_empty_input(binding(EMPTY, declared=schema)))
                self.assertIsNone(only_empty_input(binding(EMPTY, class_schema=schema)))

    def test_the_type_rule_holds_even_where_the_validator_refuses_every_non_object(self):
        # A validator that treats every schema as an object schema would show a typeless schema: the
        # structural rule alone refuses it.
        def objects_only(instance, schema):
            if instance == {}:
                return []
            return ["refused"]

        with mock.patch("mhs.schema.validate", objects_only):
            self.assertIsNotNone(only_empty_input(binding(EMPTY)))
            self.assertIsNone(only_empty_input(binding({"additionalProperties": False})))
            self.assertIsNone(only_empty_input(binding({"type": ["object", "null"], "additionalProperties": False})))

    def test_a_validator_that_admits_a_non_object_shows_nothing(self):
        # ``type: object`` is stated, but the input is checked by the validator: one that admits a string (or
        # any other non-object) leaves a second valid input.
        for admitted in ("", 0, 1.5, True, None, [], [{}]):
            def lenient_on_types(instance, schema, admitted=admitted):
                if instance == {} or (instance == admitted and type(instance) is type(admitted)):
                    return []
                return ["refused"]

            with self.subTest(admitted=admitted), mock.patch("mhs.schema.validate", lenient_on_types):
                self.assertIsNone(only_empty_input(binding(EMPTY)))


# ---------------------------------------------------------------------------
# the suite
# ---------------------------------------------------------------------------


class InputFreePermitTests(unittest.TestCase):
    def test_suite_version_is_the_patch_release(self):
        self.assertEqual(SUITE_VERSION, "1.4.1")

    def test_an_input_free_gated_action_passes_safe031(self):
        report = suite(GatedArm)
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "pass", case)
        self.assertTrue(case["required"])
        self.assertEqual(case["spec_ref"], "SAFE-030, SAFE-031")
        self.assertIn("permit required, accepted for the bound input, rejected on reuse "
                      "(MHS.SAFETY.PERMIT_INVALID)", case["detail"])
        self.assertIn("presented first with an undeclared field, it was refused before any effect "
                      "(MHS.CAPABILITY.INPUT_INVALID) and not consumed", case["detail"])
        self.assertIn("the device has no other gated binding that takes only the empty object", case["detail"])
        note = case["evidence"]["note"]
        self.assertTrue(note.startswith(f"{NOT_APPLICABLE}: {UNLOCK} on main: its input schema admits only the "
                                        "empty object"), note)
        self.assertIn(note, case["detail"])
        self.assertEqual(report["level_achieved"], "CL3", blockers(report))

    def test_the_permit_gated_reenable_passes_safe031_and_tsafe001(self):
        # The gh.ad-sdl/ur_module shape: blocked SDK_BUG under suite 1.4.0.
        report = suite(GatedReenableArm)
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(f"{NOT_APPLICABLE}: {SWITCH_ON} on main", case["detail"])
        tsafe = entry(report, "TSAFE-001")
        self.assertEqual(tsafe["status"], "pass", tsafe)
        self.assertIn(f"the declared re-enable {SWITCH_ON} was refused while latched and accepted after the reset",
                      tsafe["detail"])
        self.assertEqual(report["level_achieved"], "CL3", blockers(report))

    def test_counterfactual_suite_140_skipped_and_capped_the_level(self):
        with mock.patch.object(conformance_synth, "only_empty_input", lambda _binding: None):
            report = suite(GatedArm)
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "skip", case)
        self.assertEqual(case["detail"], f"no distinct valid second input for {UNLOCK} to test permit binding")
        self.assertEqual(report["level_achieved"], "CL2")

    def test_another_gated_capability_refuses_the_permit(self):
        report = suite(TwoGatedArm)
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "pass", case)
        # The gated binding is the first by capability id (RELEASE); the other gated one is UNLOCK.  The
        # ungated PING and the safe-state HALT are never presented the permit.
        self.assertIn(f"{NOT_APPLICABLE}: {RELEASE} on main", case["detail"])
        self.assertIn(f"presented for another gated binding of the device it was refused: {UNLOCK} on main "
                      "(MHS.SAFETY.PERMIT_INVALID)", case["detail"])
        self.assertNotIn(PING, case["detail"])
        self.assertNotIn(HALT, case["detail"])

    def test_another_resource_of_the_same_capability_refuses_the_permit(self):
        server = two_sided_server()
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "pass", outcome)
        self.assertIn(f"{NOT_APPLICABLE}: {UNLOCK} on left", outcome.detail)
        self.assertIn(f"presented for another gated binding of the device it was refused: {UNLOCK} on right "
                      "(MHS.SAFETY.PERMIT_INVALID)", outcome.detail)
        bridge = server.devices[TWO_SIDED_ID].bridge
        self.assertEqual([item[0] for item in bridge.called], [UNLOCK], bridge.called)  # step 4 only

    def test_a_gated_safe_state_action_is_never_presented_the_permit(self):
        # achieved_by actions are exempt from permits (SAFE-029): presenting the permit would run the halt.
        server = two_sided_server(gated_halt=True)
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "pass", outcome)
        self.assertNotIn(LATE_HALT, outcome.detail)
        bridge = server.devices[TWO_SIDED_ID].bridge
        self.assertNotIn(LATE_HALT, [item[0] for item in bridge.called])

    def test_a_refusal_before_the_permit_check_is_not_counted(self):
        # RELEASE is the gated binding and UNLOCK its sibling; this endpoint refuses UNLOCK before the permit.
        server = build_server(TwoGatedArm(backend="fake"))
        _wrap_commands(server, interlocked_unlock)
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "pass", outcome)
        self.assertIn(f"refused before the permit check, so not counted: {UNLOCK} on main "
                      "(MHS.SAFETY.INTERLOCK_OPEN)", outcome.detail)
        self.assertIn("the device has no other gated binding that takes only the empty object", outcome.detail)

    def test_a_fixture_with_a_non_empty_valid_input_keeps_the_140_skip(self):
        fixtures = {"capabilities": {UNLOCK: {"valid": {"force": 1}}}}
        report = suite(GatedArm, fixtures=fixtures)
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "skip", case)
        self.assertEqual(case["detail"], f"no distinct valid second input for {UNLOCK} to test permit binding")

    def test_an_input_carrying_gated_binding_is_tested_exactly_as_in_140(self):
        server, _backend = support.heater_server()
        server.devices[support.HEATER_ID].safety.requires_permit = ["cap.thermal.*"]
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "pass", outcome)
        self.assertEqual(outcome.detail, "permit required, accepted for the bound input, rejected for a different "
                                         "input (MHS.SAFETY.PERMIT_INVALID)")
        self.assertIsNone(outcome.note)


def refusal_after_a_bridge_call(server):
    """Answers the undeclared-field presentation of UNLOCK with a ``rejected`` receipt, after calling the bridge."""

    def hook(params, forward, message):
        if params.get("capability_id") == UNLOCK and UNDECLARED_FIELD in (params.get("input") or {}):
            server.devices[TWO_SIDED_ID].bridge.call(UNLOCK, {})
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": {
                "status": "rejected", "command_id": params.get("command_id"),
                "error": {"mhs_code": "MHS.CAPABILITY.INPUT_INVALID", "message": "undeclared field"}}}
        return forward(params)

    _wrap_commands(server, hook)


def sibling_answered_completed(server):
    """Answers the permit presented for UNLOCK on ``right`` with a ``completed`` receipt, without a bridge call."""

    def hook(params, forward, message):
        if (params.get("capability_id") == UNLOCK and params.get("resource") == "right"
                and params.get("permit_id")):
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": {
                "status": "completed", "command_id": params.get("command_id"), "output": {}}}
        return forward(params)

    _wrap_commands(server, hook)


class BrokenEndpointTests(unittest.TestCase):
    # Integrator-v3 edit: the two mutants of the Claude Sonnet safety lens of p3-safe031 (F1) that survived this
    # module, each killed by an endpoint that breaks only the property the dropped check tests.

    def test_a_refusal_that_reached_the_bridge_fails(self):
        # Step 2: a ``rejected`` receipt with an allowed refusal code is not enough; the capability must not
        # have reached the bridge (killed mutant: the bridge-call check of step 2 dropped).
        server = two_sided_server()
        refusal_after_a_bridge_call(server)
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "fail", outcome)
        self.assertIn("the permit presented with an undeclared field was refused (MHS.CAPABILITY.INPUT_INVALID) "
                      f"but {UNLOCK} reached the bridge", outcome.detail)

    def test_a_sibling_presentation_answered_as_completed_fails(self):
        # Step 3: a permit presented for another gated binding must not be dispatched, even when nothing reached
        # the bridge (killed mutant: the receipt-status check of step 3 dropped).
        server = two_sided_server()
        sibling_answered_completed(server)
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "fail", outcome)
        self.assertIn(f"the permit of {UNLOCK} on left was presented for {UNLOCK} on right (another input digest) "
                      "and the command returned a 'completed' receipt", outcome.detail)
        bridge = server.devices[TWO_SIDED_ID].bridge
        self.assertEqual(bridge.called, [], bridge.called)

    def test_a_reusable_permit_fails(self):
        case = entry(suite(GatedArm, patch=reusable_permits), "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertEqual(case["detail"], "reused permit with the same input returned completed")

    def test_a_refusal_that_spends_the_permit_fails(self):
        case = entry(suite(GatedArm, patch=refusal_consumes_permit), "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("permit-gated command failed with the issued permit after the refused presentations",
                      case["detail"])
        self.assertIn("PERMIT_INVALID", case["detail"])

    def test_a_permit_honoured_for_another_input_fails(self):
        case = entry(suite(GatedArm, patch=ignores_undeclared_fields), "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(f"the permit presented with an undeclared field ({UNDECLARED_FIELD!r}) returned completed",
                      case["detail"])

    def test_a_dispatched_failure_is_not_a_refusal(self):
        case = entry(suite(GatedArm, patch=dispatched_failure_for_undeclared), "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("returned MHS.CAPABILITY.INPUT_INVALID", case["detail"])
        self.assertIn("must be refused before any effect", case["detail"])

    def test_a_permit_honoured_for_another_capability_fails(self):
        case = entry(suite(TwoGatedArm, patch=lenient_permit_scope), "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(f"the permit of {RELEASE} on main was presented for {UNLOCK} on main (another input digest)",
                      case["detail"])

    def test_a_permit_honoured_for_another_resource_fails(self):
        server = two_sided_server()
        lenient_permit_scope(server)
        outcome, _ctx = direct(server)
        self.assertEqual(outcome.status, "fail", outcome)
        self.assertIn(f"the permit of {UNLOCK} on left was presented for {UNLOCK} on right (another input digest) "
                      "and the command", outcome.detail)


if __name__ == "__main__":
    unittest.main()
