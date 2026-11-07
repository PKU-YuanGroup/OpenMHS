"""RESIDUAL-B: the open 07b verifier issues (``verify-WP-07/07b/r3/adv``, read-only originals).

* ``n_anyof_class.py`` (blocker): a class-default limit on a field the
  binding declares only inside ``anyOf`` / ``oneOf`` was "not applicable",
  so an endpoint that ignores class limits accepted ``target_temperature=500``
  and still passed SAFE-014 at CL3 (in-process and over a client).
* ``o_oneof_envelope.py``: the same root cause turned an envelope limit on a
  ``oneOf``-declared field into a false gap; the enforcing runtime skipped to CL2.
* the lab: its bindings admit extra properties, so the class-default
  ``volume`` / ``wavelength_min`` limits can be sent; they were "nothing to send".
* ``p2_fixture_whole_path_cl3.py`` (major): without a base input, one
  ``out_of_envelope`` fixture refusal at ``points[0].z`` covered
  ``points[*].z`` entirely, so a tail-blind endpoint reached CL3.
* numeric allowed sets (minor): one probe at ``max(allowed)+1`` let an
  endpoint that enforces ``[1, 3, 5]`` as a range, or only its upper side, pass.
* OP-001 (minor): a read the suite could not build an input for was dropped
  without a word.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mhs.conformance import run_suite
from mhs.conformance import synth as _synth
from mhs.conformance.inprocess import reference_factory, run_suite_inprocess
from mhs.conformance.synth import bindings_for, envelope_probe_plan, valid_input

from tests.conformance import support
from tests.conformance.support import client_for, entry

SETPOINT = "cap.thermal.setpoint.v1"
POINTS = "x-cap.example.path.v1"
#: The p2 fixture: only element 0 is out of its limit.
ELEMENT0_FIXTURE = {"capabilities": {POINTS: {"out_of_envelope": [
    {"points": [{"label": "P1", "z": 50}, {"label": "P2", "z": 1}, {"label": "P3", "z": 1}]}]}}}


def blind(name: str) -> type:
    return support.blind_server_class(name)


def run_both(factory, *, level="CL3", **options):
    """``[(transport, report, SAFE-014 entry)]`` in-process (harness) and over a plain client."""

    out = []
    report = run_suite_inprocess(factory, profile="MHS-Sim", level=level, **options)
    out.append(("inprocess", report, entry(report, "SAFE-014")))
    report = run_suite(client_for(factory()), profile="MHS-Sim", level=level, **options)
    out.append(("client", report, entry(report, "SAFE-014")))
    return out


def binding_of(server, capability_id):
    client = client_for(server)
    manifest = client.devices()[0]
    published = client.inspect(manifest["device_id"])
    return [item for item in bindings_for(manifest, published=published) if item.capability_id == capability_id][0]


class BranchDeclaredFieldTests(unittest.TestCase):
    """n_anyof_class.py / o_oneof_envelope.py: a field any anyOf / oneOf branch declares is probed."""

    def test_a_class_limit_in_a_branch_is_probed_and_a_blind_endpoint_fails(self):
        for name, schema in (("anyOf", support.ANYOF_SETPOINT), ("oneOf", support.ONEOF_SETPOINT)):
            plan_binding = binding_of(support.branched_heater(schema)[0], SETPOINT)
            plan = envelope_probe_plan(plan_binding, valid_input(plan_binding)[0])
            with self.subTest(schema=name, check="plan"):
                self.assertEqual(plan.not_applicable, [], plan)
                self.assertEqual(plan.gaps, [], plan)
                self.assertEqual({(probe.path, probe.kind) for probe in plan.probes},
                                 {("target_temperature", "max"), ("target_temperature", "min")})
            for transport, report, case in run_both(
                    lambda schema=schema: support.branched_heater(schema, server_class=blind("class"))[0]):
                with self.subTest(schema=name, transport=transport, endpoint="class-blind"):
                    self.assertEqual(case["status"], "fail", case)
                    self.assertIn("target_temperature=301.0", case["detail"])
                    self.assertNotEqual(report["level_achieved"], "CL3")
            for transport, report, case in run_both(lambda schema=schema: support.branched_heater(schema)[0]):
                with self.subTest(schema=name, transport=transport, endpoint="runtime"):
                    self.assertEqual(case["status"], "pass", case)
                    self.assertIn(f"{SETPOINT} target_temperature", case["detail"])

    def test_an_envelope_limit_on_a_one_of_field_is_not_a_gap(self):
        """o_oneof_envelope.py: the enforcing runtime was skipped to CL2 with a false gap."""

        report = run_suite_inprocess(
            lambda: support.branched_heater(support.ONEOF_SETPOINT, envelope=True, fan=False)[0],
            profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("target_temperature=81.0", case["detail"])


class AdmittedFieldTests(unittest.TestCase):
    """A limited field the binding admits without declaring it reaches the endpoint, so it is probed."""

    def test_the_lab_class_limits_on_admitted_fields_are_probed(self):
        server, close = reference_factory("lab")()
        try:
            client = client_for(server)
            manifests = client.devices()
            plans = {}
            for manifest in manifests:
                for binding in bindings_for(manifest, published=client.inspect(manifest["device_id"])):
                    if binding.verb in ("write", "invoke") and binding.bounds:
                        plans[binding.capability_id] = envelope_probe_plan(binding, valid_input(binding)[0])
        finally:
            close()
        aspirate = plans["cap.fluid.aspirate.v1"]
        self.assertEqual(aspirate.not_applicable, [])
        self.assertEqual(aspirate.gaps, [])
        self.assertTrue({"volume", "volume_ul"} <= {probe.limit_path for probe in aspirate.probes}, aspirate.probes)
        report = run_suite_inprocess(reference_factory("lab"), profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "pass", case)  # the runtime refuses them with ENVELOPE_VIOLATION
        self.assertIn("cap.fluid.aspirate.v1 volume", case["detail"])
        self.assertNotIn("nothing can be sent", (case.get("evidence") or {}).get("note") or "")
        # Capped by other tests: CL2 while the plate reader's achieved_by named an unbound class,
        # CL3 (the claim) since WP-06 06c fixed it.
        self.assertIn(report["level_achieved"], ("CL2", "CL3"))

    def test_a_class_limit_on_a_field_the_binding_rejects_is_not_applicable(self):
        closed = {"type": "object", "required": ["preset"], "additionalProperties": False,
                  "properties": {"preset": {"type": "string", "enum": ["standby", "eco"]}}}
        # Every branch of the oneOf is closed and none declares target_temperature: no payload carries it.
        branches = {"type": "object", "oneOf": [dict(closed), {
            "type": "object", "required": ["mode"], "additionalProperties": False,
            "properties": {"mode": {"type": "string", "enum": ["a"]}}}]}
        binding = binding_of(support.branched_heater(branches, fan=False)[0], SETPOINT)
        self.assertIn("target_temperature", [bound.path for bound in binding.bounds])
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, ["target_temperature"])
        self.assertEqual((plan.probes, plan.gaps), ([], []))
        # One open branch is enough for the field to reach the endpoint: it is probed.
        branches["oneOf"][1] = {"type": "object", "required": ["mode"],
                                "properties": {"mode": {"type": "string", "enum": ["a"]}}}
        binding = binding_of(support.branched_heater(branches, fan=False)[0], SETPOINT)
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, [])

    def test_a_declared_limit_on_a_field_the_binding_rejects_is_a_gap_on_each_side(self):
        """The runtime refuses such a device; an endpoint that publishes it anyway cannot pass SAFE-014."""

        def manifest(closed: bool):
            schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "number"}}}
            if closed:
                schema["additionalProperties"] = False
            return {
                "device_id": "mhs://localhost/test/tool", "mode": "simulated",
                "resources": [{"resource_id": "arm", "kind": "robot.arm"}],
                "capabilities": [{"capability_id": support.TOOL_CAPABILITY, "resource": "arm",
                                  "input_schema": schema}],
                "safety": {"risk_class": "R2", "envelope": {support.TOOL_CAPABILITY: {
                    "speed": {"min": 0, "max": support.TOOL_MAX_SPEED, "unit": "mm/s", "reason": "tool"}}}},
            }

        binding = bindings_for(manifest(True))[0]
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, [])
        self.assertEqual([(gap.limit_path, gap.path, gap.kind, gap.reason) for gap in plan.gaps],
                         [("speed", "speed", side, _synth._REFUSED) for side in ("max", "min")])
        binding = bindings_for(manifest(False))[0]
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.gaps, [])
        self.assertEqual([(probe.path, probe.kind, probe.value) for probe in plan.probes],
                         [("speed", "max", float(support.TOOL_MAX_SPEED + 1)), ("speed", "min", -1.0)])


#: ``v_uneval.py``: ``target_temperature`` undeclared, closed only by a keyword :mod:`mhs.schema` ignores.
UNEVALUATED = {"type": "object", "properties": {"rate": {"type": "number", "x-mhs-unit": "K/min", "minimum": 0}},
               "unevaluatedProperties": False}
#: ``v_pattern_branch.py``: one ``anyOf`` option types ``^target`` fields as strings, the other admits them.
PATTERN_BRANCH = {"type": "object",
                  "properties": {"rate": {"type": "number", "x-mhs-unit": "K/min", "minimum": 0}},
                  "anyOf": [{"patternProperties": {"^target": {"type": "string"}}}, {"properties": {"rate": {}}}]}
#: Controls: every way of carrying ``target_temperature`` types it a string (pattern at the root, or in every
#: option), or a local ``$ref`` closes the object; the class limit is then really not applicable.
PATTERN_ROOT = {"type": "object", "properties": {"rate": {"type": "number", "minimum": 0}},
                "patternProperties": {"^target": {"type": "string"}}}
PATTERN_EVERY_OPTION = {"type": "object", "properties": {"rate": {"type": "number", "minimum": 0}},
                        "anyOf": [{"patternProperties": {"^target": {"type": "string"}}},
                                  {"properties": {"rate": {}}, "additionalProperties": {"type": "string"}}]}
REF_CLOSED = {"$ref": "#/$defs/closed", "$defs": {"closed": {
    "type": "object", "additionalProperties": False, "properties": {"rate": {"type": "number", "minimum": 0}}}}}
#: Declared, but only where no number can go (a branch types it a string; a $ref sibling cannot reopen the target).
DECLARED_STRING_BRANCH = {"type": "object", "properties": {"rate": {"type": "number", "minimum": 0}},
                          "anyOf": [{"patternProperties": {"^target": {"type": "string"}}},
                                    {"properties": {"target_temperature": {"type": "string"}}}]}
REF_CLOSED_SIBLING = dict(REF_CLOSED, properties={"target_temperature": {}})
#: ``not`` refuses the field, but only validation shows it: no refusal can be proven, so it is a gap, never a pass.
NOT_REQUIRED = {"type": "object", "properties": {"rate": {"type": "number", "minimum": 0}},
                "not": {"required": ["target_temperature"]}}


class ValidatorProvenReachTests(unittest.TestCase):
    """RESIDUAL-B verifier blocker (``v_uneval.py``, ``v_pattern_branch.py``): "not applicable" must be proven.

    The reach rule called a field refused from the schema's shape: it
    counted ``unevaluatedProperties: false`` (which :mod:`mhs.schema`
    ignores, so the endpoint accepts the field) and judged a field matched by
    a string-typed ``patternProperties`` in one ``anyOf`` option as refused
    although the other option admits a number.  The class-default limit on
    ``target_temperature`` was then "not applicable": the class-blind
    endpoint completed ``target_temperature=500`` (class max 300) yet passed
    SAFE-014 at CL3, in-process and over a client.  Now a field is refused
    only when every way of carrying it is refused under the validator's own
    keywords and no input carrying it inside its limits validates.
    """

    def test_a_field_the_validator_admits_is_probed_and_a_class_blind_endpoint_fails(self):
        for name, schema in (("unevaluatedProperties", UNEVALUATED), ("pattern in one anyOf option", PATTERN_BRANCH)):
            binding = binding_of(support.branched_heater(schema)[0], SETPOINT)
            plan = envelope_probe_plan(binding, valid_input(binding)[0])
            with self.subTest(schema=name, check="plan"):
                self.assertEqual(plan.not_applicable, [], plan)
                self.assertEqual(plan.gaps, [], plan)
                self.assertEqual({(probe.path, probe.kind) for probe in plan.probes},
                                 {("target_temperature", "max"), ("target_temperature", "min")})
                self.assertTrue(all(probe.in_schema for probe in plan.probes), plan.probes)
            for transport, report, case in run_both(
                    lambda schema=schema: support.branched_heater(schema, server_class=blind("class"))[0]):
                with self.subTest(schema=name, transport=transport, endpoint="class-blind"):
                    self.assertEqual(case["status"], "fail", case)
                    self.assertIn("target_temperature=301.0", case["detail"])
                    self.assertNotIn("nothing can be sent", (case.get("evidence") or {}).get("note") or "")
                    self.assertNotEqual(report["level_achieved"], "CL3")
            for transport, report, case in run_both(lambda schema=schema: support.branched_heater(schema)[0]):
                with self.subTest(schema=name, transport=transport, endpoint="runtime"):
                    self.assertEqual(case["status"], "pass", case)
                    self.assertIn(f"{SETPOINT} target_temperature", case["detail"])

    def test_a_field_no_valid_input_can_carry_stays_not_applicable(self):
        """Controls: the class-blind endpoint refuses ``target_temperature=500`` by its schema, so n/a is genuine."""

        for name, schema in (("pattern at the root", PATTERN_ROOT),
                             ("pattern or string in every option", PATTERN_EVERY_OPTION),
                             ("$ref to a closed object", REF_CLOSED),
                             ("declared as a string in a branch", DECLARED_STRING_BRANCH),
                             ("$ref to a closed object with a sibling property", REF_CLOSED_SIBLING)):
            binding = binding_of(support.branched_heater(schema)[0], SETPOINT)
            plan = envelope_probe_plan(binding, valid_input(binding)[0])
            with self.subTest(schema=name):
                self.assertEqual(plan.not_applicable, ["target_temperature"], plan)
                self.assertEqual((plan.probes, plan.gaps), ([], []))
                client = client_for(support.branched_heater(schema, server_class=blind("class"))[0])
                client.open_session()
                receipt = client.invoke(SETPOINT, {"target_temperature": 500}, device_id=support.HEATER_ID,
                                        resource="heater")
                self.assertEqual(receipt.get("status"), "rejected", receipt)
                self.assertEqual((receipt.get("error") or {}).get("mhs_code"), "MHS.CAPABILITY.INPUT_INVALID")

    def test_a_refusal_only_validation_shows_is_a_gap_never_a_pass(self):
        """``not`` is never read as a refusal: the field cannot be carried, so each side is an open gap."""

        binding = binding_of(support.branched_heater(NOT_REQUIRED)[0], SETPOINT)
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, [])
        self.assertEqual({(gap.path, gap.kind, gap.reason) for gap in plan.gaps},
                         {("target_temperature", side, _synth._UNBUILDABLE) for side in ("max", "min")})
        for transport, report, case in run_both(
                lambda: support.branched_heater(NOT_REQUIRED, server_class=blind("class"))[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "skip", case)
                self.assertTrue(case["required"], case)
                self.assertNotEqual(report["level_achieved"], "CL3")

    def test_a_shape_rule_the_validator_disproves_does_not_make_a_limit_not_applicable(self):
        """Defence in depth: a structural "refused" is overruled by a valid input that carries the field."""

        binding = binding_of(support.branched_heater(UNEVALUATED)[0], SETPOINT)
        with mock.patch.object(_synth, "_refused", return_value=True):
            plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, [], plan)
        self.assertEqual({(probe.path, probe.kind) for probe in plan.probes},
                         {("target_temperature", "max"), ("target_temperature", "min")})

    def test_the_refusal_rule_reads_only_keywords_the_validator_applies(self):
        refused = _synth._refused
        self.assertFalse(refused(UNEVALUATED, ("target_temperature",), UNEVALUATED, numeric=True))
        self.assertFalse(refused(PATTERN_BRANCH, ("target_temperature",), PATTERN_BRANCH, numeric=True))
        self.assertTrue(refused(PATTERN_ROOT, ("target_temperature",), PATTERN_ROOT, numeric=True))
        self.assertFalse(refused(PATTERN_ROOT, ("target_temperature",), PATTERN_ROOT, numeric=False))
        self.assertTrue(refused(PATTERN_EVERY_OPTION, ("target_temperature",), PATTERN_EVERY_OPTION, numeric=True))
        self.assertTrue(refused(REF_CLOSED, ("target_temperature",), REF_CLOSED))
        # allOf: one closed member refuses; an anyOf / oneOf needs every option closed
        closed = {"type": "object", "additionalProperties": False, "properties": {"a": {}}}
        self.assertTrue(refused({"allOf": [closed, {}]}, ("b",), {}))
        self.assertFalse(refused({"anyOf": [closed, {}]}, ("b",), {}))
        self.assertTrue(refused({"oneOf": [closed, closed]}, ("b",), {}))
        # not / if / then / else / dependentSchemas only add constraints: never a reason to call it refused
        self.assertFalse(refused({"type": "object", "not": {"required": ["b"]}}, ("b",), {}))
        # a schema the validator cannot read (an unknown type name, a bad pattern, a boolean subschema) is unknown
        self.assertFalse(refused({"type": "obj", "additionalProperties": False}, ("b",), {}))
        self.assertFalse(refused({"patternProperties": {"(": {}}, "additionalProperties": False}, ("b",), {}))
        self.assertFalse(refused({"properties": {"b": False}}, ("b",), {}))
        # arrays: past maxItems, items false after prefixItems, a non-array type
        self.assertTrue(refused({"type": "array", "maxItems": 2}, (2,), {}))
        self.assertTrue(refused({"type": "array", "prefixItems": [{}], "items": False}, (1,), {}))
        self.assertFalse(refused({"type": "array", "prefixItems": [{}], "items": False}, (0,), {}))
        self.assertTrue(refused({"type": "string"}, (0,), {}))
        self.assertTrue(refused({"type": "array", "items": {"type": "object", "additionalProperties": False}},
                                (1, "z"), {}))


class FixtureCoverageTests(unittest.TestCase):
    """p2_fixture_whole_path_cl3.py: a fixture refusal covers its own element and side, never the whole path."""

    def _factory(self, server_class=None):
        return lambda: support.points_server(server_class=server_class, labelled=True)[0]

    def test_a_tail_blind_endpoint_fails_from_a_base_derived_from_the_fixture(self):
        for transport, report, case in run_both(self._factory(blind("tail")), fixtures=ELEMENT0_FIXTURE):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("points[2].z", case["detail"])
                self.assertNotEqual(report["level_achieved"], "CL3")
        for transport, report, case in run_both(self._factory(), fixtures=ELEMENT0_FIXTURE):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn("derived from its out_of_envelope fixture", (case.get("evidence") or {}).get("note"))

    def test_without_a_derivable_base_a_refusal_covers_only_its_element_and_side(self):
        with mock.patch.object(_synth, "base_from_fixture", return_value=None):
            for transport, report, case in run_both(self._factory(blind("tail")), fixtures=ELEMENT0_FIXTURE):
                with self.subTest(transport=transport):
                    self.assertEqual(case["status"], "skip", case)
                    self.assertTrue(case["required"], case)
                    self.assertIn(f"{POINTS} points[2].z (max/min: no valid base input", case["detail"])
                    self.assertIn(f"{POINTS} points[0].z (min: no valid base input", case["detail"])
                    self.assertNotEqual(report["level_achieved"], "CL3")

    def test_the_plan_lists_every_element_and_side_without_a_base(self):
        binding = binding_of(support.points_server(labelled=True)[0], POINTS)
        plan = envelope_probe_plan(binding, None, base_error="label is a pattern-constrained string")
        self.assertEqual(plan.probes, [])
        self.assertEqual({(gap.path, gap.kind) for gap in plan.gaps},
                         {("points[0].z", "max"), ("points[0].z", "min"), ("points[2].z", "max"),
                          ("points[2].z", "min")})
        payload = ELEMENT0_FIXTURE["capabilities"][POINTS]["out_of_envelope"][0]
        self.assertEqual(_synth.fixture_sides(binding, payload, "points[0].z"), ["max"])
        self.assertEqual(_synth.fixture_sides(binding, payload, "points[2].z"), [])
        base = _synth.base_from_fixture(binding, [payload])
        self.assertEqual(base, {"points": [{"label": "P1", "z": 1.0}, {"label": "P2", "z": 1},
                                           {"label": "P3", "z": 1}]})
        self.assertTrue(binding.valid(base))


class NumericAllowedSetTests(unittest.TestCase):
    """Allowed [1, 3, 5] on an integer 0..10: probes above, below and between the members."""

    def test_the_plan_probes_both_sides_and_a_gap(self):
        binding = binding_of(support.step_arm()[0], support.STEP_CAPABILITY)
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual([(probe.kind, probe.value) for probe in plan.probes],
                         [("allowed", 6), ("allowed", 0), ("allowed", 2)])
        self.assertTrue(all(probe.in_schema for probe in plan.probes))

    def test_a_range_or_upper_side_enforcement_fails(self):
        for rule, accepted in (("step_range", "step=2"), ("step_upper", "step=0")):
            for transport, report, case in run_both(lambda rule=rule: support.step_arm(server_class=blind(rule))[0]):
                with self.subTest(endpoint=rule, transport=transport):
                    self.assertEqual(case["status"], "fail", case)
                    self.assertIn(accepted, case["detail"])
        for transport, report, case in run_both(lambda: support.step_arm()[0]):
            with self.subTest(endpoint="runtime", transport=transport):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"{support.STEP_CAPABILITY} step", case["detail"])

    def test_schema_invalid_candidates_are_dropped(self):
        leaf = {"type": "integer", "minimum": 1, "maximum": 5, "enum": [1, 2, 3, 4, 5]}
        self.assertEqual(_synth._allowed_numbers(leaf, [1, 3, 5], integer=True), [2])
        self.assertEqual(_synth._allowed_numbers({"type": "number", "multipleOf": 0.5}, [0.5, 1.5], integer=False),
                         [2.0, 0.0, 1.0])
        self.assertEqual(_synth._allowed_numbers({"type": "integer", "maximum": 5}, [5], integer=True), [4])
        self.assertEqual(_synth._allowed_numbers({"type": "integer", "minimum": 5, "maximum": 5}, [5], integer=True),
                         [6])  # nothing in the schema: the former single probe


class UnsentReadTests(unittest.TestCase):
    """OP-001 names the reads it could not send and asks for a fixture."""

    def test_an_unbuildable_read_is_named_in_the_note(self):
        report = run_suite_inprocess(lambda: support.named_read_heater()[0], profile="MHS-Sim", level="CL3")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "pass", case)
        note = (case.get("evidence") or {}).get("note") or ""
        self.assertIn(support.NAMED_READ_CAPABILITY, note)
        self.assertIn("supply a fixture", note)
        self.assertIn(support.EXT_READ_CAPABILITY, case["detail"])  # the buildable read is still sent

    def test_a_fixture_gets_the_read_sent(self):
        fixtures = {"capabilities": {support.NAMED_READ_CAPABILITY: {"valid": {"sensor": "S1"}}}}
        report = run_suite_inprocess(lambda: support.named_read_heater()[0], profile="MHS-Sim", level="CL3",
                                     fixtures=fixtures)
        case = entry(report, "OP-001")
        self.assertNotIn(support.NAMED_READ_CAPABILITY, (case.get("evidence") or {}).get("note") or "")


if __name__ == "__main__":
    unittest.main()
