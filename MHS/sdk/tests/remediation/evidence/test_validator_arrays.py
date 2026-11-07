"""CODE-003 regression: ``prefixItems``/``items``/``uniqueItems`` semantics."""

from __future__ import annotations

import unittest

from mhs.schema import validate


def errors(instance, schema) -> list[str]:
    return validate(instance, schema)


class PrefixItemsAndItemsTests(unittest.TestCase):
    def test_items_applies_only_after_prefix_items(self) -> None:
        schema = {
            "type": "array",
            "prefixItems": [{"type": "string"}],
            "items": {"type": "integer"},
        }
        self.assertEqual(errors(["axis", 2], schema), [])
        self.assertEqual(errors(["axis", 2, 3], schema), [])
        self.assertTrue(errors(["axis", "two"], schema))

    def test_items_false_rejects_the_tail(self) -> None:
        schema = {
            "type": "array",
            "prefixItems": [{"type": "string"}],
            "items": False,
        }
        self.assertEqual(errors(["axis"], schema), [])
        self.assertTrue(errors(["axis", 2], schema))

    def test_items_false_without_prefix_items_rejects_items(self) -> None:
        self.assertTrue(errors([1], {"type": "array", "items": False}))
        self.assertEqual(errors([], {"type": "array", "items": False}), [])

    def test_items_schema_without_prefix_items_applies_to_all(self) -> None:
        schema = {"type": "array", "items": {"type": "integer"}}
        self.assertEqual(errors([1, 2], schema), [])
        self.assertTrue(errors([1, "two"], schema))

    def test_items_true_allows_anything(self) -> None:
        self.assertEqual(errors([1, "two"], {"type": "array", "items": True}), [])

    def test_prefix_items_alone_allows_extra_items(self) -> None:
        schema = {"type": "array", "prefixItems": [{"type": "string"}]}
        self.assertEqual(errors(["axis", 2], schema), [])

    def test_draft07_tuple_form_and_additional_items(self) -> None:
        tuple_schema = {
            "type": "array",
            "items": [{"type": "string"}, {"type": "integer"}],
        }
        self.assertEqual(errors(["axis", 2], tuple_schema), [])
        self.assertEqual(errors(["axis", 2, "extra"], tuple_schema), [])

        closed = dict(tuple_schema, additionalItems=False)
        self.assertTrue(errors(["axis", 2, 3], closed))
        self.assertEqual(errors(["axis", 2], closed), [])

        typed_extra = dict(tuple_schema, additionalItems={"type": "boolean"})
        self.assertEqual(errors(["axis", 2, True], typed_extra), [])
        self.assertTrue(errors(["axis", 2, "no"], typed_extra))

    def test_prefix_items_schema_must_be_an_array(self) -> None:
        with self.assertRaises(Exception):
            errors([1], {"type": "array", "prefixItems": {"type": "integer"}})


class UniqueItemsTests(unittest.TestCase):
    def test_numeric_equivalence_integer_and_float(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertTrue(errors([1, 1.0], schema))
        self.assertTrue(errors([1.0, 1], schema))
        self.assertTrue(errors([0, -0.0], schema))

    def test_boolean_and_number_are_distinct(self) -> None:
        self.assertEqual(errors([True, 1], {"type": "array", "uniqueItems": True}), [])
        self.assertEqual(errors([False, 0], {"type": "array", "uniqueItems": True}), [])

    def test_ordinary_duplicates_are_rejected(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertTrue(errors([1, 1], schema))
        self.assertTrue(errors(["a", "a"], schema))
        self.assertTrue(errors([None, None], schema))

    def test_object_key_order_is_irrelevant(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertTrue(errors([{"a": 1, "b": 2}, {"b": 2, "a": 1}], schema))
        self.assertEqual(errors([{"a": 1}, {"a": 2}], schema), [])

    def test_nested_structures_compare_structurally(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertTrue(errors([[1, {"x": 2}], [1.0, {"x": 2}]], schema))
        self.assertEqual(errors([[1, {"x": 2}], [1, {"x": 3}]], schema), [])

    def test_distinct_values_are_accepted(self) -> None:
        schema = {"type": "array", "uniqueItems": True}
        self.assertEqual(errors([1, 2, 3], schema), [])
        self.assertEqual(errors([], schema), [])


if __name__ == "__main__":
    unittest.main()
