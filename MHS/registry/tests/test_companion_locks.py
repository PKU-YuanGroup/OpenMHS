#!/usr/bin/env python3
"""Lock companions (DESIGN-2, 2026-11-05): an override companion entry may name ``lock``, a clone fetched at one
pinned commit under ``work/companions`` and listed in ``work/companions/LOCK.json`` (the user's authorisation of
2026-11-05), instead of a corpus record.

Covered: triage's shape check (the optional ``lock``), the override and task-card schemas, the LOCK rules
(``triage.lock_problems`` through ``companion_problems``: the entry exists, its repo_url names the package_id, its
commit, profile and path repeat the override, the package is in needed_by; with the workspace, the clone and its
HEAD), the licence copied from LOCK.json (``lock_licence``), ``build_registry.attach_companions`` (local_path,
repo_url, ref and licence from LOCK.json; a corpus entry beside it unchanged), ``validate.check_companions`` with
LOCK.json and without it (``--no-corpus``: the card's shape only), ``check_overlays`` (the lock repeats ``lock``),
and the shipped ``companion-sources-lock.json`` (shape always; the LOCK rules when work/companions/LOCK.json exists).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, HERE)

import build_registry as BR  # noqa: E402
import triage as T  # noqa: E402
from test_build_pipeline import STORE  # noqa: E402
from test_companion_overrides import COMMIT, companion, override  # noqa: E402
import validate as V  # noqa: E402

PID = "gh.acme/bath"
LOCK_ALIAS = "acme__sim@v1.0"
LOCK_PATH = f"work/companions/acme__sim@{COMMIT[:12]}"


def lock_line(**extra):
    item = {"alias": LOCK_ALIAS, "repo_url": "https://github.com/acme/sim.git", "ref": "v1.0", "ref_type": "tag",
            "commit": COMMIT, "path": LOCK_PATH, "licence": "Apache-2.0", "profile": "ros1-noetic-gazebo11",
            "needed_by": [PID]}
    item.update(extra)
    return item


def lock_companion(**extra):
    item = companion(**extra)
    item.setdefault("lock", LOCK_ALIAS)
    return item


def resolved(**extra):
    item = dict(lock_companion(), ref="v1.0", local_path=LOCK_PATH, repo_url="https://github.com/acme/sim.git",
                license_spdx="Apache-2.0")
    item.update(extra)
    return item


class LockShapeTests(unittest.TestCase):
    def test_a_lock_entry_passes_triage_and_the_schema(self):
        T.check_override(override(lock_companion()))
        doc = {"overrides_version": "0.9", "title": "t", "overrides": [override(lock_companion())]}
        self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])

    def test_a_malformed_lock_is_refused_by_triage_and_the_schema(self):
        for bad in ("acme-sim", "acme__sim", "acme__sim@", "../x__y@1", 7):
            with self.subTest(lock=bad):
                with self.assertRaises(T.OverrideError):
                    T.check_override(override(companion(lock=bad)))
                doc = {"overrides_version": "0.9", "title": "t", "overrides": [override(companion(lock=bad))]}
                self.assertTrue(STORE.validate(doc, "overrides.schema.json"))

    def test_the_taskcard_schema_ties_lock_ref_and_local_path(self):
        path = os.path.join(REG, "schema", "examples", "taskcard.thermal-bath.json")
        with open(path, encoding="utf-8") as fh:
            card = json.load(fh)
        good = dict(card, companions=[resolved()])
        self.assertEqual(STORE.validate(good, "taskcard.schema.json"), [])
        noted = dict(card, companions=[resolved(license_spdx="NOASSERTION", licence_note="Apache-2.0 AND BSD (text)")])
        self.assertEqual(STORE.validate(noted, "taskcard.schema.json"), [])
        for name, item in (("no ref", {k: v for k, v in resolved().items() if k != "ref"}),
                           ("corpus path with lock", resolved(local_path="robots/acme/sim")),
                           ("lock path without lock", {k: v for k, v in resolved().items() if k not in ("lock", "ref")}),
                           ("ref without lock", dict(companion(), ref="v1.0", local_path="robots/acme/sim",
                                                     repo_url="https://github.com/acme/sim", license_spdx="MIT"))):
            with self.subTest(name=name):
                self.assertTrue(STORE.validate(dict(card, companions=[item]), "taskcard.schema.json"))

    def test_lock_licence(self):
        self.assertEqual(T.lock_licence("Apache-2.0"), ("Apache-2.0", None))
        self.assertEqual(T.lock_licence("Apache-2.0 AND BSD-3-Clause"), ("Apache-2.0 AND BSD-3-Clause", None))
        text = "Apache-2.0 AND BSD (per package.xml; no licence file in the repository)"
        self.assertEqual(T.lock_licence(text), ("NOASSERTION", text))
        self.assertEqual(T.lock_licence("BSD"), ("NOASSERTION", "BSD"))
        self.assertEqual(T.lock_licence(None), ("NOASSERTION", None))


class LockRuleTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mhs-companion-lock-")
        self.addCleanup(shutil.rmtree, self.root, True)
        git = os.path.join(self.root, *LOCK_PATH.split("/"), ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as fh:
            fh.write(COMMIT + "\n")  # a fetched clone has a detached HEAD
        for rel, text in (("robots/acme/bath/README.md", "Noetic\n"), (LOCK_PATH + "/VERSION", "Noetic\n")):
            path = os.path.join(self.root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        self.write_lock([lock_line()])
        self.by_pid = {PID: {"local_path": "robots/acme/bath"}}

    def write_lock(self, lines):
        path = os.path.join(self.root, "work", "companions", "LOCK.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"clones": lines}, fh)

    def problems(self, item, *, workspace=True, lines=None):
        lock = {line["alias"]: line for line in (lines if lines is not None else [lock_line()])}
        return T.companion_problems(PID, [item], self.by_pid, {}, self.root if workspace else None, lock)

    def test_a_lock_companion_need_not_be_a_corpus_record(self):
        self.assertEqual(self.problems(lock_companion()), [])
        self.assertEqual(T.read_companion_lock(self.root)[0], {LOCK_ALIAS: lock_line()})

    def test_each_lock_rule(self):
        cases = {
            "no entry": (lock_companion(lock="acme__sim@v2.0"), None),
            "does not name": (lock_companion(), [lock_line(repo_url="https://github.com/acme/other.git",
                                                           path=f"work/companions/acme__other@{COMMIT[:12]}")]),
            "no silent re-pin": (lock_companion(), [lock_line(commit="d" * 40,
                                                              path="work/companions/acme__sim@dddddddddddd")]),
            "is not the LOCK.json profile": (lock_companion(), [lock_line(profile="ros1-kinetic-gazebo7")]),
            "is not work/companions": (lock_companion(), [lock_line(path="work/companions/acme__sim@dddddddddddd")]),
            "needed_by": (lock_companion(), [lock_line(needed_by=["gh.acme/other"])]),
            # integrator edit I3 (Claude Sonnet safety F3 of p3-companion-2): missing or not a list is refused too,
            # the package id as a bare string included
            "needed_by of": (lock_companion(), [{key: value for key, value in lock_line().items()
                                                 if key != "needed_by"}]),
            "is not in the LOCK.json needed_by": (lock_companion(), [lock_line(needed_by=PID)]),
            "not in the LOCK.json needed_by": (lock_companion(), [lock_line(needed_by={PID: True})]),
        }
        for expected, (item, lines) in cases.items():
            with self.subTest(expected=expected):
                found = self.problems(item, lines=lines, workspace=False)
                self.assertEqual(len(found), 1, found)
                self.assertIn(expected, found[0])
        self.assertIn("missing or unreadable", T.companion_problems(PID, [lock_companion()], self.by_pid, {},
                                                                    None, None)[0])

    def test_with_the_workspace_the_clone_and_its_head(self):
        with open(os.path.join(self.root, *LOCK_PATH.split("/"), ".git", "HEAD"), "w", encoding="utf-8") as fh:
            fh.write("d" * 40 + "\n")
        self.assertIn("is not at", self.problems(lock_companion())[0])
        self.assertEqual(self.problems(lock_companion(), workspace=False), [])
        shutil.rmtree(os.path.join(self.root, *LOCK_PATH.split("/")))
        self.assertIn("is missing", self.problems(lock_companion())[0])

    def test_evidence_is_read_in_the_fetched_clone(self):
        hidden = lock_companion(version_evidence=[{"side": "package", "ref": "README.md:1", "token": "Noetic"},
                                                  {"side": "companion", "ref": "VERSION:1", "token": "Kinetic"}])
        self.assertIn("does not show", self.problems(hidden)[0])

    def test_build_registry_resolves_a_lock_entry_from_lock_json(self):
        original = BR.WORKSPACE
        BR.WORKSPACE = self.root
        self.addCleanup(setattr, BR, "WORKSPACE", original)
        self.write_lock([lock_line(licence="Apache-2.0 AND BSD (per package.xml)")])
        decision = type("Decision", (), {"companions": [lock_companion()]})()
        cards = {PID: {}}
        self.assertEqual(BR.attach_companions(cards, {PID: decision}, self.by_pid, {}), [])
        entry = cards[PID]["companions"][0]
        self.assertEqual({key: entry[key] for key in ("lock", "ref", "local_path", "repo_url", "license_spdx",
                                                      "licence_note")},
                         {"lock": LOCK_ALIAS, "ref": "v1.0", "local_path": LOCK_PATH,
                          "repo_url": "https://github.com/acme/sim.git", "license_spdx": "NOASSERTION",
                          "licence_note": "Apache-2.0 AND BSD (per package.xml)"})
        self.assertEqual(list(entry)[:8], ["alias", "package_id", "commit", "profile", "reason", "version_evidence",
                                           "lock", "ref"])
        self.write_lock([lock_line(needed_by=["gh.acme/other"])])
        errors = BR.attach_companions({PID: {}}, {PID: decision}, self.by_pid, {})
        self.assertIn("needed_by", errors[0])


class LockValidatorTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mhs-companion-lock-")
        self.addCleanup(shutil.rmtree, self.root, True)
        git = os.path.join(self.root, *LOCK_PATH.split("/"), ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as fh:
            fh.write(COMMIT + "\n")
        for rel, text in (("robots/acme/bath/README.md", "Noetic\n"), (LOCK_PATH + "/VERSION", "Noetic\n")):
            path = os.path.join(self.root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        with open(os.path.join(self.root, "work", "companions", "LOCK.json"), "w", encoding="utf-8") as fh:
            json.dump({"clones": [lock_line()]}, fh)
        self.by_pid = {PID: {"local_path": "robots/acme/bath"}}
        self.card = {"package_id": PID, "decision": "family-config", "companions": [resolved()]}

    def errors(self, card, *, workspace=True):
        return V.check_companions({PID: override(lock_companion())}, {PID: card}, self.by_pid, {},
                                  self.root if workspace else None)

    def test_with_lock_json_the_card_carries_the_resolved_entry(self):
        self.assertEqual(self.errors(self.card), [])
        card = copy.deepcopy(self.card)
        card["companions"][0]["ref"] = "v1.1"
        self.assertIn("differ", self.errors(card)[0])

    def test_without_lock_json_only_the_shape_is_checked(self):
        self.assertEqual(self.errors(self.card, workspace=False), [])
        for key, value, expected in (("local_path", "work/companions/acme__sim@dddddddddddd", "local_path"),
                                     ("repo_url", "https://github.com/acme/other.git", "does not name"),
                                     ("ref", "v2.0", "ref"), ("profile", "ros1-kinetic-gazebo7", "differs")):
            with self.subTest(key=key):
                card = copy.deepcopy(self.card)
                card["companions"][0][key] = value
                found = self.errors(card, workspace=False)
                self.assertTrue(found and any(expected in error for error in found), found)

    def test_the_package_lock_repeats_the_lock_alias(self):
        import overlays as OV  # noqa: E402
        card = dict(self.card, driver_dir="MHS/drivers/robots/acme__bath", upstream={"commit": "a" * 40})
        good = {"package_id": PID, "upstream": {"commit": "a" * 40},
                "companions": [{"package_id": "gh.acme/sim", "commit": COMMIT, "lock": LOCK_ALIAS}]}
        for lock, count in ((good, 0), (dict(good, companions=[{"package_id": "gh.acme/sim", "commit": COMMIT}]), 1)):
            overlay = OV.Overlay(key="robots/acme__bath", path="MHS/drivers/robots/acme__bath",
                                 docs={"task.json": copy.deepcopy(card), "driver.lock.json": lock})
            found = V.check_overlays({"robots/acme__bath": overlay}, {PID: card},
                                     {"robots/acme__bath": {"package_id": PID}}, None, stale=[])
            self.assertEqual(len([error for error in found if "companions" in error]), count, found)


class ShippedLockSourcesTests(unittest.TestCase):
    """The shipped companion-sources-lock.json: every entry's shape, and the LOCK rules when LOCK.json is present."""

    def test_the_shipped_entries_meet_the_shape_and_lock_rules(self):
        path = os.path.join(REG, "overrides", "companion-sources-lock.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])
        ids = [item["package_id"] for item in doc["overrides"]]
        self.assertEqual(ids, sorted(ids))
        workspace = os.path.abspath(os.path.join(REG, "..", ".."))
        companion_lock, problem = T.read_companion_lock(workspace)
        self.assertIsNone(problem)
        locks = {}
        with open(os.path.join(REG, "corpus.lock.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                entry = json.loads(line)
                locks[entry["package_id"]] = entry
        by_pid = {pid: {"local_path": entry["local_path"]} for pid, entry in locks.items()}
        for item in doc["overrides"]:
            with self.subTest(package=item["package_id"]):
                T.check_override(item)
                self.assertTrue(any(T.COMPANION_LOCK_KEY in entry for entry in item["companions"]))
                if companion_lock is None:
                    continue  # an export: work/companions does not travel (shape only, as validate.py --no-corpus)
                self.assertEqual(T.companion_problems(item["package_id"], item["companions"], by_pid, locks,
                                                      None, companion_lock), [])


if __name__ == "__main__":
    unittest.main()
