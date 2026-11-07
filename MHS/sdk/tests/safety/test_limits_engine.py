"""The endpoint enforces limits with mhs.limits (WP-04 step 4c, plan 3.5 / 3.6).

Ports of the reviewer repros, each first failing on the 4b server:

* sdk-core ``e8.py`` -- an operator narrows the reference arm to +/-45 deg and
  ``[90, 0]`` completed (array fields were skipped);
* driver-authoring ``arm_probe.py`` -- ``joint_positions`` [3.0, -4.0] against
  +/-1.57 rad and ``position.z`` -200 mm against 50..800 completed;
* fit-robots-ros ``arm_probe.py`` -- the same through catalogue schemas, on
  hardware, with the limit in both the binding and the envelope;
* fit-robots-sim ``limits.py`` -- a simulated arm with the class schema;
* fit-lab-instruments ``proto_psu.py`` / ``v_limits.py`` -- a nested
  ``ch1.voltage`` = 48 V write against a 5 V maximum completed;
* schema-catalog ``exp1.py`` -- a nested ``position.x`` limit was ignored and
  a bound on an object field was accepted;
* fit-robots-sim-verifier ``typo.py`` and spec-verify ``p_typo.py`` -- a
  misspelled limit path or rule member silently dropped the limit;
* verify-schema-catalog ``widen.py`` -- a wider envelope replaced the narrower
  binding limit (last writer wins).

Every refusal is ``MHS.SAFETY.ENVELOPE_VIOLATION`` with ``{path, bound, value,
unit, source}`` details, before any native call; shape errors stay
``MHS.CAPABILITY.INPUT_INVALID``.
"""

from __future__ import annotations

import copy
import json
import unittest

from mhs import canonical
from mhs.limits import LimitConfigError
from mhs.reference_file import validate as validate_reference
from mhs.schema import SchemaStore
from mhs.server import Capability, MHSServer, MHSStrictError, Resource

from ._limits_support import (
    CONFIGURE,
    EXAMPLES,
    JOINTS,
    POSE,
    SETPOINT,
    STOP,
    class_schema,
    details,
    device,
    reference_arm,
    serve,
)
from ._strict_support import RecordWarnings, strict_warnings
from ._support import Rpc, error_code

DEG_JOINTS = "x-cap.test.joints.v1"
DEG_SCHEMA = {
    "type": "object",
    "required": ["joints"],
    "properties": {"joints": {"type": "array", "minItems": 2, "maxItems": 2,
                              "items": {"type": "number", "x-mhs-unit": "deg"}}},
}


def _command(rpc, session, capability_id, payload, **params):
    return rpc("mhs.command", session_id=session, capability_id=capability_id, input=payload,
               command_id=canonical.ulid(), deadline_ms=5000, **params)


class JointArrayTests(unittest.TestCase):
    """Acceptance: [90, 0] against a +/-45 envelope names element [0]; zero bridge calls."""

    def test_array_element_outside_the_envelope_is_refused_before_the_bridge(self) -> None:
        dev = device("mhs://localhost/limits/deg", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)],
                     envelope={DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg",
                                                       "reason": "operator safe range"}}})
        server, rpc, session = serve(dev)
        revision = server._revisions[dev.device_id]
        receipt = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
        found = details(receipt)
        self.assertEqual(found["path"], "joints[0]")
        self.assertEqual(found["bound"], 45)
        self.assertEqual(found["value"], 90)
        self.assertEqual(found["unit"], "deg")
        self.assertEqual(found["source"], "envelope")
        self.assertEqual(found["kind"], "max")
        self.assertEqual(dev.bridge.native(), [], "zero native calls")
        self.assertEqual(server._revisions[dev.device_id], revision)
        inside = _command(rpc, session, DEG_JOINTS, {"joints": [44, -45]})
        self.assertEqual(inside["status"], "completed", inside)

    def test_every_violating_element_is_listed(self) -> None:
        dev = device("mhs://localhost/limits/deg2", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)],
                     envelope={DEG_JOINTS: {"joints": {"min": [-45, -10], "max": [45, 10], "unit": "deg",
                                                       "names": ["shoulder", "elbow"]}}})
        server, rpc, session = serve(dev)
        receipt = _command(rpc, session, DEG_JOINTS, {"joints": [-50, 11]})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        found = details(receipt)
        self.assertEqual(found["path"], "joints[0]")
        self.assertEqual(found["element_name"], "shoulder")
        self.assertEqual([(item["path"], item["kind"], item["bound"]) for item in found["violations"]],
                         [("joints[0]", "min", -45), ("joints[1]", "max", 10)])
        self.assertEqual(dev.bridge.native(), [])


class ReferenceArmTests(unittest.TestCase):
    """sdk-core e8.py and the acceptance line on the reference arm."""

    def test_operator_narrowed_envelope_is_enforced_on_the_array(self) -> None:
        narrowed = {
            JOINTS: {"joint_positions_deg": {"min": -45, "max": 45, "unit": "deg", "reason": "operator safe range"}},
            POSE: {"x_mm": {"min": -100, "max": 100, "unit": "mm", "reason": "operator safe range"}},
        }
        server, rpc, session, dev, calls = reference_arm(narrowed)
        before = rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["state"]
        receipt = _command(rpc, session, JOINTS, {"joint_positions_deg": [90, 0]})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(details(receipt)["path"], "joint_positions_deg[0]")
        self.assertEqual(details(receipt)["bound"], 45)
        self.assertEqual(calls, [], "zero native calls")
        after = rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["state"]
        self.assertEqual(after, before)
        scalar = _command(rpc, session, POSE, {"x_mm": 300, "y_mm": 0})
        self.assertEqual(error_code(scalar), "MHS.SAFETY.ENVELOPE_VIOLATION", scalar)
        self.assertEqual(details(scalar)["path"], "x_mm")
        self.assertEqual(calls, [])
        moved = _command(rpc, session, JOINTS, {"joint_positions_deg": [30, -30]})
        self.assertEqual(moved["status"], "completed", moved)

    def test_out_of_range_command_is_a_safety_refusal_not_input_invalid(self) -> None:
        server, rpc, session, dev, calls = reference_arm()
        receipt = _command(rpc, session, JOINTS, {"joint_positions_deg": [170, 0]})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION",
                         "the item maximum of the schema is evaluated after the limits")
        self.assertEqual(details(receipt)["bound"], 135)
        shape = _command(rpc, session, JOINTS, {"joint_positions_deg": "far"})
        self.assertEqual(error_code(shape), "MHS.CAPABILITY.INPUT_INVALID", "a shape error stays structural")
        self.assertEqual(calls, [])


class NestedLeafTests(unittest.TestCase):
    """fit-lab-instruments proto_psu.py / v_limits.py: a 48 V write passed a 5 V limit."""

    CH = {"type": "object", "properties": {"voltage": {"type": "number", "x-mhs-unit": "V", "maximum": 30},
                                           "output": {"type": "boolean"}}}
    STATE = {"ch1": {"voltage": 0.0, "output": False}, "ch2": {"voltage": 0.0, "output": False}}

    def _psu(self, capabilities, envelope):
        resources = [Resource("psu", "instrument.psu",
                              state_schema={"type": "object", "properties": {"ch1": self.CH, "ch2": self.CH}})]
        dev = device("mhs://localhost:7608/psu", capabilities, mode="hardware", risk="R2", envelope=envelope,
                     resources=resources, state=self.STATE, achieved_by=())
        return dev

    def test_the_repro_manifest_is_refused_at_load(self) -> None:
        # The envelope names 'voltage' and 'ch1.voltage' on a write binding with
        # no input schema: neither path resolves, so the limits could never be
        # enforced.  The 4b server served it and applied 48 V.
        dev = self._psu([Capability("cap.sensing.read.v1", "psu", verb="read"),
                         Capability("x-cap.psu.set.v1", "psu", verb="write")],
                        {"x-cap.psu.set.v1": {"voltage": {"max": 5.0, "unit": "V"}, "ch1.voltage": {"max": 5.0}}})
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost:7608", [dev], log_ready=False)
        self.assertEqual(caught.exception.rule, "limit-path-resolves")

    def test_nested_write_through_the_configure_class_is_refused(self) -> None:
        dev = self._psu([Capability(CONFIGURE, "psu", verb="write")],
                        {CONFIGURE: {"ch1.voltage": {"max": 5.0, "unit": "V"},
                                     "ch2.voltage": {"max": 5.0, "unit": "V"}}})
        server, rpc, session = serve(dev, armed=True)
        receipt = rpc("mhs.resource.write", session_id=session, resource_id="psu", deadline_ms=5000,
                      command_id=canonical.ulid(), patch={"ch1": {"voltage": 48.0, "output": True}})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION",
                         "not RESOURCE.STATE_INVALID: the state schema maximum is evaluated after the limits")
        self.assertEqual(details(receipt)["path"], "ch1.voltage")
        self.assertEqual(details(receipt)["value"], 48.0)
        self.assertEqual(details(receipt)["unit"], "V")
        self.assertEqual(dev.bridge.native(), [])
        self.assertEqual(dev.bridge.state["ch1"], {"voltage": 0.0, "output": False})
        ok = rpc("mhs.resource.write", session_id=session, resource_id="psu", deadline_ms=5000,
                 command_id=canonical.ulid(), patch={"ch2": {"voltage": 3.3}})
        self.assertEqual(ok["status"], "completed", ok)
        self.assertEqual(dev.bridge.state["ch2"]["voltage"], 3.3)
        beyond_schema = rpc("mhs.resource.write", session_id=session, resource_id="psu", deadline_ms=5000,
                            command_id=canonical.ulid(), patch={"ch1": {"output": "on"}})
        # WP-04 4d: the patch is the configure input (the writable state
        # properties), so a wrongly typed parameter is INPUT_INVALID.
        self.assertEqual(error_code(beyond_schema), "MHS.CAPABILITY.INPUT_INVALID", beyond_schema)

    def test_nested_input_of_an_extension_binding_is_refused(self) -> None:
        schema = {"type": "object", "properties": {"ch1": self.CH, "ch2": self.CH}}
        dev = self._psu([Capability("x-cap.psu.set.v1", "psu", verb="write", input_schema=schema)],
                        {"x-cap.psu.set.v1": {"ch1.voltage": {"max": 5.0, "unit": "V"},
                                              "ch2.voltage": {"max": 5.0, "unit": "V"}}})
        server, rpc, session = serve(dev, armed=True)
        # WP-04 4d: resource.write is served only by cap.device.configure.v1;
        # the patch is never passed as another write class's input.
        written = rpc.raw("mhs.resource.write", session_id=session, resource_id="psu", deadline_ms=5000,
                          command_id=canonical.ulid(), patch={"ch1": {"voltage": 48.0, "output": True}})
        self.assertEqual(error_code(written), "MHS.RESOURCE.NOT_WRITABLE", written)
        commanded = _command(rpc, session, "x-cap.psu.set.v1", {"ch1": {"voltage": 48.0, "output": True}})
        self.assertEqual(error_code(commanded), "MHS.SAFETY.ENVELOPE_VIOLATION", commanded)
        commanded = _command(rpc, session, "x-cap.psu.set.v1", {"ch2": {"voltage": 99.0}})
        self.assertEqual(error_code(commanded), "MHS.SAFETY.ENVELOPE_VIOLATION", commanded)
        self.assertEqual(details(commanded)["path"], "ch2.voltage")
        self.assertEqual(dev.bridge.native(), [])


class CartesianNestedTests(unittest.TestCase):
    """driver-authoring arm_probe.py and fit-robots-ros arm_probe.py."""

    def _driver_authoring(self, pose_rules):
        caps = [
            Capability(JOINTS, "arm", verb="invoke", exclusive=True,
                       input_schema={"type": "object", "required": ["joint_positions"],
                                     "properties": {"joint_positions": {"type": "array",
                                                                        "items": {"type": "number"}}}}),
            Capability(POSE, "arm", verb="invoke", exclusive=True,
                       input_schema={"type": "object", "required": ["position"],
                                     "properties": {"position": {"type": "object"}}}),
        ]
        envelope = {JOINTS: {"joint_positions": {"min": -1.57, "max": 1.57, "unit": "rad"}}, POSE: pose_rules}
        return device("mhs://localhost:7605/arm", caps, mode="hardware", risk="R2", envelope=envelope)

    def test_a_stray_top_level_key_is_refused_at_load(self) -> None:
        dev = self._driver_authoring({"position.z": {"min": 50, "max": 800, "unit": "mm"},
                                      "z": {"min": 50, "max": 800, "unit": "mm"}})
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost:7605", [dev], log_ready=False)
        self.assertEqual((caught.exception.rule, caught.exception.path), ("limit-path-resolves", "z"))

    def test_array_and_nested_limits_reach_no_native_call(self) -> None:
        dev = self._driver_authoring({"position.z": {"min": 50, "max": 800, "unit": "mm"}})
        server, rpc, session = serve(dev, armed=True)
        joints = _command(rpc, session, JOINTS, {"joint_positions": [3.0, -4.0]})
        self.assertEqual(error_code(joints), "MHS.SAFETY.ENVELOPE_VIOLATION", joints)
        self.assertEqual([item["path"] for item in details(joints)["violations"]],
                         ["joint_positions[0]", "joint_positions[1]"])
        pose = _command(rpc, session, POSE, {"position": {"x": 0, "y": 0, "z": -200}})
        self.assertEqual(error_code(pose), "MHS.SAFETY.ENVELOPE_VIOLATION", pose)
        self.assertEqual((details(pose)["path"], details(pose)["bound"], details(pose)["kind"]),
                         ("position.z", 50, "min"))
        self.assertEqual(dev.bridge.native(), [])
        self.assertNotIn("pos", dev.bridge.state)

    def _ros(self, pose_limits):
        caps = [
            Capability(JOINTS, "arm", input_schema=class_schema(JOINTS), output_schema=class_schema(JOINTS, "output_schema"),
                       limits={"joint_positions": {"min": -1.5, "max": 1.5, "unit": "rad"}}),
            Capability(POSE, "arm", input_schema=class_schema(POSE), output_schema=class_schema(POSE, "output_schema"),
                       limits=pose_limits),
            Capability(STOP, "arm"),
        ]
        envelope = {JOINTS: {"joint_positions": {"min": -1.5, "max": 1.5}}}
        return device("mhs://localhost:7610/so101", caps, mode="hardware", risk="R2", envelope=envelope,
                      achieved_by=(STOP,))

    def test_a_bound_on_an_object_field_is_refused_at_load(self) -> None:
        dev = self._ros({"position.z": {"min": 0, "max": 400, "unit": "mm"}, "position": {"min": 0, "max": 1}})
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost:7610", [dev], log_ready=False)
        self.assertEqual(caught.exception.rule, "limit-type")

    def test_catalogue_schemas_on_hardware(self) -> None:
        dev = self._ros({"position.z": {"min": 0, "max": 400, "unit": "mm"}})
        server, rpc, session = serve(dev, armed=True)
        fine = _command(rpc, session, JOINTS, {"joint_positions": [0.1, 0.2, 0, 0, 0, 0]})
        self.assertEqual(fine["status"], "completed", fine)
        joints = _command(rpc, session, JOINTS, {"joint_positions": [3.0, 0, 0, 0, 0, 0]})
        self.assertEqual(error_code(joints), "MHS.SAFETY.ENVELOPE_VIOLATION", joints)
        pose = _command(rpc, session, POSE, {"position": {"x": 0, "y": 0, "z": 9999},
                                             "orientation": {"roll": 0, "pitch": 0, "yaw": 0}})
        self.assertEqual(error_code(pose), "MHS.SAFETY.ENVELOPE_VIOLATION", pose)
        self.assertEqual(details(pose)["source"], "binding")
        self.assertEqual(dev.bridge.native(), [(JOINTS, {"joint_positions": [0.1, 0.2, 0, 0, 0, 0]})],
                         "only the in-range command reached the hardware")


class SimulatedArmTests(unittest.TestCase):
    """fit-robots-sim limits.py: [3.0, -3.0] rad against +/-1.57 completed."""

    def test_class_schema_with_an_envelope(self) -> None:
        dev = device("mhs://localhost:7611/arm", [Capability(JOINTS, "arm", input_schema=class_schema(JOINTS))],
                     envelope={JOINTS: {"joint_positions": {"min": -1.57, "max": 1.57, "unit": "rad",
                                                            "reason": "joint travel"}}})
        server, rpc, session = serve(dev)
        receipt = _command(rpc, session, JOINTS, {"joint_positions": [3.0, -3.0]})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(details(receipt)["reason"], "joint travel")
        self.assertEqual(len(details(receipt)["violations"]), 2)
        self.assertEqual(dev.bridge.native(), [])


class SchemaCatalogTests(unittest.TestCase):
    """schema-catalog exp1.py: a nested limit was ignored; class limits never applied."""

    def _exp(self, envelope):
        caps = [Capability(SETPOINT, "zone", input_schema=class_schema(SETPOINT)),
                Capability(POSE, "arm", input_schema=class_schema(POSE)),
                Capability(STOP, "arm", input_schema={"type": "object"})]
        resources = [Resource("zone", "thermal.zone", state_schema={"type": "object", "properties": {
                         "setpoint": {"type": "number", "x-mhs-unit": "Cel"}}}),
                     Resource("arm", "robot.arm", state_schema={"type": "object",
                                                                "properties": {"x": {"type": "number"}}})]
        return device("mhs://localhost/exp/d", caps, risk="R2", envelope=envelope, resources=resources,
                      achieved_by=(STOP,))

    def test_bound_on_an_object_is_refused(self) -> None:
        envelope = {POSE: {"position.x": {"min": -500, "max": 500, "unit": "mm", "reason": "workspace"},
                           "position": {"max": 500}}}
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost:7603", [self._exp(envelope)], log_ready=False)
        self.assertEqual(caught.exception.rule, "limit-type")

    def test_nested_and_class_limits_are_enforced(self) -> None:
        dev = self._exp({POSE: {"position.x": {"min": -500, "max": 500, "unit": "mm", "reason": "workspace"}}})
        server, rpc, session = serve(dev)
        pose = _command(rpc, session, POSE, {"position": {"x": 99999, "y": 0, "z": 0},
                                             "orientation": {"roll": 0, "pitch": 0, "yaw": 0}})
        self.assertEqual(error_code(pose), "MHS.SAFETY.ENVELOPE_VIOLATION", pose)
        self.assertEqual(details(pose)["path"], "position.x")
        setpoint = _command(rpc, session, SETPOINT, {"target_temperature": 5000})
        self.assertEqual(error_code(setpoint), "MHS.SAFETY.ENVELOPE_VIOLATION", setpoint)
        self.assertEqual((details(setpoint)["source"], details(setpoint)["bound"]), ("class", 300))
        self.assertEqual(details(setpoint)["provenance"], {"source": "class_default"})
        self.assertEqual(dev.bridge.native(), [])


class LoadTimeTests(unittest.TestCase):
    """fit-robots-sim-verifier typo.py, spec-verify p_typo.py, verify-schema-catalog widen.py."""

    THERMO = "cap.thermal.set_temperature.v1"  # not catalogued: compatibility mode serves it
    SCHEMA = {"type": "object", "properties": {"target_c": {"type": "number"}}, "required": ["target_c"]}

    def _typo(self, envelope):
        return device("mhs://localhost:7711/h", [Capability(self.THERMO, "h", input_schema=self.SCHEMA)],
                      mode="hardware", envelope=envelope, resources=[Resource("h", "thermal")])

    def test_typo_key_and_array_bound_are_refused_in_compatibility_mode(self) -> None:
        cases = (
            ({self.THERMO: {"target_celsius": {"max": 50, "reason": "typo key"}}}, "limit-path-resolves"),
            ({self.THERMO: {"target_c": {"max": [50], "reason": "array bound"}}}, "array-bound-length"),
            ({self.THERMO: {"target_c": {"maxx": 50}}}, "unknown-rule-member"),
            ({self.THERMO: {"target_c": {"max": 50, "per": "daily"}}}, "limit-rule-invalid"),
        )
        for envelope, rule in cases:
            with self.subTest(rule=rule):
                with self.assertRaises(LimitConfigError) as caught:
                    MHSServer("mhs://localhost:7711", [self._typo(envelope)], log_ready=False, armed=True)
                self.assertEqual(caught.exception.rule, rule)
                self.assertIn("mhs://localhost:7711/h", str(caught.exception))

    def test_an_envelope_key_that_is_no_capability_pattern_is_refused(self) -> None:
        # schema/examples/invalid/device.envelope-key-not-capability.json: a
        # field name one level too high never matched a binding (dropped).
        for key in ("target_c", "cap.thermal*"):
            with self.subTest(key=key):
                with self.assertRaises(LimitConfigError) as caught:
                    MHSServer("mhs://localhost:7711", [self._typo({key: {"target_c": {"max": 50}}})],
                              log_ready=False, armed=True)
                self.assertEqual((caught.exception.rule, caught.exception.path), ("envelope-key-invalid", key))

    def test_a_pattern_envelope_applies(self) -> None:
        dev = self._typo({"cap.thermal.*": {"target_c": {"max": 50, "reason": "pattern"}}})
        server, rpc, session = serve(dev, armed=True)
        receipt = _command(rpc, session, self.THERMO, {"target_c": 300})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(details(receipt)["source"], "envelope:cap.thermal.*")
        self.assertEqual(dev.bridge.native(), [])

    def test_conveyor_envelope_typo_is_refused(self) -> None:
        from mhs.reference import build_endpoint, build_server
        spec = build_endpoint("conveyor")
        step = next(item for item in spec.devices[0]["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        step.pop("limits", None)
        spec.devices[0]["safety"]["envelope"] = {"cap.world.step.v1": {"ticks": {"maxx": 5, "banana": 1}}}
        with self.assertRaises(LimitConfigError) as caught:
            with RecordWarnings():
                build_server(spec, log_ready=False)
        self.assertEqual(caught.exception.rule, "unknown-rule-member")

    def _widen(self, envelope):
        caps = [Capability(SETPOINT, "zone", input_schema={"type": "object",
                                                           "properties": {"target_temperature": {"type": "number"}}},
                           limits={"target_temperature": {"min": 0, "max": 100, "unit": "Cel"}})]
        return device("mhs://localhost/exp/d", caps, envelope=envelope,
                      resources=[Resource("zone", "thermal.zone")])

    def test_sources_intersect_instead_of_last_writer_wins(self) -> None:
        for envelope in ({SETPOINT: {"target_temperature": {"min": -50, "max": 1000, "unit": "Cel"}}},
                         {"cap.*": {"target_temperature": {"max": 1000}}}):
            with self.subTest(envelope=envelope):
                dev = self._widen(envelope)
                server, rpc, session = serve(dev)
                receipt = _command(rpc, session, SETPOINT, {"target_temperature": 500})
                self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
                self.assertEqual((details(receipt)["bound"], details(receipt)["source"]), (100, "binding"))
                self.assertEqual(dev.bridge.native(), [])

    def test_a_pattern_path_that_resolves_nowhere_is_refused(self) -> None:
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost:7703", [self._widen({"cap.thermal.*": {"ramp": {"max": 1}}})],
                      log_ready=False)
        self.assertEqual(caught.exception.rule, "limit-path-resolves")

    def test_an_envelope_for_no_bound_capability_is_refused_in_compatibility_mode(self) -> None:
        # SDK-03 (v11.py): the envelope key typo 'cap.thermal.set_point.v1' was
        # accepted and its limit dropped; verify-WP-04/4c U1 (a typo of the
        # capability id key) was still only a warning in compatibility mode.
        for key in ("cap.thermal.set_point.v1", "cap.motion.*"):
            with self.subTest(key=key):
                dev = self._widen({key: {"target_temperature": {"max": 50, "unit": "Cel"}}})
                with self.assertRaises(LimitConfigError) as caught:
                    with RecordWarnings():
                        MHSServer("mhs://localhost:7703", [dev], log_ready=False)
                self.assertEqual((caught.exception.rule, caught.exception.path), ("envelope-unbound", key))
        # The reserved test-profile namespace stays a warning: the reference
        # conveyor declares x-cap.mhs-test.delay.v1 outside its test profile.
        dev = self._widen({"x-cap.mhs-test.delay.v1": {"delay_ms": {"max": 5}}})
        with RecordWarnings() as warned:
            MHSServer("mhs://localhost:7703", [dev], log_ready=False)
        self.assertTrue(any("envelope-unbound" in text for text in strict_warnings(warned)))

    def test_strict_mode_reports_the_limit_finding(self) -> None:
        dev = device("mhs://localhost/limits/strict", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)],
                     envelope={DEG_JOINTS: {"joint": {"max": 45}}})
        with self.assertRaises(MHSStrictError) as caught:
            MHSServer("mhs://localhost/limits", [dev], log_ready=False, strict=True)
        self.assertIn("limits-invalid", caught.exception.rules)


class SiteLimitsTests(unittest.TestCase):
    """MHSServer(site_limits=...): the operator overlay only narrows (plan 3.5)."""

    DID = "mhs://localhost/limits/bath"

    def _bath(self, **kwargs):
        caps = [Capability(SETPOINT, "zone", limits={"target_temperature": {"min": -20, "max": 150, "unit": "Cel"}}),
                Capability(CONFIGURE, "zone", verb="write")]
        resources = [Resource("zone", "thermal.zone", state_schema={"type": "object", "properties": {
            "setpoint": {"type": "number", "x-mhs-unit": "Cel"},
            "pump_speed": {"type": "number", "x-mhs-unit": "/min"},
            "temperature": {"type": "number", "x-mhs-unit": "Cel", "readOnly": True}}})]
        return device(self.DID, caps, resources=resources, state={"setpoint": 20, "pump_speed": 0},
                      envelope={CONFIGURE: {"setpoint": {"min": -20, "max": 150, "unit": "Cel"},
                                            "pump_speed": "operator_required"}}, **kwargs)

    def _overlay(self, entry):
        return {"openmhs": "0.9", "devices": {self.DID: entry}}

    def test_overlay_narrows_and_fills_operator_required(self) -> None:
        overlay = self._overlay({
            "cap.thermal.setpoint.v1": {"target_temperature": {"max": 95, "unit": "Cel", "reason": "glycol"}},
            "setpoint": {"max": 95, "unit": "Cel", "source": "operator"},
            "pump_speed": {"min": 0, "max": 1200, "unit": "/min", "source": "operator"},
        })
        dev = self._bath()
        server, rpc, session = serve(dev, site_limits=overlay)
        receipt = _command(rpc, session, SETPOINT, {"target_temperature": 120})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual((details(receipt)["source"], details(receipt)["bound"]), ("overlay", 95))
        self.assertEqual(details(receipt)["provenance"], {"source": "operator"})
        written = rpc("mhs.resource.write", session_id=session, resource_id="zone", deadline_ms=5000,
                      patch={"pump_speed": 1500})
        self.assertEqual(error_code(written), "MHS.SAFETY.ENVELOPE_VIOLATION", written)
        fine = rpc("mhs.resource.write", session_id=session, resource_id="zone", deadline_ms=5000,
                   patch={"pump_speed": 600, "setpoint": 90})
        self.assertEqual(fine["status"], "completed", fine)

    def test_operator_required_without_an_overlay_is_limits_unset(self) -> None:
        dev = self._bath()
        server, rpc, session = serve(dev)
        receipt = rpc("mhs.resource.write", session_id=session, resource_id="zone", deadline_ms=5000,
                      patch={"pump_speed": 10})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(details(receipt)["paths"], ["pump_speed"])
        self.assertEqual(details(receipt)["reason"], "operator_required")
        self.assertEqual(dev.bridge.native(), [])
        other = rpc("mhs.resource.write", session_id=session, resource_id="zone", deadline_ms=5000,
                    patch={"setpoint": 30})
        self.assertEqual(other["status"], "completed", "a call that leaves the unset field out runs")

    def test_widening_and_unknown_targets_are_refused_at_load(self) -> None:
        cases = (
            (self._overlay({"cap.thermal.setpoint.v1": {"target_temperature": {"max": 400}}}), "overlay-narrows"),
            (self._overlay({"setpoint": {"max": 200, "source": "operator"}}), "overlay-narrows"),
            (self._overlay({"cap.motion.stop.v1": {"deceleration": {"max": 1}}}), "overlay-binding-known"),
            (self._overlay({"setpiont": {"max": 50}}), "limit-path-resolves"),
        )
        for overlay, rule in cases:
            with self.subTest(rule=rule):
                with self.assertRaises(LimitConfigError) as caught:
                    MHSServer("mhs://localhost/limits", [self._bath()], log_ready=False, site_limits=overlay)
                self.assertEqual(caught.exception.rule, rule)

    def test_an_invalid_site_limits_document_is_refused(self) -> None:
        for overlay in ({"devices": {self.DID: {"setpoint": "operator_required"}}},
                        {"devices": {self.DID: {"setpoint": {"max": 50, "source": "vendor_doc", "ref": "x"}}}},
                        ["not", "an", "object"]):
            with self.subTest(overlay=overlay):
                with self.assertRaises((LimitConfigError, ValueError, TypeError)):
                    MHSServer("mhs://localhost/limits", [self._bath()], log_ready=False, site_limits=overlay)

    def test_the_example_overlay_loads_from_a_file(self) -> None:
        example = EXAMPLES / "valid" / "site-limits.example-lab.json"
        document = json.loads(example.read_text())
        bath = "mhs://localhost:7400/lab/thermal-bath"
        self.assertIn(bath, document["devices"])
        with RecordWarnings() as warned:
            server = MHSServer("mhs://localhost:7400", [self._bath()], log_ready=False, site_limits=str(example))
        self.assertEqual(server.site_limits["devices"][bath]["setpoint"]["max"], 95)
        self.assertTrue(any("site_limits" in str(item.message) for item in warned),
                        "an overlay for devices this endpoint does not serve is reported")


class LimitsUnsetTests(unittest.TestCase):
    """Strict mode: hardware R1+ write/invoke numeric inputs need a limit (plan 3.5)."""

    def _arm(self, *, limits=None, mode="hardware"):
        caps = [Capability(JOINTS, "arm", limits=limits), Capability(STOP, "arm"),
                Capability("cap.device.describe.v1", "arm")]
        resources = [Resource("arm", "robot.arm", state_schema={"type": "object", "properties": {
            "q": {"type": "array", "items": {"type": "number"}}}})]
        return device("mhs://localhost/limits/hw", caps, mode=mode, risk="R1", resources=resources,
                      achieved_by=(STOP,))

    def _serve(self, dev, strict):
        return serve(dev, strict=strict, armed=True)

    def test_an_unlimited_numeric_input_is_refused_on_strict_hardware(self) -> None:
        dev = self._arm()
        server, rpc, session = self._serve(dev, True)
        receipt = _command(rpc, session, JOINTS, {"joint_positions": [0.1]})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(details(receipt)["paths"], ["joint_positions"])
        self.assertEqual(details(receipt)["reason"], "no_limit")
        self.assertEqual(dev.bridge.native(), [])
        findings = [item for item in server.strict_findings if item["rule"] == "limits-unset"]
        self.assertTrue(findings and not findings[0]["refuse"], server.strict_findings)
        stop = _command(rpc, session, STOP, {"deceleration": 2.0})
        self.assertEqual(stop["status"], "completed", "a stop is never refused for a missing limit")
        read = _command(rpc, session, "cap.device.describe.v1", {})
        self.assertNotEqual(error_code(read), "MHS.SAFETY.LIMITS_UNSET", "reads are unaffected")

    def test_a_declared_limit_lets_it_run_and_other_leaves_stay_unset(self) -> None:
        dev = self._arm(limits={"joint_positions": {"min": -1, "max": 1, "unit": "rad"}})
        server, rpc, session = self._serve(dev, True)
        receipt = _command(rpc, session, JOINTS, {"joint_positions": [0.1]})
        self.assertEqual(receipt["status"], "completed", receipt)
        timed = _command(rpc, session, JOINTS, {"joint_positions": [0.1], "duration_s": 3})
        self.assertEqual(error_code(timed), "MHS.SAFETY.LIMITS_UNSET", timed)
        self.assertEqual(details(timed)["paths"], ["duration_s"])
        self.assertEqual(len(dev.bridge.native()), 1)

    def test_operator_required_is_unset_until_an_overlay_fills_it(self) -> None:
        limits = {"joint_positions": {"min": -1, "max": 1, "unit": "rad"}, "duration_s": "operator_required"}
        dev = self._arm(limits=limits)
        server, rpc, session = self._serve(dev, True)
        timed = _command(rpc, session, JOINTS, {"joint_positions": [0.1], "duration_s": 3})
        self.assertEqual(error_code(timed), "MHS.SAFETY.LIMITS_UNSET", timed)
        self.assertEqual(details(timed)["reason"], "operator_required")
        overlay = {"devices": {dev.device_id: {JOINTS: {"duration_s": {"min": 0, "max": 5, "unit": "s"}}}}}
        dev = self._arm(limits=limits)
        server, rpc, session = serve(dev, strict=True, armed=True, site_limits=overlay)
        self.assertEqual(_command(rpc, session, JOINTS, {"joint_positions": [0.1], "duration_s": 3})["status"],
                         "completed")
        late = _command(rpc, session, JOINTS, {"joint_positions": [0.1], "duration_s": 30})
        self.assertEqual(error_code(late), "MHS.SAFETY.ENVELOPE_VIOLATION", late)
        self.assertEqual(details(late)["source"], "overlay")

    def test_a_stop_is_never_refused_for_a_missing_bound(self) -> None:
        caps = [Capability(JOINTS, "arm", limits={"joint_positions": {"min": -1, "max": 1, "unit": "rad"},
                                                  "duration_s": {"min": 0, "max": 5, "unit": "s"}}),
                Capability(STOP, "arm", limits={"deceleration": "operator_required"})]
        dev = device("mhs://localhost/limits/stop", caps, mode="hardware", risk="R1", achieved_by=(STOP,))
        server, rpc, session = serve(dev, strict=True, armed=True)
        stop = _command(rpc, session, STOP, {"deceleration": 3.0})
        self.assertEqual(stop["status"], "completed", stop)
        self.assertIn("operator-required-unset", [item["rule"] for item in server.strict_findings])

    def test_simulated_and_compatibility_mode_are_not_refused(self) -> None:
        for mode, strict in (("simulated", True), ("hardware", None)):
            with self.subTest(mode=mode, strict=strict):
                dev = self._arm(mode=mode)
                with RecordWarnings() as warned:
                    server, rpc, session = self._serve(dev, strict)
                receipt = _command(rpc, session, JOINTS, {"joint_positions": [0.1]})
                self.assertEqual(receipt["status"], "completed", receipt)
                if strict is None:
                    self.assertTrue(any("limits-unset" in text for text in strict_warnings(warned)))

    def test_an_extension_declared_read_is_not_exempt(self) -> None:
        # verify-WP-04/4c probes.py p1: the catalogue cannot confirm an
        # extension's verb (as for the latch and arming), so a mis-declared
        # actuating extension needs a limit on its numeric inputs too.
        probe = "x-cap.test.probe.v1"
        schema = {"type": "object", "properties": {"speed": {"type": "number"}}}
        caps = [Capability(probe, "arm", verb="read", input_schema=schema), Capability(STOP, "arm"),
                Capability("cap.device.describe.v1", "arm")]
        dev = device("mhs://localhost/limits/ext-read", caps, mode="hardware", risk="R1", achieved_by=(STOP,))
        server, rpc, session = serve(dev, strict=True, armed=True)
        receipt = _command(rpc, session, probe, {"speed": 9999})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.LIMITS_UNSET", receipt)
        self.assertEqual((details(receipt)["paths"], details(receipt)["reason"]), (["speed"], "no_limit"))
        self.assertEqual(dev.bridge.native(), [])
        self.assertIn(probe, [item.get("capability_id") for item in server.strict_findings
                              if item["rule"] == "limits-unset"])
        read = _command(rpc, session, "cap.device.describe.v1", {})
        self.assertNotEqual(error_code(read), "MHS.SAFETY.LIMITS_UNSET", "a catalogued read stays exempt")


class EvaluationOrderTests(unittest.TestCase):
    """Plan 3.6: latch (5), arming (6), structure (7), limits (8), schema (9), permit (10), interlocks (11)."""

    def _dev(self, **kwargs):
        caps = [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA), Capability(STOP, "arm")]
        envelope = {DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}}}
        return device("mhs://localhost/limits/order", caps, envelope=envelope, achieved_by=(STOP,), **kwargs)

    def test_a_binding_removed_after_start_up_invalidates_the_cached_plan(self) -> None:
        """WP-04 4c verifier minor (probe ``4c/r2/r7b.py``, mutation E): nothing
        guarded the ``plan.bindings == bindings`` staleness check of the cached
        limit plan.  A binding removed at runtime while the envelope still names
        it makes the next command on another binding MANIFEST_INVALID
        ``envelope-unbound``, before any bridge call."""
        other = "x-cap.test.other.v1"
        caps = [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA),
                Capability(other, "arm", input_schema=DEG_SCHEMA)]
        dev = device("mhs://localhost/limits/stale", caps,
                     envelope={DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}},
                               other: {"joints": {"min": -10, "max": 10, "unit": "deg"}}})
        server, rpc, session = serve(dev)
        self.assertEqual(_command(rpc, session, other, {"joints": [5, 0]})["status"], "completed")
        calls = len(dev.bridge.native())
        dev.capabilities.remove(caps[0])
        del dev._by_capability[DEG_JOINTS]
        receipt = _command(rpc, session, other, {"joints": [5, 0]})
        self.assertEqual(error_code(receipt), "MHS.ADAPTER.MANIFEST_INVALID", receipt)
        self.assertEqual(details(receipt)["rule"], "envelope-unbound", receipt)
        self.assertEqual(len(dev.bridge.native()), calls, "no bridge call")

    def test_latch_and_arming_come_before_the_limits(self) -> None:
        dev = self._dev()
        server, rpc, session = serve(dev)
        rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=2000)
        latched = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
        self.assertEqual(error_code(latched), "MHS.SAFETY.ESTOP_ENGAGED", latched)
        hardware = self._dev(mode="hardware")
        server, rpc, session = serve(hardware, armed=False)
        unarmed = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
        self.assertEqual(error_code(unarmed), "MHS.AUTH.HARDWARE_DISABLED", unarmed)

    def test_limits_come_before_permits_and_interlocks(self) -> None:
        dev = self._dev(requires_permit=[DEG_JOINTS],
                        interlocks=[{"id": "door", "required_for": [DEG_JOINTS]}])
        dev.bridge.interlock_states["door"] = "open"
        server, rpc, session = serve(dev)
        reads = dev.bridge.interlock_reads  # session.open reports the safety context
        receipt = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(dev.bridge.interlock_reads, reads, "interlocks are read after the limits")
        no_permit = _command(rpc, session, DEG_JOINTS, {"joints": [10, 0]})
        self.assertEqual(error_code(no_permit), "MHS.SAFETY.PERMIT_INVALID", no_permit)
        self.assertEqual(dev.bridge.interlock_reads, reads, "interlocks are read after the permit")
        self.assertEqual(dev.bridge.native(), [])

    def test_structure_before_limits_and_schema_bounds_after(self) -> None:
        schema = copy.deepcopy(DEG_SCHEMA)
        schema["properties"]["joints"]["items"]["maximum"] = 30
        caps = [Capability(DEG_JOINTS, "arm", input_schema=schema)]
        dev = device("mhs://localhost/limits/two-pass", caps,
                     envelope={DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}}})
        server, rpc, session = serve(dev)
        shape = _command(rpc, session, DEG_JOINTS, {"joints": ["a", 0]})
        self.assertEqual(error_code(shape), "MHS.CAPABILITY.INPUT_INVALID", shape)
        beyond_limit = _command(rpc, session, DEG_JOINTS, {"joints": [50, 0]})
        self.assertEqual(error_code(beyond_limit), "MHS.SAFETY.ENVELOPE_VIOLATION", beyond_limit)
        beyond_schema = _command(rpc, session, DEG_JOINTS, {"joints": [40, 0]})
        self.assertEqual(error_code(beyond_schema), "MHS.CAPABILITY.INPUT_INVALID",
                         "the remaining schema bound is evaluated after the limits")
        self.assertEqual(dev.bridge.native(), [])

    def test_a_limit_narrowed_after_start_up_is_enforced(self) -> None:
        dev = self._dev()
        server, rpc, session = serve(dev)
        self.assertEqual(_command(rpc, session, DEG_JOINTS, {"joints": [40, 0]})["status"], "completed")
        dev.safety.envelope[DEG_JOINTS] = {"joints": {"min": -10, "max": 10, "unit": "deg"}}
        receipt = _command(rpc, session, DEG_JOINTS, {"joints": [40, 0]})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(details(receipt)["bound"], 10)
        dev.safety.envelope[DEG_JOINTS] = {"joints": {"maxx": 10}}
        broken = _command(rpc, session, DEG_JOINTS, {"joints": [1, 0]})
        self.assertEqual(broken["status"], "rejected", "a limit that no longer compiles fails closed")
        self.assertEqual(error_code(broken), "MHS.ADAPTER.MANIFEST_INVALID", broken)

    def test_an_envelope_broken_at_device_level_after_start_up_fails_closed(self) -> None:
        # verify-WP-04/4c probes2.py M1: the device-level load-time rules run
        # again when the envelope changes, not only the per-binding ones.
        enforced = {DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}}}
        for broken, rule in (({"joints": {"min": -45, "max": 45, "unit": "deg"}}, "envelope-key-invalid"),
                             ({"x-cap.test.*": {"jionts": {"max": 45}}}, "limit-path-resolves"),
                             ({"x-cap.test.joint.v1": {"joints": {"max": 45}}}, "envelope-unbound")):
            with self.subTest(rule=rule):
                dev = self._dev()
                server, rpc, session = serve(dev)
                before = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
                self.assertEqual(error_code(before), "MHS.SAFETY.ENVELOPE_VIOLATION", before)
                dev.safety.envelope = copy.deepcopy(broken)
                receipt = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.ADAPTER.MANIFEST_INVALID", receipt)
                self.assertEqual((details(receipt)["reason"], details(receipt)["rule"]), ("limits_invalid", rule))
                self.assertEqual(dev.bridge.native(), [], "no bridge call")
                dev.safety.envelope = copy.deepcopy(enforced)
                restored = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]})
                self.assertEqual(error_code(restored), "MHS.SAFETY.ENVELOPE_VIOLATION", restored)
                self.assertEqual(_command(rpc, session, DEG_JOINTS, {"joints": [10, 0]})["status"], "completed")
        dev = self._dev()
        server, rpc, session = serve(dev)
        dev.safety.envelope["joints"] = {"max": 45}  # an in-place edit is seen too
        inplace = _command(rpc, session, DEG_JOINTS, {"joints": [10, 0]})
        self.assertEqual((error_code(inplace), details(inplace).get("rule")),
                         ("MHS.ADAPTER.MANIFEST_INVALID", "envelope-key-invalid"), inplace)
        self.assertEqual(dev.bridge.native(), [])


class CumulativeTests(unittest.TestCase):
    """Cumulative budgets come from EffectiveLimits.cumulative."""

    CAP = "x-cap.test.dose.v1"
    SCHEMA = {"type": "object", "properties": {"dose": {"type": "number", "x-mhs-unit": "mL"}}}

    def _dose(self, rules):
        return device("mhs://localhost/limits/dose", [Capability(self.CAP, "arm", input_schema=self.SCHEMA)],
                      envelope={self.CAP: rules})

    def test_the_legacy_limit_member_is_refused(self) -> None:
        with self.assertRaises(LimitConfigError) as caught:
            MHSServer("mhs://localhost/limits", [self._dose({"dose": {"limit": 10, "per": "rolling_1h"}})],
                      log_ready=False)
        self.assertEqual(caught.exception.rule, "unknown-rule-member")

    def test_budget_is_intersected_and_a_negative_amount_never_refunds(self) -> None:
        dev = self._dose({"dose": {"max": 10, "per": "rolling_1h", "unit": "mL"}})
        dev.capabilities[0].limits = {"dose": {"max": 6, "per": "rolling_1h", "unit": "mL"}}
        server, rpc, session = serve(dev)
        self.assertEqual(_command(rpc, session, self.CAP, {"dose": 4})["status"], "completed")
        refund = _command(rpc, session, self.CAP, {"dose": -1})
        self.assertEqual(refund["status"], "completed", refund)
        over = _command(rpc, session, self.CAP, {"dose": 2})
        self.assertEqual(error_code(over), "MHS.SAFETY.CUMULATIVE_LIMIT",
                         "the budget counts magnitudes: 4 + |-1| + 2 > 6 (the binding narrows the envelope)")
        self.assertEqual((details(over)["limit"], details(over)["used"]), (6, 5))
        self.assertEqual(len(dev.bridge.native()), 2)


class PublishedLimitsTests(unittest.TestCase):
    """devices.get publishes the effective limits and a rendered reference file."""

    def test_reference_arm_publishes_effective_limits_and_a_reference(self) -> None:
        narrowed = {JOINTS: {"joint_positions_deg": {"min": -45, "max": 45, "unit": "deg", "reason": "operator"}}}
        server, rpc, session, dev, calls = reference_arm(narrowed)
        got = rpc("mhs.devices.get", device_id=dev.device_id)
        binding = next(item for item in got["capabilities"] if item["capability_id"] == JOINTS)
        effective = binding["x-mhs-effective-limits"]
        self.assertEqual(effective["limits"]["joint_positions_deg"]["max"], 45)
        self.assertEqual(effective["limits"]["joint_positions_deg"]["unit"], "deg")
        self.assertIn("reference", got)
        self.assertEqual(validate_reference(got["reference"]), [])
        action = next(item for item in got["reference"]["actions"] if item["cap_id"] == JOINTS)
        field = next(item for item in action["inputs"] if item["name"] == "joint_positions_deg")
        self.assertEqual(field["limit"]["max"], 45)
        self.assertEqual(SchemaStore().validate(got, "device.schema.json"), [])
        again = rpc("mhs.devices.get", device_id=dev.device_id)
        self.assertEqual(canonical.jcs(again["reference"]), canonical.jcs(got["reference"]), "deterministic")

    def test_overlay_is_recorded_in_the_reference(self) -> None:
        bath = SiteLimitsTests()._bath()
        overlay = {"openmhs": "0.9", "devices": {SiteLimitsTests.DID: {
            "setpoint": {"max": 95, "unit": "Cel", "source": "operator"},
            "pump_speed": {"min": 0, "max": 1200, "unit": "/min", "source": "operator"}}}}
        server, rpc, session = serve(bath, site_limits=overlay)
        got = rpc("mhs.devices.get", device_id=bath.device_id)
        reference = got["reference"]
        self.assertEqual(reference["overlay"]["digest"], canonical.digest(overlay))
        self.assertIn("setpoint.max: 150 -> 95", reference["overlay"]["narrowed"])
        adjust = next(item for item in reference["adjusts"] if item["name"] == "setpoint")
        self.assertEqual(adjust["limit"]["max"], 95)
        configure = next(item for item in got["capabilities"] if item["capability_id"] == CONFIGURE)
        self.assertEqual(configure["x-mhs-effective-limits"]["limits"]["pump_speed"]["max"], 1200)

    def test_an_uncatalogued_binding_reports_why_no_reference_is_rendered(self) -> None:
        dev = device("mhs://localhost/limits/uncatalogued",
                     [Capability("cap.thermal.set_temperature.v1", "arm",
                                 input_schema={"type": "object", "properties": {"t": {"type": "number"}}},
                                 limits={"t": {"max": 50}})])
        with RecordWarnings():
            server, rpc, session = serve(dev)
        got = rpc("mhs.devices.get", device_id=dev.device_id)
        self.assertNotIn("reference", got)
        self.assertIn("unknown capability class", got["x-mhs-reference-error"])
        self.assertEqual(got["capabilities"][0]["x-mhs-effective-limits"]["limits"], {"t": {"max": 50}})

    def test_the_overlay_is_recorded_only_for_the_devices_it_names(self) -> None:
        bath = SiteLimitsTests()._bath()
        other = device("mhs://localhost/limits/other", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)])
        overlay = {"devices": {SiteLimitsTests.DID: {"setpoint": {"max": 95, "source": "operator"},
                                                     "pump_speed": {"max": 10, "source": "operator"}}}}
        server = MHSServer("mhs://localhost/limits", [bath, other], log_ready=False, site_limits=overlay)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertIsNotNone(rpc("mhs.devices.get", device_id=bath.device_id)["reference"]["overlay"])
        self.assertIsNone(rpc("mhs.devices.get", device_id=other.device_id)["reference"]["overlay"])


class LateDeviceLimitTests(unittest.TestCase):
    """A device put in MHSServer.devices after start-up gets the same limit rules."""

    def test_strict_late_device_with_a_broken_limit_is_refused(self) -> None:
        first = device("mhs://localhost/limits/first", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)])
        server = MHSServer("mhs://localhost/limits", [first], log_ready=False, strict=True)
        late = device("mhs://localhost/limits/late", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)],
                      envelope={DEG_JOINTS: {"joints": {"maxx": 45}}})
        server.devices[late.device_id] = late
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        response = rpc.raw("mhs.session.open", device_ids=[late.device_id], mode="simulated")
        refusal = response.get("error") or {}
        data = refusal.get("data") or {}
        self.assertEqual(data.get("mhs_code"), "MHS.ADAPTER.MANIFEST_INVALID", response)
        self.assertIn("limits-invalid", json.dumps(data))

    def test_compatibility_late_device_is_checked_on_first_use(self) -> None:
        first = device("mhs://localhost/limits/first", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)])
        server = MHSServer("mhs://localhost/limits", [first], log_ready=False)
        late = device("mhs://localhost/limits/late", [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)],
                      envelope={DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}}})
        server.devices[late.device_id] = late
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        session = rpc("mhs.session.open", device_ids=[late.device_id], mode="simulated")["session_id"]
        receipt = _command(rpc, session, DEG_JOINTS, {"joints": [0, 90]}, device_id=late.device_id)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(details(receipt)["path"], "joints[1]")
        self.assertEqual(late.bridge.native(), [])

    LATE = "mhs://localhost/limits/late"

    def _late_device(self, envelope):
        caps = [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA), Capability(STOP, "arm")]
        return device(self.LATE, caps, envelope=envelope, achieved_by=(STOP,))

    def test_device_level_limit_defects_of_a_compatibility_late_device_fail_closed(self) -> None:
        # verify-WP-04/4c probes2.py L1/L2: construction refuses each of these
        # devices; added to MHSServer.devices afterwards, the declared limit
        # must not be dropped silently (the bridge was called).
        cases = (
            ({"joints": {"min": -45, "max": 45, "unit": "deg"}}, None, "envelope-key-invalid"),
            ({"x-cap.test.*": {"jionts": {"max": 45, "unit": "deg"}}}, None, "limit-path-resolves"),
            ({"x-cap.test.joint.v1": {"joints": {"min": -45, "max": 45, "unit": "deg"}}}, None,
             "envelope-unbound"),
            ({DEG_JOINTS: {"joints": {"min": -45, "max": 45, "unit": "deg"}}},
             {"openmhs": "0.9", "devices": {self.LATE: {"x-cap.test.other.v1": {"x": {"max": 1}}}}},
             "overlay-binding-known"),
        )
        for envelope, overlay, rule in cases:
            with self.subTest(rule=rule):
                with self.assertRaises(LimitConfigError) as caught:
                    with RecordWarnings():
                        MHSServer("mhs://localhost/limits", [self._late_device(envelope)], log_ready=False,
                                  site_limits=overlay)
                self.assertEqual(caught.exception.rule, rule, "the same device is refused at construction")
                first = device("mhs://localhost/limits/first",
                               [Capability(DEG_JOINTS, "arm", input_schema=DEG_SCHEMA)])
                with RecordWarnings():
                    server = MHSServer("mhs://localhost/limits", [first], log_ready=False, site_limits=overlay)
                late = self._late_device(envelope)
                server.devices[late.device_id] = late
                rpc = Rpc(server)
                rpc("mhs.hello", protocol_versions=["1.0"])
                session = rpc("mhs.session.open", device_ids=[late.device_id], mode="simulated")["session_id"]
                receipt = _command(rpc, session, DEG_JOINTS, {"joints": [90, 0]}, device_id=late.device_id)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.ADAPTER.MANIFEST_INVALID", receipt)
                self.assertEqual((details(receipt)["reason"], details(receipt)["rule"]), ("limits_invalid", rule))
                self.assertEqual(late.bridge.native(), [], "no bridge call")
                published = rpc("mhs.devices.get", device_id=late.device_id)
                entry = next(item for item in published["capabilities"] if item["capability_id"] == DEG_JOINTS)
                self.assertEqual(entry["x-mhs-effective-limits"]["error"]["rule"], rule, entry)
                stop = _command(rpc, session, STOP, {}, device_id=late.device_id)
                self.assertEqual(stop["status"], "completed", "a stop is never refused for a limit defect")


if __name__ == "__main__":
    unittest.main()
