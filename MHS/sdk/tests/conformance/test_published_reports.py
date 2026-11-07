"""Published reference reports are current, honestly named and reproducible (WP-07 milestone 07b).

``MHS/conformance/reports/<subject>-<level>.json`` is named after its
``level_achieved``; the reports that stay under ``MHS/sdk/docs/reports`` (the
seeded arm and the replay endpoint, which the reference endpoints cite) are
regenerated with the current suite; the byte-identical copies that used to
live there are archived under ``_archive/sdk-docs-reports/`` (moved, never
deleted).  Every report re-runs in-process to the same verdicts
(``python -m mhs.conformance verify``).
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import unittest
from pathlib import Path

from mhs.conformance import SUITE_VERSION, validate_report
from mhs.conformance.__main__ import main as conformance_main
from mhs.conformance.inprocess import reference_factory, run_suite_inprocess
from mhs.conformance.report import compare_reports, recompute_level

ROOT = Path(__file__).resolve().parents[4]
REPORTS = ROOT / "MHS" / "conformance" / "reports"
DOCS_REPORTS = ROOT / "MHS" / "sdk" / "docs" / "reports"
ARCHIVE = ROOT / "_archive" / "sdk-docs-reports"
BUNDLE = DOCS_REPORTS / "replay-bundle-conveyor.json"



def _published(subject: str) -> Path:
    """The one ``<subject>-cl<N>.json`` report (its level is in its name; WP-06 06c renamed lab and arm)."""
    found = sorted(REPORTS.glob(f"{subject}-cl[0-4].json"))
    return found[0] if len(found) == 1 else REPORTS / f"{subject}-cl?.json"


#: Published report -> the in-process reference target that reproduces it.
TARGETS = {
    REPORTS / "conveyor-cl4.json": ("conveyor", {}),
    _published("lab"): ("lab", {}),
    _published("arm"): ("arm", {}),
    DOCS_REPORTS / "conformance-arm-2dof-seeded.json": ("arm", {"noise": True}),
    DOCS_REPORTS / "conformance-replay-recorded.json": ("replay", {"bundle": str(BUNDLE)}),
}
#: Byte-identical duplicates moved out of MHS/sdk/docs/reports in 07b.
ARCHIVED = ("conformance-conveyor-workcell.json", "conformance-lab.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = conformance_main(list(argv))
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, out.getvalue()


class PublishedReportFileTests(unittest.TestCase):
    def test_every_published_report_is_listed(self):
        published = sorted(REPORTS.glob("*.json")) + sorted(DOCS_REPORTS.glob("conformance-*.json"))
        self.assertEqual(sorted(published), sorted(TARGETS))

    def test_file_names_match_level_achieved(self):
        for path in sorted(REPORTS.glob("*.json")):
            with self.subTest(report=path.name):
                match = re.fullmatch(r"([a-z0-9-]+)-(cl[0-4])\.json", path.name)
                self.assertIsNotNone(match, path.name)
                self.assertEqual(match.group(2), _load(path)["level_achieved"].lower(), path.name)

    def test_reports_are_current_valid_and_disclaimed(self):
        for path in TARGETS:
            with self.subTest(report=path.name):
                report = _load(path)
                self.assertEqual(report["suite_version"], SUITE_VERSION)
                self.assertEqual(validate_report(report), [])
                self.assertEqual(recompute_level(report), report["level_achieved"])
                ids = {item["id"] for item in report["disclaimers"]}
                self.assertTrue({"not_certified", "not_affiliated", "simulation_only", "self_issued"} <= ids, ids)
                self.assertTrue(report["subject"]["manifest_digest"].startswith("sha256:"))
                self.assertTrue(all("required" in case and case.get("spec_ref") for case in report["tests"]))

    def test_duplicates_were_moved_to_the_archive(self):
        published = {path.read_bytes() for path in REPORTS.glob("*.json")}
        for path in DOCS_REPORTS.glob("*.json"):
            self.assertNotIn(path.read_bytes(), published, path.name)
        for name in ARCHIVED:
            with self.subTest(archived=name):
                self.assertFalse((DOCS_REPORTS / name).exists(), name)
                if ARCHIVE.is_dir():  # the archive is private research material: absent from the open-source tree
                    self.assertTrue((ARCHIVE / name).is_file(), name)
        self.assertTrue(BUNDLE.is_file())


class ReproducibilityTests(unittest.TestCase):
    def test_published_reports_reproduce_in_process(self):
        for path, (name, options) in TARGETS.items():
            with self.subTest(report=path.name):
                report = _load(path)
                rerun = run_suite_inprocess(reference_factory(name, **options), profile=report["profile"],
                                            level=report["level_claimed"])
                mismatches, _notes = compare_reports(report, rerun)
                self.assertEqual(mismatches, [], path.name)

    def test_cli_targets_the_seeded_arm_and_the_replay_endpoint(self):
        code, output = run_cli("verify", str(DOCS_REPORTS / "conformance-arm-2dof-seeded.json"),
                               "--reference", "arm", "--noise")
        self.assertEqual(code, 0, output)
        code, output = run_cli("verify", str(DOCS_REPORTS / "conformance-replay-recorded.json"),
                               "--reference", "replay", "--bundle", str(BUNDLE))
        self.assertEqual(code, 0, output)
        code, output = run_cli("--reference", "replay", "--level", "CL1")
        self.assertEqual(code, 2, output)  # the replay endpoint needs --bundle


if __name__ == "__main__":
    unittest.main()
