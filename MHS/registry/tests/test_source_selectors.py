"""Source-only selectors across registry shape, schema, pinned validation and recon."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REG = Path(__file__).resolve().parents[1]
MHS = REG.parent
sys.path.insert(0, str(REG))
sys.path.insert(0, str(MHS / "sdk" / "src"))
sys.path.insert(0, str(MHS / "sdk"))
sys.path.insert(0, str(MHS / "handoff" / "tools"))

try:
    import check_recon
except ImportError:  # the public release leaves the model-orchestration kit (recon checker) out
    check_recon = None
import taskcards
import triage
import validate
from mhs.schema import SchemaStore
from mhs.driver.upstream import _git_env

STORE = SchemaStore(MHS / "schema", extra_roots=[REG / "schema"])


def git(root, *args):
    env = _git_env()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root),
                             "-c", "user.name=source-test", "-c", "user.email=source-test@invalid",
                             "-c", "commit.gpgsign=false", *args], capture_output=True, text=True,
                            timeout=30, env=env, check=True, stdin=subprocess.DEVNULL)
    return result.stdout.strip()


class ShapeTests(unittest.TestCase):
    def override(self, symbol, file, line):
        return {"package_id": "gh.acme/probe", "strategy": "direct-driver", "role": "device-driver",
                "family": "python-object", "justification": "Verified exact pinned Python source entry.",
                "entry_symbols": [{"symbol": symbol, "file": file, "line": line}]}

    def schema_errors(self, entry):
        return STORE.validate({"overrides_version": "0.9", "title": "Source entries", "overrides": [entry]},
                              "overrides.schema.json")

    def test_four_named_shapes_and_old_form(self):
        cases = [("pyfile:spectrometer.py#*", "spectrometer.py", 1),
                 ("pyfile:2230G.py#KEI2230G", "2230G.py", 12),
                 ("pyfile:2220 Programmable DC Power Supplies.py#KEI2220S",
                  "2220 Programmable DC Power Supplies.py", 11),
                 ("TLBC2:TLBC2", "Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py", 156),
                 ("thermal.device:Bath", "thermal/device.py", 12)]
        for symbol, file, line in cases:
            with self.subTest(symbol=symbol):
                entry = self.override(symbol, file, line)
                triage.check_override(entry, "test")
                self.assertTrue(taskcards._symbol_ok(symbol, file, line))
                self.assertEqual(self.schema_errors(entry), [])
                card = json.loads((REG / "schema/examples/taskcard.thermal-bath.json").read_text())
                card["entry_symbols"] = [dict(entry["entry_symbols"][0], confidence="override")]
                self.assertEqual(STORE.validate(card, "taskcard.schema.json"), [])

    def test_unsafe_selector_and_path_rejected_by_schema_and_parser(self):
        for file in ("../a.py", "/a.py", "a//b.py", "./a.py", "a/../b.py", "a\\b.py", "a.py\n", "a:1.py"):
            entry = self.override(f"pyfile:{file}#X", file, 1)
            self.assertTrue(self.schema_errors(entry), file)
            with self.assertRaises(triage.OverrideError):
                triage.check_override(entry, "test")
        entry = self.override("2220_programmable_dc_power_supplies:KEI2220S",
                              "2220 Programmable DC Power Supplies.py", 11)
        self.assertTrue(self.schema_errors(entry))

    def test_cross_field_errors_are_rejected_without_relaxing_package_paths(self):
        for entry in (self.override("pyfile:a.py#X", "b.py", 1),
                      self.override("pyfile:a.py#*", "a.py", 2)):
            with self.assertRaises(triage.OverrideError):
                triage.check_override(entry, "test")
        # The general package relPath remains unchanged.
        schema, _ = STORE.load("defs.schema.json")
        self.assertNotIn(" ", schema["$defs"]["relPath"]["pattern"])


class PinnedEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mhs-source-registry-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clone = self.root / "labs/acme/probe"
        self.clone.mkdir(parents=True)
        self.file = "Folder With Spaces/TLBC2.py"
        path = self.clone / self.file
        path.parent.mkdir()
        path.write_text("# source\nclass TLBC2:\n    def read(self): pass\n")
        (self.clone / "spectrometer.py").write_text("def readRAW():\n    print output\n    return output\n")
        (self.clone / "README.md").write_text("Source-backed spectrometer example.\n")
        git(self.clone, "init", "-q")
        git(self.clone, "add", ".")
        git(self.clone, "commit", "-qm", "pin")
        self.pin = git(self.clone, "rev-parse", "HEAD")
        self.card = {"package_id": "gh.acme/probe", "local_path": "labs/acme/probe",
                     "driver_dir": "MHS/drivers/labs/acme__probe",
                     "upstream": {"commit": self.pin},
                     "entry_symbols": [{"symbol": f"pyfile:{self.file}#TLBC2",
                                        "file": self.file, "line": 2, "confidence": "override"}]}

    def errors(self):
        with patch.object(validate, "WORKSPACE", str(self.root)), patch.object(validate, "count_physical_dirs", return_value=1):
            return validate.check_corpus([{}], {"probe": self.card})

    def test_registry_uses_pin_not_worktree_and_checks_exact_line(self):
        (self.clone / self.file).write_text("class Wrong: pass\n")
        self.assertEqual(self.errors(), [])
        self.card["entry_symbols"][0]["line"] = 1
        self.assertTrue(self.errors())

    def test_missing_pin_and_selector_file_mismatch_fail(self):
        self.card["upstream"]["commit"] = "0" * 40
        self.assertTrue(self.errors())
        self.card["upstream"]["commit"] = self.pin
        self.card["entry_symbols"][0]["file"] = "other.py"
        self.assertTrue(self.errors())

    def test_dotted_class_with_space_hint_and_module_entry(self):
        self.card["entry_symbols"][0]["symbol"] = "TLBC2:TLBC2"
        self.assertEqual(self.errors(), [])
        self.card["entry_symbols"] = [{"symbol": "pyfile:spectrometer.py#*", "file": "spectrometer.py",
                                      "line": 1, "confidence": "override"}]
        self.assertEqual(self.errors(), [])

    def recon(self):
        proposal = self.root / "acme__probe.json"
        entry = {key: value for key, value in self.card["entry_symbols"][0].items() if key != "confidence"}
        proposal.write_text(json.dumps({"package_id": self.card["package_id"],
                                       "proposed": {"strategy": "direct-driver", "role": "device-driver",
                                                    "family": "python-object"},
                                       "entry_symbols": [entry],
                                       "evidence": [f"{entry['file']}:{entry['line']} Exact pinned source entry.",
                                                    "README.md:1 Source description."],
                                       "notes": "A source-backed device adapter can use this exact entry."}))
        allowed = {"strategy": ["direct-driver"], "role": ["device-driver"], "family": ["python-object"]}
        with patch.object(check_recon.dispatch, "kind_of", return_value="recon"):
            return check_recon.check_file(self.root, proposal, {self.card["package_id"]: self.card}, allowed, False)

    @unittest.skipIf(check_recon is None, "the recon checker is not in this tree")
    def test_recon_emits_exact_selector_and_checks_pinned_evidence(self):
        (self.clone / self.file).write_text("raise RuntimeError('do not execute')\n")
        result = self.recon()
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["override"]["entry_symbols"][0]["symbol"], f"pyfile:{self.file}#TLBC2")
        self.card["upstream"]["commit"] = "0" * 40
        self.assertTrue(self.recon()["problems"])

    @unittest.skipIf(check_recon is None, "the recon checker is not in this tree")
    def test_recon_module_entry_and_wrong_class_rejected(self):
        self.card["entry_symbols"] = [{"symbol": "pyfile:spectrometer.py#*", "file": "spectrometer.py",
                                      "line": 1, "confidence": "override"}]
        self.assertEqual(self.recon()["problems"], [])
        self.card["entry_symbols"][0]["symbol"] = "pyfile:spectrometer.py#Missing"
        self.assertTrue(self.recon()["problems"])

    @unittest.skipIf(check_recon is None, "the recon checker is not in this tree")
    def test_recon_does_not_silently_drop_unimportable_numeric_module_name(self):
        self.card["entry_symbols"] = [{"symbol": "2230G:TLBC2", "file": self.file,
                                      "line": 2, "confidence": "override"}]
        result = self.recon()
        self.assertTrue(result["problems"])
        self.assertIsNone(result["override"])


if __name__ == "__main__":
    unittest.main()
