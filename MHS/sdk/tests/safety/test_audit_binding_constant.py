"""Injected binding constants take the same checks as path values.

ADPT-024 and CORE-048: a clamp is a limit. The value that would be passed to
the native call is rejected with ``MHS.SAFETY.ENVELOPE_VIOLATION`` when it is
outside the clamp, and the clamp is applied after unit conversion (SAFE-015,
MHS-006 §7.2). ``_Rule.apply`` used to return a ``value``/``const`` immediately,
so a document ``load_bindings`` accepted could map speed 100 through a 0..1
clamp, and a constant 1000 declared with an mm-to-m conversion stayed 1000.
"""

from __future__ import annotations

import unittest
from typing import Any

from mhs.bridge.base import FieldMapping, MappingError
from mhs.bridge.bindings import load_bindings
from mhs.bridge.python import PythonObjectBridge

_DEVICE = "mhs://localhost:7400/lab/stage"
_TARGET = "tests.safety.test_audit_binding_constant:Stage"


class Stage:
    """Native target for the constant-argument regression. Records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def set_speed(self, speed: Any) -> dict[str, bool]:
        self.calls.append(("set_speed", speed))
        return {"done": True}

    def set_distance(self, distance: Any) -> dict[str, bool]:
        self.calls.append(("set_distance", distance))
        return {"done": True}


def _code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


def _binding(capability_id: str, native: str, args: dict[str, Any], *,
             units: dict[str, Any] | None = None, clamp: dict[str, Any] | None = None,
             constants: dict[str, Any] | None = None) -> dict[str, Any]:
    inner: dict[str, Any] = {
        "bridge": "python-object",
        "kind": "declarative",
        "native": native,
        "args": args,
        "result": {"map": {"done": "output.done"}},
        "concurrency": "exclusive",
        "timeout_ms": 1000,
    }
    if units is not None:
        inner["units"] = units
    if clamp is not None:
        inner["clamp"] = clamp
    if constants is not None:
        inner["constants"] = constants
    return {
        "device_id": _DEVICE,
        "capability_id": capability_id,
        "resource": "stage",
        "binding": inner,
    }


def _document(*entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "mhs_bindings": "1.0",
        "adapter_id": "org.example.audit-constant",
        "bindings": list(entries),
    }


def _args(document: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return load_bindings(document).bindings[index]["args"]


def _map(document: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return FieldMapping(_args(document, index), direction="input").map({})


class CanonicalConstantTests(unittest.TestCase):
    """The audit's load_bindings cases: clamp rejection and unit conversion."""

    def test_speed_constant_outside_clamp_is_rejected_before_native(self) -> None:
        document = _document(_binding(
            "x-cap.test.speed.v1",
            "set_speed",
            {"speed": {"value": 100}},
            clamp={"speed": {"min": 0, "max": 1}},
        ))
        loaded = load_bindings(document)
        rule = loaded.bindings[0]["args"]["speed"]
        self.assertEqual(rule["value"], 100)
        self.assertEqual(rule["clamp"], {"min": 0, "max": 1})
        with self.assertRaises(Exception) as caught:
            FieldMapping(loaded.bindings[0]["args"], direction="input").map({})
        self.assertEqual(_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")

        bridge = PythonObjectBridge(
            {"target": _TARGET, "bindings": document}, device_id=_DEVICE,
        )
        try:
            native = bridge._ensure_loaded()
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.test.speed.v1", {})
            self.assertEqual(_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(native.calls, [])
        finally:
            bridge.close()

    def test_constants_object_outside_clamp_is_rejected(self) -> None:
        # ADPT-040 also injects constants{target: value}. The clamp is declared
        # on the argument the constant fills, so the injected 100 is in range
        # of nothing: 0..1 still refuses it.
        document = _document(_binding(
            "x-cap.test.speed.v1",
            "set_speed",
            {"speed": {"default": 0}},
            constants={"speed": 100},
            clamp={"speed": {"min": 0, "max": 1}},
        ))
        loaded_args = _args(document)
        self.assertEqual(loaded_args["speed"]["value"], 100)
        with self.assertRaises(Exception) as caught:
            FieldMapping(loaded_args, direction="input").map({})
        self.assertEqual(_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_constant_millimetres_convert_to_metres(self) -> None:
        document = _document(_binding(
            "x-cap.test.distance.v1",
            "set_distance",
            {"distance": {"value": 1000}},
            units={"distance": {"from": "mm", "to": "m", "factor": 0.001}},
        ))
        loaded = load_bindings(document)
        unit = loaded.bindings[0]["args"]["distance"]["unit"]
        self.assertEqual((unit["from"], unit["to"]), ("mm", "m"))
        mapped = FieldMapping(loaded.bindings[0]["args"], direction="input").map({})
        self.assertAlmostEqual(mapped["distance"], 1.0)
        self.assertNotEqual(mapped["distance"], 1000)

        bridge = PythonObjectBridge(
            {"target": _TARGET, "bindings": document}, device_id=_DEVICE,
        )
        try:
            native = bridge._ensure_loaded()
            result = bridge.call("x-cap.test.distance.v1", {})
            self.assertEqual(result, {"done": True})
            self.assertEqual(len(native.calls), 1)
            self.assertEqual(native.calls[0][0], "set_distance")
            self.assertAlmostEqual(native.calls[0][1], 1.0)
        finally:
            bridge.close()

    def test_clamp_sees_the_converted_constant(self) -> None:
        # 1000 mm is 1 m, inside 0..1 m. 2000 mm is 2 m and is refused.
        # The violation reports the converted value, not the raw constant.
        inside = _document(_binding(
            "x-cap.test.distance.v1",
            "set_distance",
            {"distance": {"value": 1000}},
            units={"distance": {"from": "mm", "to": "m", "factor": 0.001}},
            clamp={"distance": {"min": 0, "max": 1, "unit": "m"}},
        ))
        mapped = _map(inside)
        self.assertAlmostEqual(mapped["distance"], 1.0)

        outside = _document(_binding(
            "x-cap.test.distance.v1",
            "set_distance",
            {"distance": {"value": 2000}},
            units={"distance": {"from": "mm", "to": "m", "factor": 0.001}},
            clamp={"distance": {"min": 0, "max": 1, "unit": "m"}},
        ))
        with self.assertRaises(Exception) as caught:
            _map(outside)
        self.assertEqual(_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        details = getattr(caught.exception, "data", {}).get("details", {})
        self.assertAlmostEqual(details.get("value"), 2.0)

    def test_constant_unit_overflow_is_refused_before_native(self) -> None:
        document = _document(_binding(
            "x-cap.test.distance.v1",
            "set_distance",
            {"distance": {"value": 1e308}},
            units={"distance": {"from": "m", "to": "mm", "factor": 1000}},
        ))
        loaded_args = _args(document)
        with self.assertRaises(MappingError):
            FieldMapping(loaded_args, direction="input").map({})

        bridge = PythonObjectBridge(
            {"target": _TARGET, "bindings": document}, device_id=_DEVICE,
        )
        try:
            native = bridge._ensure_loaded()
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.test.distance.v1", {})
            self.assertEqual(_code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
            self.assertEqual(native.calls, [])
        finally:
            bridge.close()

    def test_in_range_and_plain_constants_are_unchanged(self) -> None:
        document = _document(_binding(
            "x-cap.test.speed.v1",
            "set_speed",
            {"speed": {"value": 0.5}, "mode": {"value": "auto"}, "flag": {"value": True}},
            clamp={"speed": {"min": 0, "max": 1}},
        ))
        self.assertEqual(_map(document), {"speed": 0.5, "mode": "auto", "flag": True})


class ConstantTransformTests(unittest.TestCase):
    """The same rule object also carries legacy ``const`` and the other transforms."""

    def test_legacy_const_outside_clamp_is_rejected(self) -> None:
        mapping = FieldMapping(
            {"speed": {"const": 100, "clamp": {"min": 0, "max": 1}}},
            direction="input",
        )
        with self.assertRaises(Exception) as caught:
            mapping.map({})
        self.assertEqual(_code(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_constant_enum_type_and_scale_match_path_values(self) -> None:
        mapping = FieldMapping(
            {
                "gate": {"value": "closed", "enum_map": {"closed": 0, "open": 1}},
                "count": {"value": "4", "type": "integer"},
                "gain": {"const": 1000, "scale": 0.001},
            },
            direction="input",
        )
        mapped = mapping.map({})
        self.assertEqual(mapped["gate"], 0)
        self.assertEqual(mapped["count"], 4)
        self.assertAlmostEqual(mapped["gain"], 1.0)
        with self.assertRaises(MappingError):
            FieldMapping(
                {"count": {"value": "nope", "type": "integer"}},
                direction="input",
            ).map({})

    def test_non_finite_constant_is_refused(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            mapping = FieldMapping({"speed": {"value": value}}, direction="input")
            with self.assertRaises(MappingError):
                mapping.map({})


if __name__ == "__main__":
    unittest.main()
