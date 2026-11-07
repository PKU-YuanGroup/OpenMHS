"""RREG-002: every external bindings input takes the canonical safe path.

These regressions exercise the actual ``load_bindings -> PythonObjectBridge``
boundary with inert local objects.  They pin the review's counterexamples:
flattened "normalized" JSON cannot skip schema validation/normalization, an
unbounded timeout is rejected instead of compiling to ``None``, and an
out-of-envelope value always raises ``MHS.SAFETY.ENVELOPE_VIOLATION`` rather
than being silently clamped to the declared maximum.
"""
from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path

from mhs.bridge.bindings import BindingDocument, load_bindings
from mhs.bridge.python import PythonObjectBridge
from tests.remediation.bridge import support as base
from tests.remediation.round2.registry import support


def error_code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


def details_errors(exc: BaseException) -> list[str]:
    data = getattr(exc, "data", {}) or {}
    details = data.get("details", {}) if isinstance(data, dict) else {}
    errors = details.get("errors", []) if isinstance(details, dict) else []
    return [str(item) for item in errors]


class ExternalInputRejectionTests(unittest.TestCase):
    def assert_manifest_invalid(self, payload, *, contains: str | None = None):
        with self.assertRaises(Exception) as caught:
            load_bindings(payload)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        errors = details_errors(caught.exception)
        self.assertTrue(errors, "manifest errors must be reported")
        if contains is not None:
            self.assertTrue(
                any(contains in error for error in errors),
                f"{contains!r} not in errors: {errors}",
            )
        return errors

    def test_flattened_file_is_rejected(self):
        with support.TempDir() as tmp:
            path = support.write_document(tmp, support.FLATTENED_DOCUMENT)
            errors = self.assert_manifest_invalid(path)
        self.assertTrue(any("schema:" in error for error in errors), errors)
        self.assertTrue(
            any("bindings[0]" in error and "binding" in error for error in errors), errors
        )

    def test_flattened_json_string_is_rejected(self):
        self.assert_manifest_invalid(json.dumps(support.FLATTENED_DOCUMENT))

    def test_flattened_plain_dict_is_rejected(self):
        self.assert_manifest_invalid(copy.deepcopy(support.FLATTENED_DOCUMENT))

    def test_version_999_is_rejected_for_file_string_and_dict(self):
        document = support.canonical_document()
        document["mhs_bindings"] = "999.0"
        with support.TempDir() as tmp:
            path = support.write_document(tmp, document)
            self.assert_manifest_invalid(path, contains="mhs_bindings")
        self.assert_manifest_invalid(json.dumps(document), contains="mhs_bindings")
        self.assert_manifest_invalid(copy.deepcopy(document), contains="mhs_bindings")

    def test_empty_adapter_id_is_rejected_for_file_string_and_dict(self):
        document = support.canonical_document()
        document["adapter_id"] = ""
        with support.TempDir() as tmp:
            path = support.write_document(tmp, document)
            self.assert_manifest_invalid(path, contains="adapter_id")
        self.assert_manifest_invalid(json.dumps(document), contains="adapter_id")
        self.assert_manifest_invalid(copy.deepcopy(document), contains="adapter_id")

    def test_unknown_top_level_key_is_rejected(self):
        document = support.canonical_document()
        document["totally_new"] = True
        self.assert_manifest_invalid(copy.deepcopy(document), contains="totally_new")
        with support.TempDir() as tmp:
            path = support.write_document(tmp, document)
            self.assert_manifest_invalid(path, contains="totally_new")

    def test_timeout_zero_negative_and_wrong_type_are_rejected(self):
        for value in (0, -1, "5000", 5000.0, True, None):
            with self.subTest(timeout_ms=value):
                errors = self.assert_manifest_invalid(support.with_timeout(value))
                self.assertTrue(any("timeout" in error for error in errors), errors)

    def test_unparseable_file_and_json_string_are_rejected(self):
        with support.TempDir() as tmp:
            path = os.path.join(tmp, "bad.json")
            Path(path).write_text("{not json", encoding="utf-8")
            self.assert_manifest_invalid(path)
        self.assert_manifest_invalid("{not json")

    def test_timeout_zero_is_rejected_for_file_and_string_too(self):
        document = support.with_timeout(0)
        with support.TempDir() as tmp:
            path = support.write_document(tmp, document)
            self.assert_manifest_invalid(path, contains="timeout")
        self.assert_manifest_invalid(json.dumps(document), contains="timeout")

    def test_a_dict_copy_of_a_validated_document_cannot_select_the_fast_path(self):
        loaded = load_bindings(copy.deepcopy(support.canonical_document()))
        # A plain dict (or JSON round-trip) is external input; it must not be
        # accepted merely because it looks like the internal normalized shape.
        self.assert_manifest_invalid(dict(loaded))
        self.assert_manifest_invalid(json.loads(json.dumps(loaded)))

    def test_binding_document_cannot_be_constructed_by_callers(self):
        with self.assertRaises(TypeError):
            BindingDocument(
                mhs_bindings="1.0",
                adapter_id="org.example.fake-lift",
                bindings=[
                    {
                        "capability_id": "cap.motion.set-target.v1",
                        "native": "set_target",
                        "timeout_ms": 1000,
                        "concurrency": "exclusive",
                        "kind": "declarative",
                    }
                ],
            )


class PositiveControlTests(unittest.TestCase):
    def test_published_spec_example_loads_verbatim(self):
        loaded = load_bindings(support.spec_example())
        entry = loaded.bindings[0]
        self.assertEqual(loaded.adapter_id, "org.example.robosuite-lift")
        self.assertEqual(entry["native"], "gymnasium.Env.step")
        self.assertEqual(entry["args"]["action"]["enum_map"], {"left": 0, "right": 1})
        self.assertEqual(entry["result"]["reward"], {"from": "output.reward"})
        self.assertEqual(entry["timeout_ms"], 5000)
        self.assertTrue(entry["args"]["action"]["enforce_clamp"])

    def test_json_string_and_file_accept_the_canonical_document(self):
        document = support.canonical_document()
        from_string = load_bindings(json.dumps(document))
        self.assertEqual(from_string.bindings[0]["timeout_ms"], 5000)
        with support.TempDir() as tmp:
            from_file = load_bindings(support.write_document(tmp, document))
        self.assertEqual(from_file.adapter_id, "org.example.fake-lift")
        self.assertEqual(from_file.bindings[0]["timeout_ms"], 5000)

    def test_seven_dsl_primitives_execute_through_the_bridge(self):
        # field path, unit conversion, enum mapping, constant injection,
        # clamping, result mapping, ordered error mapping (ADPT-021/022).
        bridge = PythonObjectBridge(
            {"target": support.LIFT_TARGET, "bindings": copy.deepcopy(base.LIFT_BINDINGS)},
            device_id="mhs://localhost:7400/lab/lift",
        )
        try:
            native = bridge._ensure_loaded()
            result = bridge.call("cap.world.step.v1", {"action": "right"})
            self.assertEqual(native.calls, [("step", 1)])
            self.assertEqual(set(result), {"observation", "reward", "terminated", "truncated"})
            self.assertEqual(result["observation"], [1, 2])
            self.assertFalse(result["terminated"])

            joints = bridge.call("cap.motion.joints.v1", {"joints": [0, 90, 180]})
            received = native.calls[-1][1]
            self.assertEqual(len(received), 3)
            self.assertAlmostEqual(received[1], 3.141592653589793 / 2)
            self.assertAlmostEqual(joints["joints"][2], 3.141592653589793)

            with self.assertRaises(Exception) as caught:
                bridge.call("cap.motion.set-target.v1", {"target": -1})
            self.assertEqual(error_code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.motion.set-target.v1", {"target": -2})
            self.assertEqual(error_code(caught.exception), "MHS.DEVICE.BUSY")
        finally:
            bridge.close()

    def test_valid_timeout_is_preserved_at_loader_and_bridge(self):
        document = support.canonical_document(timeout_ms=5000)
        loaded = load_bindings(document)
        self.assertEqual(loaded.bindings[0]["timeout_ms"], 5000)
        bridge = PythonObjectBridge(
            {"target": support.LIFT_TARGET}, bindings=loaded, load=False
        )
        try:
            compiled = bridge._caps["cap.motion.set-target.v1"]
            self.assertEqual(compiled["timeout_ms"], 5000)
            self.assertIsNotNone(compiled["timeout_ms"])
            advertised = {
                item["capability_id"]: item for item in bridge.capabilities()
            }["cap.motion.set-target.v1"]
            self.assertEqual(advertised["timeout_ms"], 5000)
        finally:
            bridge.close()

    def test_valid_timeout_is_enforced_on_the_native_call(self):
        bridge = PythonObjectBridge(
            {"target": support.LIFT_TARGET, "bindings": copy.deepcopy(base.LIFT_BINDINGS)},
        )
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.test.slow.v1", {"seconds": 0.2})
            # a bounded native call that expires is an unknown outcome (WP-05)
            self.assertEqual(error_code(caught.exception), "MHS.OUTCOME.UNKNOWN")
            self.assertFalse(getattr(caught.exception, "retryable", True))
        finally:
            bridge.close()


class BridgeBoundaryTests(unittest.TestCase):
    def test_flattened_file_never_reaches_the_bridge(self):
        with support.TempDir() as tmp:
            path = support.write_document(tmp, support.FLATTENED_DOCUMENT)
            with self.assertRaises(Exception) as caught:
                PythonObjectBridge(
                    {"target": support.LIFT_TARGET}, bindings=path, load=False
                )
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")

    def test_flattened_string_and_dict_never_reach_the_bridge(self):
        for payload in (
            json.dumps(support.FLATTENED_DOCUMENT),
            copy.deepcopy(support.FLATTENED_DOCUMENT),
        ):
            with self.subTest(kind=type(payload).__name__):
                with self.assertRaises(Exception) as caught:
                    PythonObjectBridge(
                        {"target": support.LIFT_TARGET}, bindings=payload, load=False
                    )
                self.assertEqual(
                    error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID"
                )

    def test_canonical_file_loads_and_executes(self):
        with support.TempDir() as tmp:
            path = support.write_document(tmp, support.canonical_document())
            bridge = PythonObjectBridge(
                {"target": support.LIFT_TARGET}, bindings=path, load=False
            )
        try:
            native = bridge._ensure_loaded()
            result = bridge.call("cap.motion.set-target.v1", {"target": 5})
            self.assertEqual(native.calls, [("set_target", 5)])
            self.assertEqual(result["target"], 5)
        finally:
            bridge.close()

    def test_out_of_envelope_value_raises_instead_of_clamping(self):
        document = support.canonical_document()
        with support.TempDir() as tmp:
            path = support.write_document(tmp, document)
            bridge = PythonObjectBridge(
                {"target": support.LIFT_TARGET}, bindings=path, load=False
            )
        try:
            native = bridge._ensure_loaded()
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.motion.set-target.v1", {"target": 999})
            self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(native.calls, [])
            # The same bridge still accepts a value inside the envelope.
            result = bridge.call("cap.motion.set-target.v1", {"target": 5})
            self.assertEqual(result["target"], 5)
        finally:
            bridge.close()

    def test_tampered_timeout_is_rejected_at_compilation(self):
        loaded = load_bindings(support.canonical_document())
        loaded["bindings"][0]["timeout_ms"] = 0
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": support.LIFT_TARGET}, bindings=loaded, load=False)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")

    def test_tampered_clamp_cannot_fall_back_to_silent_clamping(self):
        loaded = load_bindings(support.canonical_document())
        rule = loaded["bindings"][0]["args"]["target"]
        rule["enforce_clamp"] = False  # simulate post-load mutation of the dict
        bridge = PythonObjectBridge(
            {"target": support.LIFT_TARGET}, bindings=loaded, load=False
        )
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("cap.motion.set-target.v1", {"target": 999})
            self.assertEqual(error_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        finally:
            bridge.close()


class LegacyMappingIsNotExternalInputTests(unittest.TestCase):
    """The legacy in-process SDK shape is not reachable through a document."""

    def test_a_flattened_clamp_rule_cannot_be_loaded_as_a_document(self):
        with support.TempDir() as tmp:
            path = support.write_document(tmp, support.FLATTENED_DOCUMENT)
            with self.assertRaises(Exception) as caught:
                load_bindings(path)
        self.assertEqual(error_code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        # No API on the external path produces the old target==10 clamp result.
        self.assertNotIn("target", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
