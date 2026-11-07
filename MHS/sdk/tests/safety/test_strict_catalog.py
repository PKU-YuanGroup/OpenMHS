"""Strict mode at construction: the catalogue and device rules (WP-04 step 4b).

``MHSServer(strict=True)`` / ``Device(strict=True)`` refuse every finding of
:func:`mhs._server.strict.resolve_device` with ``MHSStrictError``;
compatibility mode (the 0.9 default) reports each one as an
``MHSStrictWarning`` and keeps serving.  Ports: tests-run ``thermo.py`` (typo
variant, TESTS-02), schema-catalog ``exp2.py`` (risk floor, SC-01),
fit-robots-sim-verifier ``typo.py`` (limit key typo), drv / driver-authoring
SAFE-045 probes (MISSED driver-authoring), the reference drift report (SC-02).
"""

from __future__ import annotations

import unittest

from mhs.limits import LimitConfigError
from mhs.reference import build_endpoint, build_server
from mhs.server import (Capability, Device, MHSServer, MHSStrictError, MHSStrictWarning, Resource,
                        SafetyEnvelope)

from ._strict_support import (ARM_ID, DESCRIBE, JOINTS, STOP, TORQUE, ArmBridge, RecordWarnings,
                              arm_capabilities, arm_device, arm_safety, arm_server, strict_warnings)
from ._support import FIDELITY, error_code, open_session


def _rules(error: MHSStrictError) -> set[str]:
    return {finding.rule for finding in error.findings}


class StrictAcceptsAFaithfulDeviceTests(unittest.TestCase):
    def test_a_faithful_device_constructs_without_any_finding(self) -> None:
        with RecordWarnings() as caught:
            server, rpc, device, bridge = arm_server(strict=True)
        self.assertEqual(strict_warnings(caught), [])
        self.assertEqual(server.strict_findings, [])
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                      input={"joint_positions": [0.1, 0.2]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_strict_must_be_none_or_a_bool(self) -> None:
        with self.assertRaises(TypeError):
            MHSServer("mhs://localhost/strict", [arm_device()], log_ready=False, strict="yes")

    def test_strict_error_is_a_value_error_listing_every_finding(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.motion.jiont_position.v1", "arm")])
        device = arm_device(capabilities=caps, risk="R0", fidelity={"engine": "x"})
        with self.assertRaises(ValueError) as caught:
            MHSServer("mhs://localhost/strict", [device], log_ready=False, strict=True)
        error = caught.exception
        self.assertIsInstance(error, MHSStrictError)
        self.assertTrue({"unknown-capability", "risk-floor", "fidelity-incomplete"} <= _rules(error), _rules(error))
        self.assertIn("MHS.CAPABILITY.UNKNOWN", error.codes)
        self.assertIn("cap.motion.jiont_position.v1", str(error))
        for finding in error.findings:
            self.assertEqual(finding.device_id, ARM_ID)
            self.assertTrue(finding.to_json()["message"])


class StrictFlagTests(unittest.TestCase):
    def test_device_strict_refuses_at_device_construction(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.motion.jiont_position.v1", "arm")])
        with self.assertRaises(MHSStrictError) as caught:
            arm_device(capabilities=caps, strict=True)
        self.assertIn("unknown-capability", _rules(caught.exception))

    def test_a_strict_device_is_strict_on_a_compatibility_server(self) -> None:
        device = arm_device(strict=True)
        server, rpc, device, bridge = arm_server(device, strict=None)
        manifest = rpc("mhs.devices.get", device_id=device.device_id)
        verbs = {item["capability_id"]: item.get("verb") for item in manifest["capabilities"]}
        self.assertEqual(verbs[DESCRIBE], "read", "strict serves the class verb")
        self.assertTrue(server._is_strict(device))  # noqa: SLF001

    def test_a_strict_server_makes_every_device_strict(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.motion.jiont_position.v1", "arm")])
        with self.assertRaises(MHSStrictError):
            arm_server(arm_device(capabilities=caps, strict=False), strict=True)


class UnknownCapabilityTests(unittest.TestCase):
    """tests-run thermo.py 'typo': cap.thermal.setpiont.v1 was served and executed."""

    def _thermo(self, strict):
        caps = [Capability("cap.thermal.setpiont.v1", "zone",
                           input_schema={"type": "object", "properties": {"target_temperature": {"type": "number"}}})]
        device = arm_device(capabilities=caps, safety=arm_safety(risk="R2", achieved_by=()),
                            resources=[Resource("zone", "thermal.zone", state_schema={"type": "object"})])
        return arm_server(device, strict=strict)

    def test_strict_refuses_a_typo_capability_id(self) -> None:
        with self.assertRaises(MHSStrictError) as caught:
            self._thermo(True)
        finding = next(item for item in caught.exception.findings if item.rule == "unknown-capability")
        self.assertEqual(finding.code, "MHS.CAPABILITY.UNKNOWN")
        self.assertEqual(finding.capability_id, "cap.thermal.setpiont.v1")

    def test_compatibility_mode_warns_and_still_serves_it(self) -> None:
        with RecordWarnings() as caught:
            server, rpc, device, bridge = self._thermo(None)
        self.assertTrue(any("cap.thermal.setpiont.v1" in text and "unknown-capability" in text
                            for text in strict_warnings(caught)), strict_warnings(caught))
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id="cap.thermal.setpiont.v1",
                      input={"target_temperature": 1000}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_an_id_that_is_no_capability_id_is_refused(self) -> None:
        caps = arm_capabilities(extra=[Capability("Cap.Motion.Move", "arm")])
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        self.assertIn("capability-id-invalid", _rules(caught.exception))

    def test_a_binding_to_an_undeclared_resource_is_refused(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.motion.home.v1", "nowhere")])
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        self.assertIn("resource-undeclared", _rules(caught.exception))

    def test_a_capability_bound_twice_is_refused(self) -> None:
        caps = arm_capabilities(extra=[Capability(STOP, "arm")])
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        self.assertIn("capability-duplicate", _rules(caught.exception))

    def test_a_class_outside_its_modes_is_refused(self) -> None:
        resources = [Resource("world", "world.sim", state_schema={"type": "object"})]
        caps = [Capability("cap.world.state.v1", "world")]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(mode="hardware", capabilities=caps, resources=resources,
                                  safety=arm_safety(achieved_by=())), strict=True)
        self.assertIn("class-mode", _rules(caught.exception))

    def test_the_configure_class_needs_a_state_schema(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.device.configure.v1", "settings")])
        resources = [Resource("arm", "robot.arm", state_schema={"type": "object"}), Resource("settings", "device")]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps, resources=resources), strict=True)
        self.assertIn("binding-unresolvable", _rules(caught.exception))
        resources[1] = Resource("settings", "device", state_schema={
            "type": "object", "properties": {"gain": {"type": "number"}, "serial": {"type": "string", "readOnly": True}}})
        server, rpc, device, bridge = arm_server(
            arm_device(capabilities=arm_capabilities(extra=[Capability("cap.device.configure.v1", "settings")]),
                       resources=resources), strict=True)
        configure = device._by_capability["cap.device.configure.v1"]  # noqa: SLF001
        self.assertEqual(configure.verb, "write")
        self.assertEqual(sorted(configure.input_schema["properties"]), ["gain"], "readOnly state is not writable")


class DriftAndKindTests(unittest.TestCase):
    def test_drift_is_schema_drift(self) -> None:
        drifting = Capability(JOINTS, "arm", input_schema={
            "type": "object", "properties": {"joint_positions_deg": {"type": "array"}},
            "required": ["joint_positions_deg"]})
        caps = [drifting] + [cap for cap in arm_capabilities() if cap.capability_id != JOINTS]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        drift = [item for item in caught.exception.findings if item.rule == "schema-drift"]
        self.assertTrue(drift)
        self.assertEqual({item.code for item in drift}, {"MHS.INTERNAL.SCHEMA_DRIFT"})
        self.assertTrue(any("joint_positions_deg" in (item.path or "") for item in drift), drift)
        with RecordWarnings() as warned:
            arm_server(arm_device(capabilities=[Capability(JOINTS, "arm", input_schema=drifting.input_schema)]
                                  + [cap for cap in arm_capabilities() if cap.capability_id != JOINTS]),
                       strict=None)
        self.assertTrue(any("schema-drift" in text for text in strict_warnings(warned)))

    def test_kind_mismatch(self) -> None:
        resources = [Resource("arm", "world.sim", state_schema={"type": "object"})]
        caps = [Capability(STOP, "arm")]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps, resources=resources), strict=True)
        finding = next(item for item in caught.exception.findings if item.rule == "kind-mismatch")
        self.assertEqual(finding.code, "MHS.CAPABILITY.KIND_MISMATCH")
        self.assertIn("world.sim", finding.message)
        with RecordWarnings() as warned:
            arm_server(arm_device(capabilities=[Capability(STOP, "arm")], resources=resources), strict=False)
        self.assertTrue(any("KIND_MISMATCH" in text for text in strict_warnings(warned)))


class RiskFloorTests(unittest.TestCase):
    """schema-catalog exp2.py: cap.optics.set_power.v1 (class R2) on an R0 device."""

    def _laser(self, strict):
        caps = [Capability("cap.optics.set_power.v1", "laser")]
        device = arm_device(capabilities=caps, safety=arm_safety(risk="R0", achieved_by=()),
                            resources=[Resource("laser", "optics.laser", state_schema={"type": "object"})])
        return arm_server(device, strict=strict)

    def test_strict_refuses_a_risk_below_the_class_floor(self) -> None:
        with self.assertRaises(MHSStrictError) as caught:
            self._laser(True)
        finding = next(item for item in caught.exception.findings if item.rule == "risk-floor")
        self.assertIn("R2", finding.message)
        self.assertIn("cap.optics.set_power.v1", finding.message)

    def test_compatibility_mode_raises_the_risk_to_the_floor_and_warns(self) -> None:
        with RecordWarnings() as caught:
            server, rpc, device, bridge = self._laser(None)
        self.assertEqual(device.safety.risk_class, "R2")
        hello = rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertEqual(hello["devices"][0]["risk_class"], "R2")
        self.assertEqual(rpc("mhs.safety.status", device_id=device.device_id, deadline_ms=1000)["risk_class"], "R2")
        texts = strict_warnings(caught)
        self.assertTrue(any("risk-floor" in text and "raised to R2" in text for text in texts), texts)


class VerbTests(unittest.TestCase):
    def test_strict_takes_an_undeclared_verb_from_the_class(self) -> None:
        caps = [Capability("cap.thermal.setpoint.v1", "zone"),
                Capability("cap.measure.temperature.v1", "probe")]
        device = arm_device(capabilities=caps, safety=arm_safety(risk="R2", achieved_by=()),
                            resources=[Resource("zone", "thermal.zone", state_schema={"type": "object"}),
                                       Resource("probe", "sensor.temperature", state_schema={"type": "object"})])
        server, rpc, device, bridge = arm_server(device, strict=True)
        verbs = {cap.capability_id: cap.verb for cap in device.capabilities}
        self.assertEqual(verbs, {"cap.thermal.setpoint.v1": "write", "cap.measure.temperature.v1": "read"})
        summary = rpc("mhs.devices.list")["devices"][0]["capabilities"]
        self.assertEqual({item["capability_id"]: item["verb"] for item in summary}, verbs)

    def test_compatibility_mode_keeps_the_0_9_default_verb(self) -> None:
        server, rpc, device, bridge = arm_server(strict=None)
        self.assertEqual(device._by_capability[DESCRIBE].verb, "invoke")  # noqa: SLF001
        manifest = rpc("mhs.devices.get", device_id=device.device_id)
        self.assertNotIn("verb", manifest["capabilities"][0])

    def test_a_declared_verb_that_differs_from_the_class_is_refused(self) -> None:
        caps = [Capability(JOINTS, "arm", verb="read")] + [
            cap for cap in arm_capabilities() if cap.capability_id != JOINTS]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        finding = next(item for item in caught.exception.findings if item.rule == "verb-differs")
        self.assertEqual(finding.capability_id, JOINTS)
        with RecordWarnings() as warned:
            server, rpc, device, bridge = arm_server(arm_device(capabilities=[
                Capability(JOINTS, "arm", verb="read")] + [
                cap for cap in arm_capabilities() if cap.capability_id != JOINTS]), strict=None)
        self.assertEqual(device._by_capability[JOINTS].verb, "read", "compat keeps the declared verb")  # noqa: SLF001
        self.assertTrue(any("verb-differs" in text for text in strict_warnings(warned)))


class SafeStateAndInterlockTests(unittest.TestCase):
    def test_an_unbound_achieved_by_on_a_simulator_is_refused(self) -> None:
        safety = arm_safety(achieved_by=("cap.motion.stpo.v1",))
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(safety=safety), strict=True)
        self.assertIn("achieved-by-unbound", _rules(caught.exception))
        with RecordWarnings() as warned:
            arm_server(arm_device(safety=arm_safety(achieved_by=("cap.motion.stpo.v1",))), strict=None)
        self.assertTrue(any("cap.motion.stpo.v1" in text for text in strict_warnings(warned)))

    def test_on_hardware_strict_mode_reports_it_with_every_other_finding(self) -> None:
        caps = arm_capabilities(extra=[Capability("cap.motion.jiont_position.v1", "arm")])
        device = arm_device(mode="hardware", capabilities=caps, safety=arm_safety(achieved_by=("cap.motion.stpo.v1",)))
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(device, strict=True, armed=True)
        self.assertTrue({"achieved-by-unbound", "unknown-capability"} <= _rules(caught.exception))

    def test_required_for_must_name_bound_capabilities(self) -> None:
        cases = {
            "required-for-empty": [{"id": "door", "required_for": []}],
            "required-for-unbound": [{"id": "door", "required_for": ["cap.motion.joint_positon.v1"]}],
            "interlock-invalid": [{"required_for": [JOINTS]}],
        }
        for rule, interlocks in cases.items():
            with self.subTest(rule=rule):
                with self.assertRaises(MHSStrictError) as caught:
                    arm_server(arm_device(safety=arm_safety(interlocks=interlocks)), strict=True)
                self.assertIn(rule, _rules(caught.exception))
                with RecordWarnings() as warned:
                    arm_server(arm_device(safety=arm_safety(interlocks=interlocks)), strict=None)
                self.assertTrue(any(rule in text for text in strict_warnings(warned)))

    def test_an_informative_interlock_and_patterns_are_accepted(self) -> None:
        interlocks = [{"id": "lamp"}, {"id": "door", "required_for": ["cap.motion.*", JOINTS]}]
        server, rpc, device, bridge = arm_server(arm_device(safety=arm_safety(interlocks=interlocks)), strict=True)
        self.assertEqual(server.strict_findings, [])


class LimitDeclarationTests(unittest.TestCase):
    """fit-robots-sim-verifier typo.py: a misspelled limit key used to be ignored."""

    def _thermo(self, envelope, strict):
        caps = [Capability("cap.thermal.setpoint.v1", "zone")]
        device = arm_device(capabilities=caps, safety=arm_safety(risk="R2", achieved_by=(), envelope=envelope),
                            resources=[Resource("zone", "thermal.zone", state_schema={"type": "object"})])
        return arm_server(device, strict=strict)

    def test_a_limit_path_that_does_not_resolve_is_refused(self) -> None:
        envelope = {"cap.thermal.setpoint.v1": {"target_celsius": {"max": 50, "unit": "Cel"}}}
        with self.assertRaises(MHSStrictError) as caught:
            self._thermo(envelope, True)
        finding = next(item for item in caught.exception.findings if item.rule == "limits-invalid")
        self.assertIn("target_celsius", finding.message)
        self.assertIn("limit-path-resolves", finding.message)
        # WP-04 4c: a limit that cannot be enforced refuses the endpoint in
        # compatibility mode too (plan 3.5 load-time errors; it was a warning).
        with self.assertRaises(LimitConfigError) as refused:
            with RecordWarnings():
                self._thermo(envelope, None)
        self.assertEqual((refused.exception.rule, refused.exception.path), ("limit-path-resolves", "target_celsius"))

    def test_an_unknown_rule_member_is_refused(self) -> None:
        envelope = {"cap.thermal.setpoint.v1": {"target_temperature": {"maximum": 50}}}
        with self.assertRaises(MHSStrictError) as caught:
            self._thermo(envelope, True)
        self.assertIn("limits-invalid", _rules(caught.exception))

    def test_an_envelope_for_an_unbound_capability_is_refused(self) -> None:
        envelope = {"cap.motion.home.v1": {"speed": {"max": 1}}}
        with self.assertRaises(MHSStrictError) as caught:
            self._thermo(envelope, True)
        self.assertIn("envelope-unbound", _rules(caught.exception))

    def test_a_valid_envelope_is_accepted(self) -> None:
        envelope = {"cap.thermal.setpoint.v1": {"target_temperature": {"min": 4, "max": 95, "unit": "Cel"}}}
        server, rpc, device, bridge = self._thermo(envelope, True)
        self.assertEqual([item["rule"] for item in server.strict_findings], [])

    def test_a_malformed_max_duration_is_refused(self) -> None:
        caps = [Capability(JOINTS, "arm", constraints={"max_duration_ms": "10s"})] + [
            cap for cap in arm_capabilities() if cap.capability_id != JOINTS]
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(capabilities=caps), strict=True)
        self.assertIn("constraints-invalid", _rules(caught.exception))


class Safe045Tests(unittest.TestCase):
    """SAFE-045: hardware R2+ with a software-only e-stop used to start silently."""

    def _hardware(self, estop, achieved_by, strict=True):
        safety = arm_safety(risk="R2", achieved_by=achieved_by, estop=estop)
        return arm_server(arm_device(mode="hardware", torque=True, safety=safety), strict=strict, armed=True)

    def test_software_estop_and_no_safe_state_action_is_refused(self) -> None:
        with self.assertRaises(MHSStrictError) as caught:
            self._hardware({"kind": "software", "latching": True}, ())
        self.assertIn("SAFE-045", _rules(caught.exception))
        with RecordWarnings() as warned:
            self._hardware({"kind": "software", "latching": True}, (), strict=None)
        self.assertTrue(any("SAFE-045" in text for text in strict_warnings(warned)))

    def test_a_hardware_estop_needs_its_physical_ref(self) -> None:
        with self.assertRaises(MHSStrictError):
            self._hardware({"kind": "hardware", "latching": True}, ())
        server, *_ = self._hardware({"kind": "both", "latching": True,
                                     "physical_ref": "red mushroom button on the controller (manual p. 12)"}, ())
        self.assertNotIn("SAFE-045", [item["rule"] for item in server.strict_findings])

    def test_a_safe_state_action_satisfies_it(self) -> None:
        server, *_ = self._hardware({"kind": "software", "latching": True}, (STOP,))
        self.assertNotIn("SAFE-045", [item["rule"] for item in server.strict_findings])

    def test_r1_hardware_is_not_concerned(self) -> None:
        safety = arm_safety(risk="R1", achieved_by=(), estop={"kind": "software", "latching": True})
        server, *_ = arm_server(arm_device(mode="hardware", safety=safety), strict=True, armed=True)
        self.assertNotIn("SAFE-045", [item["rule"] for item in server.strict_findings])


class FidelityTests(unittest.TestCase):
    def _refused(self, fidelity, mode="simulated"):
        with self.assertRaises(MHSStrictError) as caught:
            arm_server(arm_device(mode=mode, fidelity=fidelity), strict=True)
        return caught.exception

    def test_a_simulator_without_a_contract_is_refused(self) -> None:
        error = self._refused(None)
        finding = next(item for item in error.findings if item.rule == "fidelity-required")
        self.assertEqual(finding.code, "MHS.FIDELITY.CONTRACT_REQUIRED")

    def test_every_required_field_is_checked(self) -> None:
        for name in ("engine", "fidelity_level", "determinism", "timestep_ms", "realtime_factor", "reset",
                     "snapshot_restore"):
            with self.subTest(missing=name):
                fidelity = {key: value for key, value in FIDELITY.items() if key != name}
                error = self._refused(fidelity)
                self.assertTrue(any(item.rule == "fidelity-incomplete" and name in (item.path or "")
                                    for item in error.findings), error)

    def test_legacy_string_determinism_seeded_and_f3_rules(self) -> None:
        self._refused({**FIDELITY, "determinism": "exact"})
        error = self._refused({**FIDELITY, "determinism": {"kind": "seeded"}})
        self.assertTrue(any("seed_control" in (item.path or "") for item in error.findings))
        error = self._refused({**FIDELITY, "fidelity_level": "F3"})
        self.assertIn("MHS.FIDELITY.VALIDATION_MISSING", error.codes)
        arm_server(arm_device(fidelity={**FIDELITY, "determinism": {"kind": "seeded", "seed_control": "parameter"}}),
                   strict=True)

    def test_a_hybrid_device_is_checked_too(self) -> None:
        self._refused({"engine": "x", "authority": {"arm": "model"}}, mode="hybrid")

    def test_a_hardware_device_must_not_carry_one(self) -> None:
        error = self._refused(dict(FIDELITY), mode="hardware")
        self.assertIn("fidelity-forbidden", _rules(error))

    def test_compatibility_mode_warns(self) -> None:
        with RecordWarnings() as warned:
            arm_server(arm_device(fidelity={"engine": "x"}), strict=None)
        self.assertTrue(any("fidelity-incomplete" in text for text in strict_warnings(warned)))


class ReferenceEndpointTests(unittest.TestCase):
    """The reference endpoints stay protocol fixtures: compatibility mode, warned."""

    def test_reference_endpoints_build_in_compatibility_mode_with_warnings(self) -> None:
        for name in ("conveyor", "arm", "lab"):
            with self.subTest(endpoint=name):
                with RecordWarnings() as caught:
                    server = build_server(build_endpoint(name, endpoint_id=f"mhs://localhost/{name}-strict"),
                                          log_ready=False)
                texts = strict_warnings(caught)
                self.assertTrue(texts)
                findings = server.strict_findings
                self.assertEqual(len(findings), len(texts), "one warning per finding")
                self.assertEqual({item["mode"] for item in findings}, {"compat"})

    def test_the_reference_conveyor_is_refused_in_strict_mode(self) -> None:
        compat = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost/conv-strict"), log_ready=False)
        with self.assertRaises(MHSStrictError) as caught:
            MHSServer("mhs://localhost/conv-strict", list(compat.devices.values()), log_ready=False, strict=True)
        self.assertIn("MHS.INTERNAL.SCHEMA_DRIFT", caught.exception.codes)
        self.assertIn("MHS.CAPABILITY.KIND_MISMATCH", caught.exception.codes)


class TokenPrincipalConfigTests(unittest.TestCase):
    def test_malformed_token_principals(self) -> None:
        with self.assertRaises(ValueError):
            arm_server(strict=True, auth_tokens={"t": {"kind": "operator"}})
        with self.assertRaises(ValueError):
            arm_server(strict=True, auth_tokens={"t": {"id": "x", "kind": "root"}})
        with RecordWarnings() as warned:
            server, *_ = arm_server(strict=None, auth_tokens={"t": {"id": "x", "kind": "root"}})
        self.assertTrue(any("root" in text for text in strict_warnings(warned)))
        self.assertEqual(server._principal_for_token("t"), {"id": "x", "kind": "agent"})  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
