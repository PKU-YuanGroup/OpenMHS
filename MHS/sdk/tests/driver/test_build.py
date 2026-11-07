"""The Driver class -> manifest mapping: parameters, bindings, limits, risk, safety, definition errors."""

from __future__ import annotations

import unittest

from mhs import catalog, reference_file
from mhs.driver import (
    Driver,
    DriverDefinitionError,
    Fact,
    Field,
    Limit,
    action,
    build_device,
    build_manifest,
    build_reference,
    estop,
    interlock,
    read,
    write,
)
from mhs.driver.build import strict_findings
from mhs.schema import default_store

from tests.driver import support


def binding(manifest, capability_id):
    return next(item for item in manifest["capabilities"] if item["capability_id"] == capability_id)


def problems_of(cls):
    with unittest.TestCase().assertRaises(DriverDefinitionError) as caught:
        cls.driver_model()
    return "\n".join(caught.exception.problems)


class ManifestMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = build_manifest(support.Bath)

    def test_manifest_validates_against_the_device_schema(self) -> None:
        self.assertEqual(default_store().validate(self.manifest, "device.schema.json"), [])
        self.assertEqual(default_store().validate(build_manifest(support.Arm), "device.schema.json"), [])

    def test_parameters_become_one_resource_with_read_only_flags_and_units(self) -> None:
        [resource] = self.manifest["resources"]
        self.assertEqual(resource["kind"], "thermal.zone")
        properties = resource["state_schema"]["properties"]
        self.assertEqual(properties["temperature"], {"type": "number", "x-mhs-unit": "Cel",
                                                     "description": "Bath temperature", "readOnly": True})
        self.assertNotIn("readOnly", properties["setpoint"])
        self.assertEqual(properties["setpoint"]["x-mhs-unit"], "Cel")
        self.assertEqual(properties["pump_speed"]["x-mhs-unit"], "/min")
        self.assertFalse(resource["state_schema"]["additionalProperties"])

    def test_writable_parameters_bind_the_configure_class_with_their_limits(self) -> None:
        configure = binding(self.manifest, "cap.device.configure.v1")
        self.assertEqual(configure["limits"]["setpoint"],
                         {"min": -20, "max": 150, "source": "upstream_code", "ref": "julabo/julabo.py:88"})
        self.assertEqual(configure["limits"]["pump_speed"], "operator_required")
        self.assertNotIn("input_schema", configure)  # derived from the writable state

    def test_catalogue_actions_carry_the_method_name_and_the_narrowed_class_schema(self) -> None:
        setpoint = binding(self.manifest, "cap.thermal.setpoint.v1")
        self.assertEqual(setpoint["x-mhs-name"], "ramp_to")
        self.assertEqual(sorted(setpoint["input_schema"]["properties"]), ["rate", "target_temperature"])
        self.assertEqual(setpoint["input_schema"]["required"], ["target_temperature"])
        self.assertFalse(setpoint["input_schema"]["additionalProperties"])
        self.assertEqual(setpoint["constraints"], {"long_running": True, "max_duration_ms": 3600000,
                                                   "cancellable": True})
        self.assertEqual(setpoint["limits"]["target_temperature"]["max"], 150)
        self.assertNotIn("verb", setpoint)  # the class verb applies (strict mode publishes it)

    def test_extension_actions_carry_an_inline_schema_and_its_digest(self) -> None:
        heater = binding(self.manifest, "x-cap.julabo.heater_off.v1")
        self.assertEqual(heater["verb"], "invoke")
        self.assertEqual(heater["title"], "Switch the heater off")
        self.assertEqual(heater["output_schema"]["required"], ["heater_off"])
        self.assertEqual(heater["x-mhs-schema-digest"],
                         catalog.extension_digest(heater["input_schema"], heater["output_schema"]))
        # the same inline schema as the WP-02 example manifest pins the same digest
        self.assertEqual(heater["x-mhs-schema-digest"],
                         "sha256:d782e41af9e646924c2b68be3e7bed238a2ca7f449bfa0081d73863ca831c193")

    def test_safety_object(self) -> None:
        safety = self.manifest["safety"]
        self.assertEqual(safety["risk_class"], "R2")
        self.assertEqual(safety["estop"], {"kind": "software", "latching": True, "native": "stop", "latency_ms": 200})
        self.assertEqual(safety["safe_state"], {"description": "heater off, pump stopped",
                                                "achieved_by": ["x-cap.julabo.heater_off.v1"]})
        self.assertEqual(safety["interlocks"], [{"id": "lid_closed", "description": "Bath lid closed",
                                                 "required_for": ["cap.thermal.setpoint.v1"], "source": "hardware"}])
        arm = build_manifest(support.Arm)["safety"]["estop"]
        self.assertEqual(arm["kind"], "both")
        self.assertEqual(arm["native"], "emergency_stop")
        self.assertEqual(arm["physical_ref"], "red mushroom button on the control box")

    def test_identity_vendor_tags_and_provenance(self) -> None:
        self.assertEqual(self.manifest["device_id"], "mhs://localhost/lab/bath")
        self.assertEqual(self.manifest["mode"], "hardware")
        self.assertEqual(self.manifest["vendor"], {"name": "Julabo"})
        self.assertEqual(self.manifest["model"], "CF41")
        self.assertEqual(self.manifest["display_name"], "Julabo CF41")
        self.assertEqual(self.manifest["profile"], {"tags": ["circulator", "thermal bath"]})
        self.assertNotIn("fidelity", self.manifest)
        upstream = {"repo": "https://github.com/example/bath", "commit": "b" * 40}
        manifest = build_manifest(support.Bath, upstream=upstream)
        self.assertEqual(manifest["provenance"], {"generated_by": "mhs.driver", "source_repo": upstream["repo"],
                                                  "source_commit": upstream["commit"]})

    def test_per_element_and_nested_limit_placement(self) -> None:
        manifest = build_manifest(support.Arm)
        joints = binding(manifest, "cap.motion.joint_position.v1")
        rule = joints["limits"]["joint_positions"]
        self.assertEqual(rule["names"], support.JOINTS)
        self.assertEqual(len(rule["min"]), 6)
        self.assertEqual(joints["input_schema"]["properties"]["joint_positions"],
                         {"items": {"type": "number", "x-mhs-unit": "rad"}, "minItems": 6, "maxItems": 6})
        pose = binding(manifest, "cap.motion.cartesian_pose.v1")
        self.assertEqual(sorted(pose["limits"]), ["position.x", "position.y", "position.z"])

    def test_nested_refinement_of_a_class_object_inherits_its_members(self) -> None:
        class Pose(Driver):
            device_id, device_kind, mode, risk = "pose", "robot.arm", "hardware", "R1"

            @action(cap="cap.motion.cartesian_pose.v1", input={"position": Field(properties={
                "z": Field(limit=Limit(min=0, max=500, source="vendor_doc", ref="arm.pdf:3"))})})
            def move(self, position):
                return {"reached": True}

        model = Pose.driver_model()
        [move] = [item for item in model.bindings if item.capability_id == "cap.motion.cartesian_pose.v1"]
        self.assertEqual(move.limits, {"position.z": {"min": 0, "max": 500, "source": "vendor_doc",
                                                      "ref": "arm.pdf:3"}})
        position = move.effective.input_schema["properties"]["position"]
        self.assertEqual(position["required"], ["x", "y", "z"])
        self.assertFalse(position["additionalProperties"])
        self.assertEqual(position["properties"]["z"]["x-mhs-unit"], "mm")

    def test_relative_limit_paths_on_fields(self) -> None:
        class Gripper(Driver):
            device_id, device_kind, mode, risk = "gripper", "robot.gripper", "hardware", "R1"

            @action(name="x-cap.example.grip.v1", input={
                "fingers": Field("array", length=2, items=Field("object", properties={
                    "force": Field("number", unit="N", limit=Limit(max=40, source="vendor_doc", ref="g.pdf:2"))})),
                "width": Field("number", unit="mm", limit=Limit(min=0, max=85, source="vendor_doc", ref="g.pdf:3")),
                "offset": Field("array", items="number", length=3, unit="mm",
                                limit=Limit(max=5, path="[2]", source="vendor_doc", ref="g.pdf:4"))})
            def grip(self, fingers, width, offset):
                return None

        limits = binding(build_manifest(Gripper), "x-cap.example.grip.v1")["limits"]
        self.assertEqual(sorted(limits), ["fingers[*].force", "offset[2]", "width"])
        self.assertEqual(strict_findings(Gripper), [])

    def test_risk_is_the_highest_of_declared_action_parameter_and_class_floors(self) -> None:
        class Low(Driver):
            device_id, device_kind, mode, risk = "low", "thermal.zone", "hardware", "R0"
            safe_state = "off"

            @action(cap="cap.thermal.setpoint.v1")
            def go(self, target_temperature):
                return {"setpoint": target_temperature}

            @estop
            def stop(self):
                pass

        model = Low.driver_model()
        self.assertEqual((model.declared_risk, model.risk_floor, model.risk), ("R0", "R2", "R2"))
        self.assertEqual(build_manifest(Low)["safety"]["risk_class"], "R2")

        class Raised(Driver):
            device_id, device_kind, mode, risk = "raised", "instrument", "hardware", "R0"

            @write("dose", unit="mL", limit=Limit(max=5, source="vendor_doc", ref="d.pdf:1"), risk="R3")
            def set_dose(self, value):
                pass

        self.assertEqual(Raised.driver_model().risk, "R3")

    def test_reads_are_not_bindings_but_a_device_needs_one(self) -> None:
        class ReadOnly(Driver):
            device_id, device_kind, mode = "read-only", "sensor", "hardware"

            @read("voltage", unit="V")
            def voltage(self):
                return 1.0

        self.assertIn("declares no capability", problems_of(ReadOnly))

        class Meter(ReadOnly):
            device_id, device_kind = "meter", "instrument.dmm"

            @action(cap="cap.measure.voltage.v1")
            def measure_voltage(self):
                return self.voltage()

        manifest = build_manifest(Meter)
        self.assertEqual([item["capability_id"] for item in manifest["capabilities"]], ["cap.measure.voltage.v1"])
        self.assertTrue(manifest["resources"][0]["state_schema"]["properties"]["voltage"]["readOnly"])
        reference = build_reference(Meter)
        self.assertEqual([item["name"] for item in reference["measures"]], ["voltage", "measure_voltage"])

    def test_a_driver_without_estop_publishes_a_software_only_latch(self) -> None:
        class Plain(Driver):
            device_id, device_kind, mode = "plain", "instrument.dmm", "hardware"

            @action(cap="cap.measure.voltage.v1")
            def measure(self):
                return 1.0

        self.assertIsNone(build_manifest(Plain)["safety"]["estop"]["native"])
        from mhs.bridge.base import Bridge

        self.assertIs(Plain.estop, Bridge.estop)
        self.assertIsNot(support.Bath.estop, Bridge.estop)


class DeclarationAccessTests(unittest.TestCase):
    def test_native_and_safe_state_read_as_declarations_on_the_class(self) -> None:
        self.assertEqual(support.Bath.native, "julabo.julabo:JulaboCF")
        self.assertEqual(support.Bath.safe_state, "heater off, pump stopped")
        driver = support.Bath(backend="fake")
        try:
            self.assertIsInstance(driver.native, support.FakeBath)
            self.assertTrue(callable(driver.safe_state))
        finally:
            driver.close()


class DefinitionErrorTests(unittest.TestCase):
    def test_method_parameters_must_be_class_fields(self) -> None:
        class Drift(Driver):
            device_id, device_kind, risk = "drift", "thermal.zone", "R2"

            @action(cap="cap.thermal.setpoint.v1")
            def go(self, target, rate=None):
                return {"setpoint": target}

        text = problems_of(Drift)
        self.assertIn("['target'] is not a field of cap.thermal.setpoint.v1", text)
        self.assertIn("requires ['target_temperature']", text)

    def test_unit_and_type_drift_is_a_load_error(self) -> None:
        class UnitDrift(Driver):
            device_id, device_kind, risk = "unit-drift", "thermal.zone", "R2"

            @action(cap="cap.thermal.setpoint.v1", input={"target_temperature": Field(unit="K")})
            def go(self, target_temperature):
                return {"setpoint": target_temperature}

        self.assertIn("drifts from cap.thermal.setpoint.v1 (unit-differs", problems_of(UnitDrift))

        class TypeDrift(Driver):
            device_id, device_kind, risk = "type-drift", "thermal.zone", "R2"

            @action(cap="cap.thermal.setpoint.v1", input={"wait": Field("string")})
            def go(self, target_temperature, wait=False):
                return {"setpoint": target_temperature}

        self.assertIn("type-differs", problems_of(TypeDrift))

    def test_unknown_classes_kinds_and_extension_fields(self) -> None:
        class Unknown(Driver):
            device_id, device_kind = "unknown", "thermal.zone"

            @action(cap="cap.thermal.teleport.v1")
            def go(self):
                pass

        self.assertIn("not in the capability catalogue", problems_of(Unknown))

        class Kind(Driver):
            device_id, device_kind, risk = "kind", "robot.arm", "R2"

            @action(cap="cap.thermal.setpoint.v1")
            def go(self, target_temperature):
                pass

        self.assertIn("does not bind resource kind 'robot.arm'", problems_of(Kind))

        class Inline(Driver):
            device_id, device_kind = "inline", "instrument"

            @action(name="x-cap.example.pulse.v1")
            def pulse(self, width):
                pass

        self.assertIn("x-cap input ['width'] needs a Field in input", problems_of(Inline))

    def test_structural_errors_are_collected(self) -> None:
        class Broken(Driver):
            device_id, device_kind = "broken", "instrument"
            tags = ["Not A Tag"]

            @read("x")
            def read_x(self, extra):
                return 1

            @write("y", limit=Limit(max=1, source="vendor_doc", ref="a:1"))
            def set_y(self):
                pass

            @estop
            def stop_a(self):
                pass

            @estop
            def stop_b(self):
                pass

            @action(name="x-cap.example.slow.v1", long_running=True)
            def slow(self):
                pass

            @action(cap="cap.device.configure.v1")
            def configure(self):
                pass

            @interlock("door", blocks=["cap.motion.stop.v1"])
            def door(self):
                return True

        text = problems_of(Broken)
        for expected in ("tags must be short lowercase keywords", "getter read_x() takes no parameters",
                         "setter set_y() takes exactly one parameter", "only one @estop method",
                         "long_running=True needs max_duration_ms", "is generated from the @write parameters",
                         "blocks 'cap.motion.stop.v1', which matches no bound capability"):
            self.assertIn(expected, text)

    def test_reserved_names_and_contract_overrides(self) -> None:
        class Reserved(Driver):
            device_id, device_kind = "reserved", "instrument"

            @read("status", type="string")
            def describe(self):
                return "ok"

            def call(self, capability_id, args=None, ctx=None):  # noqa: D401 - deliberately wrong
                return {}

        text = problems_of(Reserved)
        self.assertIn("method name 'describe' is reserved", text)
        self.assertIn("call() is part of the Bridge contract", text)

    def test_safe_state_actions_take_no_input_and_safe_state_is_text(self) -> None:
        class NeedsInput(Driver):
            device_id, device_kind = "needs-input", "instrument"

            @action(name="x-cap.example.park.v1", safe_state=True, input={"speed": Field("number")})
            def park(self, speed):
                pass

        self.assertIn("a safe_state action is called with an empty input", problems_of(NeedsInput))

        class Method(Driver):
            device_id, device_kind = "method", "instrument"

            def safe_state(self, ctx=None):
                return {}

        self.assertIn("safe_state is a description string", problems_of(Method))

    def test_limits_need_a_bound_and_valid_members(self) -> None:
        with self.assertRaises(DriverDefinitionError):
            Limit(source="vendor_doc", ref="a:1")
        with self.assertRaises(DriverDefinitionError):
            Limit(max=1, source="vendor_doc")  # a cited source needs ref
        with self.assertRaises(DriverDefinitionError):
            Limit(min=5, max=1)
        with self.assertRaises(DriverDefinitionError):
            Limit(min=[0, 0], max=[1, 1, 1])
        with self.assertRaises(TypeError):
            Limit(maxx=150)  # a typo can never silently drop a bound
        with self.assertRaises(DriverDefinitionError):
            Limit.operator_required("")
        self.assertEqual(Limit.operator_required("why").to_json(), "operator_required")

    def test_facts_need_provenance(self) -> None:
        with self.assertRaises(DriverDefinitionError):
            Fact("max 200 Cel", source="vendor_doc")
        with self.assertRaises(DriverDefinitionError):
            Fact("max 200 Cel", source="guess", ref="x")
        self.assertEqual(Fact("max", source="upstream_code", ref="a.py:1").to_json(),
                         {"text": "max", "source": "upstream_code", "ref": "a.py:1", "reviewed_by": None})

    def test_limit_paths_and_widening_are_refused_by_the_strict_device(self) -> None:
        class BadPath(Driver):
            device_id, device_kind, risk = "bad-path", "robot.arm", "R1"

            @action(cap="cap.motion.cartesian_pose.v1",
                    limits={"position.w": Limit(max=1, source="vendor_doc", ref="a:1")})
            def move(self, position):
                pass

        with self.assertRaises(DriverDefinitionError) as caught:
            build_device(BadPath(backend="fake", native=object()))
        self.assertIn("limits-invalid", str(caught.exception))

        class Widen(Driver):
            device_id, device_kind, risk = "widen", "thermal.zone", "R2"

            @action(cap="cap.thermal.setpoint.v1",
                    input={"target_temperature": Field(limit=Limit(max=500, source="vendor_doc", ref="a:1"))})
            def go(self, target_temperature):
                pass

        self.assertIn("limit-widens", problems_of(Widen))

    def test_hardware_r2_without_a_safe_state_path_is_refused_strictly(self) -> None:
        class NoStopPath(Driver):
            device_id, device_kind, risk = "no-stop", "thermal.zone", "R2"

            @action(cap="cap.thermal.setpoint.v1")
            def go(self, target_temperature):
                return {"setpoint": target_temperature}

            @estop
            def stop(self):
                pass

        rules = {item.rule for item in strict_findings(NoStopPath)}
        self.assertIn("SAFE-045", rules)
        self.assertEqual(strict_findings(support.Bath), [])
        self.assertEqual(strict_findings(support.Arm), [])


def meter(**attributes):
    """A minimal hardware meter class with the given class attributes."""

    def measure(self):
        return 1.0

    body = {"device_id": "meter", "device_kind": "instrument.dmm", "mode": "hardware",
            "measure": action(cap="cap.measure.voltage.v1")(measure)}
    body.update(attributes)
    return type("Meter", (Driver,), body)


class BackendVocabularyTests(unittest.TestCase):
    """Only 'hardware' drives the device; 'fake' and 'sim' are simulated and may not reach it (fail closed)."""

    def connect(self, **options):  # pragma: no cover - never called
        raise AssertionError("the hardware entry point was called")

    def test_backend_names_are_hardware_fake_and_sim(self) -> None:
        for name in ("real", "serial", "transcript", "Hardware"):
            with self.subTest(name=name):
                self.assertIn("is not one of ['hardware', 'fake', 'sim']",
                              problems_of(meter(backends={name: dict, "fake": dict})))
        build_manifest(meter(backends={"hardware": self.connect, "fake": dict, "sim": list}))

    def test_a_fake_or_sim_backend_may_not_be_the_hardware_entry_point(self) -> None:
        for backends in ({"hardware": ".native:connect", "sim": ".native:connect"},
                         {"hardware": self.connect, "fake": self.connect},
                         {"hardware": ".hw:open", "fake": ".hw:open"}):
            with self.subTest(backends=backends):
                self.assertIn("is the hardware entry point", problems_of(meter(backends=backends)))
        for entry in (".native:connect", ".native:FakeMeter"):
            with self.subTest(entry=entry):
                self.assertIn("uses .native, the hardware backend module",
                              problems_of(meter(backends={"fake": entry})))

    def test_a_simulated_driver_declares_no_hardware_backend(self) -> None:
        from mhs.driver import FAKE_FIDELITY

        cls = meter(mode="simulated", fidelity=dict(FAKE_FIDELITY), backends={"hardware": dict, "fake": list})
        self.assertIn("a simulated driver has no hardware backend", problems_of(cls))

    def test_an_unknown_backend_name_is_refused_at_construction_and_build(self) -> None:
        cls = meter(backends={"fake": dict})
        with self.assertRaises(ValueError):
            cls(backend="real")
        for backend in ("real", "transcript"):
            with self.subTest(backend=backend), self.assertRaises(ValueError):
                build_manifest(cls, backend=backend)
        self.assertEqual(build_manifest(cls, backend="sim")["mode"], "simulated")
        self.assertEqual(build_manifest(cls, backend="sim")["device_id"], "mhs://localhost/meter/sim")
        self.assertEqual(build_manifest(cls, backend="hardware")["mode"], "hardware")


class WatchdogTests(unittest.TestCase):
    def test_watchdog_ms_needs_a_sourced_fact(self) -> None:
        self.assertIn("declares a device-side watchdog", problems_of(meter(watchdog_ms=100)))
        unrelated = [Fact("Range 0..10 V", source="vendor_doc", ref="manual.pdf:3")]
        self.assertIn("declares a device-side watchdog", problems_of(meter(watchdog_ms=100, facts=unrelated)))
        cited = [Fact("The controller watchdog stops motion after 100 ms without a command", source="vendor_doc",
                      ref="manual.pdf:9")]
        manifest = build_manifest(meter(watchdog_ms=100, facts=cited))
        self.assertEqual(manifest["watchdog_ms"], 100)
        self.assertEqual(default_store().validate(manifest, "device.schema.json"), [])


class ReferenceTests(unittest.TestCase):
    def test_reference_is_valid_deterministic_and_names_methods(self) -> None:
        first = build_reference(support.Bath)
        second = build_reference(support.Bath)
        self.assertEqual(reference_file.validate(first), [])
        self.assertEqual(reference_file.dump(first), reference_file.dump(second))
        self.assertEqual(reference_file.render_markdown(first), reference_file.render_markdown(second))
        self.assertEqual(sorted(item["name"] for item in first["actions"]),
                         ["explode", "heater_off", "ramp_to"])
        self.assertEqual([item["name"] for item in first["adjusts"]], ["setpoint", "pump_speed"])
        self.assertEqual([item["name"] for item in first["measures"]], ["temperature"])
        self.assertEqual(first["safety"]["estop"]["native"], "stop")
        self.assertEqual(first["safety"]["operator_required"],
                         [{"name": "pump_speed", "reason": "the manual gives no pump range"}])
        self.assertEqual(first["facts"], [{"text": "Bath fluid range -20..150 Cel", "source": "vendor_doc",
                                           "ref": "manual.pdf:41", "reviewed_by": None}])
        self.assertEqual(first["device"]["mode"], "hardware")

    def test_reference_with_an_overlay_and_provenance(self) -> None:
        overlay = {"openmhs": "0.9", "site": "bench", "issued_by": {"id": "operator:lab"},
                   "issued_at": "2026-10-22T09:00:00Z",
                   "devices": {"mhs://localhost/lab/bath": {
                       "pump_speed": {"min": 0, "max": 1200, "unit": "/min", "source": "operator", "reason": "measured"}}}}
        reference = build_reference(support.Bath, overlay=overlay,
                                    provenance={"authored_by": {"kind": "model", "model_id": "m"}})
        self.assertEqual(reference["safety"]["operator_required"], [])
        self.assertTrue(any("pump_speed" in line for line in reference["overlay"]["narrowed"]),
                        reference["overlay"])
        pump = next(item for item in reference["adjusts"] if item["name"] == "pump_speed")
        self.assertEqual(pump["limit"]["max"], 1200)
        self.assertEqual(reference["provenance"]["authored_by"], {"kind": "model", "model_id": "m"})

    def test_fake_view_reference(self) -> None:
        reference = build_reference(support.Bath, backend="fake")
        self.assertEqual(reference["device"]["mode"], "simulated")
        self.assertEqual(reference["device"]["models"], ["mhs://localhost/lab/bath"])
        self.assertEqual(reference["fidelity"]["engine"], "fake")


if __name__ == "__main__":
    unittest.main()
