"""Bounded facts/reference advisory and collection verdict independence."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "MHS/handoff/tools"
sys.path.insert(0, str(TOOLS))
try:
    import facts_limits
    spec = importlib.util.spec_from_file_location("facts_collect_test", TOOLS / "collect.py")
    collect = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collect)
finally:
    sys.path.remove(str(TOOLS))


def reference(*bounds):
    if not bounds:
        bounds = ({"source": "upstream_code", "ref": "env.py:25", "min": [-1], "max": [1]},)
    return {"actions": [{"cap_id": "cap.world.step.v1", "inputs": [
        {"name": f"action.field{i}", "limit": value} for i, value in enumerate(bounds)]}]}


class FactsLimitsTests(unittest.TestCase):
    def test_current_source_and_ref_in_wrapped_plain_paragraph(self):
        text = "Limits: action values are bounded, with the source `upstream_code`\n and the ref `env.py:25`.\n"
        self.assertEqual(facts_limits.compare_limits(text, reference()), [])

    def test_stale_ref_detected_under_limits_heading(self):
        notes = facts_limits.compare_limits("## Limits\n\nThe step action has ref `old.py:3`.\n", reference())
        self.assertEqual(len(notes), 1)
        self.assertIn("old.py:3", notes[0])
        self.assertIn("env.py:25", notes[0])

    def test_historical_synthetic_source_is_detected(self):
        for value in ("OldEnv-v1:action_space", "<env id>:action_space", "OldEnv-v1:\naction_space"):
            with self.subTest(value=value):
                notes = facts_limits.compare_limits(f"Limits: action bounds with source `{value}`.", reference())
                self.assertEqual(len(notes), 1)
                self.assertIn("names ref", notes[0])

    def test_backticked_source_and_ref_labels_do_not_capture_space_as_value(self):
        text = "Limits: step action bounds (`source` `upstream_code`, `ref` `env.py:25`)."
        self.assertEqual(facts_limits.compare_limits(text, reference()), [])

    def test_unsourced_fake_ref_matches(self):
        ref = "action_space of the fake backend .fake:FakeEnv"
        self.assertEqual(facts_limits.compare_limits(
            f"Limits: action space with no source and ref `{ref}`.",
            reference({"ref": ref, "min": 0, "max": 1})), [])

    def test_source_claim_mismatch_both_directions(self):
        cases = [("no source", reference()),
                 ("source `upstream_code`", reference({"ref": "fake space"}))]
        for clause, doc in cases:
            with self.subTest(clause=clause):
                notes = facts_limits.compare_limits(f"Limits: step action has {clause}.", doc)
                self.assertEqual(len(notes), 1)
                self.assertIn("names source", notes[0])

    def test_multiple_fields_compare_union_without_inventing_field_mapping(self):
        doc = reference({"ref": "arm.py:1", "source": "upstream_code"},
                        {"ref": "fake space"})
        text = "Limits: step action bounds use ref `arm.py:1`, source `upstream_code`; ref `fake space`, no source."
        self.assertEqual(facts_limits.compare_limits(text, doc), [])

    def test_unrelated_prose_code_examples_and_later_sections_are_not_scanned(self):
        text = ("Facts: action source `wrong` and ref `wrong.py:1`.\n\n"
                "Limits: action bounds use ref `env.py:25`.\n\n"
                "The step previously had ref `old.py:9`.\n\n"
                "## Limits\n\n```text\nThe action ref `example.py:1`.\n```\n\n"
                "## Safety\nThe action ref `stop.py:1`.\n")
        self.assertEqual(facts_limits.compare_limits(text, reference()), [])

    def test_non_action_limit_clause_and_numeric_free_prose_not_guessed(self):
        text = "## Limits\n\nTemperature with source `vendor_text` and ref `bath.py:8`.\n\nAction is between -100 and 100."
        self.assertEqual(facts_limits.compare_limits(text, reference()), [])

    def test_only_step_action_bounds_are_compared(self):
        doc = {"actions": [{"cap_id": "cap.world.reset.v1", "inputs": [
            {"name": "action.field", "limit": {"ref": "wrong.py:1"}}]},
            {"cap_id": "cap.world.step.v1", "inputs": [
                {"name": "ticks", "limit": {"ref": "ticks.py:1"}}]}]}
        self.assertEqual(facts_limits.compare_limits("Limits: action ref `env.py:25`.", doc), [])

    def test_missing_malformed_reference_is_owned_by_gate(self):
        for doc in (None, [], {}, {"actions": None}, {"actions": [None]},
                    {"actions": [{"cap_id": "cap.world.step.v1", "inputs": None}]}):
            with self.subTest(doc=doc):
                self.assertEqual(facts_limits.compare_limits("Limits: action ref `old.py:1`.", doc), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(facts_limits.facts_limits_notes(path), [])
            (path / "facts.md").write_text("Limits: action ref `old.py:1`.")
            (path / "reference.json").write_text("{bad json")
            self.assertEqual(facts_limits.facts_limits_notes(path), [])

    def test_collect_strict_keeps_advisory_separate_from_citation_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "MHS/drivers/robots/acme__env"
            package.mkdir(parents=True)
            (package / "task.json").write_text(json.dumps({"package_id": "gh.acme/env"}))
            (package / "RESULT.json").write_text(json.dumps({"status": "pass", "gate": {"digest": "sha256:stable"}}))
            (package / "driver.lock.json").write_text(json.dumps({"reviewed_by": None}))
            (package / "facts.md").write_text("Limits: action ref `stale.py:1`.")
            (package / "reference.json").write_text(json.dumps(reference()))
            gate_report = {"passed": True, "failed": [], "gates": []}
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(collect, "run_gate", return_value={"exit_code": 0, "report": gate_report, "stderr": ""}))
                stack.enter_context(patch.object(collect, "stable_digest_of", return_value="sha256:stable"))
                stack.enter_context(patch.object(collect, "schema_problems", return_value=[]))
                stack.enter_context(patch.object(collect, "residue", return_value=[]))
                stack.enter_context(patch.object(collect, "driver_base", return_value=None))
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = collect.main(["--root", str(root), "--strict", str(package)])
                self.assertEqual(code, 0, out.getvalue())
                self.assertIn("note: FACTS_LIMITS_REVIEW", out.getvalue())
                gate_report["gates"] = [{"findings": [{"code": "G4.REF_VALUE", "path": "action.field0", "ref": "env.py:25"}]}]
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = collect.main(["--root", str(root), "--strict", str(package)])
                self.assertEqual(code, 1, out.getvalue())
                self.assertIn("warning: UNSOURCED_LIMIT_GATE_WARNING", out.getvalue())
                row = collect.summarise(root, package)
                self.assertEqual(row["accepted_by_reviewer"], [])
                self.assertEqual(len(row["warnings"]), 1)
                self.assertEqual(len(row["notes"]), 1)


if __name__ == "__main__":
    unittest.main()
