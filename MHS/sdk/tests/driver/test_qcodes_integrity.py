"""QCoDeS proof code must be guarded before any package import runs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mhs.driver.check import static_findings

SDK = Path(__file__).resolve().parents[2]
EXACT_REPLACEMENT = ('from importlib import import_module\n'
                     'checks = import_module("mhs.driver.qcodes_check")\n'
                     'checks._proof = lambda *args: None\n')

# Each stock gate probe gets a fresh interpreter. Otherwise earlier tests could
# accidentally preload an unprotected module and hide the first-import defect.
CHILD = r'''import json, shutil, sys, tempfile
from pathlib import Path
from mhs.driver.check import run_check, static_findings
sdk = Path(sys.argv[1])
source = sys.argv[2]
with tempfile.TemporaryDirectory() as temp:
    package = Path(temp) / "thermostat"
    shutil.copytree(sdk / "examples" / "thermostat", package)
    driver = package / "driver.py"
    driver.write_text(driver.read_text() + "\n" + source)
    static = static_findings(package)
    report = run_check(package, gates=["G3"], write_report=False)
    gate = next(item for item in report["gates"] if item["id"] == "G3")
    native_imports = sorted(name for name in sys.modules
                            if name.split(".")[0] in {"qcodes", "qcodes_contrib_drivers", "pyvisa", "visa"})
    print(json.dumps({"static": static, "gate": gate, "native_imports": native_imports}))
'''


class QcodesGateIntegrityTests(unittest.TestCase):
    def stock(self, source):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SDK / "src"))
        completed = subprocess.run([sys.executable, "-c", CHILD, str(SDK), source],
                                   env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_checker_import_spellings_are_forbidden(self):
        cases = (
            'import mhs.driver.qcodes_check\n',
            'from mhs.driver.qcodes_check import _proof\n',
            'from mhs.driver import qcodes_check\n',
            EXACT_REPLACEMENT,
            'import importlib\nchecks = importlib.import_module("mhs.driver." + "qcodes_check")\n',
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for source in cases:
                with self.subTest(source=source):
                    (root / "driver.py").write_text(source)
                    self.assertIn("G3.FORBIDDEN", [item[0] for item in static_findings(root)])

    def test_exact_first_import_replacement_is_refused_and_detected(self):
        result = self.stock(EXACT_REPLACEMENT)
        self.assertIn("G3.FORBIDDEN", [item[0] for item in result["static"]])
        codes = [item["code"] for item in result["gate"]["findings"]]
        self.assertIn("G3.GATE_TAMPERED", codes)
        self.assertEqual(result["gate"]["status"], "fail")
        self.assertEqual(result["native_imports"], [])

    def test_computed_import_cannot_hide_function_config_or_proof_table_mutation(self):
        cases = (
            ("qcodes_check", "module._proof = lambda *args: None", "_proof"),
            ("qcodes_config", "module.compile_parameters = lambda *args: ({}, {})", "compile_parameters"),
            ("qcodes_check", "module._IDENTITY_MEMBERS.clear()", "_IDENTITY_MEMBERS"),
        )
        for leaf, mutation, member in cases:
            with self.subTest(member=member):
                source = ('from importlib import import_module\n'
                          'module = import_module(".".join(["mhs", "driver", ' + repr(leaf) + ']))\n'
                          + mutation + '\n')
                result = self.stock(source)
                # Computed imports are intentionally outside the static literal
                # resolver; the stock pre-import integrity baseline must catch it.
                self.assertEqual(result["static"], [])
                findings = result["gate"]["findings"]
                self.assertTrue(any(item["code"] == "G3.GATE_TAMPERED" and member in item["message"]
                                    for item in findings), findings)
                self.assertEqual(result["gate"]["status"], "fail")
                self.assertEqual(result["native_imports"], [])

    def test_clean_stock_gate_still_passes_without_native_dependencies(self):
        result = self.stock("")
        self.assertEqual(result["static"], [])
        self.assertEqual(result["gate"]["status"], "pass", result["gate"])
        self.assertEqual(result["native_imports"], [])
