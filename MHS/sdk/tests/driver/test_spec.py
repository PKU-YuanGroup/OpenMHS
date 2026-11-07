"""Field, Limit and Fact declarations (no catalogue, no server)."""

from __future__ import annotations

import unittest

from mhs import limits
from mhs.driver import Action, DriverDefinitionError, Field, Limit


class FieldSchemaTests(unittest.TestCase):
    def test_scalar_and_python_type_shorthands(self) -> None:
        self.assertEqual(Field(float, unit="Cel").to_schema(), {"type": "number", "x-mhs-unit": "Cel"})
        self.assertEqual(Field(int).to_schema(), {"type": "integer"})
        self.assertEqual(Field(bool).to_schema(), {"type": "boolean"})
        self.assertEqual(Field(str, max_length=8, enum=["a", "b"]).to_schema(),
                         {"type": "string", "enum": ["a", "b"], "maxLength": 8})
        self.assertEqual(Field("number", nullable=True).to_schema(), {"type": ["number", "null"]})
        self.assertEqual(Field("number", unit="K", delta=True).to_schema(),
                         {"type": "number", "x-mhs-unit": "K", "x-mhs-delta": True})

    def test_arrays_put_the_unit_on_their_elements(self) -> None:
        self.assertEqual(Field("array", items="number", length=6, unit="rad").to_schema(),
                         {"type": "array", "items": {"type": "number", "x-mhs-unit": "rad"},
                          "minItems": 6, "maxItems": 6})
        self.assertEqual(Field(unit="rad", length=2).to_schema(),
                         {"items": {"type": "number", "x-mhs-unit": "rad"}, "minItems": 2, "maxItems": 2})
        with self.assertRaises(DriverDefinitionError):
            Field("array", items=Field("number", unit="deg"), unit="rad").to_schema()

    def test_objects_are_closed_inline_and_open_as_refinements(self) -> None:
        inline = Field("object", properties={"x": Field("number", unit="mm"),
                                             "label": Field("string", required=False)})
        self.assertEqual(inline.to_schema(), {"type": "object", "properties": {
            "x": {"type": "number", "x-mhs-unit": "mm"}, "label": {"type": "string"}},
            "required": ["x"], "additionalProperties": False})
        refinement = Field(properties={"x": Field(unit="mm")})
        self.assertEqual(refinement.to_schema(), {"properties": {"x": {"x-mhs-unit": "mm"}}})

    def test_limit_entries_follow_members_elements_and_relative_paths(self) -> None:
        field = Field("object", properties={
            "joints": Field("array", items="number", length=2, unit="rad",
                            limit=[Limit(min=[-1, -2], max=[1, 2], source="vendor_doc", ref="a:1"),
                                   Limit(max=0.5, path="[1]", source="vendor_doc", ref="a:2")]),
            "tool": Field("object", properties={"z": Field("number", unit="mm",
                                                           limit=Limit(max=10, source="vendor_doc", ref="a:3"))}),
        })
        self.assertEqual([key for key, _limit in field.limit_entries("pose")],
                         ["pose.joints", "pose.joints[1]", "pose.tool.z"])

    def test_invalid_fields(self) -> None:
        for kwargs in ({"type": "decimal"}, {"type": "string", "unit": "m"}, {"type": "number", "length": 2},
                       {"type": "array", "length": 0}, {"type": "array", "length": 2, "min_items": 1},
                       {"type": "number", "properties": {"x": Field("number")}}, {"type": "string", "pattern": "("},
                       {"type": "number", "native_unit": "K"}, {"type": "number", "enum": []}):
            with self.subTest(kwargs=kwargs), self.assertRaises(DriverDefinitionError):
                Field(**kwargs)


class LimitTests(unittest.TestCase):
    def test_limit_wraps_a_closed_rule(self) -> None:
        limit = Limit(min=-20, max=150, unit="Cel", source="upstream_code", ref="pkg/mod.py:88", reason="range")
        self.assertIsInstance(limit.rule(), limits.LimitRule)
        self.assertEqual(limit.to_json(), {"min": -20, "max": 150, "unit": "Cel", "reason": "range",
                                           "source": "upstream_code", "ref": "pkg/mod.py:88"})
        self.assertEqual(limit.key("setpoint"), "setpoint")
        self.assertEqual(Limit(max=1, path="[*]").key("joints"), "joints[*]")
        self.assertEqual(Limit(max=1, path="x").key("pose"), "pose.x")

    def test_operator_required(self) -> None:
        limit = Limit.operator_required("no documented bound")
        self.assertTrue(limit.is_operator_required)
        self.assertIsNone(limit.rule())
        self.assertEqual(limit.to_json(), "operator_required")
        self.assertEqual(limit.reason, "no documented bound")
        self.assertIn("operator_required", repr(limit))

    def test_class_default_is_not_an_author_source(self) -> None:
        with self.assertRaises(DriverDefinitionError):
            Limit(max=1, source="class_default")
        with self.assertRaises(DriverDefinitionError):
            Limit(max=10**20, source="vendor_doc", ref="a:1")


class ActionTests(unittest.TestCase):
    def test_risk_is_one_of_the_risk_classes(self) -> None:
        # A typo must not leave the device at R0 below the author's intent (verifier probe_misc).
        for risk in ("R0", "R3", None):
            self.assertEqual(Action(risk=risk).risk, risk)
        for risk in ("r2", "R9", 2, ""):
            with self.subTest(risk=risk), self.assertRaises(DriverDefinitionError) as caught:
                Action(risk=risk)
            self.assertIn("risk must be one of", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
