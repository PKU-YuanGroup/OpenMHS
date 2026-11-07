"""Lock companions (DESIGN-2 of the companion preflight, 2026-11-05): a companion entry may name ``lock``, the alias of a
clone fetched at one pinned commit under ``work/companions/`` and listed in its ``LOCK.json``.

Covered: ``companion_sources`` for lock entries (alias, ref, the ``work/companions/<owner>__<repo>@<commit12>`` local
path, ``companions_root``), ``read_companion_lock`` and ``lock_entry_problems``; gate G1 on a real package with a
temporary ``work/companions`` (a tiny git repository and its LOCK.json): the passing case, COMPANION_LOCK (LOCK.json
missing, alias absent, commit, path, profile or ref differing, repo_url naming another repository, the package not in
needed_by), COMPANION_HEAD, COMPANION_MODIFIED for an untracked file, COMPANION_WRITTEN for one created during the run,
COMPANION_WRITABLE, NO_COMPANION_CLONE, and ``--companions-root`` pointing at the clones elsewhere; G2 (the lock
repeats the ``lock`` alias); the scaffold's lock; the gate child's ``--companions-root`` option; and that a corpus
companion beside a lock companion keeps its rules (an untracked file there is not an error).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import unittest
from pathlib import Path

from mhs.driver import _gate
from mhs.driver.check import _COMPANIONS_ENV, Gate, _Context, _g1_after
from mhs.driver.package import scaffold
from mhs.driver.upstream import (CompanionSource, companion_sources, lock_entry_problems, lock_package_id,
                                 read_companion_lock)

from tests.driver import gate_support as gs
from tests.driver import test_companion_sources as base

PACKAGE_ID = "gh.acme/th1"


def read_only(tree: Path) -> None:
    """``chmod -R a-w`` of a work tree, ``.git`` left writable (as the authorised fetch left work/companions)."""
    for directory, dirs, names in os.walk(tree, topdown=False):
        if Path(directory).relative_to(tree).parts[:1] == (".git",):
            continue
        for name in names + dirs:
            full = os.path.join(directory, name)
            if Path(directory) == tree and name == ".git":
                continue
            os.chmod(full, stat.S_IMODE(os.lstat(full).st_mode) & ~0o222)
    os.chmod(tree, stat.S_IMODE(os.lstat(tree).st_mode) & ~0o222)


def writable(tree: Path) -> None:
    """Undo :func:`read_only` (the test's own clean-up of its temporary clone)."""
    for directory, dirs, names in os.walk(tree):
        os.chmod(directory, stat.S_IMODE(os.lstat(directory).st_mode) | 0o200)
        for name in names:
            full = os.path.join(directory, name)
            if not os.path.islink(full):
                os.chmod(full, stat.S_IMODE(os.lstat(full).st_mode) | 0o200)


def lock_companion(test: unittest.TestCase, root: Path, *, needed_by=(PACKAGE_ID,)) -> tuple[Path, str, dict]:
    """A fetched companion ``root/work/companions/acme__sim@<commit12>`` (read-only) and its LOCK.json entry."""
    staging, commit = base.companion_repo(test, root, rel="staging/sim")
    companions = root / "work" / "companions"
    companions.mkdir(parents=True, exist_ok=True)
    clone = companions / f"acme__sim@{commit[:12]}"
    staging.rename(clone)
    read_only(clone)
    test.addCleanup(lambda: writable(clone) if clone.exists() else None)
    entry = {"alias": "acme__sim@v1.0", "repo_url": "https://github.com/acme/sim.git", "ref": "v1.0",
             "ref_type": "tag", "commit": commit, "path": f"work/companions/acme__sim@{commit[:12]}",
             "licence": "Apache-2.0", "profile": "ros1-noetic-gazebo11", "needed_by": list(needed_by)}
    write_lock(companions, [entry])
    return clone, commit, entry


def write_lock(companions: Path, entries: list[dict]) -> None:
    (companions / "LOCK.json").write_text(json.dumps({"clones": entries}, indent=1) + "\n")


def lock_card_entry(commit: str, **changes) -> dict:
    entry = base.card_entry(commit, rel=f"work/companions/acme__sim@{commit[:12]}")
    entry.pop("local_path")
    entry.pop("repo_url")
    entry.pop("license_spdx")
    entry.update({"lock": "acme__sim@v1.0", "ref": "v1.0", "local_path": f"work/companions/acme__sim@{commit[:12]}",
                  "repo_url": "https://github.com/acme/sim.git", "license_spdx": "Apache-2.0"})
    entry.update(changes)
    return entry


class LockSourceTests(unittest.TestCase):
    def test_a_lock_entry_resolves_under_work_companions(self) -> None:
        good = lock_card_entry("a" * 40)
        sources, problems = companion_sources({"package_id": PACKAGE_ID, "companions": [good]}, Path("/nowhere"))
        self.assertEqual(problems, [])
        source = sources[base.ALIAS]
        self.assertEqual((source.lock, source.ref), ("acme__sim@v1.0", "v1.0"))
        self.assertEqual(source.lock_root, Path("/nowhere/work/companions"))
        self.assertEqual(source.path, Path("/nowhere/work/companions/acme__sim@aaaaaaaaaaaa"))
        moved, _ = companion_sources({"package_id": PACKAGE_ID, "companions": [good]}, Path("/nowhere"),
                                     Path("/elsewhere"))
        self.assertEqual((moved[base.ALIAS].lock_root, moved[base.ALIAS].path),
                         (Path("/elsewhere"), Path("/elsewhere/acme__sim@aaaaaaaaaaaa")))

    def test_bad_lock_entries_are_refused(self) -> None:
        good = lock_card_entry("a" * 40)
        cases = {"lock": dict(good, lock="sim@v1.0"), "ref": dict(good, ref="v2.0"),
                 "local_path (work": dict(good, local_path="work/companions/acme__sim@bbbbbbbbbbbb"),
                 "local_path (work/": dict(good, local_path="robots/acme/sim")}
        for expected, entry in cases.items():
            with self.subTest(expected=expected):
                found, problems = companion_sources({"package_id": PACKAGE_ID, "companions": [entry]}, None)
                self.assertEqual(found, {})
                self.assertIn(expected, problems[0])
        corpus = base.card_entry("a" * 40, rel="work/companions/acme__sim@aaaaaaaaaaaa")
        _found, problems = companion_sources({"package_id": PACKAGE_ID, "companions": [corpus]}, None)
        self.assertIn("local_path", problems[0])  # a corpus entry never reads work/companions

    def test_read_companion_lock(self) -> None:
        root = gs.temp_root(self)
        self.assertIn("does not exist", read_companion_lock(root)[1])
        (root / "LOCK.json").write_text("{")
        self.assertIn("cannot be read", read_companion_lock(root)[1])
        (root / "LOCK.json").write_text(json.dumps({"clones": [{"alias": "a__b@1"}, {"alias": "a__b@1"}]}))
        self.assertIn("listed twice", read_companion_lock(root)[1])
        (root / "LOCK.json").write_text(json.dumps({"clones": [{"alias": 3}]}))
        self.assertIn("clones must be", read_companion_lock(root)[1])
        (root / "LOCK.json").write_text(json.dumps({"clones": [{"alias": "a__b@1"}]}))
        self.assertEqual(read_companion_lock(root), ({"a__b@1": {"alias": "a__b@1"}}, None))
        self.assertIsNone(read_companion_lock(None)[0])

    def test_lock_entry_problems_compare_every_pinned_field(self) -> None:
        commit = "c" * 40
        source = CompanionSource(base.ALIAS, "gh.acme/sim", commit, "ros1-noetic-gazebo11",
                                 f"work/companions/acme__sim@{commit[:12]}", None, None, lock="acme__sim@v1.0",
                                 ref="v1.0")
        entry = {"alias": "acme__sim@v1.0", "repo_url": "https://github.com/acme/sim.git", "ref": "v1.0",
                 "commit": commit, "path": f"work/companions/acme__sim@{commit[:12]}",
                 "profile": "ros1-noetic-gazebo11", "needed_by": [PACKAGE_ID]}
        self.assertEqual(lock_entry_problems(source, entry, PACKAGE_ID), [])
        for key, value in (("commit", "d" * 40), ("path", "work/companions/x__y@cccccccccccc"),
                           ("profile", "ros1-kinetic-gazebo7"), ("ref", "v2.0"),
                           ("repo_url", "https://github.com/acme/other"), ("needed_by", ["gh.acme/other"])):
            with self.subTest(key=key):
                problems = lock_entry_problems(source, dict(entry, **{key: value}), PACKAGE_ID)
                self.assertEqual(len(problems), 1, problems)
        self.assertIn("no entry", lock_entry_problems(source, None, PACKAGE_ID)[0])
        # Integrator edit I3 (Claude Sonnet safety F3 of p3-companion-2): needed_by is the scope the fetch was
        # authorised for; a missing value or one that is not a list is refused, also the package id as a bare string,
        # which a substring test would wrongly accept.
        scopeless = {key: value for key, value in entry.items() if key != "needed_by"}
        for name, bad in (("missing", scopeless), ("the id as a string", dict(entry, needed_by=PACKAGE_ID)),
                          ("an object", dict(entry, needed_by={PACKAGE_ID: True})), ("null", dict(entry, needed_by=None)),
                          ("a number", dict(entry, needed_by=1)), ("an empty string", dict(entry, needed_by=""))):
            with self.subTest(needed_by=name):
                problems = lock_entry_problems(source, bad, PACKAGE_ID)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("needed_by", problems[0])
        self.assertEqual(lock_package_id("https://github.com/AndrejOrsula/ign_ros2_control.git"),
                         "gh.andrejorsula/ign_ros2_control")
        self.assertIsNone(lock_package_id("https://gitlab.com/acme/sim"))


class LockGateTests(unittest.TestCase):
    """G1 and G2 on a real package whose card declares a fetched (lock) companion."""

    def setUp(self) -> None:
        self.root, self.dir = gs.real_package(self)
        clone = self.root / "labs" / "acme" / "th1"
        (clone / "README.md").write_text(base.PACKAGE_README)
        gs.git(clone, "init", "-q")
        gs.git(clone, "add", "-A")
        gs.git(clone, "commit", "-q", "-m", "TH-1")
        gs.pin(self.dir, gs.git(clone, "rev-parse", "HEAD"))
        self.companion, self.commit, self.entry = lock_companion(self, self.root)
        self.companions = self.root / "work" / "companions"
        self.declare([lock_card_entry(self.commit)])

    def declare(self, entries, *, lock=None) -> None:
        card = json.loads((self.dir / "task.json").read_text())
        card["companions"] = entries
        base.write_card(self.root, self.dir, card)
        gs.edit_json(self.dir, "driver.lock.json", companions=lock if lock is not None else [
            {"package_id": item["package_id"], "commit": item["commit"],
             **({"lock": item["lock"]} if "lock" in item else {})} for item in entries])

    def relock(self, **changes) -> None:
        write_lock(self.companions, [dict(self.entry, **changes)])

    def run_gates(self, gates=("G1", "G2", "G4"), **options):
        return gs.check(self.dir, gates=list(gates), root=self.root, **options)

    def lock_findings(self, **options) -> list[str]:
        return gs.findings(self.run_gates(["G1"], **options), "G1")

    def test_a_lock_companion_and_a_fact_citing_it_pass(self) -> None:
        gs.edit(self.dir, "driver.py", "    facts = [\n",
                f"    facts = [\n        Fact('The companion pauses the world', source='upstream_code', "
                f"ref='companion:{base.ALIAS}/src/api.cpp:11'),\n")
        gs.regenerate(self.dir)
        report = self.run_gates()
        for gate in ("G1", "G2", "G4"):
            self.assertEqual(gs.findings(report, gate, severity=None), [], (gate, report))

    def test_lock_json_missing_or_without_the_alias(self) -> None:
        (self.companions / "LOCK.json").rename(self.root / "LOCK.json.aside")
        self.assertIn("G1.COMPANION_LOCK", self.lock_findings())
        write_lock(self.companions, [dict(self.entry, alias="acme__sim@v2.0")])
        self.assertIn("G1.COMPANION_LOCK", self.lock_findings())

    def test_every_pinned_lock_field_must_repeat_the_card(self) -> None:
        for key, value in (("commit", "e" * 40), ("path", "work/companions/acme__sim@eeeeeeeeeeee"),
                           ("profile", "ros1-kinetic-gazebo7"), ("ref", "v1.1"),
                           ("repo_url", "https://github.com/acme/other.git"), ("needed_by", ["gh.acme/other"])):
            with self.subTest(key=key):
                self.relock(**{key: value})
                findings = self.lock_findings()
                self.assertEqual(findings.count("G1.COMPANION_LOCK"), 1, findings)
        self.relock()
        self.assertEqual(self.lock_findings(), [])

    def test_needed_by_missing_or_not_a_list_is_refused(self) -> None:
        # Integrator edit I3 (Claude Sonnet safety F3 of p3-companion-2): G1 refuses a LOCK.json entry whose needed_by
        # is missing or is not a list, the package id as a bare string included.
        write_lock(self.companions, [{key: value for key, value in self.entry.items() if key != "needed_by"}])
        self.assertEqual(self.lock_findings().count("G1.COMPANION_LOCK"), 1)
        for value in (PACKAGE_ID, {PACKAGE_ID: True}, None, 1):
            with self.subTest(needed_by=value):
                self.relock(needed_by=value)
                self.assertEqual(self.lock_findings().count("G1.COMPANION_LOCK"), 1)
        self.relock()
        self.assertEqual(self.lock_findings(), [])

    def test_head_away_from_the_pin(self) -> None:
        writable(self.companion)
        (self.companion / "NEW.txt").write_text("later\n")
        gs.git(self.companion, "add", "-A")
        gs.git(self.companion, "commit", "-q", "-m", "later")
        read_only(self.companion)
        self.assertIn("G1.COMPANION_HEAD", self.lock_findings())

    def test_an_untracked_file_is_a_modification_of_a_lock_companion(self) -> None:
        os.chmod(self.companion, 0o755)
        (self.companion / "untracked.txt").write_text("x\n")
        os.chmod(self.companion / "untracked.txt", 0o444)
        os.chmod(self.companion, 0o555)
        findings = self.lock_findings()
        self.assertIn("G1.COMPANION_MODIFIED", findings)
        self.assertNotIn("G1.COMPANION_WRITABLE", findings)

    def test_an_untracked_file_created_during_the_run(self) -> None:
        ctx = _Context(self.dir, "fake", self.root, None, False)
        self.addCleanup(ctx.close)
        os.chmod(self.companion, 0o755)
        (self.companion / "during.txt").write_text("x\n")
        gate = Gate("G1", "Layout and isolation")
        _g1_after(ctx, gate)
        self.assertIn("G1.COMPANION_WRITTEN", [finding.code for finding in gate.findings])

    def test_a_write_bit_anywhere_in_the_work_tree(self) -> None:
        target = self.companion / "src" / "api.cpp"
        os.chmod(target, 0o644)
        findings = self.lock_findings()
        self.assertIn("G1.COMPANION_WRITABLE", findings)
        os.chmod(target, 0o444)
        os.chmod(self.companion / "src", 0o755)
        self.assertIn("G1.COMPANION_WRITABLE", self.lock_findings())
        os.chmod(self.companion / "src", 0o555)
        self.assertEqual(self.lock_findings(), [])

    def test_a_missing_clone(self) -> None:
        writable(self.companion)
        self.companion.rename(self.root / "aside")
        self.addCleanup(lambda: writable(self.root / "aside"))
        findings = self.lock_findings()
        self.assertIn("G1.NO_COMPANION_CLONE", findings)

    def test_companions_root_points_the_gate_at_clones_elsewhere(self) -> None:
        elsewhere = self.root / "fetched"
        writable(self.companion)
        self.companions.rename(elsewhere)
        read_only(elsewhere / self.companion.name)
        self.addCleanup(lambda: writable(elsewhere / self.companion.name))
        missing = self.lock_findings()
        self.assertIn("G1.NO_COMPANION_CLONE", missing)
        self.assertIn("G1.COMPANION_LOCK", missing)
        self.assertEqual(self.lock_findings(companions_root=elsewhere), [])

    def test_the_lock_repeats_the_lock_alias(self) -> None:
        self.declare([lock_card_entry(self.commit)],
                     lock=[{"package_id": "gh.acme/sim", "commit": self.commit}])
        self.assertIn("G2.COMPANION_MISMATCH", gs.findings(self.run_gates(["G2"]), "G2"))

    def test_a_corpus_companion_beside_a_lock_companion_keeps_its_rules(self) -> None:
        corpus, commit = base.companion_repo(self, self.root, rel="robots/acme/other")
        other = base.card_entry(commit, alias="other_sim", rel="robots/acme/other")
        other["package_id"] = "gh.acme/other"
        self.declare([lock_card_entry(self.commit), other])
        (corpus / "untracked.txt").write_text("not an error for a corpus clone\n")
        self.assertEqual(self.lock_findings(), [])


class LockToolingTests(unittest.TestCase):
    def test_new_copies_the_lock_alias_into_the_lock(self) -> None:
        root = gs.temp_root(self)
        card = json.loads((gs.TUTORIAL / "task.json").read_text())
        card["companions"] = [lock_card_entry("c" * 40)]
        (root / "card.json").write_text(json.dumps(card))
        scaffold(root / "pkg", card=root / "card.json", kind="ros")
        lock = json.loads((root / "pkg" / "driver.lock.json").read_text())
        self.assertEqual(lock["companions"], [{"package_id": "gh.acme/sim", "commit": "c" * 40,
                                               "lock": "acme__sim@v1.0"}])

    def test_the_gate_child_takes_companions_root(self) -> None:
        options = _gate._parse(["--result", "r", "--progress", "p", "--companions-root", "/x", "pkg"])
        self.assertEqual((options["companions_root"], options["directory"]), ("/x", "pkg"))
        self.assertIsNone(_gate._parse(["--result", "r", "--progress", "p", "pkg"])["companions_root"])
        self.assertEqual(_COMPANIONS_ENV, "MHS_DRIVER_GATE_COMPANIONS")


if __name__ == "__main__":
    unittest.main()
