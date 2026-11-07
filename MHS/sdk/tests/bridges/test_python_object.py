"""PythonObjectBridge: grammar, units, scalar results, reject-not-clamp, timeouts.

Ported reviewer repros (each failed before WP-05):

* drv-verify/scalar_probe.py (DRV-06): a getter returning a float cannot be
  mapped -- ``output`` gives the wrapper, ``output.temperature`` gives ``{}``;
* fit-robots-ros/bind_probe + DRV-11 notes: a legacy clamp of 200 against a
  maximum of 95 silently executes ``set_point(95)``;
* fit-lab-automation-verify/timeout_test.py (LAB-08/DRV-11): adding
  ``timeout_ms`` to a legacy entry silently flips it to the canonical grammar;
* FIT-08 / FIT-ROS-07: ``convert_unit(50, '%', '1')`` is 50 and a binding
  cannot state the correct factor 0.01;
* FIT-08 (long tail): a native timeout is a retryable failure.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
import unittest
import warnings

from tests.bridges import support

from mhs import signals
from mhs.bridge.base import FieldMapping, MappingError, UnitError, convert_unit
from mhs.bridge.bindings import load_bindings, validate_binding
from mhs.bridge.python import PythonObjectBridge
from mhs.server import Resource


def code_of(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


THERMOMETER = "tests.bridges.support:Thermometer"
HEATER = "tests.bridges.support:Heater"


def canonical_entry(native: str, result_map: dict, *, args: dict | None = None,
                    timeout_ms: int = 2000, **extra) -> dict:
    binding = {
        "bridge": "python-object",
        "kind": "declarative",
        "native": native,
        "result": {"map": result_map},
        "concurrency": "exclusive",
        "timeout_ms": timeout_ms,
    }
    if args is not None:
        binding["args"] = args
    binding.update(extra)
    return binding


class UnitEngineTests(unittest.TestCase):
    def test_percent_is_a_ratio_of_one_hundredth(self) -> None:
        self.assertEqual(convert_unit(50, "%", "1"), 0.5)
        mapping = FieldMapping(
            {"fraction": {"from": "input.open_pct", "unit": {"from": "%", "to": "1"}}},
            direction="input",
        )
        self.assertEqual(mapping.map({"open_pct": 50}), {"fraction": 0.5})
        # the correct explicit factor is accepted, the old wrong one is refused
        FieldMapping({"f": {"from": "input.p", "unit": {"from": "%", "to": "1", "factor": 0.01}}},
                     direction="input")
        with self.assertRaises(MappingError):
            FieldMapping({"f": {"from": "input.p", "unit": {"from": "%", "to": "1", "factor": 1}}},
                         direction="input")

    def test_compound_units_are_derived_and_checked(self) -> None:
        self.assertEqual(convert_unit(1, "m/s", "mm/s"), 1000)
        self.assertAlmostEqual(convert_unit(1, "uL/s", "uL/h"), 3600)
        mapping = FieldMapping(
            {"speed": {"from": "input.v", "unit": {"from": "m/s", "to": "mm/s", "factor": 1000}}},
            direction="input",
        )
        self.assertEqual(mapping.map({"v": 0.25}), {"speed": 250.0})
        with self.assertRaises(MappingError):  # 0.001 instead of 1000: never trusted
            FieldMapping({"s": {"from": "input.v", "unit": {"from": "m/s", "to": "mm/s", "factor": 0.001}}},
                         direction="input")
        with self.assertRaises(UnitError):
            convert_unit(1, "m/s", "N.m")

    def test_custom_codes_keep_the_explicit_factor_fallback(self) -> None:
        mapping = FieldMapping(
            {"count": {"from": "input.c", "unit": {"from": "{counts}/[foo]", "to": "{raw}", "factor": 4}}},
            direction="input",
        )
        self.assertEqual(mapping.map({"c": 2}), {"count": 8.0})
        with self.assertRaises(MappingError):
            FieldMapping({"x": {"from": "input.c", "unit": {"from": "[foo]", "to": "[bar]"}}},
                         direction="input")

    def test_offset_zero_declares_a_temperature_difference(self) -> None:
        delta = FieldMapping({"tol": {"from": "input.t", "unit": {"from": "Cel", "to": "K", "offset": 0}}},
                             direction="input")
        self.assertEqual(delta.map({"t": 2.5}), {"tol": 2.5})
        absolute = FieldMapping({"t": {"from": "input.t", "unit": {"from": "Cel", "to": "K"}}},
                                direction="input")
        self.assertAlmostEqual(absolute.map({"t": 25})["t"], 298.15)


class ScalarResultTests(unittest.TestCase):
    """DRV-06: the root path is the raw native return."""

    def bridge(self, result_map: dict, **kwargs) -> PythonObjectBridge:
        return PythonObjectBridge(
            {"target": THERMOMETER,
             "capabilities": {"cap.measure.temperature.v1": canonical_entry("read_temperature", result_map)}},
            **kwargs,
        )

    def test_output_dollar_maps_a_scalar_return(self) -> None:
        for path in ("output.$", "output"):
            with self.subTest(path=path):
                bridge = self.bridge({"temperature": path})
                try:
                    self.assertEqual(bridge.call("cap.measure.temperature.v1", {}), {"temperature": 22.0})
                finally:
                    bridge.close()

    def test_a_misspelled_result_path_is_an_output_error_not_an_empty_output(self) -> None:
        bridge = self.bridge({"temperature": "output.temperature"})
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.measure.temperature.v1", {})
            self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.OUTPUT_INVALID")
            self.assertIsInstance(caught.exception, signals.DriverFailed)
        finally:
            bridge.close()

    def test_result_targets_must_exist_in_the_provided_output_schema(self) -> None:
        schemas = {"cap.measure.temperature.v1": {
            "output_schema": support.class_schema("cap.measure.temperature.v1")["output_schema"]}}
        with self.assertRaises(Exception) as caught:
            self.bridge({"temp_c": "output.$"}, capability_schemas=schemas)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertIn("temp_c", json.dumps(getattr(caught.exception, "data", {})))
        ok = self.bridge({"temperature": "output.$"}, capability_schemas=schemas)
        ok.close()

    def test_scalar_return_end_to_end_through_the_server(self) -> None:
        bridge = self.bridge({"temperature": "output.$"})
        device = support.simulated_device(
            "mhs://localhost:7799/lab/thermometer",
            resources=[Resource("probe", "sensor.temperature")],
            capabilities=[support.open_capability("cap.measure.temperature.v1", "probe", verb="read")],
            bridge=bridge,
            risk_class="R0",
        )
        harness = support.Harness(device)
        receipt = harness.command("cap.measure.temperature.v1", {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"temperature": 22.0})


class GrammarTests(unittest.TestCase):
    """The canonical grammar is the default; legacy needs an explicit marker."""

    LEGACY_ENTRY = {
        "resource": "heater",
        "native": "set_point",
        "args": {"celsius": {"from": "input.target_temperature", "clamp": {"min": 4, "max": 95}}},
        "result": {"setpoint": {"from": "setpoint"}},
        "errors": {"ValueError": "MHS.CAPABILITY.INPUT_INVALID"},
    }

    def test_a_legacy_entry_without_the_marker_is_refused(self) -> None:
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": HEATER, "capabilities": {
                "cap.thermal.setpoint.v1": copy.deepcopy(self.LEGACY_ENTRY)}})
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertIn("legacy", str(getattr(caught.exception, "data", {})))

    def test_timeout_ms_no_longer_flips_the_grammar(self) -> None:
        # timeout_test.py: the same legacy entry plus timeout_ms used to be
        # re-read as canonical and fail with unrelated errors.
        entry = dict(copy.deepcopy(self.LEGACY_ENTRY), timeout_ms=1000)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            bridge = PythonObjectBridge({"target": HEATER, "grammar": "legacy",
                                         "capabilities": {"cap.thermal.setpoint.v1": entry}})
        try:
            self.assertEqual(bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 50}),
                             {"setpoint": 50})
        finally:
            bridge.close()

    def test_the_legacy_marker_emits_a_deprecation_warning(self) -> None:
        with self.assertWarns(DeprecationWarning):
            bridge = PythonObjectBridge({"target": HEATER, "grammar": "legacy", "capabilities": {
                "cap.thermal.setpoint.v1": copy.deepcopy(self.LEGACY_ENTRY)}})
        bridge.close()

    def test_unknown_grammar_is_refused(self) -> None:
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": HEATER, "grammar": "guess"})
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")

    def test_a_binding_for_another_bridge_family_is_refused(self) -> None:
        entry = canonical_entry("set_point", {"setpoint": "output.setpoint"},
                                args={"celsius": {"from": "input.target_temperature"}})
        entry["bridge"] = "ros2"
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": HEATER, "capabilities": {"cap.thermal.setpoint.v1": entry}})
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class RejectNotClampTests(unittest.TestCase):
    """ADPT-024 / plan 3.5: every clamp is a rejection, legacy included."""

    def legacy_bridge(self) -> PythonObjectBridge:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return PythonObjectBridge({"target": HEATER, "grammar": "legacy", "capabilities": {
                "cap.thermal.setpoint.v1": copy.deepcopy(GrammarTests.LEGACY_ENTRY)}})

    def test_legacy_clamp_of_200_against_95_is_rejected_without_a_native_call(self) -> None:
        bridge = self.legacy_bridge()
        try:
            native = bridge._ensure_loaded()
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 200})
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            details = caught.exception.data["details"]
            self.assertEqual(details["value"], 200)
            self.assertEqual(details["bound"], 95)
            self.assertEqual(native.calls, [])
        finally:
            bridge.close()

    def test_legacy_clamp_rejection_end_to_end(self) -> None:
        bridge = self.legacy_bridge()
        device = support.simulated_device(
            "mhs://localhost:7799/lab/heater",
            resources=[Resource("heater", "thermal.zone")],
            capabilities=[support.open_capability("cap.thermal.setpoint.v1", "heater")],
            bridge=bridge,
        )
        harness = support.Harness(device)
        receipt = harness.command("cap.thermal.setpoint.v1", {"target_temperature": 200})
        self.assertIn(receipt["status"], ("rejected", "failed"), receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(bridge._ensure_loaded().calls, [])
        inside = harness.command("cap.thermal.setpoint.v1", {"target_temperature": 60})
        self.assertEqual(inside["status"], "completed", inside)

    def test_a_canonical_clamp_inside_a_wider_envelope_is_rejected_too(self) -> None:
        entry = canonical_entry(
            "set_point", {"setpoint": "output.setpoint"},
            args={"celsius": {"from": "input.target_temperature", "type": "number"}},
            clamp={"input.target_temperature": {"min": 4, "max": 95, "envelope": {"min": 0, "max": 120}}},
        )
        bridge = PythonObjectBridge({"target": HEATER, "capabilities": {"cap.thermal.setpoint.v1": entry}})
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 100})
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(bridge._ensure_loaded().calls, [])
        finally:
            bridge.close()

    def test_a_clamp_key_typo_is_a_load_error(self) -> None:
        with self.assertRaises(MappingError):
            FieldMapping({"t": {"from": "input.t", "clamp": {"min": 0, "maxx": 5}}}, direction="input")


class NativeTimeoutTests(unittest.TestCase):
    """A native timeout is an unknown outcome, never a retryable failure."""

    def bridge(self) -> PythonObjectBridge:
        entry = canonical_entry("slow", {"slept": "output.slept"},
                                args={"seconds": {"from": "input.seconds", "type": "number"}},
                                timeout_ms=50)
        return PythonObjectBridge({"target": HEATER, "capabilities": {"x-cap.test.slow.v1": entry}})

    def test_bridge_raises_outcome_unknown(self) -> None:
        bridge = self.bridge()
        try:
            started = time.monotonic()
            with self.assertRaises(signals.OutcomeUnknown) as caught:
                bridge.call("x-cap.test.slow.v1", {"seconds": 0.5})
            self.assertLess(time.monotonic() - started, 0.4)
            self.assertEqual(code_of(caught.exception), "MHS.OUTCOME.UNKNOWN")
            self.assertFalse(caught.exception.retryable)
            self.assertEqual(signals.outcome(caught.exception).status, "unknown")
        finally:
            bridge.close()

    def test_receipt_is_unknown_and_not_retryable(self) -> None:
        bridge = self.bridge()
        device = support.simulated_device(
            "mhs://localhost:7799/lab/slow",
            resources=[Resource("heater", "thermal.zone")],
            capabilities=[support.open_capability("x-cap.test.slow.v1", "heater")],
            bridge=bridge,
        )
        harness = support.Harness(device)
        receipt = harness.command("x-cap.test.slow.v1", {"seconds": 0.5})
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertFalse(receipt["error"]["retryable"])
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.OUTCOME.UNKNOWN")


class StrictErrorRuleTests(unittest.TestCase):
    def entry(self, code: str) -> dict:
        return canonical_entry(
            "set_point", {"setpoint": "output.setpoint"},
            args={"celsius": {"from": "input.target_temperature"}},
            errors=[{"native": "ValueError", "mhs_code": code}],
        )

    def test_strict_mode_restricts_error_codes_to_the_driver_subset(self) -> None:
        config = {"target": HEATER, "capabilities": {"cap.thermal.setpoint.v1": self.entry("MHS.SESSION.EXPIRED")}}
        PythonObjectBridge(copy.deepcopy(config)).close()  # compatibility mode accepts it
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge(copy.deepcopy(config), strict=True)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertIn("driver subset", json.dumps(caught.exception.data))
        PythonObjectBridge({"target": HEATER, "capabilities": {
            "cap.thermal.setpoint.v1": self.entry("MHS.DEVICE.PRECONDITION_UNMET")}}, strict=True).close()

    def test_strict_loader_checks_error_rules(self) -> None:
        binding = self.entry("MHS.SESSION.EXPIRED")
        self.assertEqual(validate_binding(binding), [])
        errors = validate_binding(binding, strict=True)
        self.assertTrue(any("driver subset" in error for error in errors), errors)


class BindingsRefTests(unittest.TestCase):
    def test_bindings_ref_is_loaded_relative_to_base_dir(self) -> None:
        document = {
            "mhs_bindings": "1.0",
            "adapter_id": "org.example.thermometer",
            "bindings": [{
                "device_id": "mhs://localhost:7799/lab/thermometer",
                "capability_id": "cap.measure.temperature.v1",
                "resource": "probe",
                "binding": canonical_entry("read_temperature", {"temperature": "output.$"}),
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bindings.json"), "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            bridge = PythonObjectBridge({"target": THERMOMETER, "bindings_ref": "bindings.json"}, base_dir=tmp)
        try:
            self.assertEqual(bridge.call("cap.measure.temperature.v1", {}), {"temperature": 22.0})
        finally:
            bridge.close()

    def test_bindings_and_bindings_ref_together_are_refused(self) -> None:
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": THERMOMETER, "bindings_ref": "a.json",
                                "bindings": {"mhs_bindings": "1.0"}})
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class InvokeFormTests(unittest.TestCase):
    """FIT-09: property getters/setters are expressible with ``invoke``."""

    def test_get_and_set_a_property(self) -> None:
        config = {
            "target": "tests.bridges.support:Pump",
            "capabilities": {
                "x-cap.test.pump_rate.v1": canonical_entry("rate", {"rate": "output.$"}, invoke="get"),
                "x-cap.test.set_pump_rate.v1": canonical_entry(
                    "rate", {"rate": "output.$"}, invoke="set",
                    args={"value": {"from": "input.rate", "type": "number"}}),
            },
        }
        bridge = PythonObjectBridge(config)
        try:
            self.assertEqual(bridge.call("x-cap.test.pump_rate.v1", {}), {"rate": 1.0})
            self.assertEqual(bridge.call("x-cap.test.set_pump_rate.v1", {"rate": 2.5}), {"rate": 2.5})
            self.assertEqual(bridge._ensure_loaded().writes, [2.5])
            self.assertEqual(bridge.call("x-cap.test.pump_rate.v1", {}), {"rate": 2.5})
        finally:
            bridge.close()

    def test_set_needs_exactly_one_argument(self) -> None:
        entry = canonical_entry("rate", {"rate": "output.$"}, invoke="set",
                                args={"a": {"from": "input.a"}, "b": {"from": "input.b"}})
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": "tests.bridges.support:Pump",
                                "capabilities": {"x-cap.test.set.v1": entry}})
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")

    def test_unknown_invoke_form_is_refused(self) -> None:
        errors = validate_binding(canonical_entry("rate", {"rate": "output.$"}, invoke="poke"))
        self.assertTrue(any("invoke" in error for error in errors), errors)

    def test_resource_write_params_and_the_configure_class(self) -> None:
        bridge = PythonObjectBridge({
            "target": "tests.bridges.support:Pump",
            "reads": {"pump": {"fields": {"rate": "rate"}}},
            "writes": {"pump": {"params": {"rate": {"native": "rate", "invoke": "set"}}}},
        })
        try:
            self.assertEqual(bridge.write("pump", {"rate": 3.0}), {"applied": {"rate": 3.0}})
            self.assertEqual(bridge.read("pump"), {"rate": 3.0})
            out = bridge.call("cap.device.configure.v1", {"rate": 4.0}, {"resource": "pump"})
            self.assertEqual(out, {"applied": {"rate": 4.0}})
            with self.assertRaises(Exception) as caught:
                bridge.write("pump", {"rate": 1.0, "colour": "red"})
            self.assertEqual(code_of(caught.exception), "MHS.RESOURCE.NOT_WRITABLE")
            self.assertEqual(bridge._ensure_loaded().writes, [3.0, 4.0])
            ids = {item["capability_id"] for item in bridge.capabilities()}
            self.assertIn("cap.device.configure.v1", ids)
        finally:
            bridge.close()


class LoaderCompatibilityTests(unittest.TestCase):
    def test_load_bindings_strict_keyword(self) -> None:
        document = {
            "mhs_bindings": "1.0",
            "adapter_id": "org.example.heater",
            "bindings": [{
                "device_id": "mhs://localhost:7799/lab/heater",
                "capability_id": "cap.thermal.setpoint.v1",
                "resource": "heater",
                "binding": StrictErrorRuleTests().entry("MHS.SESSION.EXPIRED"),
            }],
        }
        load_bindings(copy.deepcopy(document))
        with self.assertRaises(Exception) as caught:
            load_bindings(copy.deepcopy(document), strict=True)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


if __name__ == "__main__":
    unittest.main()
