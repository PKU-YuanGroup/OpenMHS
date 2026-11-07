"""Leftovers of the WP-03 verification (ported from the reviewer repros in verify-WP-03/r2).

* ``probe1.py`` 1: overlay rules on related keys of one array were order dependent;
* ``probe1.py``/``probe2.py`` 2: ``units.conversion`` raised ``OverflowError`` beyond the double range;
* ``probe1.py`` 3: ``Violation.to_details`` carried integer bounds that ``canonical.jcs`` refuses;
* ``probe1.py`` 7/8: drift did not descend into a binding's ``allOf`` or local ``$ref``;
* ``probe2.py``: read bindings rendered as measures lost their optional inputs (12 classes);
* ``probe_overlay_mismatch.py``: a reference file recorded an overlay its limits never applied.
"""

from __future__ import annotations

import copy
import unittest

from mhs import canonical, catalog, limits, reference_file, units
from mhs.limits import LimitConfigError, LimitRule, LimitSource, Violation, check, compile_limits
from mhs.reference_file import ReferenceFileError, dump, render
from mhs.schema import validate

from ._support import VALID, load_json

TRIPLE = {"type": "object", "properties": {
    "a": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "number"}},
    "d": {"type": "number", "x-mhs-unit": "s"},
    "on_time_s": {"type": "number", "x-mhs-unit": "s"},
}}


def _overlay(rules):
    return [LimitSource("overlay", rules, narrow_only=True)]


class OverlayOrderTests(unittest.TestCase):
    """Narrow-only rules are checked against the regular sources only, so their order never matters."""

    BASE = [LimitSource("binding", {"a": {"max": 0.5}, "d": {"max": 10},
                                    "on_time_s": {"max": 3600, "per": "rolling_24h"}})]

    def compile(self, rules):
        return compile_limits(TRIPLE, self.BASE, _overlay(rules))

    def test_related_keys_in_either_order(self):
        # reviewer repro probe1.py 1: a[2] then a was refused, a then a[2] accepted
        one = self.compile({"a[2]": {"max": 0.25}, "a": {"max": 0.3}})
        two = self.compile({"a": {"max": 0.3}, "a[2]": {"max": 0.25}})
        self.assertEqual(one.to_json(), two.to_json())
        self.assertEqual(sorted(one.narrowed), sorted(two.narrowed))
        self.assertEqual(sorted(one.narrowed), ["a.max: 0.5 -> 0.3", "a[2].max: 0.5 -> 0.25"])
        for effective in (one, two):
            self.assertEqual([(v.path, v.bound) for v in check({"a": [0.31, 0, 0.26]}, effective)],
                             [("a[0]", 0.3), ("a[2]", 0.25)])
        # the wider of two overlay rules never widens: the intersection still applies
        three = self.compile({"a": {"max": 0.25}, "a[2]": {"max": 0.3}})
        four = self.compile({"a[2]": {"max": 0.3}, "a": {"max": 0.25}})
        self.assertEqual(three.to_json(), four.to_json())
        self.assertEqual([v.path for v in check({"a": [0, 0, 0.28]}, three)], ["a[2]"])
        self.assertEqual([v.path for v in check({"a": [0, 0, 0.28]}, four)], ["a[2]"])

    def test_widening_the_regular_sources_is_refused_in_either_order(self):
        for rules in ({"a[2]": {"max": 0.6}, "a": {"max": 0.3}}, {"a": {"max": 0.3}, "a[2]": {"max": 0.6}},
                      {"a": {"max": 0.6}, "a[2]": {"max": 0.3}}, {"a[2]": {"max": 0.3}, "a": {"max": 0.6}}):
            with self.subTest(rules=list(rules)):
                with self.assertRaises(LimitConfigError) as caught:
                    self.compile(rules)
                self.assertEqual(caught.exception.rule, "overlay-narrows")
                self.assertEqual(caught.exception.source, "overlay")

    def test_two_overlay_layers_on_one_key(self):
        # the configure class reads a capability-keyed and a parameter-keyed overlay entry
        for first, second in ((4, 5), (5, 4)):
            with self.subTest(order=(first, second)):
                effective = compile_limits(TRIPLE, self.BASE, [LimitSource("overlay", {"d": {"max": first}}),
                                                               LimitSource("overlay", {"d": {"max": second}})])
                self.assertEqual(effective.rules["d"].max.value, 4)
                self.assertIn("d.max: 10 -> 4", effective.narrowed)
        with self.assertRaises(LimitConfigError):
            compile_limits(TRIPLE, self.BASE, [LimitSource("overlay", {"d": {"max": 4}}),
                                               LimitSource("overlay", {"d": {"max": 11}})])

    def test_cumulative_overlay_layers(self):
        for first, second in ((1800, 3000), (3000, 1800)):
            with self.subTest(order=(first, second)):
                effective = compile_limits(TRIPLE, self.BASE, [
                    LimitSource("overlay", {"on_time_s": {"max": first, "per": "rolling_24h"}}),
                    LimitSource("overlay", {"on_time_s": {"max": second, "per": "rolling_24h"}})], )
                self.assertEqual([c.max.value for c in effective.cumulative], [1800])
        with self.assertRaises(LimitConfigError):
            compile_limits(TRIPLE, self.BASE, [
                LimitSource("overlay", {"on_time_s": {"max": 1800, "per": "rolling_24h"}}),
                LimitSource("overlay", {"on_time_s": {"max": 7200, "per": "rolling_24h"}})])


class CanonicalSafetyTests(unittest.TestCase):
    def test_bounds_beyond_the_canonical_integer_range_are_refused(self):
        # reviewer repro probe1.py 3: max 2**60 compiled, then to_details() broke canonical.jcs
        for value in ({"max": 2**60}, {"min": -(2**53)}, {"max": [1, 2**60]}, {"allowed": [1, 2**61]}):
            with self.subTest(rule=value):
                with self.assertRaises(LimitConfigError) as caught:
                    LimitRule.parse(value)
                self.assertEqual(caught.exception.rule, "limit-rule-invalid")
        self.assertEqual(LimitRule.parse({"max": 2**53 - 1}).max, 2**53 - 1)
        self.assertEqual(LimitRule.parse({"max": 1e300}).max, 1e300)   # a double is fine

    def test_violation_details_are_always_canonical_json(self):
        effective = compile_limits({"type": "object", "properties": {"d": {"type": "integer"}}},
                                   [("binding", {"d": {"max": 10}})])
        details = check({"d": 2**61}, effective)[0].to_details()
        self.assertEqual(details["value"], str(2**61))
        canonical.jcs(details)
        made = Violation(path="d", kind="max", bound=2**60, value={"nested": [2**62, 1.5]})
        details = made.to_details()
        self.assertEqual(details["bound"], str(2**60))
        self.assertEqual(details["value"], {"nested": [str(2**62), 1.5]})
        canonical.jcs(details)
        listed = Violation(path="m", kind="allowed", bound=["a", 2**60], value="b").to_details()
        self.assertEqual(listed["bound"], ["a", str(2**60)])
        canonical.jcs(listed)


class UnitOverflowTests(unittest.TestCase):
    def test_factors_beyond_the_double_range_raise_unit_error(self):
        # reviewer repro probe2.py: OverflowError escaped from conversion() and convert(factor=)
        for call in (lambda: units.conversion("Ym20", "m20"),
                     lambda: units.convert(1, "Ym20", "m20", factor=1.0),
                     lambda: units.convert(1, "Ym20", "m20"),
                     lambda: units.conversion("ym20", "Ym20")):     # a factor that rounds to 0.0
            with self.assertRaises(units.UnitError):
                call()
        self.assertEqual(units.convert(0, "Ym20", "m20"), 0.0)      # exact: zero stays zero
        self.assertEqual(units.conversion("m", "mm"), (1000.0, 0.0))


class DriftCombinatorTests(unittest.TestCase):
    CAP = "cap.thermal.setpoint.v1"

    def kinds(self, schema):
        return sorted((item.kind, item.path) for item in catalog.resolve_binding(self.CAP, schema).drift)

    def test_ref_and_all_of_are_compared_with_the_class(self):
        # reviewer repro probe1.py 7/8: no drift although the merged schema can never accept a value
        by_ref = {"$ref": "#/$defs/x", "$defs": {"x": {"type": "object",
                                                       "properties": {"target_temperature": {"type": "string"}}}}}
        self.assertEqual(self.kinds(by_ref), [("type-differs", "input.target_temperature")])
        cases = [
            ({"allOf": [{"type": "object", "properties": {"temp": {"type": "number"}}}]},
             [("property-not-in-class", "input.temp")]),
            ({"allOf": [{"properties": {"rate": {"type": "number", "minimum": -1}}}]}, [("widens", "input.rate")]),
            ({"allOf": [{"properties": {"tolerance": {"x-mhs-unit": "mK"}}}]}, [("unit-differs", "input.tolerance")]),
            ({"allOf": [{"$ref": "#/$defs/t"}], "$defs": {"t": {"properties": {"wait": {"type": "integer"}}}}},
             [("type-differs", "input.wait")]),
            ({"properties": {"target_temperature": {"$ref": "#/$defs/t"}},
              "$defs": {"t": {"type": "number", "x-mhs-unit": "K"}}},
             [("unit-differs", "input.target_temperature")]),
            # a stated required set is read together with the required lists of its branches
            ({"required": ["wait"], "allOf": [{"required": ["rate"]}]}, [("required-missing", "input")]),
        ]
        for schema, expected in cases:
            with self.subTest(schema=schema):
                self.assertEqual(self.kinds(dict(schema, type="object")), expected)

    def test_combinators_that_narrow_are_not_drift(self):
        narrow = [
            {"allOf": [{"type": "object", "properties": {"target_temperature": {"type": "number", "maximum": 100}}}]},
            {"allOf": [{"properties": {"target_temperature": {}}, "required": ["target_temperature"]},
                       {"properties": {"wait": {"type": "boolean"}}, "required": ["wait"]}]},
            {"$ref": "#/$defs/x", "$defs": {"x": {"type": "object", "required": ["target_temperature"],
                                                   "properties": {"target_temperature": {"type": "integer"}}}}},
            # a branch only adds required properties; the class's stay required (inherited at the top)
            {"allOf": [{"properties": {"wait": {}}, "required": ["wait"]}]},
            {"required": ["wait"], "allOf": [{"required": ["target_temperature"]}]},
        ]
        for schema in narrow:
            with self.subTest(schema=schema):
                self.assertEqual(self.kinds(schema), [])
        # the merged schema keeps the class-required property next to the branch's
        effective = catalog.resolve_binding(self.CAP, {"allOf": [{"properties": {"wait": {}}, "required": ["wait"]}]})
        self.assertNotEqual(validate({"wait": True}, effective.input_schema), [])
        self.assertEqual(validate({"wait": True, "target_temperature": 20}, effective.input_schema), [])
        # a reference cycle terminates
        cycle = {"$ref": "#/$defs/a", "$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"allOf": [{"$ref": "#/$defs/a"}]}}}
        self.assertEqual(self.kinds(cycle), [])


class MeasureInputTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(VALID / "device.thermal-bath.json")

    def test_optional_inputs_of_a_read_measure_are_kept(self):
        reference = render(self.manifest)
        measure = next(item for item in reference["measures"] if item.get("cap_id") == "cap.measure.temperature.v1")
        self.assertEqual([(item["name"], item["type"], item["required"]) for item in measure["inputs"]],
                         [("location", "string", False), ("probe", "string", False)])
        self.assertEqual(reference_file.validate(reference), [])
        self.assertIn("`location`", reference_file.render_markdown(reference))

    def test_every_catalogue_read_measure_keeps_its_inputs(self):
        # reviewer repro probe2.py: 12 read classes with optional inputs lost them
        cat = catalog.default_catalog()
        checked = []
        for capability_id in cat.ids():
            entry = cat.get(capability_id)
            properties = (entry.get("input_schema") or {}).get("properties") or {}
            if (entry.get("verb") != "read" or not properties or (entry.get("input_schema") or {}).get("required")
                    or entry.get("limits") or entry.get("requires_permit") or entry.get("risk_class", "R0") != "R0"):
                continue
            manifest = {
                "device_id": "mhs://localhost/test/reader", "mode": "simulated",
                "resources": [{"resource_id": "r", "kind": entry["resource_kinds"][0]}],
                "capabilities": [{"capability_id": capability_id, "resource": "r"}],
                "safety": {"risk_class": "R0"},
            }
            with self.subTest(capability_id=capability_id):
                reference = render(manifest)
                measure = next(item for item in reference["measures"] if item.get("cap_id") == capability_id)
                names = {item["name"] for item in measure.get("inputs") or []}
                self.assertTrue(set(properties) <= names, sorted(set(properties) - names))
                self.assertFalse(any(item.get("required") for item in measure["inputs"]))
                checked.append(capability_id)
        self.assertGreaterEqual(len(checked), 12)

    def test_a_read_without_input_has_no_inputs_member(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["capabilities"].append({
            "capability_id": "x-cap.example.level.v1", "resource": "bath", "verb": "read", "title": "Fluid level",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {"type": "object", "properties": {"level": {"type": "number", "x-mhs-unit": "mm"}},
                              "required": ["level"]},
        })
        measure = next(item for item in render(manifest)["measures"] if item.get("cap_id") == "x-cap.example.level.v1")
        self.assertEqual((measure["type"], measure["unit"]), ("number", "mm"))
        self.assertNotIn("inputs", measure)


class OverlayRecordTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(VALID / "device.thermal-bath.json")
        self.overlay = load_json(VALID / "site-limits.example-lab.json")

    def test_an_overlay_the_limits_do_not_apply_is_refused(self):
        # reviewer repro probe_overlay_mismatch.py: limits compiled without the overlay, overlay recorded
        without = catalog.compile_manifest_limits(self.manifest)
        for given in (without, without.by_capability(),
                      {"cap.thermal.setpoint.v1": without.get("cap.thermal.setpoint.v1").limits}):
            with self.subTest(given=type(given).__name__):
                with self.assertRaises(ReferenceFileError) as caught:
                    render(self.manifest, given, overlay=self.overlay)
                self.assertIn("overlay", str(caught.exception))

    def test_limits_compiled_with_the_overlay_are_accepted(self):
        compiled = catalog.compile_manifest_limits(self.manifest, self.overlay)
        expected = dump(render(self.manifest, overlay=self.overlay))
        self.assertEqual(dump(render(self.manifest, compiled, overlay=self.overlay)), expected)
        self.assertEqual(dump(render(self.manifest, compiled.by_capability(), overlay=self.overlay)), expected)
        # without an overlay, given limits are the caller's business (they are rendered as given)
        narrower = limits.compile_limits(compiled.get("cap.thermal.setpoint.v1").effective.input_schema,
                                         [("binding", {"target_temperature": {"min": 10, "max": 40, "unit": "Cel"}})])
        self.assertIsNone(render(self.manifest, {"cap.thermal.setpoint.v1": narrower})["overlay"])


class DeltaFieldTests(unittest.TestCase):
    def test_catalogue_temperature_differences_never_get_an_offset(self):
        entry = catalog.get("cap.thermal.setpoint.v1")
        tolerance = entry["input_schema"]["properties"]["tolerance"]
        rate = entry["input_schema"]["properties"]["rate"]
        self.assertTrue(units.field_is_delta(tolerance))
        self.assertTrue(units.field_is_delta(rate))
        self.assertEqual(units.convert(0.5, tolerance["x-mhs-unit"], "Cel", delta=units.field_is_delta(tolerance)), 0.5)
        self.assertFalse(units.field_is_delta(entry["input_schema"]["properties"]["target_temperature"]))
        effective = catalog.resolve_binding("cap.thermal.setpoint.v1",
                                            {"type": "object", "properties": {"target_temperature": {},
                                                                              "tolerance": {"maximum": 2}}})
        self.assertIs(effective.input_schema["properties"]["tolerance"].get("x-mhs-delta"), True)
        self.assertEqual(validate({"target_temperature": 20, "tolerance": 1}, effective.input_schema), [])


if __name__ == "__main__":
    unittest.main()
