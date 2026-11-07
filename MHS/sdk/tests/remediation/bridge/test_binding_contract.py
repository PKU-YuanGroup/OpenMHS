"""REG-002 contract tests: the canonical MHS-006 §4/§7 binding DSL.

The exact published example shape (enum_map, result.map, constants, units,
clamp, ordered errors[]) is loaded by ``mhs.bridge.bindings`` and executed
through ``PythonObjectBridge`` against a fake native Python object.  The tests
also pin the review's original counterexamples so the finding cannot regress.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.remediation.bridge import support

from mhs import signals
from mhs.bridge.base import ErrorMap, FieldMapping, MappingError
from mhs.bridge.bindings import (
    BindingDocument,
    load_bindings,
    normalize_binding,
    validate_binding,
)
from mhs.bridge.python import PythonObjectBridge


def error_code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


def _doc_with(binding: dict, *, adapter_id: str = "org.example.fake-lift", **entry: object) -> dict:
    """Wrap one inner binding object in a canonical document."""

    item = {
        "device_id": "mhs://localhost:7400/lab/lift",
        "capability_id": "cap.world.step.v1",
        "resource": "world",
        "binding": binding,
    }
    item.update(entry)
    return {"mhs_bindings": "1.0", "adapter_id": adapter_id, "bindings": [item]}


def _step_binding() -> dict:
    return copy.deepcopy(support.LIFT_BINDINGS["bindings"][0]["binding"])


REPO_ROOT = Path(__file__).resolve().parents[5]
SPEC_06 = REPO_ROOT / "MHS" / "spec" / "06-adapters.md"


def _published_section_4_1_example() -> dict:
    """Extract the actual JSON example from MHS-006 §4.1 (read-only)."""

    text = SPEC_06.read_text(encoding="utf-8")
    section = text.split("### 4.1 Shape", 1)[1]
    block = section.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(block)


class CanonicalLoaderTests(unittest.TestCase):
    def test_published_spec_example_loads_verbatim(self) -> None:
        example = _published_section_4_1_example()
        document = load_bindings(example)
        self.assertEqual(document.adapter_id, "org.example.robosuite-lift")
        entry = document.bindings[0]
        self.assertEqual(entry["native"], "gymnasium.Env.step")
        self.assertEqual(entry["args"]["action"]["enum_map"], {"left": 0, "right": 1})
        self.assertEqual(entry["result"]["reward"], {"from": "output.reward"})
        self.assertEqual(entry["timeout_ms"], 5000)

    def test_normative_example_loads_without_rewriting(self) -> None:
        document = load_bindings(copy.deepcopy(support.NORMATIVE_EXAMPLE))
        self.assertIsInstance(document, BindingDocument)
        self.assertEqual(document.mhs_bindings, "1.0")
        self.assertEqual(document.adapter_id, "org.example.robosuite-lift")
        self.assertEqual(len(document.bindings), 1)
        entry = document.bindings[0]
        self.assertEqual(entry["capability_id"], "cap.world.step.v1")
        self.assertEqual(entry["native"], "gymnasium.Env.step")
        self.assertEqual(entry["kind"], "declarative")
        self.assertEqual(entry["concurrency"], "exclusive")
        self.assertEqual(entry["timeout_ms"], 5000)
        self.assertEqual(entry["args"]["action"]["enum_map"], {"left": 0, "right": 1})
        self.assertEqual(entry["args"]["expected_revision"], {"value": "ignore"})
        self.assertEqual(entry["args"]["action"]["unit"]["from"], "1")
        self.assertEqual(entry["args"]["action"]["unit"]["factor"], 1.0)
        self.assertTrue(entry["args"]["action"]["enforce_clamp"])
        self.assertEqual(entry["args"]["action"]["clamp"], {"min": 0, "max": 1})
        self.assertEqual(
            entry["result"]["observation"], {"from": "output.observation"}
        )
        self.assertEqual(len(entry["errors"]), 1)
        self.assertEqual(entry["errors"][0]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_per_arg_value_constant_is_equivalent_to_constants_object(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        binding = document["bindings"][0]["binding"]
        binding["args"]["expected_revision"] = {"value": "ignore"}
        binding.pop("constants")
        entry = load_bindings(document).bindings[0]
        self.assertEqual(entry["args"]["expected_revision"], {"value": "ignore"})

    def test_load_bindings_accepts_a_json_string(self) -> None:
        document = load_bindings(json.dumps(support.NORMATIVE_EXAMPLE))
        self.assertEqual(document.adapter_id, "org.example.robosuite-lift")

    def test_arg_units_alias_is_normalised(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        binding = document["bindings"][0]["binding"]
        action = binding["args"]["action"]
        action["units"] = binding.pop("units")["input.action"]
        entry = load_bindings(document).bindings[0]
        self.assertEqual(entry["args"]["action"]["unit"]["to"], "1")

    def test_load_bindings_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bindings.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(support.NORMATIVE_EXAMPLE, handle)
            document = load_bindings(path)
        self.assertEqual(document.adapter_id, "org.example.robosuite-lift")

    def test_normalize_binding_returns_fieldmapping_compatible_specs(self) -> None:
        normalized = normalize_binding(copy.deepcopy(support.LIFT_BINDINGS["bindings"][0]))
        inputs = FieldMapping(normalized["args"], direction="input").map({"action": "right"})
        self.assertEqual(inputs, {"action": 1, "expected_revision": "ignore"})
        outputs = FieldMapping(normalized["result"], direction="output").map(
            {"observation": [1, 2], "reward": 0.5, "terminated": False, "truncated": False}
        )
        self.assertEqual(outputs["observation"], [1, 2])
        errors = ErrorMap(normalized["errors"])
        self.assertEqual(errors.translate(AssertionError("x"))[0], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_document_validation_reports_every_error(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document.pop("adapter_id")
        document["bindings"][0]["binding"].pop("native")
        with self.assertRaises(Exception) as caught:
            load_bindings(document)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        details = getattr(caught.exception, "data", {}).get("details", {})
        self.assertTrue(details.get("errors"))
        joined = "\n".join(details["errors"])
        self.assertIn("adapter_id", joined)
        self.assertIn("native", joined)

    def test_unknown_top_level_keys_are_refused(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["totally_new"] = True
        with self.assertRaises(Exception) as caught:
            load_bindings(document)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class PythonBridgeCanonicalExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = PythonObjectBridge(
            {"target": support.LIFT_TARGET, "bindings": support.LIFT_BINDINGS},
            device_id="mhs://localhost:7400/lab/lift",
        )
        self.native: support.FakeLift = self.bridge._ensure_loaded()

    def tearDown(self) -> None:
        self.bridge.close()

    def test_input_mapping_enum_type_and_constant_injection(self) -> None:
        result = self.bridge.call("cap.world.step.v1", {"action": "left"})
        self.assertEqual(self.native.calls, [("step", 0)])
        self.assertIn("observation", result)
        result = self.bridge.call("cap.world.step.v1", {"action": "right"})
        self.assertEqual(self.native.calls[-1], ("step", 1))
        self.assertEqual(result["observation"], [1, 2])

    def test_result_map_maps_capability_output_fields(self) -> None:
        result = self.bridge.call("cap.world.step.v1", {"action": "left"})
        self.assertEqual(
            set(result), {"observation", "reward", "terminated", "truncated"}
        )
        self.assertEqual(result["reward"], 1.0)
        self.assertFalse(result["terminated"])

    def test_ordered_errors_first_match_wins_and_default_is_shim_failed(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.set-target.v1", {"target": -1})
        self.assertEqual(error_code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.set-target.v1", {"target": -2})
        self.assertEqual(error_code(caught.exception), "MHS.DEVICE.BUSY")
        self.assertTrue(getattr(caught.exception, "data", {}).get("retryable"))
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.set-target.v1", {"target": -3})
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.SHIM_FAILED")
        details = getattr(caught.exception, "data", {}).get("details", {})
        self.assertTrue(details.get("redacted"))
        self.assertNotIn("vendor SDK returned", str(getattr(caught.exception, "message", "")))

    def test_clamp_outside_declared_envelope_is_rejected_not_clamped(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.joints.v1", {"joints": [0, 400]})
        self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.native.calls, [])

    def test_clamp_inside_declared_envelope_is_rejected_too(self) -> None:
        # 190 deg = 3.316 rad: outside the clamp (pi) but inside the declared
        # envelope (2*pi).  Plan 3.5: every clamp goes through mhs.limits and
        # an out-of-range value is rejected, never silently truncated.
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.joints.v1", {"joints": [0, 190]})
        self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.native.calls, [])

    def test_wildcard_joints_fans_out_all_elements(self) -> None:
        result = self.bridge.call("cap.motion.joints.v1", {"joints": [0, 90, 180]})
        received = self.native.calls[-1][1]
        self.assertEqual(len(received), 3)
        self.assertAlmostEqual(received[1], 3.141592653589793 / 2)
        self.assertAlmostEqual(result["joints"][2], 3.141592653589793)

    def test_binding_timeout_is_enforced(self) -> None:
        # a native timeout is an unknown outcome (not retryable), never a failure
        with self.assertRaises(signals.OutcomeUnknown) as caught:
            self.bridge.call("cap.test.slow.v1", {"seconds": 0.2})
        self.assertEqual(error_code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertFalse(caught.exception.retryable)

    def test_bridge_refuses_a_shim_binding(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["kind"] = "shim"
        document["bindings"][0]["binding"]["shim"] = "mhs/shim.py:run"
        # A shim has no declarative result requirement; remove it.
        document["bindings"][0]["binding"].pop("result", None)
        loaded = load_bindings(document)
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": support.LIFT_TARGET, "bindings": loaded})
        self.assertIn(
            error_code(caught.exception),
            ("MHS.DEVICE.UNSUPPORTED", "MHS.CAPABILITY.NOT_BOUND"),
        )

    def test_bridge_accepts_a_canonical_capability_entry_in_the_config_map(self) -> None:
        binding = copy.deepcopy(support.LIFT_BINDINGS["bindings"][0]["binding"])
        bridge = PythonObjectBridge(
            {
                "target": support.LIFT_TARGET,
                "capabilities": {"cap.world.step.v1": binding},
            }
        )
        try:
            result = bridge.call("cap.world.step.v1", {"action": "right"})
            self.assertEqual(result["observation"], [1, 2])
        finally:
            bridge.close()

    def test_bridge_accepts_a_loaded_document_as_a_keyword(self) -> None:
        loaded = load_bindings(copy.deepcopy(support.LIFT_BINDINGS))
        bridge = PythonObjectBridge({"target": support.LIFT_TARGET}, bindings=loaded)
        try:
            result = bridge.call("cap.motion.set-target.v1", {"target": 42})
            self.assertEqual(result["target"], 42)
        finally:
            bridge.close()


class CanonicalValidationTests(unittest.TestCase):
    def test_units_require_explicit_from_and_to(self) -> None:
        binding = _step_binding()
        binding["units"]["input.action"] = {"from": "1", "factor": 1}
        errors = validate_binding(binding)
        self.assertTrue(any("explicit non-empty 'to'" in error for error in errors), errors)
        binding["units"]["input.action"] = {"to": "1", "factor": 1}
        errors = validate_binding(binding)
        self.assertTrue(any("explicit non-empty 'from'" in error for error in errors), errors)

    def test_wrong_or_dimensionally_invalid_unit_is_refused(self) -> None:
        binding = _step_binding()
        binding["units"]["input.action"] = {"from": "mm", "to": "s", "factor": 0.001}
        errors = validate_binding(binding)
        self.assertTrue(any("invalid unit" in error.lower() for error in errors), errors)
        binding["units"]["input.action"] = {"from": "mm", "to": "m", "factor": 0.01}
        errors = validate_binding(binding)
        self.assertTrue(any("factor" in error for error in errors), errors)

    def test_offset_unit_conversion_in_args(self) -> None:
        mapping = FieldMapping(
            {"celsius": {"from": "input.celsius", "unit": {"from": "Cel", "to": "K", "offset": 273.15}}},
            direction="input",
        )
        self.assertAlmostEqual(mapping.map({"celsius": 25})["celsius"], 298.15)

    def test_totality_rejects_unmapped_required_input(self) -> None:
        binding = _step_binding()
        binding["required_inputs"] = ["action", "speed"]
        errors = validate_binding(binding)
        self.assertTrue(any("required input 'speed'" in error for error in errors), errors)
        with self.assertRaises(Exception) as caught:
            load_bindings(_doc_with(binding))
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        details = getattr(caught.exception, "data", {}).get("details", {})
        self.assertTrue(any("required input 'speed'" in error for error in details["errors"]))

    def test_totality_accepts_constant_or_declared_unsupported_input(self) -> None:
        with_constants = _step_binding()
        with_constants["required_inputs"] = ["action", "speed"]
        with_constants["constants"]["speed"] = 0
        self.assertEqual(validate_binding(with_constants), [])

        with_unsupported = _step_binding()
        with_unsupported["required_inputs"] = ["action", "camera"]
        with_unsupported["inputs"] = {
            "camera": {"required": True, "unsupported": True, "reason": "not exposed by the SDK"}
        }
        self.assertEqual(validate_binding(with_unsupported), [])

    def test_unsupported_without_reason_is_refused(self) -> None:
        binding = _step_binding()
        binding["args"]["camera"] = {"unsupported": True}
        errors = validate_binding(binding)
        self.assertTrue(any("reason" in error for error in errors), errors)

    def test_precise_native_symbol_is_required(self) -> None:
        binding = _step_binding()
        binding["native"] = "call the environment step function"
        errors = validate_binding(binding)
        self.assertTrue(any("precise symbol" in error for error in errors), errors)
        binding["native"] = ""
        errors = validate_binding(binding)
        self.assertTrue(any("precise 'native'" in error for error in errors), errors)

    def test_noncanonical_legacy_arg_keys_are_rejected_by_the_canonical_parser(self) -> None:
        binding = _step_binding()
        binding["args"]["action"] = {
            "from": "input.action",
            "enum": {"left": 0, "right": 1},
        }
        errors = validate_binding(binding)
        self.assertTrue(any("non-canonical keys" in error for error in errors), errors)
        binding["args"]["action"] = {"from": "input.action", "scale": 2}
        errors = validate_binding(binding)
        self.assertTrue(any("non-canonical keys" in error for error in errors), errors)

    def test_result_map_is_required_for_declarative_bindings(self) -> None:
        binding = _step_binding()
        binding.pop("result")
        errors = validate_binding(binding)
        self.assertTrue(any("result.map" in error for error in errors), errors)

    def test_errors_must_be_an_ordered_array(self) -> None:
        binding = _step_binding()
        binding["errors"] = {"AssertionError": "MHS.DEVICE.PRECONDITION_UNMET"}
        errors = validate_binding(binding)
        self.assertTrue(any("ordered array" in error for error in errors), errors)

    def test_timeout_and_concurrency_validation(self) -> None:
        binding = _step_binding()
        binding["concurrency"] = "parallel"
        binding["timeout_ms"] = 0
        errors = validate_binding(binding)
        self.assertTrue(any("concurrency" in error for error in errors), errors)
        self.assertTrue(any("timeout_ms must be positive" in error for error in errors), errors)

        binding = _step_binding()
        binding.pop("timeout_ms")
        binding.pop("concurrency")
        errors = validate_binding(binding)
        self.assertTrue(any("requires 'concurrency'" in error for error in errors), errors)
        self.assertTrue(any("requires 'timeout_ms'" in error for error in errors), errors)

    def test_timeout_and_concurrency_are_checked_against_the_class(self) -> None:
        capability = {
            "constraints": {"concurrency": "exclusive", "max_duration_ms": 1000}
        }
        binding = _step_binding()
        binding["concurrency"] = "shared"
        binding["timeout_ms"] = 5000
        errors = validate_binding(binding, capability=capability)
        self.assertTrue(any("weaker than the class default" in error for error in errors), errors)
        self.assertTrue(any("max_duration_ms" in error for error in errors), errors)
        binding["concurrency"] = "exclusive"
        binding["timeout_ms"] = 1000
        self.assertEqual(validate_binding(binding, capability=capability), [])


class ReviewCounterexampleTests(unittest.TestCase):
    """The review's original probes must now pass (REG-002 acceptance)."""

    def test_numeric_index_control(self) -> None:
        mapping = FieldMapping(
            {"joint": {"from": "input.joints[0]", "required": True}}, direction="input"
        )
        self.assertEqual(mapping.map({"joints": [10, 20]}), {"joint": 10})

    def test_wildcard_fans_out(self) -> None:
        mapping = FieldMapping(
            {"joints": {"from": "input.joints[*]", "required": True}}, direction="input"
        )
        self.assertEqual(mapping.map({"joints": [10, 20]}), {"joints": [10, 20]})

    def test_spec_enum_example(self) -> None:
        mapping = FieldMapping(
            {
                "action": {
                    "from": "input.action",
                    "type": "integer",
                    "enum_map": {"left": 0, "right": 1},
                }
            },
            direction="input",
        )
        self.assertEqual(mapping.map({"action": "left"}), {"action": 0})

    def test_spec_result_map(self) -> None:
        mapping = FieldMapping(
            {"map": {"observation": "output.observation"}}, direction="output"
        )
        self.assertEqual(mapping.map({"observation": [1, 2]}), {"observation": [1, 2]})

    def test_spec_constant(self) -> None:
        mapping = FieldMapping({"flag": {"value": True}}, direction="input")
        self.assertEqual(mapping.map({}), {"flag": True})

    def test_spec_errors(self) -> None:
        errors = ErrorMap(
            [
                {
                    "native": "^AssertionError$",
                    "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                    "retryable": False,
                }
            ]
        )
        self.assertEqual(
            errors.translate(AssertionError("test")),
            ("MHS.DEVICE.PRECONDITION_UNMET", "test"),
        )


class LegacyInternalMappingTests(unittest.TestCase):
    """The deprecated internal shape works behind ``grammar: legacy``; its clamps reject."""

    def setUp(self) -> None:
        self.config = {
            "target": support.LIFT_TARGET,
            "grammar": "legacy",
            "capabilities": {
                "cap.motion.set-target.v1": {
                    "resource": "lift",
                    "native": "set_target",
                    "args": {
                        "target": {
                            "from": "input.target",
                            "required": True,
                            "clamp": {"min": 0, "max": 10},
                        }
                    },
                    "result": {"target": {"from": "target"}},
                    "errors": {"ValueError": "MHS.SAFETY.ENVELOPE_VIOLATION"},
                },
                "cap.world.step.v1": {
                    "resource": "world",
                    "native": "step",
                    "args": {
                        "action": {"from": "input.action", "default": 0},
                        "expected_revision": {"const": "ignore"},
                    },
                    "result": {"observation": {"from": "observation"}},
                    "errors": {"AssertionError": "MHS.DEVICE.PRECONDITION_UNMET"},
                },
            },
        }
        with self.assertWarns(DeprecationWarning):
            self.bridge = PythonObjectBridge(self.config)

    def tearDown(self) -> None:
        self.bridge.close()

    def test_internal_mapping_dict_is_still_accepted(self) -> None:
        result = self.bridge.call("cap.world.step.v1", {})
        self.assertEqual(result["observation"], [0, 1])

    def test_internal_mapping_clamp_rejects_instead_of_clamping(self) -> None:
        # DRV-11 repro: a legacy clamp {min 0, max 10} used to execute
        # set_target(10) for an input of 50 (ADPT-024 forbids silent clamping).
        native = self.bridge._ensure_loaded()
        with self.assertRaises(Exception) as caught:
            self.bridge.call("cap.motion.set-target.v1", {"target": 50})
        self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(native.calls, [])
        self.assertEqual(self.bridge.call("cap.motion.set-target.v1", {"target": 7})["target"], 7)

    def test_a_legacy_entry_needs_the_grammar_marker(self) -> None:
        config = dict(self.config)
        config.pop("grammar")
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge(config)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


if __name__ == "__main__":
    unittest.main()
