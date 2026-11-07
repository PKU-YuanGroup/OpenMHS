"""mhs.limits: path grammar, closed rules, intersection, narrow-only overlays and runtime checks."""

from __future__ import annotations

import copy
import unittest

from mhs import limits
from mhs.limits import (
    WILDCARD,
    LimitConfigError,
    LimitRule,
    LimitSource,
    check,
    compile_limits,
    parse_path,
)

JOINTS = ["base", "shoulder", "elbow", "wrist1", "wrist2", "wrist3"]

ARM = {
    "type": "object",
    "properties": {
        "joint_positions": {
            "type": "array",
            "items": {"type": "number", "x-mhs-unit": "rad", "minimum": -6.3, "maximum": 6.3},
            "minItems": 6,
            "maxItems": 6,
        },
        "duration_s": {"type": "number", "x-mhs-unit": "s", "minimum": 0, "default": 2.0},
        "speeds": {"type": "array", "items": {"type": "number", "x-mhs-unit": "rad/s"}, "maxItems": 64},
        "block": {"type": "boolean"},
        "mode": {"type": "string", "enum": ["fast", "safe", "teach"]},
    },
    "required": ["joint_positions"],
    "additionalProperties": False,
}

POSE = {
    "type": "object",
    "properties": {
        "position": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "x-mhs-unit": "mm"},
                "y": {"type": "number", "x-mhs-unit": "mm"},
                "z": {"type": "number", "x-mhs-unit": "mm", "default": 250},
            },
            "required": ["x", "y"],
        },
        "waypoints": {
            "type": "array",
            "items": {"type": "object", "properties": {"x": {"type": "number", "x-mhs-unit": "mm"},
                                                     "label": {"type": "string"}}},
        },
        "grid": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "frame": {"type": "string", "enum": ["base", "tool"]},
    },
    "required": ["position"],
}

LOW = [-3.1, -2.0, -2.8, -3.1, -1.5, -6.2]
HIGH = [3.1, 2.0, 0.5, 3.1, 1.5, 6.2]


def _arm(**rule):
    return compile_limits(ARM, [("binding", {"joint_positions": rule})])


class PathGrammarTests(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(parse_path("ticks"), ("ticks",))
        self.assertEqual(parse_path("position.x"), ("position", "x"))
        self.assertEqual(parse_path("joints[*]"), ("joints", WILDCARD))
        self.assertEqual(parse_path("joints[3]"), ("joints", 3))
        self.assertEqual(parse_path("a[0].b[*].c"), ("a", 0, "b", WILDCARD, "c"))
        self.assertEqual(limits.format_path(parse_path("a[0].b[*].c")), "a[0].b[*].c")

    def test_bad_paths(self):
        for path in ("", "a.", ".a", "a..b", "a[-1]", "a[x]", "a[", "1a", "a b", "a[1", "a]", "a.b-c", "x" * 257):
            with self.subTest(path=path):
                with self.assertRaises(LimitConfigError) as caught:
                    parse_path(path)
                self.assertEqual(caught.exception.rule, "limit-path-grammar")

    def test_tokens_match_the_bridge_field_path_reader(self):
        from mhs.bridge import base

        for path in ("ticks", "position.x", "joints[*]", "joints[3]", "a[0].b[*].c", "a_b.c_d[12]"):
            with self.subTest(path=path):
                bridge = [WILDCARD if token is base._WILDCARD else token for token in base._tokenize(path)]
                self.assertEqual(list(parse_path(path)), bridge)
        payload = {"position": {"x": 1}, "joints": [1, 2, 3], "a": [{"b": [{"c": 5}]}]}
        self.assertEqual(base.get_path(payload, "position.x"), 1)
        self.assertEqual(base.get_path(payload, "joints[2]"), 3)
        self.assertEqual(base.get_path(payload, "a[0].b[0].c"), 5)


class RuleTests(unittest.TestCase):
    def test_closed_rule(self):
        for rule in ({"maxx": 5}, {"max": 5, "clamp": True}, {"max": 5, "banana": 1}):
            with self.subTest(rule=rule):
                with self.assertRaises(LimitConfigError) as caught:
                    LimitRule.parse(rule)
                self.assertEqual(caught.exception.rule, "unknown-rule-member")

    def test_invalid_members(self):
        for rule in ({}, {"max": "5"}, {"max": True}, {"max": float("nan")}, {"max": []}, {"allowed": []},
                     {"allowed": [None]}, {"source": "guess"}, {"max": 1, "source": "vendor_doc"},
                     {"max": 1, "source": "upstream_code", "ref": ""}, {"names": []}, {"per": "daily", "max": 1},
                     {"per": "rolling_1h"}, {"min": [0, 1], "max": [1, 2, 3]}):
            with self.subTest(rule=rule):
                with self.assertRaises(LimitConfigError):
                    LimitRule.parse(rule)
        with self.assertRaises(LimitConfigError):
            LimitRule.parse("operator_requird")

    def test_empty_range_in_one_rule(self):
        with self.assertRaises(LimitConfigError) as caught:
            LimitRule.parse({"min": 5, "max": 1})
        self.assertEqual(caught.exception.rule, "empty-range")
        with self.assertRaises(LimitConfigError):
            LimitRule.parse({"min": [0, 0, 3], "max": 2})

    def test_round_trip(self):
        rule = {"min": -20, "max": 150, "unit": "Cel", "source": "vendor_doc", "ref": "manual p.12",
                "reason": "rated range", "per": None}
        rule.pop("per")
        self.assertEqual(LimitRule.parse(rule).to_json(), rule)
        self.assertEqual(LimitRule.parse({"max": 3600, "per": "rolling_24h"}).to_json(),
                         {"max": 3600, "per": "rolling_24h"})


class CompileTests(unittest.TestCase):
    def test_unresolvable_path(self):
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"joint_positons": {"max": 1}})])
        self.assertEqual(caught.exception.rule, "limit-path-resolves")
        self.assertEqual(caught.exception.source, "binding")
        for path in ("joint_positions[6]", "duration_s.x", "block[0]", "mode.a"):
            with self.subTest(path=path):
                with self.assertRaises(LimitConfigError):
                    compile_limits(ARM, [("binding", {path: {"max": 1}})])

    def test_a_ref_without_a_source_is_published(self):
        # A Gymnasium driver's bounds from its fake's action space name the backend in ref and claim no source.
        ref = "action_space of the fake backend .fake:FakeArm"
        effective = compile_limits(ARM, [("binding", {"duration_s": {"max": 10, "ref": ref}})])
        self.assertEqual(effective.rule("duration_s").to_json(), {"max": 10, "unit": "s", "ref": ref})
        sourced = compile_limits(ARM, [("binding", {"duration_s": {"max": 10, "source": "vendor_doc", "ref": "m.pdf:3"}})])
        self.assertEqual(sourced.rule("duration_s").to_json(),
                         {"max": 10, "unit": "s", "source": "vendor_doc", "ref": "m.pdf:3"})

    def test_typo_in_an_envelope_rule_is_refused(self):
        # Reviewer repro p_typo.py: {"maxx": 5, "banana": 1} used to drop the bound silently.
        schema = {"type": "object", "properties": {"ticks": {"type": "integer", "minimum": 1}}}
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(schema, [("envelope", {"ticks": {"maxx": 5, "banana": 1}})])
        self.assertEqual(caught.exception.rule, "unknown-rule-member")

    def test_scalar_array_mismatch(self):
        cases = [
            ("duration_s", {"max": [1, 2]}, "array-bound-length"),
            ("speeds", {"max": [1, 2]}, "array-bound-length"),             # variable length
            ("joint_positions", {"max": [1, 2, 3]}, "array-bound-length"),  # wrong length
            ("joint_positions", {"names": ["a", "b"]}, "array-bound-length"),
            ("joint_positions[*]", {"max": HIGH}, "array-bound-length"),
            ("joint_positions[2]", {"max": HIGH}, "array-bound-length"),
            ("mode", {"max": 3}, "limit-type"),
            ("block", {"min": 0}, "limit-type"),
            ("mode", {"allowed": [1, 2]}, "limit-type"),
        ]
        for path, rule, expected in cases:
            with self.subTest(path=path, rule=rule):
                with self.assertRaises(LimitConfigError) as caught:
                    compile_limits(ARM, [("binding", {path: rule})])
                self.assertEqual(caught.exception.rule, expected)
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(POSE, [("binding", {"position": {"allowed": [1]}})])
        self.assertEqual(caught.exception.rule, "limit-type")
        with self.assertRaises(LimitConfigError):
            compile_limits(POSE, [("binding", {"grid": {"max": [1, 2]}})])

    def test_unit_must_match_the_field(self):
        with self.assertRaises(LimitConfigError) as caught:
            _arm(max=3.0, unit="deg")
        self.assertEqual(caught.exception.rule, "limit-unit-matches-field")
        self.assertEqual(caught.exception.member, "unit")
        self.assertEqual(_arm(max=3.0, unit="rad").rules["joint_positions"].unit, "rad")
        # without a field unit, the sources must agree among themselves
        untyped = {"type": "object", "properties": {"v": {"type": "number"}}}
        with self.assertRaises(LimitConfigError):
            compile_limits(untyped, [("class", {"v": {"max": 1, "unit": "mm"}}), ("binding", {"v": {"max": 1, "unit": "m"}})])

    def test_intersection(self):
        effective = compile_limits(ARM, [
            ("class", {"joint_positions": {"min": -6.28, "max": 6.28}}),
            ("binding", {"joint_positions": {"min": LOW, "max": HIGH, "names": JOINTS}}),
            ("envelope", {"joint_positions": {"max": 3.0}}),
        ])
        rule = effective.rules["joint_positions"]
        self.assertEqual([bound.value for bound in rule.max], [3.0, 2.0, 0.5, 3.0, 1.5, 3.0])
        self.assertEqual([bound.origin.label for bound in rule.max],
                         ["envelope", "binding", "binding", "envelope", "binding", "envelope"])
        self.assertEqual([bound.value for bound in rule.min], LOW)
        self.assertEqual(rule.names, tuple(JOINTS))
        self.assertEqual(effective.to_json()["joint_positions"]["max"], [3.0, 2.0, 0.5, 3.0, 1.5, 3.0])

    def test_a_wider_source_never_widens(self):
        # Reviewer repro widen.py: an envelope max 1000 used to replace the binding max 100.
        schema = {"type": "object", "properties": {"target_temperature": {"type": "number", "x-mhs-unit": "Cel"}}}
        effective = compile_limits(schema, [
            ("binding", {"target_temperature": {"min": 0, "max": 100, "unit": "Cel"}}),
            ("envelope", {"target_temperature": {"min": -50, "max": 1000, "unit": "Cel"}}),
        ])
        found = check({"target_temperature": 500}, effective)
        self.assertEqual([(v.kind, v.bound, v.source) for v in found], [("max", 100, "binding")])
        self.assertEqual(check({"target_temperature": -10}, effective)[0].bound, 0)

    def test_names_must_agree(self):
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"joint_positions": {"names": JOINTS}}),
                                 ("envelope", {"joint_positions": {"names": list(reversed(JOINTS))}})])
        self.assertEqual(caught.exception.rule, "names-agree")

    def test_contradictory_sources(self):
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("class", {"duration_s": {"min": 1}}), ("binding", {"duration_s": {"max": 0.5}})])
        self.assertEqual(caught.exception.rule, "empty-range")
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("class", {"mode": {"allowed": ["fast"]}}), ("binding", {"mode": {"allowed": ["safe"]}})])
        self.assertEqual(caught.exception.rule, "empty-range")

    def test_allowed_intersection(self):
        effective = compile_limits(ARM, [("class", {"mode": {"allowed": ["fast", "safe", "teach"]}}),
                                         ("binding", {"mode": {"allowed": ["safe", "teach", "fast"]}}),
                                         ("envelope", {"mode": {"allowed": ["teach", "safe"]}})])
        self.assertEqual(effective.rules["mode"].allowed, ("safe", "teach"))
        self.assertEqual(check({"joint_positions": [0] * 6, "mode": "fast"}, effective)[0].kind, "allowed")

    def test_partial_sources_skip_unknown_paths(self):
        effective = compile_limits(ARM, [LimitSource("class", {"volume": {"max": 1}}, partial=True),
                                         LimitSource("envelope:cap.*", {"duration_s": {"max": 10}}, partial=True)])
        self.assertEqual(effective.skipped, (("class", "volume"),))
        self.assertIn("duration_s", effective.rules)

    def test_trailing_wildcard_is_the_whole_array(self):
        effective = compile_limits(ARM, [("binding", {"joint_positions[*]": {"max": 3.0}}),
                                         ("envelope", {"joint_positions": {"max": 2.5}})])
        self.assertEqual(list(effective.rules), ["joint_positions"])
        self.assertEqual(effective.rules["joint_positions"].max.value, 2.5)
        self.assertIs(effective.rule("joint_positions[*]"), effective.rules["joint_positions"])

    def test_sources_given_as_a_mapping_and_none(self):
        effective = compile_limits(ARM, {"class": None, "binding": {"duration_s": {"max": 5}}})
        self.assertEqual(effective.labels, ("binding",))
        self.assertEqual(effective.rules["duration_s"].max.value, 5)
        with self.assertRaises(LimitConfigError):
            compile_limits(ARM, [("binding", ["duration_s"])])


class OverlayTests(unittest.TestCase):
    def test_widening_overlay_is_rejected(self):
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"duration_s": {"min": 0, "max": 150}})],
                           [("overlay", {"duration_s": {"max": 200, "source": "operator"}})])
        self.assertEqual(caught.exception.rule, "overlay-narrows")
        self.assertEqual(caught.exception.source, "overlay")
        self.assertEqual(caught.exception.member, "max")

    def test_per_element_widening_is_rejected(self):
        wider = list(LOW)
        wider[0] = -7.0
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"joint_positions": {"min": LOW, "max": HIGH}})],
                           [("overlay", {"joint_positions": {"min": wider}})])
        self.assertEqual(caught.exception.rule, "overlay-narrows")
        self.assertIn("[0]", str(caught.exception))

    def test_a_blanket_overlay_bound_must_narrow_every_element(self):
        # max 1.0 for every joint is wider than the elbow's 0.5: the overlay is refused, never half-applied.
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"joint_positions": {"max": HIGH}})],
                           [("overlay", {"joint_positions": {"max": 1.0}})])
        self.assertEqual(caught.exception.rule, "overlay-narrows")
        self.assertIn("max[2]", str(caught.exception))

    def test_overlay_cannot_add_allowed_values(self):
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, [("binding", {"mode": {"allowed": ["safe"]}})],
                           [("overlay", {"mode": {"allowed": ["safe", "fast"]}})])
        self.assertEqual(caught.exception.rule, "overlay-narrows")

    def test_overlay_cannot_widen_through_another_key_of_the_same_array(self):
        # a whole-array rule bounds every a[N]; a[N] bounds element N of the whole array
        cases = [
            ({"joint_positions": {"max": 1.0}}, {"joint_positions[2]": {"max": 10}}),
            ({"joint_positions": {"max": HIGH}}, {"joint_positions[2]": {"max": 0.6}}),
            ({"joint_positions[2]": {"max": 1.0}}, {"joint_positions": {"max": 10}}),
            ({"joint_positions[1]": {"max": 1.0}}, {"joint_positions": {"max": [0.5, 5, 0.5, 0.5, 0.5, 0.5]}}),
            ({"waypoints[*].x": {"min": 0}}, {"waypoints[3].x": {"min": -1}}),
            ({"waypoints[3].x": {"min": 0}}, {"waypoints[*].x": {"min": -1}}),
            ({"speeds": {"max": 2}}, {"speeds[0]": {"max": 3}}),
        ]
        for base, overlay in cases:
            with self.subTest(overlay=overlay):
                schema = POSE if "waypoints" in str(base) else ARM
                with self.assertRaises(LimitConfigError) as caught:
                    compile_limits(schema, [("binding", base)], [("overlay", overlay)])
                self.assertEqual(caught.exception.rule, "overlay-narrows")
                self.assertEqual(caught.exception.source, "overlay")
        schema = {"type": "object", "properties": {"modes": {"type": "array", "items": {"type": "string"}}}}
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(schema, [("binding", {"modes": {"allowed": ["a", "b"]}})],
                           [("overlay", {"modes[1]": {"allowed": ["a", "c"]}})])
        self.assertEqual(caught.exception.member, "allowed")

    def test_overlay_narrowing_through_another_key_is_logged_against_the_real_bound(self):
        effective = compile_limits(ARM, [("binding", {"joint_positions": {"max": HIGH}})],
                                   [("overlay", {"joint_positions[2]": {"max": 0.25}})])
        self.assertEqual(effective.narrowed, ("joint_positions[2].max: 0.5 -> 0.25",))
        self.assertEqual([v.path for v in check({"joint_positions": [0, 0, 0.3, 0, 0, 0]}, effective)],
                         ["joint_positions[2]"])
        same = compile_limits(ARM, [("binding", {"joint_positions": {"max": 1.0}})],
                              [("overlay", {"joint_positions[2]": {"max": 1.0}})])
        self.assertEqual(same.narrowed, ())
        modes = {"type": "object", "properties": {"modes": {"type": "array", "items": {"type": "string"}}}}
        narrowed = compile_limits(modes, [("binding", {"modes": {"allowed": ["a", "b"]}})],
                                  [("overlay", {"modes[1]": {"allowed": ["a"]}})])
        self.assertEqual(narrowed.narrowed, ('modes[1].allowed: ["a", "b"] -> ["a"]',))
        # regular sources still intersect at runtime without a load error (both keys are enforced)
        both = compile_limits(ARM, [("class", {"joint_positions": {"max": 1.0}}),
                                    ("binding", {"joint_positions[2]": {"max": 10}})])
        self.assertEqual([v.limit_path for v in check({"joint_positions": [0, 0, 2, 0, 0, 0]}, both)],
                         ["joint_positions"])

    def test_overlay_narrowing_is_applied(self):
        effective = compile_limits(
            ARM,
            [("binding", {"joint_positions": {"min": LOW, "max": HIGH, "names": JOINTS}, "duration_s": {"max": 10}})],
            [LimitSource("overlay", {"joint_positions": {"max": 0.4}, "duration_s": {"max": 4, "reason": "bench"}},
                         default_source="operator")],
        )
        rule = effective.rules["joint_positions"]
        self.assertEqual([bound.value for bound in rule.max], [0.4] * 6)
        self.assertEqual([bound.value for bound in rule.min], LOW)
        self.assertIn("duration_s.max: 10 -> 4", effective.narrowed)
        self.assertIn("joint_positions[0].max: 3.1 -> 0.4", effective.narrowed)
        found = check({"joint_positions": [0, 0, 0, 0, 0, 1.2], "duration_s": 5}, effective)
        self.assertEqual([(v.path, v.source, v.provenance) for v in found],
                         [("duration_s", "overlay", "operator"), ("joint_positions[5]", "overlay", "operator")])
        self.assertEqual(effective.rules["duration_s"].to_json(),
                         {"max": 4, "reason": "bench", "source": "operator", "unit": "s"})

    def test_operator_required(self):
        sources = [("binding", {"duration_s": "operator_required", "joint_positions": {"max": 3}})]
        effective = compile_limits(ARM, sources)
        self.assertEqual(effective.unset, ("duration_s",))
        self.assertEqual(effective.to_json()["duration_s"], "operator_required")
        filled = compile_limits(ARM, sources, [("overlay", {"duration_s": {"max": 4, "source": "operator"}})])
        self.assertEqual(filled.unset, ())
        self.assertTrue(filled.rules["duration_s"].filled)
        with self.assertRaises(LimitConfigError) as caught:
            compile_limits(ARM, sources, [("overlay", {"duration_s": "operator_required"})])
        self.assertEqual(caught.exception.rule, "overlay-supplies-bounds")

    def test_cumulative_rules_are_not_per_call_bounds(self):
        schema = {"type": "object", "properties": {"on_time_s": {"type": "number", "x-mhs-unit": "s"}}}
        effective = compile_limits(schema, [("envelope", {"on_time_s": {"max": 3600, "per": "rolling_24h", "unit": "s"}})],
                                   [("overlay", {"on_time_s": {"max": 1800, "per": "rolling_24h"}})])
        self.assertEqual(check({"on_time_s": 5000}, effective), [])
        self.assertEqual([(c.path, c.per, c.max.value, c.max.origin.label) for c in effective.cumulative],
                         [("on_time_s", "rolling_24h", 1800, "overlay")])
        with self.assertRaises(LimitConfigError):
            compile_limits(schema, [("envelope", {"on_time_s": {"max": 3600, "per": "rolling_24h"}})],
                           [("overlay", {"on_time_s": {"max": 7200, "per": "rolling_24h"}})])


class CheckTests(unittest.TestCase):
    def test_per_element_bounds_and_names(self):
        effective = _arm(min=LOW, max=HIGH, names=JOINTS, unit="rad", source="vendor_doc", ref="arm.pdf p.4")
        found = check({"joint_positions": [0, 0, 1.2, 0, -2.0, 0]}, effective)
        self.assertEqual([(v.path, v.kind, v.bound, v.value, v.element_name) for v in found],
                         [("joint_positions[2]", "max", 0.5, 1.2, "elbow"),
                          ("joint_positions[4]", "min", -1.5, -2.0, "wrist2")])
        details = found[0].to_details()
        for key in ("path", "bound", "value", "unit", "source", "element_name"):
            self.assertIn(key, details)
        self.assertEqual(details["unit"], "rad")
        self.assertEqual(details["source"], "binding")
        self.assertEqual(details["provenance"], {"source": "vendor_doc", "ref": "arm.pdf p.4"})
        self.assertIn("elbow", found[0].message())

    def test_scalar_bound_applies_to_every_element(self):
        found = check({"joint_positions": [4, 0, 0, 0, 0, -4]}, _arm(min=-3, max=3))
        self.assertEqual([v.path for v in found], ["joint_positions[0]", "joint_positions[5]"])

    def test_per_index_path(self):
        effective = compile_limits(ARM, [("binding", {"joint_positions[2]": {"max": 0.1}})])
        self.assertEqual([v.path for v in check({"joint_positions": [5, 5, 0.2, 5, 5, 5]}, effective)],
                         ["joint_positions[2]"])
        self.assertEqual(check({"joint_positions": [0, 0]}, effective), [])

    def test_nested_fields(self):
        effective = compile_limits(POSE, [("binding", {"position.x": {"min": -450, "max": 450, "unit": "mm"},
                                                       "position.z": {"max": 200},
                                                       "waypoints[*].x": {"max": 100},
                                                       "grid": {"max": 9}})])
        payload = {"position": {"x": 600, "y": 0, "z": 10}, "waypoints": [{"x": 1}, {"x": 101, "label": "b"}],
                   "grid": [[1, 2], [3, 10]]}
        self.assertEqual([v.path for v in check(payload, effective)],
                         ["grid[1][1]", "position.x", "waypoints[1].x"])
        self.assertEqual(check({"position": {"x": 1, "y": 0, "z": 1}}, effective), [])

    def test_nested_clamp_repro(self):
        # Reviewer repro clamp_nested.py: a bound on input.position.x of a nested input was never applied.
        effective = compile_limits(POSE, [("binding", {"position.x": {"min": -500, "max": 500}})])
        self.assertEqual(check({"position": {"x": 100, "y": 0}}, effective), [])
        self.assertEqual([v.value for v in check({"position": {"x": 99999, "y": 0}}, effective)], [99999])

    def test_absent_optional_fields_are_skipped_and_defaults_evaluated(self):
        effective = compile_limits(ARM, [("binding", {"duration_s": {"max": 1}, "speeds": {"max": 1}})])
        found = check({"joint_positions": [0] * 6}, effective)
        self.assertEqual([(v.path, v.value) for v in found], [("duration_s", 2.0)])   # the schema default
        self.assertEqual(check({"joint_positions": [0] * 6, "duration_s": 0.5}, effective), [])
        nested = compile_limits(POSE, [("binding", {"position.z": {"max": 200}})])
        self.assertEqual([(v.path, v.value) for v in check({"position": {"x": 0, "y": 0}}, nested)],
                         [("position.z", 250)])
        self.assertEqual(check({}, nested), [])

    def test_values_that_cannot_be_compared_never_pass(self):
        effective = compile_limits(ARM, [("binding", {"duration_s": {"min": 0, "max": 10}})])
        for value in ("5", True, None, [1], {"v": 1}, float("nan"), float("inf")):
            with self.subTest(value=value):
                found = check({"duration_s": value}, effective)
                self.assertEqual([v.kind for v in found], ["type"])
        self.assertEqual(check({"duration_s": 10}, effective), [])
        self.assertEqual(check({"duration_s": 10.000001}, effective)[0].kind, "max")
        wrong_shape = compile_limits(POSE, [("binding", {"position.x": {"max": 1}})])
        self.assertEqual([v.kind for v in check({"position": "far"}, wrong_shape)], ["type"])
        array = _arm(max=1)
        self.assertEqual([v.kind for v in check({"joint_positions": 3}, array)], ["type"])

    def test_integers_beyond_the_double_range(self):
        # json.loads returns 1e400 written as an integer literal as int: a violation, never OverflowError
        effective = compile_limits(ARM, [("binding", {"duration_s": {"min": 0, "max": 10}})])
        for value in (10**400, -(10**400)):
            with self.subTest(value=value):
                found = check({"duration_s": value}, effective)
                self.assertEqual([v.kind for v in found], ["type"])
                self.assertEqual(found[0].to_details()["value"], str(value))   # JCS-safe
        found = check({"duration_s": 2**60}, effective)
        self.assertEqual([v.kind for v in found], ["max"])
        self.assertEqual(found[0].to_details()["value"], str(2**60))
        with self.assertRaises(LimitConfigError) as caught:
            LimitRule.parse({"max": 10**400})
        self.assertEqual(caught.exception.member, "max")
        with self.assertRaises(LimitConfigError):
            LimitRule.parse({"min": [0, 10**400]})

    def test_extra_elements_without_a_bound(self):
        found = check({"joint_positions": [0] * 7}, _arm(max=HIGH))
        self.assertEqual([(v.path, v.kind) for v in found], [("joint_positions[6]", "length")])

    def test_allowed_uses_json_equality(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        effective = compile_limits(schema, [("binding", {"n": {"allowed": [1, 2]}})])
        self.assertEqual(check({"n": 1.0}, effective), [])
        self.assertEqual([v.kind for v in check({"n": True}, effective)], ["allowed"])


class TwoPassTests(unittest.TestCase):
    def test_bound_keyword_paths_and_stripping(self):
        effective = compile_limits(ARM, [("binding", {"joint_positions": {"max": 2.0}, "mode": {"allowed": ["safe"]}})])
        self.assertEqual(limits.bound_keyword_paths(effective),
                         ("/properties/joint_positions/items", "/properties/mode"))
        stripped = limits.strip_bound_keywords(effective)
        items = stripped["properties"]["joint_positions"]["items"]
        self.assertNotIn("maximum", items)
        self.assertNotIn("minimum", items)
        self.assertEqual(items["x-mhs-unit"], "rad")
        self.assertEqual(stripped["properties"]["joint_positions"]["maxItems"], 6)
        self.assertNotIn("enum", stripped["properties"]["mode"])
        self.assertEqual(stripped["properties"]["duration_s"]["minimum"], 0)   # not limited: kept
        self.assertEqual(ARM["properties"]["joint_positions"]["items"]["maximum"], 6.3)   # input untouched

    def test_ref_and_allof_are_followed(self):
        schema = {
            "type": "object",
            "$defs": {"mm": {"type": "number", "x-mhs-unit": "mm", "maximum": 900}},
            "allOf": [{"properties": {"x": {"$ref": "#/$defs/mm"}}}],
        }
        effective = compile_limits(schema, [("binding", {"x": {"max": 450, "unit": "mm"}})])
        self.assertEqual([v.value for v in check({"x": 500}, effective)], [500])
        self.assertIn("/$defs/mm", limits.bound_keyword_paths(effective))
        with self.assertRaises(LimitConfigError):
            compile_limits(schema, [("binding", {"x": {"max": 450, "unit": "m"}})])

    def test_unlimited_numeric_leaves(self):
        effective = compile_limits(ARM, [("binding", {"joint_positions": {"max": 1}, "duration_s": "operator_required"})])
        self.assertEqual(limits.unlimited_numeric_leaves(effective), ("speeds",))
        self.assertEqual(limits.numeric_leaf_paths(POSE), ("position.x", "position.y", "position.z",
                                                           "waypoints[*].x", "grid"))
        reason_only = compile_limits(ARM, [("class", {"joint_positions": {"reason": "declared per binding"}})])
        self.assertIn("joint_positions", limits.unlimited_numeric_leaves(reason_only))


class ManifestHelperTests(unittest.TestCase):
    def test_pattern_matches(self):
        self.assertTrue(limits.pattern_matches("cap.thermal.*", "cap.thermal.setpoint.v1"))
        self.assertTrue(limits.pattern_matches("cap.*", "cap.thermal.setpoint.v1"))
        self.assertFalse(limits.pattern_matches("cap.thermal.*", "cap.thermalx.setpoint.v1"))
        self.assertTrue(limits.pattern_matches("cap.thermal.setpoint.v1", "cap.thermal.setpoint.v1"))
        self.assertFalse(limits.pattern_matches("cap.thermal.setpoint.v1", "cap.thermal.setpoint.v2"))

    def test_envelope_sources(self):
        envelope = {"cap.motion.*": {"duration_s": {"max": 5}}, "cap.motion.joint_position.v1": {"joint_positions": {"max": 1}},
                    "cap.thermal.*": {"x": {"max": 1}}}
        sources = limits.envelope_sources(envelope, "cap.motion.joint_position.v1")
        self.assertEqual([(s.label, s.partial) for s in sources],
                         [("envelope:cap.motion.*", True), ("envelope", False)])

    def test_overlay_sources(self):
        overlay = {"devices": {"dev": {"setpoint": {"max": 95}, "cap.thermal.setpoint.v1": {"target_temperature": {"max": 95}}}}}
        cap = limits.overlay_sources(overlay, "dev", "cap.thermal.setpoint.v1")
        self.assertEqual([(s.label, s.narrow_only, dict(s.limits)) for s in cap],
                         [("overlay", True, {"target_temperature": {"max": 95}})])
        configure = limits.overlay_sources(overlay, "dev", "cap.device.configure.v1", parameter_paths=True)
        self.assertEqual([dict(s.limits) for s in configure], [{"setpoint": {"max": 95}}])
        self.assertEqual(configure[0].default_source, "operator")
        self.assertEqual(limits.overlay_sources(overlay, "other", "cap.thermal.setpoint.v1"), [])
        self.assertEqual(limits.overlay_sources(None, "dev", "cap.thermal.setpoint.v1"), [])

    def test_inputs_are_not_mutated(self):
        schema = copy.deepcopy(ARM)
        sources = [("binding", {"joint_positions": {"max": HIGH, "names": JOINTS}})]
        snapshot = copy.deepcopy(sources)
        effective = compile_limits(schema, sources)
        check({"joint_positions": [9] * 6}, effective)
        self.assertEqual(schema, ARM)
        self.assertEqual(sources, snapshot)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
