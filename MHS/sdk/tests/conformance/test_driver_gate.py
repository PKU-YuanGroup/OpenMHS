"""The suite tests the driver, not the SDK (DRV-08, CONF-01/02/05/06/08, TESTS-03, FIT-13).

Each class ports one reviewer repro (see ``support``) and pins the honest
outcome: a do-nothing driver cannot reach CL2, a correct one reaches the same
level whatever its capability order, a no-op e-stop fails CL3, hardware is
never actuated without ``allow_actuation`` and the envelope is probed inside
the schema range.
"""

from __future__ import annotations

import unittest

from mhs.client import MHSClient
from mhs.conformance import run_suite
from mhs.conformance.inprocess import Harness, run_suite_inprocess
from mhs.errors import MHSError

from tests.conformance import support
from tests.conformance.support import client_for, entry, statuses

ORDER = ("CL0", "CL1", "CL2", "CL3", "CL4")


def at_most(level: str, ceiling: str) -> bool:
    return ORDER.index(level) <= ORDER.index(ceiling)


def wrapped(client_class, server):
    client = client_class(support.Loopback(server))
    client.hello()
    return client


class _IgnoresRevisionClient(MHSClient):
    """An endpoint that ignores expected_revision: OP-005's negative probe is executed."""

    def invoke(self, capability_id, input=None, **kwargs):  # noqa: A002
        kwargs.pop("expected_revision", None)
        return super().invoke(capability_id, input, **kwargs)


class _ResourceRequiredClient(MHSClient):
    """Plan 3.6 step 3 / WP-04 4d: a binding-targeted invoke without ``resource`` is INVALID_PARAMS."""

    bound: frozenset = frozenset()
    seen: list

    def invoke(self, capability_id, input=None, **kwargs):  # noqa: A002
        self.seen.append((capability_id, kwargs.get("resource")))
        if capability_id in self.bound and not kwargs.get("resource"):
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "resource is required for this capability",
                           {"details": {"reason": "resource_required"}})
        return super().invoke(capability_id, input, **kwargs)


class _ProtocolRefusalClient(MHSClient):
    """Refuses out-of-envelope setpoints with a protocol error instead of a safety or input refusal."""

    def invoke(self, capability_id, input=None, **kwargs):  # noqa: A002
        value = (input or {}).get("target_temperature")
        if capability_id == "cap.thermal.setpoint.v1" and isinstance(value, (int, float)) and value > 80:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "rejected before the limits engine")
        return super().invoke(capability_id, input, **kwargs)


class _NoResetClient(MHSClient):
    """An endpoint whose reset is always refused: an e-stop stays latched for the rest of the group."""

    def reset(self, *args, **kwargs):
        raise MHSError("MHS.SAFETY.RESET_REFUSED", "reset refused by the endpoint")


class NullDriverTests(unittest.TestCase):
    """DRV-08: a Bridge returning {} must not be awarded CL2 or above."""

    def test_null_driver_at_mhs_device_cl3_is_at_most_cl1(self):
        report = run_suite(client_for(support.null_server()), profile="MHS-Device", level="CL3")
        self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])

    def test_null_driver_is_at_most_cl1_even_when_actuation_is_allowed(self):
        report = run_suite(client_for(support.null_server()), profile="MHS-Device", level="CL3",
                           allow_actuation=True)
        self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])
        write_effect = entry(report, "TCAP-003")
        self.assertEqual(write_effect["status"], "fail", write_effect)
        self.assertTrue(write_effect["required"])

    def test_null_driver_simulated_is_at_most_cl1(self):
        report = run_suite_inprocess(lambda: support.null_server(mode="simulated"), profile="MHS-Sim", level="CL3")
        self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])

    def test_null_invoke_driver_with_a_permissive_output_schema_is_at_most_cl1(self):
        """Verifier null_variants.py / null_env2.py: an invoke probe with output_schema {"type": "object"}."""

        envelope = {"cap.motion.joint_position.v1": {"duration_s": {"min": 0, "max": 5, "unit": "s",
                                                                    "reason": "travel time"}}}
        runs = {
            "in-process": lambda: run_suite_inprocess(lambda: support.null_invoke_server(), profile="MHS-Sim",
                                                      level="CL3"),
            "client": lambda: run_suite(client_for(support.null_invoke_server()), profile="MHS-Sim", level="CL3"),
            "hardware client": lambda: run_suite(
                client_for(support.null_invoke_server(mode="hardware", estop_kind="both", envelope=envelope)),
                profile="MHS-Device", level="CL3", allow_actuation=True),
            "hardware in-process": lambda: run_suite_inprocess(
                lambda: support.null_invoke_server(mode="hardware", estop_kind="both", envelope=envelope),
                profile="MHS-Device", level="CL3", allow_actuation=True),
        }
        for label, run in runs.items():
            with self.subTest(run=label):
                report = run()
                self.assertTrue(at_most(report["level_achieved"], "CL1"), (label, report["level_achieved"]))
                output = entry(report, "TCAP-001")
                self.assertEqual(output["status"], "fail", output)
                self.assertTrue(output["required"])
                self.assertIn("no output", output["detail"])


    def test_null_extension_driver_is_at_most_cl1(self):
        """Verifier r2/acc_null.py ``null_ext`` and acc_null2.py: an x-cap probe has no class output contract.

        TCAP-001 has nothing to enforce for ``{"type": "object"}``, so the effect
        check (TCAP-003) covers invoke probes without a class output contract.
        """

        runs = {
            "hardware client": lambda: run_suite(
                client_for(support.null_extension_server()), profile="MHS-Device", level="CL3",
                allow_actuation=True),
            "hardware in-process": lambda: run_suite_inprocess(
                lambda: support.null_extension_server(), profile="MHS-Device", level="CL3", allow_actuation=True),
            "hardware in-process, overridden no-op estop": lambda: run_suite_inprocess(
                lambda: support.null_extension_server(noop_estop=True), profile="MHS-Device", level="CL3",
                allow_actuation=True),
            "simulated in-process CL4, overridden no-op estop": lambda: run_suite_inprocess(
                lambda: support.null_extension_server(mode="simulated", noop_estop=True), profile="MHS-Sim",
                level="CL4"),
            "simulated client CL4": lambda: run_suite(
                client_for(support.null_extension_server(mode="simulated")), profile="MHS-Sim", level="CL4"),
        }
        for label, run in runs.items():
            with self.subTest(run=label):
                report = run()
                self.assertTrue(at_most(report["level_achieved"], "CL1"), (label, report["level_achieved"]))
                effect = entry(report, "TCAP-003")
                self.assertEqual(effect["status"], "fail", effect)
                self.assertTrue(effect["required"], effect)
                self.assertIn("no observable effect", effect["detail"])

    def test_a_driver_with_an_observable_invoke_effect_passes_the_effect_check(self):
        server, _bridge = support.envelope_server()
        report = run_suite(client_for(server), profile="MHS-Sim", level="CL2")
        effect = entry(report, "TCAP-003")
        self.assertEqual(effect["status"], "pass", effect)
        self.assertEqual(report["level_achieved"], "CL2", [t for t in report["tests"] if t["status"] != "pass"])


class CapabilityOrderTests(unittest.TestCase):
    """TESTS-03 / DRV-08: the level does not depend on declaration order or on a declared envelope."""

    def test_thermostat_gets_the_same_level_with_setpoint_first_or_last(self):
        for variant in ("plain", "limits"):
            with self.subTest(variant=variant):
                last = run_suite(client_for(support.thermostat_server(variant=variant)),
                                 profile="MHS-Sim", level="CL3")
                first = run_suite(client_for(support.thermostat_server(variant=variant, setpoint_first=True)),
                                  profile="MHS-Sim", level="CL3")
                self.assertEqual(first["level_achieved"], last["level_achieved"])
                self.assertEqual(statuses(first), statuses(last))
                self.assertIn(first["level_achieved"], ("CL2", "CL3"))

    def test_declared_envelope_does_not_lower_the_level(self):
        plain = run_suite(client_for(support.thermostat_server(variant="plain")), profile="MHS-Sim", level="CL3")
        limited = run_suite(client_for(support.thermostat_server(variant="limits")), profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(limited, "OP-001")["status"], "pass", entry(limited, "OP-001"))
        self.assertGreaterEqual(ORDER.index(limited["level_achieved"]), ORDER.index(plain["level_achieved"]))

    def test_heater_order_independent_in_process(self):
        first = run_suite_inprocess(lambda: support.heater_server()[0], profile="MHS-Sim", level="CL3")
        last = run_suite_inprocess(lambda: support.heater_server(setpoint_first=False)[0],
                                   profile="MHS-Sim", level="CL3")
        self.assertEqual(statuses(first), statuses(last))
        self.assertEqual(first["level_achieved"], last["level_achieved"])
        self.assertIn("cap.thermal.setpoint.v1", entry(first, "OP-001")["detail"])


class EstopTests(unittest.TestCase):
    """CONF-02: an e-stop that never reaches the device fails CL3."""

    def test_noop_estop_fails_at_cl3(self):
        report = run_suite_inprocess(lambda: support.heater_server(implement_estop=False)[0],
                                     profile="MHS-Sim", level="CL3")
        self.assertTrue(at_most(report["level_achieved"], "CL2"), report["level_achieved"])
        estop = entry(report, "SAFE-028")
        self.assertEqual(estop["status"], "fail", estop)
        self.assertTrue(estop["required"])

    def test_working_estop_passes_cl3(self):
        report = run_suite_inprocess(lambda: support.heater_server()[0], profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(report, "SAFE-028")["status"], "pass", entry(report, "SAFE-028"))
        self.assertEqual(report["level_achieved"], "CL3", [t for t in report["tests"] if t["status"] != "pass"])

    def test_noop_estop_also_fails_over_a_plain_client(self):
        report = run_suite(client_for(support.heater_server(implement_estop=False)[0]),
                           profile="MHS-Sim", level="CL3")
        self.assertEqual(entry(report, "SAFE-028")["status"], "fail")
        self.assertTrue(at_most(report["level_achieved"], "CL2"))


    def test_noop_safe_state_action_fails_safe028(self):
        """Verifier r2/acc_estop.py NoopOffHeater: the bridge itself reports safe_state.achieved=false."""

        runs = {
            "in-process": lambda: run_suite_inprocess(lambda: support.noop_safe_state_heater()[0],
                                                      profile="MHS-Sim", level="CL3"),
            "client": lambda: run_suite(client_for(support.noop_safe_state_heater()[0]),
                                        profile="MHS-Sim", level="CL3"),
            "hardware in-process": lambda: run_suite_inprocess(
                lambda: support.hardware_heater(implement_estop=False,
                                                bridge_class=support.NoopSafeStateHeaterBridge)[0],
                profile="MHS-Device", level="CL3", allow_actuation=True),
            "hardware client": lambda: run_suite(
                client_for(support.hardware_heater(implement_estop=False,
                                                   bridge_class=support.NoopSafeStateHeaterBridge)[0]),
                profile="MHS-Device", level="CL3", allow_actuation=True),
        }
        for label, run in runs.items():
            with self.subTest(run=label):
                report = run()
                estop = entry(report, "SAFE-028")
                self.assertEqual(estop["status"], "fail", estop)
                self.assertTrue(estop["required"], estop)
                self.assertIn("safe_state.achieved", estop["detail"])
                self.assertTrue(at_most(report["level_achieved"], "CL2"), (label, report["level_achieved"]))


class HardwareGateTests(unittest.TestCase):
    """CONF-05 / FIT-13 / CON-031 / CON-032: hardware is never actuated without an explicit opt-in."""

    def test_hardware_without_allow_actuation_makes_no_native_writes(self):
        server, backend = support.hardware_heater()
        report = run_suite(client_for(server), profile="MHS-Device", level="CL3")
        self.assertEqual(backend.actuations(), [])
        self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])
        self.assertEqual(entry(report, "CON-031")["status"], "pass")
        self.assertEqual(entry(report, "OP-001")["status"], "skip")
        self.assertIn("allow-actuation", entry(report, "OP-001")["detail"])

    def test_hardware_without_allow_actuation_in_process_records_no_bridge_calls(self):
        backends = []

        def factory():
            server, backend = support.hardware_heater()
            backends.append(backend)
            return server

        report = run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
        self.assertTrue(backends)
        for backend in backends:
            self.assertEqual(backend.actuations(), [])
        self.assertEqual(entry(report, "CON-031")["status"], "pass", entry(report, "CON-031"))

    def test_hardware_with_allow_actuation_is_tested(self):
        server, backend = support.hardware_heater()
        report = run_suite(client_for(server), profile="MHS-Device", level="CL3", allow_actuation=True)
        self.assertTrue(backend.actuations())
        self.assertEqual(report["level_achieved"], "CL3", [t for t in report["tests"] if t["status"] != "pass"])

    def test_hardware_cl4_is_not_capped_by_replay(self):
        report = run_suite_inprocess(lambda: support.hardware_heater()[0], profile="MHS-Device", level="CL4",
                                     allow_actuation=True)
        for test_id in ("FID-016", "FID-025"):
            case = entry(report, test_id)
            self.assertEqual(case["status"], "skip", case)
            self.assertFalse(case["required"], case)
        self.assertEqual(report["level_achieved"], "CL4", [t for t in report["tests"] if t["status"] != "pass"])

    def test_hardware_only_estop_is_never_sent(self):
        server, backend = support.hardware_heater(
            estop={"kind": "hardware", "latching": True, "physical_ref": "panel button"})
        client = client_for(server)
        report = run_suite(client, profile="MHS-Device", level="CL3", allow_actuation=True)
        self.assertNotIn("mhs.safety.estop", client.transport.methods)
        self.assertNotIn("mhs.safety.reset", client.transport.methods)
        self.assertNotIn(("stop",), backend.native_calls)
        self.assertEqual(entry(report, "TSAFE-001")["status"], "skip")
        self.assertEqual(entry(report, "CON-032")["status"], "pass")

    def test_hardware_door_hook_is_not_actuated_without_allow_actuation(self):
        """Verifier door_hook.py: SAFE-011's x-cap.mhs-test.set_door hook path on a hardware device."""

        server, backend = support.hardware_heater(interlock=True, door_hook=True)
        client = client_for(server)
        report = run_suite(client, profile="MHS-Device", level="CL3")
        self.assertEqual(backend.actuations(), [])
        self.assertNotIn("mhs.safety.reset", client.transport.methods)
        case = entry(report, "SAFE-011")
        self.assertEqual(case["status"], "skip", case)
        self.assertIn("allow-actuation", case["detail"])
        self.assertEqual(entry(report, "CON-031")["status"], "pass", entry(report, "CON-031"))

    def test_hardware_door_hook_is_used_with_allow_actuation(self):
        server, backend = support.hardware_heater(interlock=True, door_hook=True)
        report = run_suite(client_for(server), profile="MHS-Device", level="CL3", allow_actuation=True)
        self.assertIn(("set_lid", "open"), backend.native_calls)
        self.assertIn(("set_lid", "closed"), backend.native_calls)
        self.assertEqual(entry(report, "SAFE-011")["status"], "pass", entry(report, "SAFE-011"))

    def test_negative_tests_are_not_sent_to_hardware_over_a_plain_client(self):
        """An endpoint that ignores expected_revision would execute OP-005's command: it is never sent."""

        server, backend = support.hardware_heater()
        client = wrapped(_IgnoresRevisionClient, server)
        report = run_suite(client, profile="MHS-Device", level="CL3")
        self.assertEqual(backend.actuations(), [])
        for test_id in ("OP-005", "PROTO-027", "SAFE-014"):
            case = entry(report, test_id)
            self.assertEqual(case["status"], "skip", case)
            self.assertIn("allow-actuation", case["detail"])
        self.assertEqual(entry(report, "PROTO-014")["status"], "pass", entry(report, "PROTO-014"))
        self.assertEqual(entry(report, "CON-031")["status"], "pass", entry(report, "CON-031"))

    def test_con031_fails_when_a_negative_test_reaches_the_hardware_bridge(self):
        """In-process the harness blocks the dispatched command at the bridge: nothing reaches the device."""

        server, backend = support.hardware_heater()
        harness = Harness(server)
        try:
            report = run_suite(wrapped(_IgnoresRevisionClient, server), profile="MHS-Device", level="CL3",
                               harness=harness)
        finally:
            harness.restore()
        self.assertEqual(backend.actuations(), [])
        self.assertEqual(entry(report, "OP-005")["status"], "fail", entry(report, "OP-005"))
        case = entry(report, "CON-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("OP-005", case["detail"])
        self.assertIn("cap.thermal.setpoint.v1", case["detail"])
        self.assertIn("blocked", case["detail"])
        blocked = [record for record in harness.records if record.faulted == "blocked"]
        self.assertTrue(blocked)
        self.assertEqual({record.test_id for record in blocked}, {"OP-005"})

    def test_out_of_envelope_probes_never_reach_a_hardware_arm(self):
        """Verifier r2/acc_hw_arm.py: SAFE-014 probes outside a per-joint (or scalar) envelope, no opt-in."""

        for scalar in (False, True):
            for transport in ("client", "in-process"):
                with self.subTest(scalar=scalar, transport=transport):
                    arms = []

                    def factory(scalar=scalar):
                        server, arm = support.hardware_arm(scalar=scalar)
                        arms.append(arm)
                        return server

                    if transport == "client":
                        report = run_suite(client_for(factory()), profile="MHS-Device", level="CL3")
                    else:
                        report = run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
                    self.assertEqual([call for arm in arms for call in arm.actuations()], [])
                    self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])
                    envelope, gate = entry(report, "SAFE-014"), entry(report, "CON-031")
                    if transport == "client":
                        self.assertEqual(envelope["status"], "skip", envelope)
                        self.assertIn("allow-actuation", envelope["detail"])
                        self.assertEqual(gate["status"], "pass", gate)
                    elif envelope["status"] != "pass":
                        # The endpoint did not enforce the limit: the harness blocked the probe at the bridge.
                        self.assertEqual(gate["status"], "fail", gate)
                        self.assertIn("SAFE-014", gate["detail"])
                        self.assertIn("blocked", gate["detail"])

    def test_binding_limits_are_never_probed_on_hardware_without_opt_in(self):
        """Verifier r2/acc_hw.py 'binding limits': limits [10, 60] under the envelope [0, 80]."""

        limits = {"target_temperature": {"min": 10, "max": 60}}
        for level in ("CL3", "CL4"):
            for transport in ("client", "in-process"):
                with self.subTest(level=level, transport=transport):
                    backends = []

                    def factory():
                        server, backend = support.hardware_heater(capability_limits=limits)
                        backends.append(backend)
                        return server

                    if transport == "client":
                        report = run_suite(client_for(factory()), profile="MHS-Device", level=level)
                    else:
                        report = run_suite_inprocess(factory, profile="MHS-Device", level=level)
                    self.assertEqual([call for backend in backends for call in backend.actuations()], [])
                    self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])

    def test_permit_gated_hardware_without_opt_in_is_capped_at_cl1(self):
        """Verifier r2/acc_permit.py: no probe (permit-gated setpoint) must not lift the CL1 cap."""

        server, backend = support.hardware_heater()
        server.devices[support.HEATER_ID].safety.requires_permit = ["cap.thermal.*"]
        report = run_suite(client_for(server), profile="MHS-Device", level="CL3")
        self.assertEqual(backend.actuations(), [])
        self.assertEqual(report["level_achieved"], "CL1", [t for t in report["tests"] if t["status"] != "pass"])
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "skip", case)
        self.assertTrue(case["required"], case)
        self.assertTrue(any("capped at CL1" in line for line in report["limitations"]), report["limitations"])

    def test_hardware_sensor_without_actuating_bindings_is_not_capped(self):
        server, _bridge = support.class_faithful_server("cap.measure.temperature.v1", mode="hardware")
        report = run_suite(client_for(server), profile="MHS-Device", level="CL2")
        self.assertFalse(entry(report, "OP-001")["required"], entry(report, "OP-001"))
        self.assertFalse(any("capped at CL1" in line for line in report["limitations"]), report["limitations"])

    STRICT_HEATER = {"resource_kind": "instrument.incubator", "interlock": True}
    NOT_REACHED = ("OP-005", "PROTO-027", "SAFE-011", "SAFE-012", "SAFE-014")

    def _strict_run(self, armed):
        backends = []

        def factory():
            server, backend = support.hardware_heater(server_options={"strict": True, "armed": armed},
                                                      **self.STRICT_HEATER)
            backends.append(backend)
            return server

        report = run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
        self.assertTrue(backends)
        for backend in backends:
            self.assertEqual(backend.actuations(), [])
        self.assertEqual(entry(report, "CON-031")["status"], "pass", entry(report, "CON-031"))
        self.assertTrue(at_most(report["level_achieved"], "CL1"), report["level_achieved"])
        return report

    def test_strict_unarmed_hardware_negative_tests_are_not_reached(self):
        """MERGE-B (verifier 07a r3): plan 3.6 checks arming (step 6) before the check a negative test targets.

        A strict endpoint arms no hardware by default, so it answers every
        negative test with ``MHS.AUTH.HARDWARE_DISABLED``; that is not reported
        as the subject failing the check the test targets.
        """
        report = self._strict_run(armed=None)
        for test_id in self.NOT_REACHED:
            with self.subTest(test=test_id):
                case = entry(report, test_id)
                self.assertEqual(case["status"], "skip", case)
                self.assertIn("MHS.AUTH.HARDWARE_DISABLED", case["detail"])
                self.assertIn("not armed", case["detail"])

    def test_strict_armed_hardware_negative_tests_reach_their_checks(self):
        report = self._strict_run(armed=True)
        for test_id in self.NOT_REACHED:
            with self.subTest(test=test_id):
                self.assertEqual(entry(report, test_id)["status"], "pass", entry(report, test_id))

    def test_a_refused_reset_is_reported_as_refused(self):
        """MERGE-B fix round (MERGE-B.md follow-up): TSAFE-001 said "e-stop is still
        engaged after a *successful* reset" when the endpoint refused the reset (a
        strict hardware endpoint lets only an authenticated operator reset)."""
        report = run_suite_inprocess(
            lambda: support.hardware_heater(server_options={"strict": True, "armed": True},
                                            **self.STRICT_HEATER)[0],
            profile="MHS-Device", level="CL3", allow_actuation=True)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertNotIn("successful reset", case["detail"])
        self.assertIn("MHS.AUTH.FORBIDDEN", case["detail"])
        self.assertIn("rejected", case["detail"])

    def test_no_self_issued_permits_on_hardware(self):
        server, _backend = support.hardware_heater()
        server.devices[support.HEATER_ID].safety.requires_permit = ["cap.thermal.*"]
        client = client_for(server)
        report = run_suite(client, profile="MHS-Device", level="CL3", allow_actuation=True)
        self.assertNotIn("mhs.safety.permit", client.transport.methods)
        permit = entry(report, "SAFE-031")
        self.assertEqual(permit["status"], "skip", permit)
        self.assertIn("approvals", permit["detail"])


class StopPathTests(unittest.TestCase):
    """SAFE-045: a hardware R2+ device needs a hardware stop (kind hardware, or both with physical_ref)
    or a non-empty achieved_by."""

    def _safe045(self, estop):
        server, _backend = support.hardware_heater(estop=estop, achieved_by=[], heater_off=False)
        return entry(run_suite(client_for(server), profile="MHS-Device", level="CL3"), "SAFE-045")

    def test_software_estop_with_a_physical_ref_is_not_a_stop_path(self):
        case = self._safe045({"kind": "software", "latching": True, "physical_ref": "a sticker"})
        self.assertEqual(case["status"], "fail", case)
        self.assertTrue(case["required"])

    def test_both_without_physical_ref_is_not_a_stop_path(self):
        case = self._safe045({"kind": "both", "latching": True})
        self.assertEqual(case["status"], "fail", case)

    def test_hardware_or_both_with_physical_ref_is_a_stop_path(self):
        for estop in ({"kind": "hardware", "latching": True},
                      {"kind": "both", "latching": True, "physical_ref": "panel"}):
            with self.subTest(kind=estop["kind"]):
                self.assertEqual(self._safe045(estop)["status"], "pass")


class EnvelopeTests(unittest.TestCase):
    """CONF-06: SAFE-014 probes the envelope, not the schema."""

    def test_safe014_probes_inside_the_schema_range(self):
        report = run_suite(client_for(support.heater_server()[0]), profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "pass", case)
        self.assertEqual(case.get("mhs_code"), "MHS.SAFETY.ENVELOPE_VIOLATION", case)

    def test_wildcard_envelope_key_and_capability_limits_are_probed(self):
        rule = {"v": {"min": 0, "max": 80}}
        for label, options in (("pattern", {"envelope": {"cap.motion.*": rule}}), ("limits", {"limits": rule})):
            with self.subTest(source=label):
                server, bridge = support.envelope_server(**options)
                report = run_suite(client_for(server), profile="MHS-Sim", level="CL3")
                case = entry(report, "SAFE-014")
                self.assertEqual(case["status"], "pass", case)
                self.assertNotIn(("cap.motion.joint_position.v1", {"v": 81}), bridge.calls)

    def test_envelope_probes_name_the_bound_resource(self):
        """Plan 3.6 step 3: an omitted resource must not turn SAFE-014 into an INVALID_PARAMS 'pass'."""

        server, backend = support.heater_server()
        client = _ResourceRequiredClient(support.Loopback(server))
        client.bound = frozenset({"cap.thermal.setpoint.v1", "cap.measure.temperature.v1"})
        client.seen = []
        client.hello()
        report = run_suite(client, profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "pass", case)
        self.assertEqual(case.get("mhs_code"), "MHS.SAFETY.ENVELOPE_VIOLATION", case)
        self.assertEqual(entry(report, "OP-001")["status"], "pass", entry(report, "OP-001"))
        bound_calls = [item for item in client.seen if item[0] in client.bound]
        self.assertTrue(bound_calls)
        self.assertTrue(all(resource == "heater" for _capability, resource in bound_calls), bound_calls)

    def test_protocol_errors_are_not_envelope_refusals(self):
        server, _backend = support.heater_server()
        report = run_suite(wrapped(_ProtocolRefusalClient, server), profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-014")
        self.assertEqual(case["status"], "fail", case)
        self.assertIn("INVALID_PARAMS", case["detail"])

    def test_envelope_probes_never_reach_the_bridge(self):
        server, backend = support.heater_server()
        run_suite_inprocess(lambda: server, profile="MHS-Sim", level="CL3")
        self.assertFalse([call for call in backend.native_calls if call[0] == "set_setpoint" and call[1] > 80])


class InterlockTests(unittest.TestCase):
    """CONF-08: interlock tests no longer depend on reference-only hooks."""

    def test_declared_interlock_is_required_and_injected_in_process(self):
        report = run_suite_inprocess(lambda: support.heater_server(interlock=True)[0], profile="MHS-Sim",
                                     level="CL3")
        for test_id in ("SAFE-011", "SAFE-012"):
            case = entry(report, test_id)
            self.assertEqual(case["status"], "pass", case)
            self.assertTrue(case["required"], case)

    def test_interlock_tests_do_not_pass_on_a_latched_device(self):
        """A device left latched (reset refused) must not 'pass' the interlock tests with ESTOP_ENGAGED."""

        server, _backend = support.heater_server(interlock=True)
        harness = Harness(server)
        try:
            report = run_suite(wrapped(_NoResetClient, server), profile="MHS-Sim", level="CL3", harness=harness)
        finally:
            harness.restore()
        for test_id in ("SAFE-011", "SAFE-012"):
            case = entry(report, test_id)
            self.assertEqual(case["status"], "fail", case)
            self.assertIn("latched", case["detail"])

    def test_declared_interlock_without_injection_is_required_over_a_client(self):
        report = run_suite(client_for(support.heater_server(interlock=True)[0]), profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-011")
        self.assertTrue(case["required"], case)
        self.assertEqual(case["status"], "skip", case)
        self.assertEqual(report["level_achieved"], "CL2")


class FaultInjectionTests(unittest.TestCase):
    """CONF-08: deadline, cancellation and unknown-outcome tests run on any in-process driver."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_suite_inprocess(lambda: support.heater_server(cancellable=True)[0], profile="MHS-Sim",
                                         level="CL3")

    def test_cancellation_is_required_and_exercised(self):
        case = entry(self.report, "OP-011")
        self.assertTrue(case["required"], case)
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("cancelled", case["detail"])
        # In-process the harness delay stands in for the native call: the scope is disclosed.
        self.assertIn("harness", case["detail"])

    def test_deadline_and_lost_response_are_exercised(self):
        for test_id in ("PROTO-011", "OP-013"):
            case = entry(self.report, test_id)
            self.assertEqual(case["status"], "pass", case)
        self.assertEqual(entry(self.report, "OP-013").get("mhs_code"), "MHS.OUTCOME.UNKNOWN")

    def test_level_is_cl3(self):
        self.assertEqual(self.report["level_achieved"], "CL3",
                         [t for t in self.report["tests"] if t["status"] != "pass"])


class SynthesisTests(unittest.TestCase):
    """CONF-01: inputs come from fixtures, class examples or envelope-aware synthesis."""

    def test_class_faithful_bindings_without_required_inputs_reach_cl2(self):
        for capability_id in ("cap.world.step.v1", "cap.motion.home.v1"):
            with self.subTest(capability=capability_id):
                server, bridge = support.class_faithful_server(capability_id)
                report = run_suite(client_for(server), profile="MHS-Sim", level="CL2")
                self.assertEqual(entry(report, "OP-004")["status"], "pass", entry(report, "OP-004"))
                self.assertEqual(report["level_achieved"], "CL2", [t for t in report["tests"] if t["status"] != "pass"])

    def test_read_only_device_is_not_failed_by_mutation_tests(self):
        server, bridge = support.class_faithful_server("cap.measure.temperature.v1")
        report = run_suite(client_for(server), profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        # 07b: OP-001 checks the read revision rule with the read command itself (plan 3.7).
        self.assertEqual(case["status"], "pass", case)
        self.assertTrue(case["required"])
        self.assertTrue(bridge.calls)
        self.assertEqual({capability_id for capability_id, _args in bridge.calls}, {"cap.measure.temperature.v1"})
        self.assertEqual(report["level_achieved"], "CL2")

    def test_pattern_string_needs_a_fixture(self):
        server, bridge = support.pattern_server()
        report = run_suite(client_for(server), profile="MHS-Sim", level="CL2")
        case = entry(report, "OP-001")
        self.assertEqual(case["status"], "skip", case)
        self.assertIn("fixture", case["detail"])
        self.assertEqual(bridge.calls, [])

    def test_pattern_string_with_a_fixture_reaches_cl2(self):
        server, bridge = support.pattern_server()
        fixtures = {"cap.world.step.v1": {"valid": {"well": "A1"}, "alternate": {"well": "B2"}}}
        report = run_suite(client_for(server), profile="MHS-Sim", level="CL2", fixtures=fixtures)
        self.assertEqual(report["level_achieved"], "CL2", [t for t in report["tests"] if t["status"] != "pass"])
        self.assertIn(("cap.world.step.v1", {"well": "A1"}), bridge.calls)


class OutputTests(unittest.TestCase):
    """CONF-02: outputs are validated against the binding output schema."""

    def test_garbage_output_fails_cl2(self):
        report = run_suite(client_for(support.heater_server(garbage_output=True)[0]),
                           profile="MHS-Sim", level="CL3")
        case = entry(report, "TCAP-001")
        self.assertEqual(case["status"], "fail", case)
        self.assertTrue(at_most(report["level_achieved"], "CL1"))


if __name__ == "__main__":
    unittest.main()
