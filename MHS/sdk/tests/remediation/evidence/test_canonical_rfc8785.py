"""PROTO-001 regression: RFC 8785 canonicalization (numbers, strings, keys).

The expected byte strings are fixed independent vectors: RFC 8785 Appendix B /
ECMAScript ``Number::toString``, cross-checked against Node 24's
``JSON.stringify`` (an independent ECMAScript implementation) when the vectors
were authored.  ``_independent.independent_jcs`` provides a second in-tree
encoder that shares no code with ``mhs.canonical``.
"""

from __future__ import annotations

import hashlib
import json
import unittest

from mhs import canonical

from ._independent import independent_jcs, independent_record_digest

# RFC 8785 §3.2.2.3 / ECMAScript Number::toString samples, plus boundary cases.
NUMBER_VECTORS: list[tuple[str, int | float, bytes]] = [
    ("zero", 0.0, b"0"),
    ("negative zero", -0.0, b"0"),
    ("integer float", 1.0, b"1"),
    ("negative integer float", -1.0, b"-1"),
    ("json integer", 1, b"1"),
    ("json negative integer", -1, b"-1"),
    ("small negative exponent", 1e-7, b"1e-7"),
    ("fixed six decimals", 1e-6, b"0.000001"),
    ("small fixed", 2e-3, b"0.002"),
    ("fixed upper threshold", 1e20, b"100000000000000000000"),
    ("exponential lower threshold", 1e21, b"1e+21"),
    ("large exponent", 1e30, b"1e+30"),
    ("appendix B rounded", 333333333.33333329, b"333333333.3333333"),
    ("appendix B trailing zero", 4.50, b"4.5"),
    ("appendix B tiny", 1e-27, b"1e-27"),
    ("max double", 1.7976931348623157e308, b"1.7976931348623157e+308"),
    ("min subnormal", 5e-324, b"5e-324"),
    ("2^53-1 float", 9007199254740991.0, b"9007199254740991"),
    ("2^53-1 int", 2**53 - 1, b"9007199254740991"),
    ("one and a half", 1.5, b"1.5"),
    ("negative fraction", -1.5, b"-1.5"),
    ("three decimals", 123.456, b"123.456"),
    ("1e16 fixed", 1e16, b"10000000000000000"),
    ("2.5e-5 fixed", 2.5e-5, b"0.000025"),
]

# RFC 8785 Appendix B example and its canonical output.
RFC_EXAMPLE = {
    "numbers": [
        333333333.33333329,
        1e30,
        4.50,
        2e-3,
        0.000000000000000000000000001,
    ],
    "string": "\u20ac$\u000f\nA'B\"\\\\\"/",
    "literals": [None, True, False],
}
RFC_EXPECTED = (
    b'{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,'
    b'0.002,1e-27],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
)

# sha256 of the independently produced bytes for this object.
DIGEST_VECTOR_OBJECT = {
    "numbers": [1e-7, 1e20, 333333333.33333329],
    "string": "\u20ac\U0001f600",
    "flag": True,
}
DIGEST_VECTOR_BYTES = (
    b'{"flag":true,"numbers":[1e-7,100000000000000000000,333333333.3333333],'
    b'"string":"\xe2\x82\xac\xf0\x9f\x98\x80"}'
)
DIGEST_VECTOR = "sha256:a786c956a807024014d9da8186485e8e897255ad043ccd82f94ed23d353d8cfc"

# Every mandatory escape, U+2028/U+2029 unescaped, literal non-BMP, and the
# characters JSON does not escape.
STRING_INPUT = "\u0000\u0001\u001f\b\t\n\f\r\u2028\u2029\U0001f600<>&/\"\\"
STRING_EXPECTED = (
    b'"\\u0000\\u0001\\u001f\\b\\t\\n\\f\\r'
    b'\xe2\x80\xa8\xe2\x80\xa9\xf0\x9f\x98\x80<>&/\\"\\\\"'
)

UTF16_KEY_OBJECT = {"\uE000": 1, "\U00010000": 2}
UTF16_KEY_EXPECTED = b'{"\xf0\x90\x80\x80":2,"\xee\x80\x80":1}'


class NumberSerializationTests(unittest.TestCase):
    def test_rfc_8785_number_vectors(self) -> None:
        for label, value, expected in NUMBER_VECTORS:
            with self.subTest(label=label):
                self.assertEqual(canonical.jcs(value), expected)

    def test_rfc_8785_appendix_b_example(self) -> None:
        self.assertEqual(canonical.jcs(RFC_EXAMPLE), RFC_EXPECTED)

    def test_appendix_b_output_parses_back_to_the_same_value(self) -> None:
        self.assertEqual(json.loads(RFC_EXPECTED), RFC_EXAMPLE)

    def test_parse_roundtrip_for_numbers(self) -> None:
        for label, value, _expected in NUMBER_VECTORS:
            with self.subTest(label=label):
                parsed = json.loads(canonical.jcs(value))
                self.assertEqual(parsed, value)

    def test_parse_roundtrip_for_strings_and_objects(self) -> None:
        for value in [
            STRING_INPUT,
            UTF16_KEY_OBJECT,
            {"nested": [1e-7, {"\U0001f600": "x"}]},
        ]:
            with self.subTest(value=value):
                self.assertEqual(json.loads(canonical.jcs(value)), value)

    def test_digest_is_stable_for_independent_expected_bytes(self) -> None:
        self.assertEqual(canonical.jcs(DIGEST_VECTOR_OBJECT), DIGEST_VECTOR_BYTES)
        self.assertEqual(canonical.digest(DIGEST_VECTOR_OBJECT), DIGEST_VECTOR)
        self.assertEqual(
            "sha256:" + hashlib.sha256(DIGEST_VECTOR_BYTES).hexdigest(),
            DIGEST_VECTOR,
        )

    def test_independent_encoder_agrees_on_numbers(self) -> None:
        values = [
            0.0,
            -0.0,
            1.0,
            1e-7,
            1e-6,
            2e-3,
            1e16,
            1e20,
            1e21,
            1e30,
            1e-27,
            0.1,
            0.30000000000000004,
            1 / 3,
            3.141592653589793,
            333333333.33333329,
            12345.6789,
            1e300,
            1e-300,
            5e-324,
            9007199254740991.0,
            -42.125,
        ]
        for value in values:
            with self.subTest(value=repr(value)):
                self.assertEqual(canonical.jcs(value), independent_jcs(value))

    def test_independent_encoder_agrees_on_structures(self) -> None:
        cases = [
            RFC_EXAMPLE,
            DIGEST_VECTOR_OBJECT,
            {},
            [],
            {"\uE000": [1, {"z": None}], "\U00010000": "v"},
            {"a": True, "b": False, "c": None, "d": "\u0000\n"},
        ]
        for case in cases:
            with self.subTest(case=repr(case)):
                self.assertEqual(canonical.jcs(case), independent_jcs(case))


class NumberRejectionTests(unittest.TestCase):
    def test_non_finite_numbers_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(canonical.CanonicalJSONError):
                    canonical.jcs(value)

    def test_integers_outside_ieee754_exact_range_are_rejected(self) -> None:
        for value in (2**53, -(2**53), 2**53 + 1, 10**30, -(10**30)):
            with self.subTest(value=value):
                with self.assertRaises(canonical.CanonicalJSONError) as caught:
                    canonical.jcs(value)
                self.assertIn("MUST be carried as decimal strings", str(caught.exception))

    def test_largest_exact_integer_is_accepted(self) -> None:
        self.assertEqual(canonical.jcs(2**53 - 1), b"9007199254740991")
        self.assertEqual(canonical.jcs(-(2**53 - 1)), b"-9007199254740991")


class StringSerializationTests(unittest.TestCase):
    def test_mandatory_escapes_and_literal_unicode(self) -> None:
        self.assertEqual(canonical.jcs(STRING_INPUT), STRING_EXPECTED)
        self.assertEqual(json.loads(STRING_EXPECTED), STRING_INPUT)

    def test_non_bmp_characters_are_literal_utf8(self) -> None:
        self.assertEqual(canonical.jcs("\U0001f600"), b'"\xf0\x9f\x98\x80"')

    def test_lone_surrogates_are_rejected(self) -> None:
        for value in ("\ud800", "\udfff", "a\ud800b"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(canonical.CanonicalJSONError):
                    canonical.jcs(value)

    def test_lone_surrogate_object_key_is_rejected(self) -> None:
        with self.assertRaises(canonical.CanonicalJSONError):
            canonical.jcs({"\ud800": 1})

    def test_non_string_object_keys_are_rejected(self) -> None:
        with self.assertRaises(canonical.CanonicalJSONError):
            canonical.jcs({1: "x"})


class KeyOrderingTests(unittest.TestCase):
    def test_keys_sort_by_utf16_code_units(self) -> None:
        self.assertEqual(canonical.jcs(UTF16_KEY_OBJECT), UTF16_KEY_EXPECTED)

    def test_python_and_utf16_order_differ_for_astral_keys(self) -> None:
        # Python code-point order puts U+E000 first; RFC 8785 puts the astral
        # key (UTF-16 high surrogate D800) first.
        self.assertLess("\uE000", "\U00010000")
        encoded = canonical.jcs({"\uE000": "bmp", "\U00010000": "astral"})
        self.assertLess(encoded.index("\U00010000".encode()), encoded.index("\uE000".encode()))

    def test_ascii_key_ordering_matches_lexicographic_order(self) -> None:
        value = {"b": 2, "aa": 3, "A": 4, "a": 1, "": 0}
        self.assertEqual(
            canonical.jcs(value),
            b'{"":0,"A":4,"a":1,"aa":3,"b":2}',
        )

    def test_empty_key_sorts_before_digit_key_by_code_unit(self) -> None:
        # ECMAScript *object enumeration* hoists integer-like keys, so this
        # ordering cannot be checked with JSON.stringify; RFC 8785 prescribes
        # raw UTF-16 code-unit order, where "" sorts before "9".
        self.assertEqual(canonical.jcs({"9": 1, "": 2}), b'{"":2,"9":1}')


class PublicApiCompatibilityTests(unittest.TestCase):
    def test_jcs_json_returns_unicode_text(self) -> None:
        self.assertEqual(canonical.jcs_json({"a": 1}), '{"a":1}')
        self.assertEqual(canonical.jcs_json("\u20ac"), '"\u20ac"')

    def test_digest_text_and_digest_bytes_are_utf8_digests(self) -> None:
        self.assertEqual(canonical.digest_text("caf\u00e9"), canonical.digest_bytes("caf\u00e9".encode("utf-8")))
        self.assertTrue(canonical.is_digest(canonical.digest_text("x")))

    def test_state_hash_applies_json_pointer_exclusions(self) -> None:
        state = {"mono_ms": 1, "tick": 2}
        self.assertNotEqual(
            canonical.state_hash(state),
            canonical.state_hash(state, ["/mono_ms"]),
        )
        self.assertEqual(
            canonical.state_hash(state, ["/mono_ms"]),
            canonical.digest({"tick": 2}),
        )

    def test_ulid_and_rfc3339_helpers_remain_compatible(self) -> None:
        value = canonical.ulid()
        self.assertTrue(canonical.is_ulid(value))
        self.assertEqual(len(value), 26)
        stamp = canonical.now_rfc3339()
        self.assertTrue(stamp.endswith("Z"))
        self.assertIsNotNone(canonical.parse_rfc3339(stamp))

    def test_record_digest_uses_independent_canonical_bytes(self) -> None:
        record = {"b": 1e-7, "a": [1, 2]}
        prev = "sha256:" + "1" * 64
        self.assertEqual(
            canonical.digest_bytes(independent_jcs({"a": [1, 2], "b": 1e-7}) + prev.encode()),
            canonical.digest_bytes(canonical.jcs({"a": [1, 2], "b": 1e-7}) + prev.encode()),
        )
        # And the evidence helper agrees with the independent chain digest.
        from mhs.evidence import compute_record_digest

        self.assertEqual(
            compute_record_digest(record, prev),
            independent_record_digest(record, prev),
        )


if __name__ == "__main__":
    unittest.main()
