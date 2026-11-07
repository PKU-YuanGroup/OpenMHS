"""Milestone 07b verification fix round 2: SAFE-014 never passes with a limited path unprobed; OP-001 reads.

Ported verifier repros (``verify-WP-07/07b/r2/adv``, read-only originals);
each passed the suite of the first 07b fix round:

* ``h_unsynth.py``: a limited extension whose required ``tool_id`` is a
  pattern-constrained string has no synthesizable base input.  The binding
  was skipped with an evidence note, so an endpoint that accepted
  ``speed=50`` against an envelope max of 10 passed SAFE-014 at CL3.
* ``i_allowed_pattern.py``: an allowed set on a pattern-constrained string;
  the suite built no out-of-limit value, noted it and passed SAFE-014 while
  the endpoint accepted ``gear=high``.
* ``j_tail_budget.py``: 20 limited axes plus a scalar-bounded 3-element
  array; the 32-probe cut dropped the array tail, so an endpoint that checks
  only ``arr[0]`` passed.
* ``m_wildcard_tail.py``: an envelope on ``points[*].z`` was probed at
  ``points[0].z`` only, so an endpoint that checks the first element passed.
* ``k_ext_read.py``: an extension binding declared ``verb: read`` (the
  runtime treats it as a read) advanced the revision, and OP-001 never sent it.
"""

from __future__ import annotations

import unittest

from mhs.conformance import run_suite
from mhs.conformance.inprocess import run_suite_inprocess
from mhs.conformance import synth as _synth
from mhs.conformance.synth import bindings_for, envelope_probe_plan, envelope_probes, valid_input

from tests.conformance import support
from tests.conformance.support import client_for, entry

_ORDER = ("CL0", "CL1", "CL2", "CL3", "CL4")


def at_most(level: str, ceiling: str) -> bool:
    return _ORDER.index(level) <= _ORDER.index(ceiling)


def blind(name: str) -> type:
    return support.blind_server_class(name)


def _failing(report):
    return [(item["id"], item["status"], (item.get("detail") or "")[:200]) for item in report["tests"]
            if item.get("required") and item["status"] != "pass"]


def _binding(server, capability_id):
    manifest = client_for(server).devices()[0]
    return [item for item in bindings_for(manifest) if item.capability_id == capability_id][0]


class _Runs(unittest.TestCase):
    def run_both(self, factory, *, level="CL3", **options):
        """``[(transport, report, SAFE-014 entry)]`` in-process (harness) and over a plain client."""

        out = []
        for client in (False, True):
            if client:
                report = run_suite(client_for(factory()), profile="MHS-Sim", level=level, **options)
            else:
                report = run_suite_inprocess(factory, profile="MHS-Sim", level=level, **options)
            out.append(("client" if client else "inprocess", report, entry(report, "SAFE-014")))
        return out


class UnsynthesizableBindingTests(_Runs):
    """h_unsynth.py: a limited binding without a base input is unprobed, so SAFE-014 cannot pass."""

    TOOL = support.TOOL_CAPABILITY

    def test_blind_binding_without_a_base_input_never_passes(self):
        natives = []

        def factory():
            server, native = support.tool_arm(server_class=blind("speed"))
            natives.append(native)
            return server

        for transport, report, case in self.run_both(factory):
            with self.subTest(transport=transport):
                self.assertNotEqual(case["status"], "pass", case)
                self.assertEqual(case["status"], "skip", case)
                self.assertTrue(case["required"], case)
                self.assertIn(f"{self.TOOL} speed", case["detail"])
                self.assertIn("supply a fixture", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        # nothing out of limit reached the tool: the suite sent it nothing
        self.assertFalse([call for native in natives for call in native.native_calls if call[0] == self.TOOL])

    def test_runtime_without_a_fixture_skips_with_the_reason(self):
        for transport, report, case in self.run_both(lambda: support.tool_arm()[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "skip", case)
                self.assertIn("no valid base input", case["detail"])
                self.assertIn("tool_id", case["detail"])
                self.assertIn("valid / out_of_envelope", case["detail"])
                # the probes that could be built were sent and refused
                self.assertIn("joint_positions", case["detail"])
                self.assertEqual(report["level_achieved"], "CL2", _failing(report))

    def test_a_valid_fixture_makes_the_binding_probed(self):
        fixtures = {"capabilities": {self.TOOL: {"valid": {"tool_id": "T001", "speed": 1}}}}
        for transport, report, case in self.run_both(lambda: support.tool_arm(server_class=blind("speed"))[0],
                                                     fixtures=fixtures):
            with self.subTest(transport=transport, blind=True):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn(f"speed={float(support.TOOL_MAX_SPEED + 1)!r}", case["detail"])
        for transport, report, case in self.run_both(lambda: support.tool_arm()[0], fixtures=fixtures):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"{self.TOOL} speed", case["detail"])
                self.assertEqual(report["level_achieved"], "CL3", _failing(report))

    def test_an_out_of_envelope_fixture_covers_the_paths_its_refusal_names(self):
        fixtures = {"capabilities": {self.TOOL: {"out_of_envelope": [{"tool_id": "T001", "speed": 50}]}}}
        for transport, report, case in self.run_both(lambda: support.tool_arm()[0], fixtures=fixtures):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"{self.TOOL} speed", case["detail"])
                self.assertEqual(report["level_achieved"], "CL3", _failing(report))
        for transport, report, case in self.run_both(lambda: support.tool_arm(server_class=blind("speed"))[0],
                                                     fixtures=fixtures):
            with self.subTest(transport=transport, blind=True):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("fixture", case["detail"])


class AllowedPatternTests(_Runs):
    """i_allowed_pattern.py: an allowed set on a pattern string is probed with a value the pattern accepts."""

    GEAR = support.GEAR_CAPABILITY

    def test_not_allowed_value_matching_the_pattern_is_probed(self):
        server, _native = support.tool_arm(tool=False, gear_pattern="^[a-z]+$")
        binding = _binding(server, self.GEAR)
        probes = [probe for probe in envelope_probes(binding, valid_input(binding)[0]) if probe.path == "gear"]
        self.assertEqual([probe.kind for probe in probes], ["allowed"], probes)
        value = probes[0].value
        self.assertNotIn(value, support.GEAR_ALLOWED)
        self.assertRegex(value, "^[a-z]+$")
        self.assertTrue(probes[0].in_schema, probes[0])

    def test_endpoint_ignoring_the_allowed_set_fails(self):
        for transport, report, case in self.run_both(
                lambda: support.tool_arm(tool=False, gear_pattern="^[a-z]+$", server_class=blind("gear"))[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn(f"{self.GEAR} gear=", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        for transport, report, case in self.run_both(
                lambda: support.tool_arm(tool=False, gear_pattern="^[a-z]+$")[0]):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"{self.GEAR} gear", case["detail"])
                self.assertEqual(report["level_achieved"], "CL3", _failing(report))

    def test_no_buildable_value_skips_never_passes(self):
        """The pattern admits only the allowed values: no in-schema out-of-limit value exists to send."""

        for name in ("gear", None):
            for transport, report, case in self.run_both(lambda name=name: support.tool_arm(
                    tool=False, gear_pattern="^(low|mid)$",
                    server_class=blind(name) if name else None)[0]):
                with self.subTest(transport=transport, blind=name):
                    self.assertEqual(case["status"], "skip", case)
                    self.assertIn(f"{self.GEAR} gear", case["detail"])
                    self.assertIn("out_of_envelope", case["detail"])
                    self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])


class ArrayTailTests(_Runs):
    """j_tail_budget.py / m_wildcard_tail.py: array tails are mandatory probes, also under a wildcard."""

    def test_every_probe_of_every_path_is_sent(self):
        server, _bridge = support.many_axes_server(array=True)
        binding = _binding(server, "x-cap.example.multi_axis.v1")
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.unprobed, [])
        sent = {(probe.path, probe.kind) for probe in plan.probes}
        expected = {(name, kind) for name in support.MANY_AXES_FIELDS for kind in ("min", "max")}
        expected |= {(f"arr[{index}]", kind) for index in (0, 2) for kind in ("min", "max")}
        self.assertEqual(sent, expected)

    def test_endpoint_blind_at_the_array_tail_fails_among_many_axes(self):
        for transport, report, case in self.run_both(
                lambda: support.many_axes_server(server_class=blind("tail"), array=True)[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("arr[2]", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        for transport, report, case in self.run_both(lambda: support.many_axes_server(array=True)[0]):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"covering {support.MANY_AXES + 1} limited path(s)", case["detail"])

    def test_wildcard_paths_probe_the_first_and_the_last_element(self):
        for length, last in ((3, 2), (None, 1)):
            with self.subTest(length=length):
                server, _bridge = support.points_server(length=length)
                binding = _binding(server, "x-cap.example.path.v1")
                probes = envelope_probes(binding, valid_input(binding)[0])
                sent = {(probe.path, probe.kind) for probe in probes}
                self.assertEqual(sent, {(f"points[{index}].z", kind) for index in (0, last)
                                        for kind in ("min", "max")})
                for probe in probes:
                    self.assertEqual(probe.limit_path, "points[*].z")
                    self.assertTrue(probe.in_schema, probe)

    def test_tail_of_an_array_whose_elements_only_a_fixture_can_build(self):
        """The array is grown with a copy of the fixture's element (its pattern string is never invented)."""

        fixtures = {"capabilities": {"x-cap.example.path.v1": {"valid": {"points": [{"label": "P1", "z": 1}]}}}}
        server, _bridge = support.points_server(length=None, labelled=True)
        binding = _binding(server, "x-cap.example.path.v1")
        from mhs.conformance.synth import load_fixtures

        probes = envelope_probes(binding, valid_input(binding, load_fixtures(fixtures))[0])
        self.assertEqual({probe.path for probe in probes}, {"points[0].z", "points[1].z"})
        for probe in probes:
            if probe.path == "points[1].z":
                self.assertEqual([point["label"] for point in probe.payload["points"]], ["P1", "P1"])
        for transport, report, case in self.run_both(
                lambda: support.points_server(server_class=blind("tail"), length=None, labelled=True)[0],
                fixtures=fixtures):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("points[1].z", case["detail"])
        for transport, report, case in self.run_both(
                lambda: support.points_server(length=None, labelled=True)[0]):
            with self.subTest(transport=transport, fixture=False):
                self.assertEqual(case["status"], "skip", case)
                # RESIDUAL-B: every element and side without a base is named (not the whole path)
                self.assertIn("points[0].z (max/min: no valid base input", case["detail"])
                self.assertIn("points[1].z (max/min: no valid base input", case["detail"])

    def test_an_unbuildable_element_is_never_covered_by_another_element(self):
        """points[0].z is probed and refused, points[1].z cannot be built: the run skips, it never passes."""

        one = {"capabilities": {"x-cap.example.path.v1": {"valid": {"points": [{"label": "P1", "z": 1}]}}}}
        two = {"capabilities": {"x-cap.example.path.v1": {"valid": {
            "points": [{"label": "P1", "z": 1}, {"label": "P2", "z": 1}]}}}}
        factory = lambda: support.points_server(length=None, labelled=True, unique=True)[0]  # noqa: E731
        for transport, report, case in self.run_both(factory, fixtures=one):
            with self.subTest(transport=transport, fixture="one"):
                self.assertEqual(case["status"], "skip", case)
                self.assertIn("2 out-of-limit probe(s) refused", case["detail"])  # points[0].z, both sides
                self.assertIn("x-cap.example.path.v1 points[1].z (max/min: its container cannot be synthesized",
                              case["detail"])
        for transport, report, case in self.run_both(factory, fixtures=two):
            with self.subTest(transport=transport, fixture="two"):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn("points[1].z", case["detail"])

    def test_endpoint_blind_after_the_first_element_of_a_wildcard_path_fails(self):
        for length, last in ((3, 2), (None, 1)):
            for transport, report, case in self.run_both(
                    lambda length=length: support.points_server(server_class=blind("tail"), length=length)[0]):
                with self.subTest(length=length, transport=transport):
                    self.assertEqual(case["status"], "fail", case)
                    self.assertIn(f"points[{last}].z", case["detail"])
            for transport, report, case in self.run_both(
                    lambda length=length: support.points_server(length=length)[0]):
                with self.subTest(length=length, transport=transport, runtime=True):
                    self.assertEqual(case["status"], "pass", case)
                    self.assertIn("points[*].z", case["detail"])


class ApplicabilityTests(unittest.TestCase):
    """Only a class-default limit on a field the binding's schema rejects is not applicable.

    RESIDUAL-B (07b r3 blocker): "undeclared" used to mean "not in the
    top-level ``properties``"; a field the binding admits (the lab's bindings
    allow extra properties) or declares in a branch is now probed.  The
    remaining cases are in ``test_safe014_reach.AdmittedFieldTests``.
    """

    def test_class_default_limit_on_an_admitted_field_is_probed(self):
        from mhs.conformance.inprocess import reference_factory

        server, close = reference_factory("lab")()
        try:
            manifests = client_for(server).devices()
        finally:
            close()
        plans = {}
        for manifest in manifests:
            for binding in bindings_for(manifest):
                if binding.verb in ("write", "invoke") and binding.bounds:
                    plans[binding.capability_id] = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plans["cap.fluid.aspirate.v1"].not_applicable, [])
        self.assertEqual(plans["cap.fluid.aspirate.v1"].gaps, [])
        self.assertTrue({"volume_ul", "volume"} <= {probe.limit_path for probe in plans["cap.fluid.aspirate.v1"].probes})

    def test_a_declared_limit_on_a_rejected_field_is_a_gap(self):
        """The runtime refuses such a device; an endpoint that publishes it anyway cannot pass SAFE-014."""

        manifest = {
            "device_id": "mhs://localhost/test/tool", "mode": "simulated",
            "resources": [{"resource_id": "arm", "kind": "robot.arm"}],
            "capabilities": [{"capability_id": support.TOOL_CAPABILITY, "resource": "arm",
                              "input_schema": {"type": "object", "required": ["a"], "additionalProperties": False,
                                               "properties": {"a": {"type": "number"}}}}],
            "safety": {"risk_class": "R2", "envelope": {support.TOOL_CAPABILITY: {
                "speed": {"min": 0, "max": support.TOOL_MAX_SPEED, "unit": "mm/s", "reason": "tool"}}}},
        }
        binding = bindings_for(manifest)[0]
        plan = envelope_probe_plan(binding, valid_input(binding)[0])
        self.assertEqual(plan.not_applicable, [])
        self.assertEqual({(gap.limit_path, gap.reason) for gap in plan.gaps},
                         {("speed", _synth._REFUSED)})


class ExtensionReadRevisionTests(unittest.TestCase):
    """k_ext_read.py: extension bindings that declare the read verb are held to the read revision rule."""

    def test_extension_read_that_advances_the_revision_fails_op001(self):
        report = run_suite_inprocess(lambda: support.ext_read_heater(server_class=support.ExtReadBumpServer)[0],
                                     profile="MHS-Sim", level="CL3")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(support.EXT_READ_CAPABILITY, case["detail"])
        self.assertEqual(report["level_achieved"], "CL1")

    def test_runtime_keeps_the_revision_for_extension_reads(self):
        report = run_suite_inprocess(lambda: support.ext_read_heater()[0], profile="MHS-Sim", level="CL3")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(support.EXT_READ_CAPABILITY, case["detail"])
        self.assertIn("cap.measure.temperature.v1", case["detail"])

    def test_extension_reads_are_not_sent_to_hardware_without_opt_in(self):
        """An extension's verb is the driver's own claim: CON-031 does not trust it on hardware."""

        backends = []

        def factory(read_only=False):
            options = {"heater_off": False, "achieved_by": []} if read_only else {}
            server, backend = support.ext_read_heater(hardware=True, **options)
            if read_only:  # no write/invoke binding: OP-001 runs its read check alone
                device = server.devices[support.HEATER_ID]
                device.capabilities[:] = [item for item in device.capabilities
                                          if item.capability_id != "cap.thermal.setpoint.v1"]
                device.safety.envelope = {}
            backends.append(backend)
            return server

        for read_only in (False, True):
            with self.subTest(read_only=read_only):
                run_suite_inprocess(lambda: factory(read_only), profile="MHS-Device", level="CL3")
                run_suite(client_for(factory(read_only)), profile="MHS-Device", level="CL3")
                self.assertFalse([call for backend in backends for call in backend.native_calls
                                  if call[0] == "probe_temp"])
                self.assertFalse([call for backend in backends for call in backend.actuations()])
        # with the operator's opt-in the extension read is held to the rule like any other read
        report = run_suite_inprocess(lambda: factory(True), profile="MHS-Device", level="CL3", allow_actuation=True)
        self.assertIn(support.EXT_READ_CAPABILITY, entry(report, "OP-001")["detail"])


if __name__ == "__main__":
    unittest.main()
