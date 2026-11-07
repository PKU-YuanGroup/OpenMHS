"""Adversarial L04 cases: local ones/Box evidence without evaluating source."""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mhs.driver.check import _numbers_in, _unshown
from mhs.driver.ref_numeric import MAX_NODES, MAX_STATEMENTS, MAX_TEXT, ones_box_bounds


class LocalBoxEvidenceTests(unittest.TestCase):
    def test_five_pinned_source_forms(self):
        cases = [
            ("\t\thigh = np.ones([action_dim])\n\t\tself.action_space = gym.spaces.Box(-high, high)", 1),
            ("a_lim = np.ones((act_dim,), dtype=np.float32)\n"
             "self.observation_space = gym.spaces.Box(-o_lim, o_lim, dtype=np.float32)\n"
             "self.action_space = gym.spaces.Box(-a_lim, a_lim, dtype=np.float32)", 1),
            ("self._action_dim = 1\n"
             "self.cart_velocity_upper_limits = np.ones(self._action_dim) * 5.0\n"
             "self.cart_velocity_lower_limits = -self.cart_velocity_upper_limits\n"
             "self.action_space = spaces.Box(\nlow=self.cart_velocity_lower_limits,\n"
             "high=self.cart_velocity_upper_limits,\ndtype=np.float32,\n)", 5),
            ("self.action_dim = ACTION_DIM\nact_bound = 1\n"
             "act_high = np.ones(self.action_dim) * act_bound\n"
             "self.action_space = gym.spaces.Box(-act_high, act_high)", 1),
            ("self.max_torque = 1000\naction_bound = np.ones((self.n_links,)) * self.max_torque\n"
             "self.action_space = spaces.Box(low=-action_bound, high=action_bound, shape=action_bound.shape)", 1000),
        ]
        for text, magnitude in cases:
            with self.subTest(magnitude=magnitude, text=text):
                self.assertEqual(ones_box_bounds(text), [-magnitude, magnitude])
                self.assertEqual(_unshown({"min": [-magnitude] * 2, "max": [magnitude] * 2}, text), [])
                self.assertEqual(_unshown({"min": -magnitude - 0.25, "max": magnitude}, text), [-magnitude - 0.25])

    def test_keyword_ones_numpy_alias_and_scale_order(self):
        for definition in ("numpy.ones(shape=(n,), dtype=numpy.float64) * scale",
                           "scale * np.ones(n)"):
            text = f"scale = 2.5\nhigh = {definition}\nBox(low=-high, high=high)"
            self.assertEqual(ones_box_bounds(text), [-2.5, 2.5])

    def test_separate_lower_and_upper_and_independent_boxes(self):
        text = ("a = np.ones(n) * 2\nlow = -a\nfirst = spaces.Box(low, a)\n"
                "b = numpy.ones(m) * 8\nsecond = gymnasium.spaces.Box(-b, b)")
        self.assertEqual(ones_box_bounds(text), [-2., 2., -8., 8.])

    def test_comments_docstrings_and_nonexecuting_source(self):
        text = '# dangerous(): not a statement\n"""high = unknown()"""\nhigh = np.ones(n)\nBox(-high, high)'
        self.assertEqual(ones_box_bounds(text), [-1., 1.])
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "must-not-exist"
            malicious = f"high = np.ones(n)\n__import__('pathlib').Path({str(sentinel)!r}).touch()\nBox(-high, high)"
            self.assertEqual(ones_box_bounds(malicious), [])
            self.assertFalse(sentinel.exists())

    def test_no_inference_without_the_box_or_local_scale(self):
        cases = ["high = np.ones(n)", "Box(-high, high)",
                 "high = np.ones(n) * scale\nBox(-high, high)",
                 "high = np.ones(n) * self.max_torque\nBox(-high, high)",
                 "scale = EXTERNAL_DEFAULT\nhigh = np.ones(n) * scale\nBox(-high, high)",
                 "high = np.ones(n)\nBox(-other, high)",
                 "scale = 17\nBox(-scale, scale)"]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(ones_box_bounds(text), [])
        self.assertNotIn(-1., _numbers_in("high = np.ones(n)\nBox(-other, high)"))

    def test_control_flow_and_scope_are_not_followed(self):
        bodies = ["if True:\n    high = np.ones(n)", "for x in values:\n    high = np.ones(n)",
                  "while ready:\n    high = np.ones(n)", "try:\n    high = np.ones(n)\nexcept Exception:\n    pass",
                  "with context:\n    high = np.ones(n)", "def f():\n    high = np.ones(n)",
                  "class C:\n    high = np.ones(n)", "import numpy as np\nhigh = np.ones(n)",
                  "high = (np.ones(n) if ready else np.ones(n))", "high = [np.ones(n) for _ in values]",
                  "high = (lambda: np.ones(n))()"]
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(ones_box_bounds(body + "\nBox(-high, high)"), [])

    def test_reassignment_mutation_and_aliases_reject_whole_span(self):
        hazards = ["high = np.ones(m)", "high += 3", "high[0] = 3", "high[:] = 3", "del high",
                   "alias = high", "self.alias = high", "high.fill(3)", "mutate(high)",
                   "np.ones = custom", "np = custom", "numpy = custom", "spaces = custom", "Box = custom",
                   "self = other", "self.__dict__ = other", "low, high = values", "low = high = np.ones(n)"]
        for hazard in hazards:
            for at_end in (False, True):
                text = "high = np.ones(n)\n" + ("Box(-high, high)\n" + hazard if at_end else hazard + "\nBox(-high, high)")
                with self.subTest(hazard=hazard, at_end=at_end):
                    self.assertEqual(ones_box_bounds(text), [])
        self.assertEqual(ones_box_bounds("scale = 9\nscale = 17\nhigh = np.ones(n) * scale\nBox(-high, high)"), [])
        self.assertEqual(ones_box_bounds("self.high = np.ones(n)\nself.high[0] = 9\nBox(-self.high, self.high)"), [])

    def test_calls_and_unsupported_operators_are_not_inferred(self):
        expressions = ["ones(n)", "jnp.ones(n)", "self.np.ones(n)", "np.ones_like(x)",
                       "np.ones(get_n())", "np.ones(n).astype(np.float32)", "np.ones(n)[0]",
                       "np.ones(n) + 2", "np.ones(n) / 2", "np.ones(n) ** 2", "np.ones(n) * dynamic()",
                       "np.ones(n) * np.ones(n)", "np.ones(n) * 2 * 3", "np.ones(n, **options)",
                       "np.ones(*shape)", "np.ones(n, order='C')", "np.ones(n, dtype=choose())"]
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assertEqual(ones_box_bounds(f"high = {expression}\nBox(-high, high)"), [])
        for call in ["custom.Box(-high, high)", "self.Box(-high, high)", "Box(-high, high, seed=9)",
                     "Box(-high, high, **options)", "Box(*bounds)", "Box(low=-high, high=high, shape=shape())"]:
            with self.subTest(call=call):
                self.assertEqual(ones_box_bounds("high = np.ones(n)\n" + call), [])

    def test_dtype_rounding_wrap_bool_and_nonfinite_are_not_proof(self):
        for dtype in ["np.uint8", "np.int8", "bool", "np.float16", "dtype", "np.complex64"]:
            for target in ("ones", "box"):
                ones = f"np.ones(n, dtype={dtype})" if target == "ones" else "np.ones(n)"
                box = f"Box(-high, high, dtype={dtype})" if target == "box" else "Box(-high, high)"
                with self.subTest(dtype=dtype, target=target):
                    self.assertEqual(ones_box_bounds(f"high = {ones}\n{box}"), [])
        for scale in ["True", "False", "1e309", "float('inf')", "None", "'17'", "1j", "0.1"]:
            with self.subTest(scale=scale):
                self.assertEqual(ones_box_bounds(f"scale = {scale}\nhigh = np.ones(n) * scale\nBox(-high, high)"), [])
        self.assertEqual(ones_box_bounds("high = np.ones(n) * .1\nBox(-high, high, dtype=np.float64)"), [-.1, .1])
        self.assertEqual(ones_box_bounds("high = np.ones(n, dtype=np.float32) * .1\nBox(-high, high, dtype=np.float64)"), [])

    def test_shape_is_opaque_but_known_invalid_shapes_are_refused(self):
        for shape in ["0", "-1", "True", "1.5", "[]", "()", "((2,),)", "[2, [3]]"]:
            with self.subTest(shape=shape):
                self.assertEqual(ones_box_bounds(f"high = np.ones({shape})\nBox(-high, high)"), [])
        for number in (0, -2, 1.5):
            self.assertEqual(ones_box_bounds(f"n = {number}\nhigh = np.ones(n)\nBox(-high, high)"), [])
        self.assertEqual(ones_box_bounds("high = np.ones(n)\nn = 2\nBox(-high, high)"), [])
        self.assertEqual(ones_box_bounds("high = np.ones(n)\nshape = high\nBox(-high, high, shape=shape)"), [])

    def test_bounded_text_nodes_and_statements(self):
        text = "high = np.ones(n)\nBox(-high, high)"
        with patch("mhs.driver.ref_numeric.ast.parse", side_effect=AssertionError("oversized source parsed")):
            self.assertEqual(ones_box_bounds("#" * (MAX_TEXT + 1)), [])
        many_statements = "\n".join(f"x{i} = {i}" for i in range(MAX_STATEMENTS)) + "\n" + text
        self.assertEqual(ones_box_bounds(many_statements), [])
        many_nodes = "high = np.ones([" + ",".join("n" for _ in range(MAX_NODES)) + "])\nBox(-high, high)"
        self.assertLess(len(many_nodes), MAX_TEXT)
        self.assertGreater(sum(1 for _ in ast.walk(ast.parse(many_nodes))), MAX_NODES)
        self.assertEqual(ones_box_bounds(many_nodes), [])
        self.assertEqual(ones_box_bounds("[" * 500 + "]" * 500), [])

    def test_legacy_evidence_survives_refused_new_inference(self):
        # This task adds Box inference; existing literal/comment/angle semantics
        # are intentionally unchanged, even in an unsupported Python span.
        self.assertEqual(ones_box_bounds("high = dynamic()  # bound is 17\nBox(-high, high)"), [])
        self.assertIn(17., _numbers_in("high = dynamic()  # bound is 17\nBox(-high, high)"))
        self.assertNotIn(-17., _numbers_in("high = dynamic()  # bound is 17\nBox(-high, high)"))


if __name__ == "__main__":
    unittest.main()
