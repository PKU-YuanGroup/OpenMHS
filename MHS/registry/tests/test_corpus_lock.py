#!/usr/bin/env python3
"""Tests for MHS/registry/corpus_lock.py and the committed corpus.lock.jsonl.

The committed-lock tests read only files under MHS/, so they also pass in a
copy of MHS/ without the corpus.  The git test builds a throwaway repository
and is skipped when git is not installed.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)

import corpus_lock as L  # noqa: E402

SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


class RemoteAndIdTests(unittest.TestCase):
    def test_normalise_remote(self):
        cases = {
            "https://github.com/Owner/Repo.git": "https://github.com/Owner/Repo",
            "git@github.com:owner/repo.git": "https://github.com/owner/repo",
            "ssh://git@gitlab.com/group/sub/repo.git": "https://gitlab.com/group/sub/repo",
            "http://github.com/o/r/": "https://github.com/o/r",
            "https://user:token@github.com/o/r.git": "https://github.com/o/r",
            "": None,
            None: None,
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(L.normalise_remote(raw), want)

    def test_package_id_matches_the_registry_rule(self):
        self.assertEqual(L.package_id_for("PyVISA", "pyvisa-sim"), "gh.pyvisa/pyvisa-sim")
        self.assertEqual(L.package_id_for("ap--", "python-seabreeze"), "gh.ap/python-seabreeze")


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class GitReadTests(unittest.TestCase):
    def test_build_lock_reads_head_and_remote_without_writing(self):
        with tempfile.TemporaryDirectory() as ws:
            clone = os.path.join(ws, "labs", "acme", "widget")
            os.makedirs(clone)
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
            run = lambda *a: subprocess.run(["git", "-C", clone, *a], check=True, capture_output=True, env=env)
            run("init", "-q")
            with open(os.path.join(clone, "README.md"), "w") as fh:
                fh.write("x\n")
            run("add", "README.md")
            run("commit", "-q", "-m", "init")
            run("remote", "add", "origin", "git@github.com:acme/widget.git")
            os.makedirs(os.path.join(ws, "robots", "acme", "empty"))
            subprocess.run(["git", "-C", os.path.join(ws, "robots", "acme", "empty"), "init", "-q"], check=True)
            before = sorted(glob.glob(os.path.join(clone, ".git", "**"), recursive=True))
            entries = L.build_lock(ws, jobs=2)
            after = sorted(glob.glob(os.path.join(clone, ".git", "**"), recursive=True))
        self.assertEqual(before, after)
        self.assertEqual([e["package_id"] for e in entries], ["gh.acme/empty", "gh.acme/widget"])
        widget = next(e for e in entries if e["local_path"] == "labs/acme/widget")
        self.assertRegex(widget["commit"], SHA)
        self.assertEqual(widget["repo_url"], "https://github.com/acme/widget")
        empty = next(e for e in entries if e["local_path"] == "robots/acme/empty")
        self.assertIsNone(empty["commit"])
        self.assertEqual(L.dumps(entries), L.dumps(list(entries)))


    def test_a_directory_without_its_own_git_does_not_inherit_a_parent_work_tree(self):
        with tempfile.TemporaryDirectory() as ws:
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
            run = lambda *a: subprocess.run(["git", "-C", ws, *a], check=True, capture_output=True, env=env)
            run("init", "-q")
            run("remote", "add", "origin", "https://github.com/acme/workspace.git")
            with open(os.path.join(ws, "README.md"), "w") as fh:
                fh.write("x\n")
            run("add", "README.md")
            run("commit", "-q", "-m", "init")
            for name in ("one", "two"):
                os.makedirs(os.path.join(ws, "labs", "acme", name))
                with open(os.path.join(ws, "labs", "acme", name, "driver.py"), "w") as fh:
                    fh.write("x = 1\n")
            entries = L.build_lock(ws, jobs=2)
        self.assertEqual([e["package_id"] for e in entries], ["gh.acme/one", "gh.acme/two"])
        for entry in entries:
            self.assertIsNone(entry["commit"], entry)
            self.assertIsNone(entry["repo_url"], entry)


class CommittedLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(L.LOCK_PATH):
            raise unittest.SkipTest("corpus.lock.jsonl not generated")
        with open(L.LOCK_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.entries = [json.loads(line) for line in cls.text.splitlines()]

    def test_format_is_sorted_unique_and_closed(self):
        ids = [e["package_id"] for e in self.entries]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        for e in self.entries:
            self.assertEqual(sorted(e), ["commit", "local_path", "package_id", "repo_url"])
            self.assertTrue(e["commit"] is None or SHA.match(e["commit"]), e)
            self.assertRegex(e["local_path"], r"^(labs|robots)/[^/]+/[^/]+$")
            self.assertTrue(e["repo_url"] is None or e["repo_url"].startswith("https://"), e)
        self.assertEqual(self.text, L.dumps(self.entries))

    def test_every_registry_record_is_locked_with_the_same_id(self):
        records = {}
        for path in glob.glob(os.path.join(REG, "repos", "*", "*.json")):
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
            records[rec["local_path"]] = rec["package_id"]
        locked = {e["local_path"]: e["package_id"] for e in self.entries}
        self.assertEqual(locked, records)

    def test_most_clones_are_pinned(self):
        pinned = sum(1 for e in self.entries if e["commit"])
        self.assertGreaterEqual(pinned, len(self.entries) - 10)


if __name__ == "__main__":
    unittest.main()
