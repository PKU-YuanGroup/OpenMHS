"""mhs.units: UCUM parsing, exact conversion, explicit-factor checks and temperature offsets."""

from __future__ import annotations

import math
import unittest

from mhs import units
from mhs.units import UnitError, UnknownUnitError, convert

from ._support import CAPABILITIES, load_json


def _catalogue_units() -> set[str]:
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "x-mhs-unit" and isinstance(value, str):
                    found.add(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    document = load_json(CAPABILITIES)
    walk(document)
    for entry in document["capabilities"]:
        found.update(value for value in (entry.get("units") or {}).values() if isinstance(value, str))
        found.update(rule["unit"] for rule in (entry.get("limits") or {}).values() if "unit" in rule)
    return found


class AcceptanceTests(unittest.TestCase):
    def test_percent_is_a_ratio_of_one_hundredth(self):
        self.assertEqual(convert(50, "%", "1"), 0.5)
        self.assertEqual(convert(0.25, "1", "%"), 25.0)

    def test_metres_per_second_to_millimetres_per_second(self):
        self.assertEqual(convert(1, "m/s", "mm/s"), 1000)

    def test_wrong_explicit_factor_raises(self):
        with self.assertRaises(UnitError):
            convert(1, "m", "mm", factor=100)
        with self.assertRaises(UnitError):
            convert(1, "m/s", "mm/s", 1.0)

    def test_right_explicit_factor_passes_within_tolerance(self):
        self.assertEqual(convert(2, "m", "mm", factor=1000), 2000)
        self.assertEqual(convert(2, "m", "mm", factor=1000 * (1 + 1e-12)), 2000)
        with self.assertRaises(UnitError):
            convert(2, "m", "mm", factor=1000 * (1 + 1e-6))

    def test_tiny_factors_are_checked_relatively(self):
        # 1e-15 is not "close enough" to 0: the tolerance is relative, never absolute
        self.assertEqual(convert(1, "fL", "L", factor=1e-15), 1e-15)
        for factor in (0, 1e-16, 2e-15, -1e-15):
            with self.subTest(factor=factor):
                with self.assertRaises(UnitError):
                    convert(1, "fL", "L", factor=factor)
        with self.assertRaises(UnitError):
            convert(1, "nm", "km", factor=0)
        # an offset that is exactly 0 keeps a tiny absolute slack
        self.assertEqual(convert(1, "K", "K", offset=1e-13), 1.0)
        with self.assertRaises(UnitError):
            convert(1, "K", "K", offset=1e-6)


class CompoundUnitTests(unittest.TestCase):
    CASES = [
        ("m/s2", "mm/s2", 1000),
        ("N.m", "J", 1),
        ("N.m", "mN.m", 1000),
        ("uL/s", "mL/min", 0.06),
        ("K/min", "K/s", 1 / 60),
        ("rad/s", "deg/s", 180 / math.pi),
        ("/min", "Hz", 1 / 60),
        ("/min", "s-1", 1 / 60),
        ("mL/min", "uL/s", 1000 / 60),
        ("uL/h", "uL/s", 1 / 3600),
        ("kg.m/s2", "N", 1),
        ("(kg.m)/s2", "N", 1),
        ("m2", "cm2", 10000),
        ("m{chamber}", "mm", 1000),
    ]

    def test_compound_conversions(self):
        for src, dst, factor in self.CASES:
            with self.subTest(src=src, dst=dst):
                self.assertTrue(math.isclose(convert(1, src, dst), factor, rel_tol=1e-12))

    def test_division_is_left_associative(self):
        # UCUM: "J/kg.K" is (J/kg).K, not J/(kg.K).
        self.assertEqual(units.dimension("J/kg.K"), units.dimension("J.K/kg"))
        self.assertNotEqual(units.dimension("J/kg.K"), units.dimension("J/(kg.K)"))

    def test_new_atoms(self):
        cases = [("mW", "W", 1e-3), ("Ohm", "kOhm", 1e-3), ("nA", "A", 1e-9), ("uV", "V", 1e-6),
                 ("kOhm", "Ohm", 1e3), ("GHz", "Hz", 1e9), ("Torr", "Pa", 101325 / 760),
                 ("mL/min", "mL/s", 1 / 60), ("uL/h", "nL/h", 1000)]
        for src, dst, factor in cases:
            with self.subTest(src=src):
                self.assertTrue(math.isclose(convert(1, src, dst), factor, rel_tol=1e-12))

    def test_dimension_mismatch(self):
        for src, dst in (("m", "s"), ("rad", "1"), ("%", "rad"), ("Hz", "rad/s"), ("uL", "mm"), ("N", "N.m")):
            with self.subTest(src=src, dst=dst):
                with self.assertRaises(UnitError):
                    convert(1, src, dst)

    def test_unknown_or_malformed_codes(self):
        for code in ("banana", "", "m/", "(m", "m s", "kCel", "0", "m0", "rpm", "deg F", "[degF"):
            with self.subTest(code=code):
                with self.assertRaises(UnknownUnitError):
                    units.parse(code)
                self.assertFalse(units.is_known(code))
        self.assertFalse(units.is_known(None))
        self.assertFalse(units.is_known(["m"]))


class TemperatureTests(unittest.TestCase):
    def test_absolute_temperatures_apply_the_offset(self):
        self.assertTrue(math.isclose(convert(37, "Cel", "K"), 310.15))
        self.assertTrue(math.isclose(convert(310.15, "K", "Cel"), 37))
        self.assertTrue(math.isclose(convert(98.6, "[degF]", "Cel"), 37))
        self.assertTrue(math.isclose(convert(0, "Cel", "mK"), 273150))

    def test_delta_fields_never_apply_the_offset(self):
        self.assertEqual(convert(5, "K", "Cel", delta=True), 5)
        self.assertEqual(convert(5, "Cel", "K", delta=True), 5)
        self.assertTrue(units.field_is_delta({"type": "number", "x-mhs-unit": "K", "x-mhs-delta": True}))
        self.assertFalse(units.field_is_delta({"type": "number", "x-mhs-unit": "K"}))

    def test_compound_temperature_units_have_no_offset(self):
        self.assertEqual(convert(2, "K/min", "Cel/min"), 2)
        self.assertEqual(units.conversion("Cel/min", "K/min"), (1.0, 0.0))

    def test_explicit_offset_is_checked(self):
        self.assertTrue(math.isclose(convert(1, "Cel", "K", factor=1, offset=273.15), 274.15))
        with self.assertRaises(UnitError):
            convert(1, "Cel", "K", offset=273)
        with self.assertRaises(UnitError):
            convert(1, "Cel", "K", offset=273.15, delta=True)

    def test_non_numeric_values_are_refused(self):
        for value in (True, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    convert(value, "m", "mm")
        with self.assertRaises(UnitError):
            convert(float("nan"), "m", "mm")

    def test_values_beyond_the_double_range_raise_unit_error(self):
        # json.loads returns such literals as int; never an OverflowError
        for value in (10**400, -(10**400)):
            with self.subTest(value=value):
                with self.assertRaises(UnitError):
                    convert(value, "m", "mm")
        with self.assertRaises(UnitError):
            convert(1e308, "km", "mm")          # the result overflows
        with self.assertRaises(UnitError):
            convert(1, "m", "mm", factor=10**400)
        self.assertEqual(convert(2**60, "m", "m"), float(2**60))


class CatalogueUnitTests(unittest.TestCase):
    def test_every_catalogue_unit_parses_and_converts(self):
        found = _catalogue_units()
        self.assertGreater(len(found), 20)
        for code in sorted(found):
            with self.subTest(unit=code):
                parsed = units.parse(code)
                self.assertEqual(convert(3, code, code), 3)
                # every unit converts to its coherent SI form and back
                coherent = parsed.dimension
                there = convert(3, code, coherent)
                self.assertTrue(math.isclose(convert(there, coherent, code), 3, rel_tol=1e-12))

    def test_bridge_unit_table_still_converts_except_percent(self):
        from mhs.bridge import base

        for code, (dimension, factor) in base._UNITS.items():
            with self.subTest(unit=code):
                self.assertTrue(units.is_known(code))
        for src in base._UNITS:
            for dst in base._UNITS:
                if base._UNITS[src][0] != base._UNITS[dst][0]:
                    continue
                if "%" in (src, dst):
                    continue
                with self.subTest(src=src, dst=dst):
                    self.assertTrue(math.isclose(convert(7, src, dst), base.convert_unit(7, src, dst),
                                                 rel_tol=1e-12, abs_tol=1e-12))
        # the bridge table treated % as 1; the fixed table is a ratio of 0.01
        self.assertIn(base.convert_unit(50, "%", "1"), (50, 0.5))  # 0.5 once the bridge adopts mhs.units
        self.assertEqual(units.convert_unit(50, "%", "1"), 0.5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
