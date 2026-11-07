"""Milestone 07b verification fix: SAFE-014 probes every limited binding and path, OP-001 every read.

Ported verifier repros (``verify-WP-07/07b/adv``, read-only originals); each
passed the suite as first delivered in 07b:

* ``a_permit.py`` / ``a_permit_direct.py``: a permit-gated joint binding
  whose array envelope is not enforced passed SAFE-014 at CL3, because
  permit-gated bindings were never probed.  Plan 3.6 checks limits (step 8)
  before permits (step 10), so an out-of-limit command sent without a permit
  is refused with ``MHS.SAFETY.ENVELOPE_VIOLATION`` by a correct endpoint; a
  ``PERMIT_*`` refusal means the limit check is missing or comes too late.
* ``b_laser.py``: ``cap.optics.set_power.v1`` (a class that requires a
  permit) with an unenforced 50 mW envelope passed SAFE-014.  Conversely an
  endpoint whose only limited binding was permit-gated skipped SAFE-014 and
  was capped below CL3 although it enforced its limits.
* ``e_middle.py``: only the first and the last element of a per-element
  (vector) bound were probed, so an endpoint blind at index 1 passed.
* ``f_trunc.py``: the 32-probe budget ran out before the last limited paths
  were probed; they were reported as paths "with no out-of-limit value the
  suite could build" and SAFE-014 passed.  (Round 2, ``j_tail_budget.py``:
  that cut is gone; see ``test_safe014_completeness``.)
* ``g_readbump.py``: OP-001 checked a single read command, so a
  ``cap.world.state.v1`` that advances the revision (TESTS-04) went unnoticed
  next to another read.

Plus: a refusal that drives ``Bridge.safe_state`` (the harness did not record
it), a limited ``safe_state.achieved_by`` action (exempt from the latch, not
from limits) and ``--reference arm --seed N`` without ``--noise``.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from mhs.conformance import run_suite, synth
from mhs.conformance.__main__ import main as conformance_main
from mhs.conformance.inprocess import INSTRUMENTED, run_suite_inprocess
from mhs.conformance.synth import bindings_for, envelope_probes, valid_input
from mhs.conformance.tests_core import _ACTUATING_METHODS

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


class _Runs(unittest.TestCase):
    def run_both(self, factory, *, level="CL3"):
        """``[(transport, report, SAFE-014 entry)]`` in-process (harness) and over a plain client."""

        out = []
        for client in (False, True):
            if client:
                report = run_suite(client_for(factory()), profile="MHS-Sim", level=level)
            else:
                report = run_suite_inprocess(factory, profile="MHS-Sim", level=level)
            out.append(("client" if client else "inprocess", report, entry(report, "SAFE-014")))
        return out


class PermitGatedLimitTests(_Runs):
    """a_permit.py / b_laser.py: limits are checked before permits, so permit-gated bindings are probed."""

    def test_unenforced_permit_gated_array_envelope_fails_safe014(self):
        for transport, report, case in self.run_both(lambda: support.limited_arm(
                server_class=blind("arrays"), cartesian=True, schema_bounds=False, permit_joint=True)[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertTrue(case["required"], case)
                self.assertIn("joint_positions", case["detail"])
                self.assertIn("MHS.SAFETY.PERMIT_INVALID", case["detail"])
                self.assertIn("before permits", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])

    def test_the_runtime_refuses_permit_gated_probes_on_their_limits(self):
        arms = []

        def factory():
            server, arm = support.limited_arm(cartesian=True, schema_bounds=False, permit_joint=True)
            arms.append(arm)
            return server

        for transport, report, case in self.run_both(factory):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "pass", case)
                self.assertEqual(case.get("mhs_code"), "MHS.SAFETY.ENVELOPE_VIOLATION", case)
                self.assertIn("cap.motion.joint_position.v1 joint_positions", case["detail"])
                self.assertIn("cap.motion.cartesian_pose.v1 position.z", case["detail"])
                self.assertEqual(report["level_achieved"], "CL3", _failing(report))
        for arm in arms:
            for _name, q in [call for call in arm.moves() if call[0] == "move_joints"]:
                self.assertTrue(all(-1.0 <= value <= 1.0 for value in q), q)

    def test_unenforced_laser_power_limit_fails_safe014(self):
        """cap.optics.set_power.v1 requires a permit by class; compatibility mode runs it without one."""

        for permit_binding in (False, True):
            bridges = []

            def factory(permit_binding=permit_binding):
                server, bridge = support.laser_server(server_class=blind("power"), permit_binding=permit_binding)
                bridges.append(bridge)
                return server

            for transport, report, case in self.run_both(factory):
                with self.subTest(permit_binding=permit_binding, transport=transport):
                    self.assertEqual(case["status"], "fail", case)
                    self.assertIn(f"power={support.LASER_MAX_MW + 1}", case["detail"])
                    self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])

    def test_enforced_laser_power_limit_passes(self):
        bridges = []

        def factory():
            server, bridge = support.laser_server()
            bridges.append(bridge)
            return server

        for transport, report, case in self.run_both(factory):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn("cap.optics.set_power.v1 power", case["detail"])
                self.assertIn("cap.thermal.setpoint.v1 target_temperature", case["detail"])
        self.assertFalse([args for bridge in bridges for capability_id, args in bridge.native_calls
                          if capability_id == "cap.optics.set_power.v1"
                          and args.get("power", 0) > support.LASER_MAX_MW])

    def test_permit_only_endpoint_that_enforces_reaches_cl3(self):
        """Its only limited binding is permit-gated: SAFE-014 used to skip, and the required skip capped CL2."""

        for transport, report, case in self.run_both(
                lambda: support.limited_arm(schema_bounds=False, permit_joint=True)[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn("joint_positions", case["detail"])
                self.assertEqual(report["level_achieved"], "CL3", _failing(report))
        for transport, report, case in self.run_both(
                lambda: support.limited_arm(schema_bounds=False, permit_joint=True,
                                            server_class=blind("arrays"))[0]):
            with self.subTest(transport=transport, blind=True):
                self.assertEqual(case["status"], "fail", case)


class SafeStateActionLimitTests(_Runs):
    """A safe_state.achieved_by action is exempt from the latch (plan 3.6 step 5), not from its limits."""

    def test_unenforced_limits_of_a_safe_state_action_fail_safe014(self):
        achieved_by = ("cap.motion.joint_position.v1", "cap.motion.stop.v1")
        for transport, report, case in self.run_both(lambda: support.limited_arm(
                schema_bounds=False, achieved_by=achieved_by, server_class=blind("arrays"))[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("joint_positions", case["detail"])
        for transport, report, case in self.run_both(lambda: support.limited_arm(
                schema_bounds=False, achieved_by=achieved_by)[0]):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn("joint_positions", case["detail"])


class ElementCoverageTests(_Runs):
    """e_middle.py: a per-element (vector) bound has its own value at every index; each index is probed."""

    def test_endpoint_blind_at_a_middle_element_fails(self):
        for transport, report, case in self.run_both(lambda: support.limited_arm(
                per_joint=True, schema_bounds=False, server_class=blind("middle"))[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn("joint_positions[1]", case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])

    def test_vector_bounds_probe_every_index_scalar_bounds_first_and_last(self):
        for per_joint, expected in ((True, {0, 1, 2}), (False, {0, 2})):
            with self.subTest(per_joint=per_joint):
                server, _arm = support.limited_arm(per_joint=per_joint, schema_bounds=False)
                manifest = client_for(server).devices()[0]
                binding = [item for item in bindings_for(manifest)
                           if item.capability_id == "cap.motion.joint_position.v1"][0]
                probes = envelope_probes(binding, valid_input(binding)[0])
                indices = {int(probe.path.rsplit("[", 1)[1].rstrip("]")) for probe in probes}
                self.assertEqual(indices, expected, [probe.path for probe in probes])
                if per_joint:
                    for probe in probes:
                        index = int(probe.path.rsplit("[", 1)[1].rstrip("]"))
                        bound = (support.ARM_JOINT_MAX if probe.kind == "max" else support.ARM_JOINT_MIN)[index]
                        self.assertEqual(probe.bound, bound, probe)


class ProbeBudgetTests(_Runs):
    """f_trunc.py: the probe budget is spent breadth-first, and an unprobed path never passes silently."""

    def test_every_limited_path_is_probed_first_and_every_probe_is_sent(self):
        """Round 2 (j_tail_budget.py): the 32-probe cut is gone; every probe of every element is mandatory."""

        server, _bridge = support.many_axes_server()
        binding = bindings_for(client_for(server).devices()[0])[0]
        probes = envelope_probes(binding, valid_input(binding)[0])
        self.assertEqual({(probe.limit_path, probe.kind) for probe in probes},
                         {(name, kind) for name in support.MANY_AXES_FIELDS for kind in ("min", "max")})
        # breadth-first: one probe of every limited path before the other side of any bound
        self.assertEqual({probe.limit_path for probe in probes[:support.MANY_AXES]}, set(support.MANY_AXES_FIELDS))
        many = [f"a{index:02d}" for index in range(40)]
        server, _bridge = support.many_axes_server(fields=many)
        binding = bindings_for(client_for(server).devices()[0])[0]
        probes = envelope_probes(binding, valid_input(binding)[0])
        self.assertEqual({probe.limit_path for probe in probes}, set(many))
        self.assertEqual(len(probes), 2 * len(many))

    def test_endpoint_blind_at_the_last_axis_fails(self):
        for transport, report, case in self.run_both(
                lambda: support.many_axes_server(server_class=blind("last_axis"))[0]):
            with self.subTest(transport=transport):
                self.assertEqual(case["status"], "fail", case)
                self.assertIn(support.MANY_AXES_FIELDS[-1], case["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        for transport, report, case in self.run_both(lambda: support.many_axes_server()[0]):
            with self.subTest(transport=transport, runtime=True):
                self.assertEqual(case["status"], "pass", case)
                self.assertIn(f"covering {support.MANY_AXES} limited path(s)", case["detail"])

    def test_paths_beyond_the_hard_budget_skip_with_a_truthful_reason(self):
        with mock.patch.object(synth, "_MAX_PATH_PROBES", 8):
            report = run_suite_inprocess(lambda: support.many_axes_server()[0], profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "skip", case)
        self.assertIn("budget", case["detail"])
        self.assertIn(f"{support.MANY_AXES - 8} limited path(s)", case["detail"])
        self.assertIn(support.MANY_AXES_FIELDS[-1], case["detail"])
        self.assertNotIn("no out-of-limit value", case["detail"])
        self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        with mock.patch.object(synth, "_MAX_PATH_PROBES", 8):
            report = run_suite_inprocess(lambda: support.many_axes_server(server_class=blind("last_axis"))[0],
                                         profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(report, "SAFE-014")["status"], "skip")  # f19 unprobed: unknown, never a pass
        with mock.patch.object(synth, "_MAX_PATH_PROBES", 8):
            report = run_suite_inprocess(lambda: support.many_axes_server(server_class=blind("first_axis"))[0],
                                         profile="MHS-Sim", level="CL3")
        # a violation the probes found is a failure, whatever the budget left unprobed
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn(support.MANY_AXES_FIELDS[0], case["detail"])


class RefusalBridgeCallTests(unittest.TestCase):
    """A refusal must not reach the device: Bridge.safe_state is recorded like every actuating method."""

    def test_safe_state_is_instrumented_and_counts_as_actuating(self):
        self.assertIn("safe_state", INSTRUMENTED)
        self.assertIn("safe_state", _ACTUATING_METHODS)

    def test_refusal_that_drives_safe_state_fails_safe014(self):
        report = run_suite_inprocess(lambda: support.limited_arm(
            schema_bounds=False, server_class=support.SafeStateOnRefusalServer)[0], profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("safe_state", case["detail"])


class ReadRevisionCoverageTests(unittest.TestCase):
    """g_readbump.py: every catalogued read binding is held to the read revision rule."""

    def test_world_state_that_advances_the_revision_fails_op001(self):
        report = run_suite_inprocess(lambda: support.world_state_heater(server_class=support.WorldStateBumpServer)[0],
                                     profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("cap.world.state.v1", case["detail"])
        self.assertEqual(report["level_achieved"], "CL1")

    def test_runtime_keeps_the_revision_for_every_read(self):
        report = run_suite_inprocess(lambda: support.world_state_heater()[0], profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("cap.measure.temperature.v1", case["detail"])
        self.assertIn("cap.world.state.v1", case["detail"])

    def test_read_only_endpoint_checks_every_read(self):
        def factory():
            server, _backend = support.world_state_heater(server_class=support.WorldStateBumpServer)
            device = server.devices[support.HEATER_ID]
            device.capabilities[:] = [item for item in device.capabilities
                                      if item.capability_id != "cap.thermal.setpoint.v1"]
            device.safety.envelope = {}
            return server

        report = run_suite_inprocess(factory, profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("cap.world.state.v1", case["detail"])


class CliSeedTests(unittest.TestCase):
    @staticmethod
    def run_cli(*argv: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return conformance_main(list(argv))
            except SystemExit as exc:
                return int(exc.code or 0)

    def test_seed_without_noise_is_a_usage_error(self):
        self.assertEqual(self.run_cli("--reference", "arm", "--seed", "3", "--level", "CL1"), 2)
        self.assertEqual(self.run_cli("--reference", "conveyor", "--seed", "0", "--level", "CL1"), 2)


if __name__ == "__main__":
    unittest.main()
