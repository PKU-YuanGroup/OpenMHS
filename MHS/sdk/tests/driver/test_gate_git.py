"""The gate against a real git clone pinned at a commit (G1, G2, G4, G7 read the object store, never the checkout).

Each test builds a throw-away git repository in a temporary directory from
the tutorial's synthetic SDK; nothing outside the temporary directory is
touched.  Skipped when git is not installed.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.driver import gate_support as gs

GIT = shutil.which("git")


def _case_insensitive() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "probe").touch()
        return (Path(tmp) / "PROBE").exists()


CASE_INSENSITIVE = _case_insensitive()


@unittest.skipUnless(GIT, "git is not installed")
class PinnedCloneTests(unittest.TestCase):
    def test_a_package_pinned_in_a_git_clone_passes(self) -> None:
        root, directory, _clone, commit = gs.git_package(self)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], report)
        self.assertEqual(report["upstream"]["commit"], commit)
        warnings = gs.findings(report, None, severity="warning")
        for code in ("G2.NOT_GIT", "G2.HEAD_DIFFERS", "G4.WORKTREE", "G1.CLONE_NOTE"):
            self.assertNotIn(code, warnings)

    def test_a_commit_missing_from_the_clone_fails_g2(self) -> None:
        root, directory, _clone, _commit = gs.git_package(self)
        gs.pin(directory, "b" * 40)
        report = gs.check(directory, root=root, gates=["G1", "G2", "G4"])
        self.assertIn("G2.COMMIT_ABSENT", gs.findings(report, "G2"))

    def test_g4_and_g7_read_the_pinned_commit_not_the_checkout(self) -> None:
        root, directory, clone, commit = gs.git_package(self)
        # A later upstream commit drops the cited bound and a method the fake implements; HEAD moves on.
        manual = clone / "MANUAL.md"
        manual.write_text(manual.read_text(encoding="utf-8").replace("Setpoint range: 5 to 80 Cel.",
                                                                     "Setpoint range: see the datasheet."),
                          encoding="utf-8")
        controller = clone / "thermo" / "controller.py"
        controller.write_text(controller.read_text(encoding="utf-8").replace("def heater_off(self):",
                                                                             "def heater_disable(self):"),
                              encoding="utf-8")
        gs.git(clone, "commit", "-q", "-am", "later upstream change")
        self.assertNotEqual(gs.git(clone, "rev-parse", "HEAD"), commit)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], report)
        self.assertIn("G2.HEAD_DIFFERS", gs.findings(report, "G2", severity="warning"))
        self.assertNotIn("G4.REF_VALUE", gs.findings(report, "G4", severity="warning"))
        # Pinned at the later commit instead, the same package fails G7 (heater_off is gone upstream).
        gs.pin(directory, gs.git(clone, "rev-parse", "HEAD"))
        report = gs.check(directory, root=root)
        self.assertIn("G7.NOT_UPSTREAM", gs.findings(report, "G7"))
        self.assertIn("G4.REF_VALUE", gs.findings(report, "G4", severity="warning"))

    def test_a_reference_beyond_the_pinned_file_fails_g4(self) -> None:
        root, directory, _clone, _commit = gs.git_package(self)
        gs.edit(directory, "driver.py", 'ref="thermo/controller.py:39"', 'ref="thermo/controller.py:400"')
        gs.regenerate(directory)
        report = gs.check(directory, root=root, gates=["G3", "G4"])
        self.assertIn("G4.REF_LINE", gs.findings(report, "G4"))

    def test_a_modified_clone_fails_g1(self) -> None:
        root, directory, clone, _commit = gs.git_package(self)
        with (clone / "MANUAL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nlocal edit\n")
        report = gs.check(directory, root=root, gates=["G1"])
        self.assertIn("G1.CLONE_MODIFIED", gs.findings(report, "G1"))

    @unittest.skipUnless(CASE_INSENSITIVE, "the temporary directory is on a case-sensitive file system")
    def test_tracked_paths_that_differ_only_in_case_do_not_fail_g1(self) -> None:
        # Upstream tracks meshes/terrain.STL and meshes/terrain.stl; here they share one file, which holds one content.
        root, directory, clone, _commit = gs.git_package(self)
        (clone / "meshes").mkdir()
        (clone / "meshes" / "terrain.STL").write_bytes(b"solid upper\n")
        gs.git(clone, "add", "meshes/terrain.STL")
        other = root / "terrain-lower.stl"
        other.write_bytes(b"solid lower\n")
        blob = gs.git(clone, "hash-object", "-w", str(other))
        gs.git(clone, "update-index", "--add", "--cacheinfo", f"100644,{blob},meshes/terrain.stl")
        gs.git(clone, "commit", "-q", "-m", "two paths that differ only in case")
        gs.pin(directory, gs.git(clone, "rev-parse", "HEAD"))
        self.assertTrue(gs.git(clone, "status", "--porcelain", "--untracked-files=no"))
        report = gs.check(directory, root=root, gates=["G1"])
        self.assertEqual(report["failed"], [], report)
        self.assertIn("G1.CLONE_NOTE", gs.findings(report, "G1", severity="warning"))
        # A content that is neither of the two is a modification.
        (clone / "meshes" / "terrain.STL").write_bytes(b"solid edited\n")
        report = gs.check(directory, root=root, gates=["G1"])
        self.assertIn("G1.CLONE_MODIFIED", gs.findings(report, "G1"))

    def test_a_write_to_the_clone_during_the_run_fails_g1(self) -> None:
        root, directory, clone, _commit = gs.git_package(self)
        target = clone / "MANUAL.md"
        gs.edit(directory, "fake.py", "        self.lid = True\n",
                "        self.lid = True\n"
                f"        with open({str(target)!r}, 'a', encoding='utf-8') as handle:\n"
                "            handle.write('written by the fake\\n')\n")
        report = gs.check(directory, root=root)
        self.assertIn("G1", report["failed"])
        self.assertIn("G1.CLONE_WRITTEN", gs.findings(report, "G1"))
        self.assertNotIn("G1.CLONE_MODIFIED", gs.findings(report, "G1"))

    def test_the_card_commit_is_reported(self) -> None:
        root, directory, _clone, commit = gs.git_package(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(card["upstream"]["commit"], commit)
        report = gs.check(directory, root=root, gates=["G1", "G2"])
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["upstream"], {"commit": commit, "repo_url": "https://github.com/acme/th1"})


if __name__ == "__main__":
    unittest.main()
