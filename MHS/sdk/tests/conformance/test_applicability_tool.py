"""tools/build_applicability.py regenerates the inventory reproducibly (WP-07 (9), FOLLOWUPS WP-07)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from mhs.conformance.requirements import APPLICABILITY_FILE, applicability_entries

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "MHS/sdk/tools/build_applicability.py"
TRACEABILITY = ROOT / "MHS/sdk/src/mhs/conformance/traceability.json"


class BuildApplicabilityTests(unittest.TestCase):
    def test_check_mode_exits_zero(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, str(TOOL), "--check"], cwd=str(ROOT), env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generated_by_points_at_the_tool(self):
        document = json.loads(APPLICABILITY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(document["generated_by"], "MHS/sdk/tools/build_applicability.py")

    def test_line_numbers_are_current(self):
        for requirement_id, record in applicability_entries().items():
            lines = (ROOT / record["doc"]).read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines[record["line"] - 1].startswith(f"**{requirement_id}.**"), requirement_id)

    def test_grouped_checks_do_not_overstate_the_inventory(self):
        """TCAP-002 (resource kind) and TCAP-001 (output) check no numbered requirement (CONF-07/CONF-11)."""

        entries = applicability_entries()
        self.assertEqual(entries["CAP-007"]["disposition"], "not_verified", entries["CAP-007"])
        self.assertNotIn("TCAP-001", entries["CAP-016"]["checks"])
        trace = json.loads(TRACEABILITY.read_text(encoding="utf-8"))
        self.assertEqual(trace["tests"]["TCAP-001"], [])
        self.assertEqual(trace["tests"]["TCAP-002"], [])
        self.assertIn("resource_kinds", trace["sections"]["TCAP-002"])
        self.assertIn("output_schema", trace["sections"]["TCAP-001"])

    def test_suite_behaviour_requirements_are_suite_checks(self):
        entries = applicability_entries()
        for requirement_id in ("CON-031", "CON-032"):
            self.assertEqual(entries[requirement_id]["disposition"], "executable", requirement_id)
            self.assertEqual(entries[requirement_id]["checks"], [requirement_id])


if __name__ == "__main__":
    unittest.main()
