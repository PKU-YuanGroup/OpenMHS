"""G4 REF_VALUE: the numbers a cited line shows, including the angle forms upstream code writes for them."""

import math
import unittest

from mhs.driver.check import _RANGE, _numbers_in, _range_ends, _unshown


class NumbersInTests(unittest.TestCase):
    def assertShows(self, text, *values):
        found = _numbers_in(text)
        for value in values:
            self.assertTrue(any(abs(value - item) < 1e-9 for item in found), f"{value} not in {found} for {text!r}")

    def assertNotShows(self, text, value):
        found = _numbers_in(text)
        self.assertFalse(any(abs(value - item) < 1e-9 for item in found), f"{value} wrongly in {found} for {text!r}")

    def test_plain_literals(self):
        self.assertShows("limits = (-750, 750.5), 1e-3", -750, 750.5, 1e-3)

    def test_a_range_without_spaces_shows_both_ends(self):
        self.assertShows('""" Set top speed in `pulses_per_sec` [5-6000] """', 5, 6000)
        self.assertShows("# allowed 50-1000 Hz", 50, 1000)
        self.assertShows("range(0-3000)", 0, 3000)

    def test_a_sign_stays_a_sign_when_no_digit_precedes_it(self):
        self.assertShows("x = -5", -5)
        self.assertNotShows("x = -5", 5)
        self.assertShows("limits = (-750, 750)", -750, 750)
        self.assertNotShows("limits = (-750, 750)", 0 + 0.5)
        self.assertNotShows("a, b = 3, -4", 4)  # a comma and a space precede the minus sign: no range
        self.assertShows("1e-3", 1e-3)
        self.assertNotShows("1e-3", 3)

    def test_pi_forms(self):
        self.assertShows("(-2 * math.pi, 2 * math.pi),", -2 * math.pi, 2 * math.pi)
        self.assertShows("(-math.pi, math.pi)", -math.pi, math.pi)
        self.assertShows("half = math.pi / 2", math.pi / 2)
        self.assertShows("full = np.pi * 2", 2 * math.pi)
        self.assertShows("pi", math.pi)

    def test_radians_calls(self):
        self.assertShows("max = np.radians(90)", math.radians(90))
        self.assertShows("max = math.radians(-45.5)", math.radians(-45.5))

    def test_a_line_in_degrees_also_shows_the_radians(self):
        # A catalogue class speaks rad, upstream code often degrees (the two Cozmo SDKs of wave A).
        self.assertShows("MIN_HEAD_ANGLE = util.degrees(-25)", math.radians(-25))
        self.assertShows("MAX_HEAD_ANGLE = util.Angle(degrees=44.5)", math.radians(44.5))
        self.assertShows("# the joint travels -170 to 170 deg", math.radians(-170), math.radians(170))
        self.assertShows("range: 0-90°", math.radians(90))
        # A Chinese comment writes the degree sign U+5EA6 after the number (the servo arm of wave C); the same
        # sign after another character is part of a word (speed, temperature), not a unit.
        self.assertShows("# angle (0-180\u5ea6) to a servo position", math.radians(180))
        self.assertNotShows("# speed (\u901f\u5ea6) 0-180", math.radians(180))
        self.assertNotShows("MAX_LIFT_HEIGHT = util.Distance(mm=92.0)", math.radians(92))
        self.assertNotShows("delay = 25  # ms", math.radians(25))

    def test_a_zero_bound_needs_no_number_on_the_line(self):
        # "OutputSpec(1, 30.0, 3.0, ...)" rates the output; its floor 0 is the setter's, on another line (wave B).
        line = "OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001),"
        self.assertEqual(_unshown({"min": 0.0, "max": 30.0}, line), [])
        self.assertEqual(_unshown({"min": [0, 0], "max": [30.0, 3.0]}, line), [])
        self.assertEqual(_unshown({"min": 0.5, "max": 31.0}, line), [0.5, 31.0], "any other number is still checked")
        self.assertEqual(_unshown({"min": -30.0, "max": 30.0}, line), [-30.0])

    def test_thousands_separators(self):
        # "The range is 5,000 to 2,147,400,000 samples" (a Tektronix docstring of wave B).
        self.assertShows("The range is 5,000 to 2,147,400,000 samples.", 5000, 2147400000)
        self.assertShows("Allowable x values range from -1,000 um to 1,000 um.", -1000, 1000)
        self.assertNotShows("channels = [1,2,3]", 123)
        self.assertNotShows("x = 1,2345", 12345)

    def test_python_literals(self):
        # "assert 1 <= speed_in_rpm <= 750_000", "b <= 0b1111_1111", "max decimation of 65_535." (wave B)
        self.assertShows("assert 1 <= speed_in_rpm <= 750_000", 1, 750000)
        self.assertShows("assert all(b <= 0b1111_1111 for b in waveform)", 255)
        self.assertShows("less than 65_535. This is not perfect", 65535)
        self.assertShows("mask = 0xFF; mode = 0o17; step = 1_000.5", 255, 15, 1000.5)
        self.assertNotShows("var_1_000 = 3", 1000)
        self.assertNotShows("value = x0b11", 3)

    def test_a_magnitude_bound_also_shows_the_negatives(self):
        # "A magnitude past these is refused" over MAX_LINEAR_MPS = 1.0; "if abs(x) > 1000:" (wave B).
        self.assertShows("#: A magnitude past these is refused by name MAX_LINEAR_MPS = 1.0", -1.0, 1.0)
        self.assertShows("if abs(x) > 1000:", -1000)
        self.assertShows("output ±5 V", -5)
        self.assertShows("travel +/- 12.5 mm", -12.5)
        self.assertNotShows("speed = 1.0  # m/s", -1.0)
        self.assertNotShows("accuracy ±0.5, range 0 to 100", -100)  # the sign belongs to the tolerance only
        self.assertNotShows("if abs(x - offset) > tol: limit = 30", -30)

    def test_a_quantity_in_another_unit_shows_its_value_in_the_rule_unit(self):
        # The Franka Hand stroke "constant 0.08 m ... 8 cm stroke" bounds a width in mm (wave B).
        line = "| `max_width` | constant `0.08` m | Correct, it matches the real Franka Hand's 8 cm stroke. |"
        self.assertEqual(_unshown({"min": 0, "max": 80, "unit": "mm"}, line), [])
        self.assertEqual(_unshown({"min": 0, "max": 80}, line), [80], "without a unit there is nothing to convert")
        self.assertEqual(_unshown({"min": 0, "max": 80, "unit": "mm"}, "stroke 0.08 s"), [80], "another dimension")
        self.assertEqual(_unshown({"min": 0, "max": 5, "unit": "mm"}, "about 5 apples"), [])  # the literal 5

    def test_a_discrete_space_shows_its_largest_action(self):
        # CartPole's "self.action_space = spaces.Discrete(2)" allows the actions 0 and 1 (GYM-SPACE-REF).
        self.assertShows("self.action_space = spaces.Discrete(2)", 1)
        self.assertShows("self.action_space = gym.spaces.Discrete(17)", 16)
        self.assertShows("action_space = Discrete(n=5)", 4)
        self.assertShows("spaces.Discrete(3, start=-1)", -1, 1)
        self.assertShows("'type': gym.spaces.Discrete(7), # please refer to line 192-210", 6)
        self.assertEqual(_unshown({"min": 0, "max": 1}, "self.action_space = spaces.Discrete(2)"), [])
        self.assertEqual(_unshown({"min": 0, "max": 3}, "self.action_space = spaces.Discrete(2)"), [3.0])
        self.assertNotShows("self.action_space = spaces.MultiDiscrete([3, 3])", 2)
        self.assertNotShows("self.action_space = spaces.Discrete(len(self.actions))", -1)

    def test_a_literal_python_range_shows_its_first_and_last_element(self):
        # The AS7265x guard "if time not in range(0,255):" accepts 0 through 254 (spectrometer.py:280).
        guard = "\tif time not in range(0,255):"
        self.assertShows(guard, 0, 254)
        self.assertEqual(_unshown({"min": 0, "max": 254}, guard), [])
        self.assertEqual(_unshown({"min": 0, "max": 253}, guard), [253.0], "only the first and last element")
        self.assertShows("for index in range(18):", 0, 17)
        self.assertShows("range( 1 , 19 )", 1, 18)
        self.assertShows("range(0, 255, 5)", 0, 250)
        self.assertNotShows("range(0, 255, 5)", 254)
        self.assertShows("range(10, 0, -2)", 10, 2)
        self.assertShows("range(-3, 4)", -3, 3)
        # An empty range or a zero step states no element; the literals themselves are still shown.
        self.assertNotShows("range(5, 5)", 4)
        self.assertNotShows("range(0, 10, 0)", 9)
        # Dynamic, float and other-name forms show nothing more than their literals.
        self.assertNotShows("range(0, n_max)", -1)
        self.assertNotShows("range(0, len(values))", -1)
        self.assertNotShows("range(0, 2.5)", 1)
        self.assertNotShows("np.arange(0, 255)", 254)
        self.assertNotShows("xrange(0, 255)", 254)
        self.assertNotShows("my_range(0, 255)", 254)
        self.assertNotShows("self.range(0, 255)", 254)
        # The text range "range(0-3000)" keeps its earlier reading.
        self.assertShows("range(0-3000)", 0, 3000)
        self.assertNotShows("range(0-3000)", 2999)

    def test_a_range_of_literals_no_float_holds_shows_nothing_more_and_never_raises(self):
        # A range() argument of more than 308 digits (float() overflows) or more than 4300 (int() refuses it) made the
        # reader raise and the gate crash; such a line now shows exactly what the same literals show without range().
        huge = "9" * 400
        for line in (f"range(0,{huge})", f"range({huge})", f"range(-{huge}, 0, {huge})", f"range(1, {huge}, 2)"):
            with self.subTest(line=line[:24]):
                self.assertEqual(sorted(_numbers_in(line)), sorted(_numbers_in(line.replace("range(", "rng("))))
        # the int() digit limit, on the range reader alone (the full line scan of 4,301 digits takes minutes)
        self.assertEqual(_range_ends(_RANGE.search("range(0," + "9" * 4301 + ")")), [])
        self.assertShows("if time not in range(0,255):", 0, 254)

    def test_an_array_of_ones_shows_one(self):
        # gymfc's "spaces.Box(-np.ones(4), np.ones(4), dtype=np.float32)" bounds each motor command by -1 and 1.
        self.assertShows("self.action_space = spaces.Box(-np.ones(4), np.ones(4), dtype=np.float32)", -1, 1)
        self.assertShows("self.action_space = spaces.Box(-np.ones([4]), np.ones([4]))", -1, 1)
        self.assertShows("spaces.Box(low=-np.ones(11), high=numpy.ones((11,), dtype=np.float32))", -1, 1)
        self.assertEqual(_unshown({"min": [-1] * 4, "max": [1] * 4}, "spaces.Box(-np.ones(4), np.ones(4))"), [])
        self.assertEqual(_unshown({"min": -2, "max": 1}, "spaces.Box(-np.ones(4), np.ones(4))"), [-2.0])
        self.assertShows("high = np.ones([action_dim])", 1)
        self.assertNotShows("high = np.ones([action_dim])", -1)  # its "Box(-high, high)" writes no -1
        # A scaled or offset array holds another number.
        self.assertNotShows("action_bound = np.ones((self.n_links,)) * self.max_torque", 1)
        self.assertNotShows("o_lim = 3 * np.ones((obs_dim, ), dtype=np.float32)", 1)
        self.assertNotShows("high = np.array(self.maze_size) - np.ones(len(self.maze_size), dtype=int)", -1)
        self.assertNotShows("high = np.array(self.maze_size) - np.ones(len(self.maze_size), dtype=int)", 1)
        self.assertNotShows("high += np.ones(2); low -= np.ones(2); same = x == np.ones(2)", 1)
        self.assertNotShows("steps = -jnp.ones((n_worlds, 2)); mask = np.ones_like(x)", -1)
        self.assertNotShows("steps = -jnp.ones((n_worlds, 2)); mask = np.ones_like(x)", 1)

    def test_words_that_end_in_pi_are_not_pi(self):
        self.assertNotShows("from xarm.wrapper.xarm_api import XArmAPI", math.pi)
        self.assertNotShows("spiral = 3; self.pi = 3", math.pi)


if __name__ == "__main__":
    unittest.main()
