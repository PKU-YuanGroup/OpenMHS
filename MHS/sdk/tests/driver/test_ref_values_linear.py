"""G4's number reader runs in linear time and reads what it read before (RUNTIME-AND-GATE-FIXES).

The pi-term and quantity patterns (``\\d+\\.?\\d*`` before a required continuation) retried every split of a digit run
at every digit: a cited line with an 800-digit literal took about a second, one with 5,000 digits more than two
minutes. The snapshot's patterns are kept here as the reference; the changed reader must give the same numbers on a
seeded corpus of lines built from the forms the reader knows, and stay fast on long runs of digits or blanks.
"""

from __future__ import annotations

import math
import random
import re
import time
import unittest
import warnings
from unittest.mock import patch

from mhs.driver import check
from mhs.driver.check import _RANGE, _in_unit, _numbers_in, _range_ends, _unshown

#: The patterns of the snapshot (2026-11-05) that this change rewrote, as the reference reader.
OLD = {
    "_PI_TERM": re.compile(r"(?P<sign>[-+]?)\s*(?:(?P<k>\d+\.?\d*)\s*\*\s*)?(?<![A-Za-z0-9_.])(?:(?:math|np|numpy)\.)?pi\b"
                           r"(?:\s*\*\s*(?P<m>\d+\.?\d*))?(?:\s*/\s*(?P<d>\d+\.?\d*))?"),
    "_RADIANS_CALL": re.compile(r"(?:math|np|numpy)\.(?:radians|deg2rad)\(\s*(?P<deg>[-+]?(?:\d+\.?\d*|\.\d+))\s*\)"),
    "_QUANTITY": re.compile(r"(?P<value>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s?(?P<unit>[A-Za-zµμ]{1,3})\b"),
    "_ONES": re.compile(r"(?:^|[(\[,:]|(?<![=<>!+\-*/%@&|^])=)\s*(?P<sign>-?)\s*(?:np|numpy)\.ones\((?:[^()]|\([^()]*\))*\)"
                        r"(?!\s*[-+*/%@.\[])"),
}

ATOMS = ["0", "1", "7", "12", "3.5", ".", "-", "+", " ", "  ", "\t", "\n", "*", "/", "pi", "math.", "np.", "numpy.",
         "e", "E", "mm", "V", "deg", "°", "±", "+/-", "abs(x) > ", "(", ")", ",", "_", "x", "radians(", "np.radians(",
         "Discrete(", "range(", "np.ones(", "numpy.ones(3)", "-np.ones([2])", "(n,)", "=", ":", "[", "]", "magnitude",
         "\u5ea6", "µm", "kHz", "A", "start=", "0x1F", "0b10", "1_000", "     ", "0.0", "00", " * ", "@", "!=", "+="]


def _norm(values):
    return ["nan" if isinstance(value, float) and math.isnan(value) else value for value in values]


def _read(text: str, unit: str):
    return _norm(_numbers_in(text)), _norm(_in_unit(text, unit))


class SameReadingTests(unittest.TestCase):
    def test_the_changed_patterns_read_what_the_snapshot_read(self) -> None:
        rnd = random.Random(20261105)
        lines = ["".join(rnd.choice(ATOMS) for _ in range(rnd.randint(1, 20))) for _ in range(6000)]
        lines += ["(-2 * math.pi, 2 * math.pi),", "half = math.pi / 2", "x = 0.08 m", "-170 to 170 deg",
                  "spaces.Box(-np.ones(4), np.ones(4))", "angle = np.radians(90)", "± 5 V", "3 * pi / 4"]
        for unit in ("V", "mm", "rad"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)  # the Box reader parses lines such as "0x1Fe"
                with patch.multiple(check, **OLD):
                    before = [_read(line, unit) for line in lines]
                after = [_read(line, unit) for line in lines]
            for line, old, new in zip(lines, before, after):
                self.assertEqual(old, new, repr(line))

    def test_a_zero_divisor_no_longer_stops_the_gate(self) -> None:
        # "pi / 0" made the reader divide by zero (ZeroDivisionError: the gate crashed); it now shows no angle.
        self.assertEqual(_numbers_in("x = math.pi / 0"), [0.0])
        found = _numbers_in("a = 2 * pi / 0.0, b = pi / 2")
        self.assertIn(math.pi / 2, found)
        self.assertTrue(all(math.isfinite(value) for value in found), found)
        self.assertNotIn(2 * math.pi, found)


class HugeLiteralTests(unittest.TestCase):
    def test_literals_no_float_holds_never_stop_the_gate(self) -> None:
        # A Discrete(n) of more than 308 digits, or a hex, binary or octal literal past the float range, raised
        # OverflowError (more than 4,300 decimal digits: ValueError) and stopped the gate, as range() did before.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            for digits in (400, 5000):
                for line in ("Discrete(" + "7" * digits + ")", "Discrete(3, start=" + "7" * digits + ")",
                             "0x" + "f" * (digits // 2), "0b" + "1" * (digits * 2), "0o" + "7" * digits):
                    with self.subTest(line=line[:24], digits=digits):
                        found = _numbers_in(line)
                        self.assertIsInstance(found, list)
                        _in_unit(line, "mm")
        self.assertIn(4.0, _numbers_in("Discrete(5)"))  # an ordinary Discrete still shows its largest action
        self.assertIn(255.0, _numbers_in("mask = 0xFF"))


class LinearTimeTests(unittest.TestCase):
    #: generous: the changed reader takes milliseconds for these lines on a laptop; the old one took hours
    BOUND_S = 5.0

    def time_of(self, text: str) -> float:
        started = time.perf_counter()
        _numbers_in(text)
        _in_unit(text, "V")
        _unshown({"min": -1, "max": 1, "unit": "V"}, text)
        return time.perf_counter() - started

    def test_long_runs_of_digits_and_blanks_are_read_in_linear_time(self) -> None:
        for label, text in (("digits", "x = " + "7" * 50_000), ("digits before pi", "7" * 50_000 + " * pi"),
                            ("decimal", "1." * 25_000), ("blanks", "x" + " " * 50_000 + "y"),
                            ("blanks before pi", " " * 50_000 + "pi"), ("radians", "np.radians(" + "7" * 50_000),
                            ("quantity", "7" * 50_000 + " mm"), ("signs", "- " * 25_000)):
            with self.subTest(label=label):
                self.assertLess(self.time_of(text), self.BOUND_S)

    def test_growth_is_linear(self) -> None:
        # Ten times the digits must cost far less than a hundred times the time (a quadratic reader's growth).
        small = min(self.time_of("x = " + "7" * 5_000) for _ in range(3))
        large = min(self.time_of("x = " + "7" * 50_000) for _ in range(3))
        self.assertLess(large, max(30 * small, 0.05))

    def test_the_line_that_took_minutes_is_read_now(self) -> None:
        # test_ref_values could only read the range() alone: the full line scan of 4,301 digits took minutes.
        line = "range(0," + "9" * 4301 + ")"
        self.assertEqual(_range_ends(_RANGE.search(line)), [])
        self.assertLess(self.time_of(line), self.BOUND_S)
        self.assertEqual(sorted(_numbers_in(line)), sorted(_numbers_in(line.replace("range(", "rng("))))


if __name__ == "__main__":
    unittest.main()
