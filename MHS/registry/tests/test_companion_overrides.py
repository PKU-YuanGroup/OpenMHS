#!/usr/bin/env python3
"""Companion sources (user decision 2026-11-05): a reviewed override's ``companions`` reach the task card.

A stop may cite a locally cloned companion repository at a pinned commit.  The override declares it (alias, corpus
package_id, corpus-lock commit, profile, reason, version evidence); triage checks the shape; build_registry.py checks
it against the corpus (a corpus record, its lock commit, never the repository itself; with the corpus present, the
clone's HEAD and every evidence range) and copies it onto the card with the clone's local_path, repo_url and licence;
validate.py repeats the rules, refuses a card whose companions no override declares, and refuses a package whose
task.json companions differ from the card's.
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

import triage as T  # noqa: E402
from test_build_pipeline import STORE  # noqa: E402
from test_triage import decide, facts  # noqa: E402
import validate as V  # noqa: E402

COMMIT = "c" * 40
OTHER = "d" * 40


def companion(**extra):
    item = {"alias": "sim_ros", "package_id": "gh.acme/sim", "commit": COMMIT, "profile": "ros1-noetic-gazebo11",
            "reason": "the pause, its read-back and the unpause are served by this companion (test)",
            "version_evidence": [{"side": "package", "ref": "README.md:1", "token": "Noetic"},
                                 {"side": "companion", "ref": "VERSION:1", "token": "Noetic"}]}
    item.update(extra)
    return item


def override(*companions, **extra):
    item = {"package_id": "gh.acme/bath", "strategy": "family-config", "role": "sim-env", "family": "ros",
            "reason_code": "family:ros", "justification": "Model review: the stop lives in the simulator's own repo.",
            "companions": list(companions) or [companion()]}
    item.update(extra)
    return item


class CompanionOverrideCheckTests(unittest.TestCase):
    def test_a_well_formed_entry_passes_triage_and_the_schema(self):
        T.check_override(override())
        doc = {"overrides_version": "0.9", "title": "t", "overrides": [override()]}
        self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])

    def test_malformed_entries_are_refused_by_triage(self):
        cases = {
            "unknown key": companion(extra=1),
            "bad alias": companion(alias="Sim"),
            "own repository": companion(package_id="gh.acme/bath"),
            "short commit": companion(commit="abc"),
            "bad profile": companion(profile="noetic"),
            "multi-line reason": companion(reason="two\nlines of reason text"),
            "one evidence item": companion(version_evidence=[{"side": "package", "ref": "README.md:1", "token": "No"}]),
            "no companion side": companion(version_evidence=[{"side": "package", "ref": "a:1", "token": "Noetic"},
                                                              {"side": "package", "ref": "b:1", "token": "Noetic"}]),
            "bad side": companion(version_evidence=[{"side": "package", "ref": "a:1", "token": "Noetic"},
                                                     {"side": "elsewhere", "ref": "b:1", "token": "Noetic"}]),
            "traversal": companion(version_evidence=[{"side": "package", "ref": "../a:1", "token": "Noetic"},
                                                      {"side": "companion", "ref": "b:1", "token": "Noetic"}]),
            "undeclared other side": companion(version_evidence=[
                {"side": "package", "ref": "a:1", "token": "Noetic"},
                {"side": "companion:other_sim", "ref": "b:1", "token": "Noetic"}]),
        }
        for name, item in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(T.OverrideError):
                    T.check_override(override(item))
        with self.assertRaises(T.OverrideError):
            T.check_override(override(companion(), companion()))  # duplicate alias
        with self.assertRaises(T.OverrideError):
            T.check_override(override(*[companion(alias=f"sim_{n}") for n in range(4)]))  # more than three
        with self.assertRaises(T.OverrideError):
            T.check_override(override(strategy="reference", role="prior-art"))  # not a driver card

    def test_the_schema_refuses_what_triage_refuses(self):
        for item in (companion(alias="Sim"), companion(commit="abc"), companion(extra=1)):
            with self.subTest(item=item):
                doc = {"overrides_version": "0.9", "title": "t", "overrides": [override(item)]}
                self.assertTrue(STORE.validate(doc, "overrides.schema.json"))
        doc = {"overrides_version": "0.9", "title": "t",
               "overrides": [override(strategy="reference", role="prior-art")]}
        self.assertTrue(STORE.validate(doc, "overrides.schema.json"))

    def test_companions_pass_through_the_decision_but_stay_off_the_decision_record(self):
        f = facts(name="bath")
        d = decide(f, overrides={f.package_id: override()})
        self.assertEqual(d.companions[0]["alias"], "sim_ros")
        self.assertNotIn("companions", d.to_json())


class CompanionCorpusRuleTests(unittest.TestCase):
    """triage.companion_problems: the rules build_registry.py and validate.py share."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mhs-companion-")
        self.addCleanup(shutil.rmtree, self.root, True)
        for rel, text in (("robots/acme/bath/README.md", "ROS Noetic\n"), ("robots/acme/sim/VERSION", "Noetic 2.9\n")):
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        git = os.path.join(self.root, "robots/acme/sim/.git")
        os.makedirs(os.path.join(git, "refs", "heads"))
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as fh:
            fh.write("ref: refs/heads/main\n")
        with open(os.path.join(git, "refs", "heads", "main"), "w", encoding="utf-8") as fh:
            fh.write(COMMIT + "\n")
        self.by_pid = {"gh.acme/bath": {"local_path": "robots/acme/bath"},
                       "gh.acme/sim": {"local_path": "robots/acme/sim", "license_spdx": "Apache-2.0"}}
        self.locks = {"gh.acme/sim": {"package_id": "gh.acme/sim", "commit": COMMIT, "local_path": "robots/acme/sim",
                                      "repo_url": "https://github.com/acme/sim"}}

    def problems(self, item, workspace=True):
        return T.companion_problems("gh.acme/bath", [item], self.by_pid, self.locks,
                                    self.root if workspace else None)

    def test_a_companion_at_its_lock_commit_with_shown_evidence_passes(self):
        self.assertEqual(self.problems(companion()), [])

    def test_the_head_is_read_from_packed_refs_too(self):
        git = os.path.join(self.root, "robots/acme/sim/.git")
        os.remove(os.path.join(git, "refs", "heads", "main"))
        with open(os.path.join(git, "packed-refs"), "w", encoding="utf-8") as fh:
            fh.write(f"# pack-refs with: peeled\n{COMMIT} refs/heads/main\n")
        self.assertEqual(T.clone_head(os.path.join(self.root, "robots/acme/sim")), COMMIT)

    def test_unknown_record_repinned_commit_and_self_reference_stop_the_build(self):
        self.assertIn("not a corpus record", self.problems(companion(package_id="gh.acme/nowhere"))[0])
        self.assertIn("no silent re-pin", self.problems(companion(commit=OTHER))[0])
        self.assertIn("the repository itself", self.problems(companion(package_id="gh.acme/bath"))[0])

    def test_with_the_corpus_the_head_and_the_evidence_are_checked(self):
        with open(os.path.join(self.root, "robots/acme/sim/.git/refs/heads/main"), "w", encoding="utf-8") as fh:
            fh.write(OTHER + "\n")
        self.assertIn("is not at", self.problems(companion())[0])
        self.assertEqual(self.problems(companion(), workspace=False), [])  # --no-corpus: shape and lock only
        with open(os.path.join(self.root, "robots/acme/sim/.git/refs/heads/main"), "w", encoding="utf-8") as fh:
            fh.write(COMMIT + "\n")
        hidden = companion(version_evidence=[{"side": "package", "ref": "README.md:1", "token": "Melodic"},
                                             {"side": "companion", "ref": "VERSION:1", "token": "Noetic"}])
        self.assertIn("does not show", self.problems(hidden)[0])
        beyond = companion(version_evidence=[{"side": "package", "ref": "README.md:9", "token": "Noetic"},
                                             {"side": "companion", "ref": "VERSION:1", "token": "Noetic"}])
        self.assertIn("does not show", self.problems(beyond)[0])
        shutil.rmtree(os.path.join(self.root, "robots/acme/sim"))
        self.assertIn("is missing", self.problems(companion())[0])


class CompanionValidatorTests(unittest.TestCase):
    """validate.check_companions: the card carries exactly the resolved override, and only an override adds one."""

    def setUp(self):
        self.by_pid = {"gh.acme/bath": {"local_path": "robots/acme/bath"},
                       "gh.acme/sim": {"local_path": "robots/acme/sim", "license_spdx": "Apache-2.0"}}
        self.locks = {"gh.acme/sim": {"package_id": "gh.acme/sim", "commit": COMMIT, "local_path": "robots/acme/sim",
                                      "repo_url": "https://github.com/acme/sim"}}
        resolved = dict(companion(), local_path="robots/acme/sim", repo_url="https://github.com/acme/sim",
                        license_spdx="Apache-2.0")
        self.card = {"package_id": "gh.acme/bath", "decision": "family-config", "companions": [resolved]}

    def errors(self, overrides, card):
        return V.check_companions(overrides, {"gh.acme/bath": card}, self.by_pid, self.locks, None)

    def test_a_card_that_carries_the_resolved_override_passes(self):
        self.assertEqual(self.errors({"gh.acme/bath": override()}, self.card), [])

    def test_companions_without_an_override_are_refused(self):
        self.assertIn("without a reviewed override", self.errors({}, self.card)[0])

    def test_a_card_that_differs_from_the_override_is_refused(self):
        card = copy.deepcopy(self.card)
        card["companions"][0]["profile"] = "ros1-melodic-gazebo9"
        self.assertIn("differ", self.errors({"gh.acme/bath": override()}, card)[0])
        card = copy.deepcopy(self.card)
        del card["companions"]
        self.assertIn("differ", self.errors({"gh.acme/bath": override()}, card)[0])

    def test_the_taskcard_schema_admits_companions_only_on_driver_cards(self):
        path = os.path.join(REG, "schema", "examples", "taskcard.thermal-bath.json")
        with open(path, encoding="utf-8") as fh:
            card = json.load(fh)
        card = dict(card, companions=self.card["companions"])
        self.assertEqual(STORE.validate(card, "taskcard.schema.json"), [])
        reference = dict(card, decision="reference", family=None, helper=None, helper_status=None)
        self.assertTrue(STORE.validate(reference, "taskcard.schema.json"))
        del reference["companions"]
        self.assertEqual(STORE.validate(reference, "taskcard.schema.json"), [])  # refused for the companions only
        bad = copy.deepcopy(card)
        bad["companions"][0]["local_path"] = "../outside"
        self.assertTrue(STORE.validate(bad, "taskcard.schema.json"))


class CompanionOverlayTests(unittest.TestCase):
    """validate.check_overlays: a package's task.json carries exactly the card's companions (the gate reads them from
    task.json, a file of the package) and its lock repeats their [package_id, commit]."""

    def setUp(self):
        resolved = dict(companion(), local_path="robots/acme/sim", repo_url="https://github.com/acme/sim",
                        license_spdx="Apache-2.0")
        self.card = {"package_id": "gh.acme/bath", "decision": "family-config",
                     "driver_dir": "MHS/drivers/robots/acme__bath", "upstream": {"commit": "a" * 40},
                     "companions": [resolved]}
        self.lock = {"package_id": "gh.acme/bath", "upstream": {"commit": "a" * 40},
                     "companions": [{"package_id": "gh.acme/sim", "commit": COMMIT}]}

    def errors(self, task, *, card=None, lock=None):
        import overlays as OV  # noqa: E402
        overlay = OV.Overlay(key="robots/acme__bath", path="MHS/drivers/robots/acme__bath",
                             docs={"task.json": task, "driver.lock.json": lock if lock is not None else self.lock})
        found = V.check_overlays({"robots/acme__bath": overlay}, {"gh.acme/bath": card or self.card},
                                 {"robots/acme__bath": {"package_id": "gh.acme/bath"}}, None, stale=[])
        return [error for error in found if "companions" in error]

    def test_a_task_json_equal_to_the_card_passes(self):
        self.assertEqual(self.errors(copy.deepcopy(self.card)), [])

    def test_a_task_json_that_rewrites_drops_or_nulls_the_companions_is_refused(self):
        tampered = copy.deepcopy(self.card)
        tampered["companions"][0]["profile"] = "ros1-noetic-gazebo9"
        tampered["companions"][0]["version_evidence"] = [{"side": "package", "ref": "README.md:1", "token": "TH"},
                                                         {"side": "companion", "ref": "VERSION:1", "token": "Noetic"}]
        dropped = {key: value for key, value in self.card.items() if key != "companions"}
        nulled = dict(self.card, companions=None)
        for name, task in (("rewritten", tampered), ("dropped", dropped), ("null", nulled)):
            with self.subTest(name=name):
                errors = self.errors(task)
                self.assertEqual(len(errors), 1, errors)  # the lock still repeats the card: only task.json differs
                self.assertIn("task.json: companions differ from the card's", errors[0])

    def test_a_package_cannot_add_companions_to_a_card_without_them(self):
        card = {key: value for key, value in self.card.items() if key != "companions"}
        errors = self.errors(copy.deepcopy(self.card), card=card)
        self.assertTrue(any("task.json: companions differ from the card's" in error for error in errors), errors)
        self.assertTrue(any("driver.lock.json: companions != the card's companions []" in error for error in errors),
                        errors)
        # even an empty declaration (null) is a field the card does not have
        lock = {key: value for key, value in self.lock.items() if key != "companions"}
        errors = self.errors(dict(card, companions=None), card=card, lock=lock)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("task.json: companions differ from the card's", errors[0])


class ShippedCompanionSourcesTests(unittest.TestCase):
    """The shipped override file: six Gazebo-pause packages, two companions each, at their corpus-lock commits, and
    (integrator v4, 2026-11-05) rickstaa/ros-gazebo-gym's unchanged Gymnasium routing with gazebo_ros_pkgs alone, for
    the facts about the pause and its read-back that its isolated host calls. The sixth pause package is
    gh.wh200720041/warehouse_simulation_toolkit (phase-5)."""

    def test_the_shipped_entries_meet_the_shape_and_lock_rules(self):
        path = os.path.join(REG, "overrides", "companion-sources.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])
        locks = {}
        with open(os.path.join(REG, "corpus.lock.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                entry = json.loads(line)
                locks[entry["package_id"]] = entry
        by_pid = {pid: {"local_path": entry["local_path"]} for pid, entry in locks.items()}
        ids = [item["package_id"] for item in doc["overrides"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 7)
        for item in doc["overrides"]:
            with self.subTest(package=item["package_id"]):
                T.check_override(item)
                self.assertEqual(T.companion_problems(item["package_id"], item["companions"], by_pid, locks), [])
                if item["package_id"] == "gh.rickstaa/ros-gazebo-gym":
                    # its routing of ros-routing-20261102.json, moved here unchanged (a repository is overridden once)
                    self.assertEqual((item["strategy"], item["family"], item["role"]),
                                     ("family-config", "gymnasium", "sim-env"))
                    self.assertEqual([entry["alias"] for entry in item["companions"]], ["gazebo_ros_pkgs"])
                    self.assertEqual(item["companions"][0]["profile"], "ros1-noetic-gazebo11")
                    continue
                self.assertEqual([entry["alias"] for entry in item["companions"]],
                                 ["gazebo_ros_pkgs", "gazebo_classic"])


if __name__ == "__main__":
    unittest.main()
