"""Milestone 07b: SAFE-014 resolves limits like the runtime, OP-001 pins the revision rule.

Ported reviewer repros (each failed on suite 1.2.0, the 07a suite):

* ``fit-robots-ros/arm_probe.py`` / ``driver-authoring/arm_probe.py`` (DRV-02,
  FIT-ROS-01) and CONF-06: an endpoint that publishes array or nested limits
  but does not enforce them.  Where the schema repeats the bound the endpoint
  answers ``MHS.CAPABILITY.INPUT_INVALID``, which suite 1.2.0 counted as a
  pass; an endpoint that checks only the first array element passed because
  only element 0 was probed; class-default limits were never probed; the
  effective limits ``devices.get`` publishes (the operator overlay) were
  ignored.
* ``conformance-verify/v_readverb.py`` (TESTS-04): a read-verb command that
  advances the revision; plan 3.7: a write that changes nothing must not
  advance it either.
"""

from __future__ import annotations

import copy
import json
import unittest

from mhs.conformance import run_suite, validate_report
from mhs.conformance.inprocess import run_suite_inprocess
from mhs.conformance.report import finalize_report
from mhs.conformance.synth import bindings_for, envelope_probes, valid_input
from mhs.schema import SchemaStore

from tests.conformance import support
from tests.conformance.support import client_for, entry

_ORDER = ("CL0", "CL1", "CL2", "CL3", "CL4")


def at_most(level: str, ceiling: str) -> bool:
    return _ORDER.index(level) <= _ORDER.index(ceiling)


def blind(name: str) -> type:
    return support.blind_server_class(name)


OVERLAY_MAX = 50
OVERLAY = {"openmhs": "0.9", "devices": {support.HEATER_ID: {
    "cap.thermal.setpoint.v1": {"target_temperature": {"max": OVERLAY_MAX, "unit": "Cel", "reason": "glycol bath"}}}}}


class UnenforcedEnvelopeTests(unittest.TestCase):
    """SAFE-014 requires MHS.SAFETY.ENVELOPE_VIOLATION for every limited path (acceptance, 07b)."""

    def _run(self, factory, *, level="CL3", client=False):
        if client:
            report = run_suite(client_for(factory()), profile="MHS-Sim", level=level)
        else:
            report = run_suite_inprocess(factory, profile="MHS-Sim", level=level)
        return report, entry(report, "SAFE-014")

    def test_fake_arm_whose_array_envelope_is_unenforced_fails_safe014(self):
        """WPS WP-07 acceptance: the schema repeats the ±1 rad bound, the endpoint skips arrays."""

        for client in (False, True):
            with self.subTest(client=client):
                arms = []

                def factory():
                    server, arm = support.limited_arm(server_class=blind("arrays"))
                    arms.append(arm)
                    return server

                report, case = self._run(factory, client=client)
                self.assertEqual(case["status"], "fail", case)
                self.assertTrue(case["required"], case)
                self.assertIn("joint_positions", case["detail"])
                self.assertIn("MHS.CAPABILITY.INPUT_INVALID", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])

    def test_without_schema_bounds_the_unenforced_envelope_moves_the_arm_and_fails(self):
        arms = []

        def factory():
            server, arm = support.limited_arm(server_class=blind("arrays"), schema_bounds=False)
            arms.append(arm)
            return server

        report, case = self._run(factory)
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("completed", case["detail"])
        self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])

    def test_enforced_array_envelopes_pass_with_envelope_refusals(self):
        for per_joint in (False, True):
            with self.subTest(per_joint=per_joint):
                arms = []

                def factory(per_joint=per_joint):
                    server, arm = support.limited_arm(per_joint=per_joint, schema_bounds=not per_joint)
                    arms.append(arm)
                    return server

                report, case = self._run(factory)
                self.assertEqual(case["status"], "pass", case)
                self.assertEqual(case.get("mhs_code"), "MHS.SAFETY.ENVELOPE_VIOLATION", case)
                self.assertEqual(report["level_achieved"], "CL3", [t for t in report["tests"] if t["status"] != "pass"])
                lows = support.ARM_JOINT_MIN if per_joint else [-1.0] * 3
                highs = support.ARM_JOINT_MAX if per_joint else [1.0] * 3
                for arm in arms:
                    for _name, q in [call for call in arm.moves() if call[0] == "move_joints"]:
                        self.assertTrue(all(lo <= value <= hi for value, lo, hi in zip(q, lows, highs)), q)

    def test_every_array_element_is_probed(self):
        """An endpoint that checks only element 0 of a per-joint envelope fails."""

        report, case = self._run(lambda: support.limited_arm(per_joint=True, schema_bounds=False,
                                                             server_class=blind("tail"))[0])
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("joint_positions[2]", case["detail"])
        self.assertNotIn("joint_positions[0]", case["detail"])

    def test_nested_leaves_are_enforced_as_envelope_refusals(self):
        report, case = self._run(lambda: support.limited_arm(cartesian=True, server_class=blind("nested"))[0])
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("position.z", case["detail"])
        self.assertIn("MHS.CAPABILITY.INPUT_INVALID", case["detail"])
        report, case = self._run(lambda: support.limited_arm(cartesian=True)[0])
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("position.z", case["detail"])

    def test_class_default_limits_are_probed(self):
        """cap.thermal.setpoint.v1 carries class limits [-50, 300] Cel; the runtime enforces them (plan 3.5)."""

        report, case = self._run(lambda: support.heater_server(envelope=False)[0])
        self.assertEqual(case["status"], "pass", case)
        self.assertEqual(case.get("mhs_code"), "MHS.SAFETY.ENVELOPE_VIOLATION", case)
        self.assertIn("301", case["detail"])
        report, case = self._run(lambda: support.heater_server(envelope=False, server_class=blind("class"))[0])
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("target_temperature", case["detail"])

    def test_published_effective_limits_are_probed(self):
        """devices.get publishes the overlay-narrowed limit (max 50); the suite probes 51 like the runtime."""

        backends = []

        def factory(server_class=None):
            server, backend = support.heater_server(server_options={"site_limits": OVERLAY},
                                                    server_class=server_class)
            backends.append(backend)
            return server

        report, case = self._run(factory)
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(f"target_temperature={OVERLAY_MAX + 1}", case["detail"])
        self.assertFalse([call for backend in backends for call in backend.native_calls
                          if call[0] == "set_setpoint" and call[1] > OVERLAY_MAX])
        backends.clear()
        report, case = self._run(lambda: factory(blind("overlay")))
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(f"target_temperature={OVERLAY_MAX + 1}", case["detail"])
        self.assertIn("completed", case["detail"])

    def test_out_of_schema_probes_must_also_be_envelope_refusals(self):
        """Plan 3.5: limits are checked before the remaining schema bounds, so an INPUT_INVALID is not enough."""

        report, case = self._run(lambda: support.limited_arm(server_class=blind("arrays"))[0])
        self.assertIn("ENVELOPE_VIOLATION", case["detail"])  # names what was expected


class LimitResolutionTests(unittest.TestCase):
    """The suite's effective limits are the runtime's (``mhs._server.limits_plan.compile_binding``)."""

    def test_bindings_resolve_like_the_server_plan(self):
        from mhs._server import limits_plan

        for factory in (lambda: support.limited_arm(cartesian=True)[0], lambda: support.heater_server()[0],
                        lambda: support.heater_server(envelope=False)[0]):
            server = factory()
            client = client_for(server)
            for manifest in client.devices():
                device = server.devices[manifest["device_id"]]
                for binding in bindings_for(manifest):
                    capability = device.binding(binding.capability_id, binding.resource)
                    plan = limits_plan.compile_binding(device, capability, overlay=None, key="test")
                    with self.subTest(capability=binding.capability_id):
                        expected = {path: (rule.min, rule.max) for path, rule in plan.limits.rules.items()
                                    if rule.has_bound}
                        got = {bound.path for bound in binding.bounds}
                        self.assertEqual(got, set(expected), binding.capability_id)

    def test_probes_cover_the_last_array_element_and_respect_multiple_of(self):
        server, _arm = support.limited_arm(per_joint=True, schema_bounds=False)
        manifest = client_for(server).devices()[0]
        binding = [item for item in bindings_for(manifest) if item.capability_id == "cap.motion.joint_position.v1"][0]
        probes = envelope_probes(binding, valid_input(binding)[0])
        paths = {probe.path for probe in probes}
        self.assertIn("joint_positions[0]", paths)
        self.assertIn("joint_positions[2]", paths)
        for probe in probes:
            self.assertEqual(len(probe.payload["joint_positions"]), 3, probe)
        manifest = copy.deepcopy(manifest)
        capability = [item for item in manifest["capabilities"]
                      if item["capability_id"] == "cap.motion.joint_position.v1"][0]
        capability["input_schema"]["properties"]["joint_positions"]["items"]["multipleOf"] = 0.25
        binding = [item for item in bindings_for(manifest) if item.capability_id == "cap.motion.joint_position.v1"][0]
        for probe in envelope_probes(binding, valid_input(binding)[0]):
            self.assertAlmostEqual(probe.value / 0.25, round(probe.value / 0.25), msg=probe)
            self.assertTrue(probe.in_schema, probe)

    def test_published_limits_narrow_the_synthesized_inputs(self):
        server, _backend = support.heater_server(server_options={"site_limits": OVERLAY})
        client = client_for(server)
        manifest = client.devices()[0]
        published = client.inspect(manifest["device_id"])
        binding = [item for item in bindings_for(manifest, published=published)
                   if item.capability_id == "cap.thermal.setpoint.v1"][0]
        self.assertIn(OVERLAY_MAX + 1, [probe.value for probe in envelope_probes(binding, valid_input(binding)[0])])
        payload = valid_input(binding)[0]
        self.assertLessEqual(payload["target_temperature"], OVERLAY_MAX)


class RevisionRuleTests(unittest.TestCase):
    """OP-001: reads never advance the revision; other commands advance it only on a state change (plan 3.7)."""

    def test_a_read_that_advances_the_revision_fails_op001(self):
        """TESTS-04 / v_readverb.py: cap.measure.temperature.v1 advanced the revision."""

        report = run_suite_inprocess(lambda: support.heater_server(server_class=support.ReadBumpServer)[0],
                                     profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("cap.measure.temperature.v1", case["detail"])
        self.assertIn("read", case["detail"])
        self.assertEqual(report["level_achieved"], "CL1")

    def test_reads_keep_the_revision_on_the_runtime(self):
        report = run_suite_inprocess(lambda: support.heater_server()[0], profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("cap.measure.temperature.v1", case["detail"])

    def test_a_no_op_write_that_advances_the_revision_fails_op001(self):
        report = run_suite_inprocess(
            lambda: support.heater_server(server_class=support.NoopBumpServer,
                                          bridge_class=support.NoopWriteHeaterBridge)[0],
            profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("no resource state changed", case["detail"])
        report = run_suite_inprocess(lambda: support.heater_server(bridge_class=support.NoopWriteHeaterBridge)[0],
                                     profile="MHS-Sim", level="CL2")
        self.assertEqual(entry(report, "OP-001")["status"], "pass", entry(report, "OP-001"))

    def test_read_only_simulated_device_runs_the_read_check(self):
        server, _bridge = support.class_faithful_server("cap.measure.temperature.v1")
        report = run_suite(client_for(server), profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertTrue(case["required"], case)
        self.assertIn("cap.measure.temperature.v1", case["detail"])


class ReportStrictnessTests(unittest.TestCase):
    """The last suite 1.1.0 reports are regenerated, so no report is validated leniently any more."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_suite_inprocess(lambda: support.heater_server()[0], profile="MHS-Sim", level="CL3")

    def test_schema_requires_disclaimers(self):
        report = copy.deepcopy(self.report)
        report.pop("disclaimers")
        errors = SchemaStore().validate(finalize_report(report), "conformance-report.schema.json")
        self.assertTrue(any("disclaimers" in str(item) for item in errors), errors)

    def test_downgraded_report_is_invalid_offline(self):
        """verify-WP-07/07a/r3/forge/forge.py (d): a suite 1.1.0 / report 1.0.0 disguise of a strict report."""

        from mhs.conformance.report import SUITE_1_1_TEST_IDS, recompute_level

        for keep_disclaimers in (False, True):
            with self.subTest(keep_disclaimers=keep_disclaimers):
                forged = copy.deepcopy(self.report)
                forged["suite_version"], forged["report_version"] = "1.1.0", "1.0.0"
                forged["tests"] = [{key: value for key, value in case.items() if key not in ("required", "spec_ref")}
                                   for case in forged["tests"]
                                   if case["id"] in SUITE_1_1_TEST_IDS and case["status"] == "pass"]
                if not keep_disclaimers:
                    forged.pop("disclaimers", None)
                forged["subject"].pop("manifest_digest", None)
                forged["level_achieved"] = recompute_level(forged)
                self.assertTrue(validate_report(finalize_report(forged)))


if __name__ == "__main__":
    unittest.main()
