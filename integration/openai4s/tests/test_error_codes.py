"""Every MHS error code the integration emits is registered and current (TESTS-11).

Scans the source of ``openai4s_mhs`` and the demo for ``MHS.<AREA>.<NAME>``
literals and checks each against the SDK's error registry
(``mhs.errors``, generated from ``MHS/spec/errors.json``): a code must be
registered and must not be deprecated (``MHS.HOST.OPENAI4S_MISSING`` was
replaced by ``MHS.HOST.ADAPTER_MISSING``).  A literal used as a prefix in a
``startswith`` test (``"MHS.SAFETY.PERMIT"``) must be the prefix of a
registered code.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from mhs import errors

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "openai4s_mhs").glob("*.py")) + sorted((ROOT / "demo").glob("*.py"))
CODE = re.compile(r"\bMHS\.[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b")


class ErrorCodeTests(unittest.TestCase):
    def test_emitted_codes_are_registered_and_not_deprecated(self) -> None:
        registered = set(errors.all_error_codes())
        self.assertIn("MHS.HOST.ADAPTER_MISSING", registered)
        seen = 0
        problems = []
        for path in SOURCES:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for match in CODE.finditer(line):
                    code = match.group(0)
                    seen += 1
                    where = f"{path.relative_to(ROOT)}:{number}"
                    if code in errors.DEPRECATED_CODES:
                        problems.append(f"{where}: {code} is deprecated, use {errors.DEPRECATED_CODES[code]}")
                    elif code not in registered:
                        prefix = "startswith" in line and any(c.startswith(code + "_") for c in registered)
                        if not prefix:
                            problems.append(f"{where}: {code} is not a registered MHS error code")
        self.assertGreater(seen, 20)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
