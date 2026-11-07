"""tools/spec_doctest.py: the specification's runnable blocks run, its identifiers lint clean (WP-09 (8)).

The positive tests run the tool over the real ``MHS/spec``; the negative tests run it over small temporary
specification directories to show that each lint really fails when it should.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "MHS" / "sdk" / "tools" / "spec_doctest.py"
SPEC = ROOT / "MHS" / "spec"


def _load_tool():
    spec = importlib.util.spec_from_file_location("spec_doctest_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_doctest_under_test"] = module
    spec.loader.exec_module(module)
    return module


tool = _load_tool()


def make_spec(files: dict[str, str], errors: list[str] | None = None) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="specdoctest-"))
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    if errors is not None:
        (directory / "errors.json").write_text(
            json.dumps({"errors": [{"code": code} for code in errors]}), encoding="utf-8")
    return directory


class RealSpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = tool.run(SPEC)

    def test_every_runnable_block_runs_and_every_lint_is_clean(self) -> None:
        self.assertEqual(self.report.errors, [], "\n".join(self.report.errors))

    def test_the_documents_that_promise_runnable_examples_have_them(self) -> None:
        by_file: dict[str, int] = {}
        for path in tool.spec_files(SPEC):
            by_file[path.name] = sum(1 for block in tool.extract_blocks(path.read_text(encoding="utf-8"), path.name)
                                     if block.runnable)
        for name in ("core.md", "driver-profile.md", "00-architecture.md", "09-host-profile.md"):
            self.assertGreaterEqual(by_file.get(name, 0), 1, name)
        self.assertGreaterEqual(by_file.get("appendix-c-examples.md", 0), 5)
        self.assertGreaterEqual(self.report.runnable, 9)

    def test_schema_valid_examples_are_validated(self) -> None:
        self.assertGreaterEqual(self.report.validated, 5)

    def test_command_line_exits_zero_and_prints_a_summary(self) -> None:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT / "MHS" / "sdk" / "src"))
        result = subprocess.run([sys.executable, str(TOOL), "MHS/spec"], cwd=str(ROOT), env=env,
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("spec doctest ok", result.stdout)

    def test_the_catalogue_section_equals_the_rendering_of_capabilities_json(self) -> None:
        report = tool.Report()
        tool.check_catalogue(SPEC, report)
        self.assertEqual(report.errors, [])

    def test_the_informative_documents_use_no_rfc_2119_keyword(self) -> None:
        for name in tool.INFORMATIVE:
            for number, line in enumerate((SPEC / name).read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(tool.KEYWORDS.search(line), f"{name}:{number}: {line[:80]}")

    def test_core_and_driver_profile_ids_are_defined_once_in_their_own_document(self) -> None:
        core = (SPEC / "core.md").read_text(encoding="utf-8")
        driver = (SPEC / "driver-profile.md").read_text(encoding="utf-8")
        core_ids = [m.group("id") for m in map(tool.DEFINITION.match, core.splitlines()) if m]
        driver_ids = [m.group("id") for m in map(tool.DEFINITION.match, driver.splitlines()) if m]
        self.assertTrue(core_ids and all(i.startswith("CORE-") for i in core_ids))
        self.assertTrue(driver_ids and all(i.startswith("DRV-") for i in driver_ids))
        self.assertEqual(len(core_ids), len(set(core_ids)))
        self.assertEqual(len(driver_ids), len(set(driver_ids)))
        self.assertLessEqual(len(core.splitlines()), 900, "core.md is the short normative core")

    def test_core_ids_are_invisible_to_the_applicability_tool(self) -> None:
        """The inventory tool counts ``**AREA-NNN.**`` paragraphs; CORE and DRV ids use ``:`` and are not counted."""

        document = json.loads((ROOT / "MHS/sdk/src/mhs/conformance/applicability.json").read_text(encoding="utf-8"))
        self.assertFalse([key for key in document["requirements"] if key.startswith(("CORE-", "DRV-"))])
        self.assertEqual(document["nonconforming_ids"], [])
        self.assertEqual(document["duplicate_locations"], [])


class LintTests(unittest.TestCase):
    def test_an_id_defined_twice_is_reported(self) -> None:
        directory = make_spec({"a.md": "**SAFE-001.** First.\n", "b.md": "**SAFE-001.** Second.\n"})
        report = tool.run(directory, execute=False)
        self.assertTrue(any("SAFE-001 is defined 2 times" in message for message in report.errors), report.errors)

    def test_an_orphan_reference_is_reported(self) -> None:
        directory = make_spec({"a.md": "**SAFE-001.** See SAFE-099 and CORE-007.\n"})
        report = tool.run(directory, execute=False)
        orphans = [message for message in report.errors if "orphan" in message]
        self.assertEqual(len(orphans), 2, report.errors)

    def test_a_summary_line_is_a_reference_not_a_definition(self) -> None:
        directory = make_spec({"a.md": "**GOV-001.** Real.\n\n**GOV-001** summary line.\n"})
        report = tool.run(directory, execute=False)
        self.assertEqual(report.errors, [])

    def test_colon_definitions_count_for_core_and_driver_ids(self) -> None:
        directory = make_spec({"core.md": "**CORE-001:** A rule.\n\nSee CORE-001 and DRV-001.\n",
                               "driver-profile.md": "**DRV-001:** A driver rule.\n"})
        self.assertEqual(tool.run(directory, execute=False).errors, [])

    def test_test_ids_with_a_t_prefix_are_not_requirement_ids(self) -> None:
        directory = make_spec({"a.md": "The group test TCAP-003 and TSAFE-001 are not requirement ids.\n"})
        self.assertEqual(tool.run(directory, execute=False).errors, [])

    def test_informative_documents_must_not_use_keywords(self) -> None:
        directory = make_spec({"00-architecture.md": "The endpoint MUST do this.\n"})
        report = tool.run(directory, execute=False)
        self.assertTrue(any("00-architecture.md:1" in message and "MUST" in message for message in report.errors),
                        report.errors)

    def test_normative_documents_may_use_keywords(self) -> None:
        directory = make_spec({"core.md": "**CORE-001:** The core MUST do this.\n"})
        self.assertEqual(tool.run(directory, execute=False).errors, [])

    def test_legacy_identifiers_are_reported_and_the_domain_only_in_appendix_d(self) -> None:
        directory = make_spec({"a.md": "Edited by MHS Editors, MHS-1.0 Draft 1.0 on modelhardwarestandard.com.\n",
                               "appendix-d-anthropic-mhs.md": "Cited: https://modelhardwarestandard.com/\n"})
        messages = "\n".join(tool.run(directory, execute=False).errors)
        for legacy in ("MHS Editors", "MHS-1.0", "Draft 1.0", "legacy domain"):
            self.assertIn(legacy, messages)
        self.assertNotIn("appendix-d-anthropic-mhs.md", messages)

    def test_an_unregistered_error_code_in_the_core_is_reported(self) -> None:
        directory = make_spec({"core.md": "**CORE-001:** Refuse with `MHS.SAFETY.ENVELOPE_VIOLATION` or `MHS.SAFETY.MADE_UP`.\n"},
                               errors=["MHS.SAFETY.ENVELOPE_VIOLATION"])
        report = tool.run(directory, execute=False)
        self.assertEqual([m for m in report.errors if "MADE_UP" in m].__len__(), 1, report.errors)
        self.assertFalse([m for m in report.errors if "ENVELOPE_VIOLATION" in m])

    def test_a_broken_link_and_a_missing_anchor_are_reported(self) -> None:
        directory = make_spec({"a.md": "# A\n\n## Real heading\n\nSee [gone](missing.md), [bad](b.md#nope), "
                                       "[good](b.md#section-one) and [self](#real-heading).\n",
                               "b.md": "# B\n\n## Section one\n"})
        messages = "\n".join(tool.run(directory, execute=False).errors)
        self.assertIn("missing.md", messages)
        self.assertIn("#nope", messages)
        self.assertNotIn("section-one", messages)
        self.assertNotIn("real-heading", messages)


class RunnableBlockTests(unittest.TestCase):
    def test_a_passing_and_a_failing_block(self) -> None:
        good = "```python\n# runnable\nassert 1 + 1 == 2\n```\n"
        bad = "```python\n# runnable\nassert 1 + 1 == 3, 'arithmetic'\n```\n"
        self.assertEqual(tool.run(make_spec({"a.md": good}), execute=True).errors, [])
        report = tool.run(make_spec({"a.md": bad}), execute=True)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("a.md:1", report.errors[0])
        self.assertIn("arithmetic", report.errors[0])

    def test_blocks_without_the_marker_are_not_run(self) -> None:
        report = tool.run(make_spec({"a.md": "```python\nraise RuntimeError('not run')\n```\n"}), execute=True)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.runnable, 0)

    def test_the_info_string_marker_is_read_and_each_block_has_a_fresh_namespace(self) -> None:
        self.assertTrue(tool.extract_blocks("```python runnable\nvalue = 1\n```\n")[0].runnable)
        text = "```python\n# runnable\nvalue = 1\n```\n\n```python\n# runnable\nassert 'value' not in globals()\n```\n"
        self.assertEqual(tool.run(make_spec({"a.md": text}), execute=True).errors, [])

    def test_a_block_that_exits_or_times_out_is_a_failure_not_a_crash(self) -> None:
        exits = tool.run(make_spec({"a.md": "```python\n# runnable\nraise SystemExit(3)\n```\n"}), execute=True)
        self.assertEqual(len(exits.errors), 1)
        hangs = tool.run_block(tool.extract_blocks("```python\n# runnable\nimport time\ntime.sleep(5)\n```\n")[0], timeout_s=0.3)
        self.assertIsNotNone(hangs)
        self.assertIn("timed out", hangs)

    def test_indented_fences_in_list_items_are_found(self) -> None:
        text = "1. Step\n\n   ```python\n   # runnable\n   assert True\n   ```\n"
        blocks = tool.extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].runnable)
        self.assertEqual(blocks[0].code, "# runnable\nassert True\n")


class JsonBlockTests(unittest.TestCase):
    def test_validate_marker_in_the_info_string_in_a_comment_and_in_the_paragraph_above(self) -> None:
        bad = json.dumps({"mhs_adapter": "1.0"})
        sentence = "The block is valid against `adapter.schema.json`:"
        # (text, errors besides the schema error): the info-string form is read, but it also fails the fence lint
        for text, extra in ((f"```json validate=adapter.schema.json\n{bad}\n```\n", 1),
                            (f"<!-- validate=adapter.schema.json -->\n```json\n{bad}\n```\n", 0),
                            (f"{sentence}\n\n```json\n{bad}\n```\n", 0),
                            (f"A list item that\nis valid against `adapter.schema.json`\nfollows:\n\n```json\n{bad}\n```\n", 0)):
            report = tool.run(make_spec({"a.md": text}), execute=False)
            schema_errors = [e for e in report.errors if "does not validate against adapter.schema.json" in e]
            self.assertEqual(len(schema_errors), 1, report.errors)
            self.assertEqual(len(report.errors), 1 + extra, report.errors)
        linked = "It is valid against [`adapter.schema.json`](../schema/adapter.schema.json):"
        self.assertEqual(tool.extract_blocks(f"{linked}\n\n```json\n{bad}\n```\n")[0].schema, "adapter.schema.json")

    def test_the_paragraph_hint_needs_the_sentence_and_a_json_block(self) -> None:
        bad = json.dumps({"mhs_adapter": "1.0"})
        sentence = "The block is valid against `adapter.schema.json`:"
        cases = {
            "no sentence": f"Some text.\n\n```json\n{bad}\n```\n",
            "another paragraph in between": f"{sentence}\n\nOther text.\n\n```json\n{bad}\n```\n",
            "not a json block": f"{sentence}\n\n```python\nprint(1)\n```\n",
        }
        for label, text in cases.items():
            report = tool.run(make_spec({"a.md": text}), execute=False)
            self.assertEqual(report.validated, 0, label)
            self.assertEqual(report.errors, [], label)

    def test_a_fence_info_string_of_several_words_is_reported(self) -> None:
        report = tool.run(make_spec({"a.md": "```json some words\n{}\n```\n\n```json\n{}\n```\n"}), execute=False)
        fence = [e for e in report.errors if "single token" in e]
        self.assertEqual(len(fence), 1, report.errors)
        self.assertIn("a.md:1", fence[0])

    def test_unparseable_json_is_a_warning_unless_abridged(self) -> None:
        plain = tool.run(make_spec({"a.md": "```json\n{not json}\n```\n"}), execute=False)
        abridged = tool.run(make_spec({"a.md": "```json\n{\"a\": …}\n```\n"}), execute=False)
        self.assertEqual(len([w for w in plain.warnings if "does not parse" in w]), 1)
        self.assertEqual([w for w in abridged.warnings if "does not parse" in w], [])
        self.assertEqual(plain.errors, [])

    def test_the_hint_does_not_change_the_fence_text_tests_cut_blocks_out_by(self) -> None:
        text = (SPEC / "06-adapters.md").read_text(encoding="utf-8")
        section = text.split("### 4.1 Shape", 1)[1]
        block = section.split("```json", 1)[1].split("```", 1)[0]
        self.assertEqual(json.loads(block)["adapter_id"], "org.example.robosuite-lift")


class CatalogueGenerationTests(unittest.TestCase):
    def test_a_drifting_section_is_detected_and_rewritten(self) -> None:
        catalogue = json.loads((SPEC / "capabilities.json").read_text(encoding="utf-8"))
        catalogue["capabilities"] = catalogue["capabilities"][:2]
        document = ("# 03\n\n## 7. Catalogue\n\n<!-- BEGIN GENERATED: catalogue (x) -->\n\nstale\n\n"
                    "<!-- END GENERATED: catalogue -->\n\ntail\n")
        directory = make_spec({"03-capability-registry.md": document})
        (directory / "capabilities.json").write_text(json.dumps(catalogue), encoding="utf-8")
        report = tool.Report()
        tool.check_catalogue(directory, report)
        self.assertEqual(len(report.errors), 1)
        self.assertTrue(tool.write_catalogue(directory))
        report = tool.Report()
        tool.check_catalogue(directory, report)
        self.assertEqual(report.errors, [])
        rewritten = (directory / "03-capability-registry.md").read_text(encoding="utf-8")
        self.assertIn("### 7.1 ", rewritten)
        self.assertTrue(rewritten.endswith("tail\n"))
        self.assertFalse(tool.write_catalogue(directory), "a second write changes nothing")

    def test_entries_carry_status_permit_and_replacement(self) -> None:
        catalogue = json.loads((SPEC / "capabilities.json").read_text(encoding="utf-8"))
        rendered = tool.render_catalogue(catalogue)
        self.assertIn("`cap.device.configure.v1`", rendered)
        deprecated = next(entry for entry in catalogue["capabilities"] if entry["status"] == "deprecated")
        self.assertIn("status `deprecated`", tool.render_catalogue_entry(deprecated))
        gated = next(entry for entry in catalogue["capabilities"] if entry.get("requires_permit"))
        self.assertIn("**requires permit**", tool.render_catalogue_entry(gated))
        self.assertEqual(rendered.count("#### `"), len(catalogue["capabilities"]))


if __name__ == "__main__":
    unittest.main()
