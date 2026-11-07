"""gen_errors.py and gen_appendices.py reproduce the committed files exactly."""

from __future__ import annotations

import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path

from ._support import CAPABILITIES, ERRORS, SPEC_DIR, load_json, load_tool


def _quiet(function, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return function(*args)


class GeneratorTests(unittest.TestCase):
    def test_errors_module_is_fresh(self):
        self.assertEqual(_quiet(load_tool("gen_errors").main, ["--check"]), 0)

    def test_appendices_are_fresh(self):
        self.assertEqual(_quiet(load_tool("gen_appendices").main, ["--check"]), 0)

    def test_check_detects_a_stale_module(self):
        tool = load_tool("gen_errors")
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "errors.py"
            text = tool.ERRORS_PY.read_text(encoding="utf-8")
            module.write_text(text.replace("'MHS.SAFETY.LIMITS_UNSET'", "'MHS.SAFETY.LIMITS_GONE'", 1), encoding="utf-8")
            self.assertEqual(_quiet(tool.main, ["--check", "--module", str(module)]), 1)
            self.assertEqual(_quiet(tool.main, ["--module", str(module)]), 0)
            self.assertEqual(module.read_text(encoding="utf-8"), text)

    def test_invalid_registry_is_refused(self):
        tool = load_tool("gen_errors")
        registry = copy.deepcopy(load_json(ERRORS))
        registry["errors"][0]["area"] = "SESSION"
        registry["errors"][1].pop("since")
        deprecated = next(r for r in registry["errors"] if r["status"] == "deprecated")
        deprecated.pop("replaced_by")
        problems = "\n".join(tool.registry_problems(registry))
        self.assertIn("does not match the code", problems)
        self.assertIn("missing ['since']", problems)
        self.assertIn("deprecated without replaced_by", problems)

    def test_appendices_cover_every_code_and_class(self):
        appendix_a = (SPEC_DIR / "appendix-a-capabilities.md").read_text(encoding="utf-8")
        appendix_b = (SPEC_DIR / "appendix-b-errors.md").read_text(encoding="utf-8")
        for entry in load_json(CAPABILITIES)["capabilities"]:
            self.assertIn(f"`{entry['capability_id']}`", appendix_a)
        for record in load_json(ERRORS)["errors"]:
            self.assertIn(f"`{record['code']}`", appendix_b)
        for requirement in [f"ERR-{n:03d}" for n in range(1, 13)] + ["CAP-046"]:  # MHS-A-001 was renumbered (WP-09)
            self.assertIn(f"**{requirement}.**", appendix_a + appendix_b)


if __name__ == "__main__":
    unittest.main()
