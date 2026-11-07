"""Git submodules of a pinned clone (SUBMODULES): read at the gitlink commit from their own object store, or not at all.

Every repository here is a throw-away one in a temporary directory; nothing outside it is touched. Skipped when git is
not installed.
"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from mhs.driver.source_selector import parse_selector
from mhs.driver.source_surface import regular_source
from mhs.driver.upstream import UpstreamTree, _parse_gitmodules, _read_head, class_surface

from tests.driver import gate_support as gs
from tests.driver import submodule_support as ss

GIT = shutil.which("git")
SUB = "vendor-sdk"
CONTROLLER = "thermo/controller.py"


def parent_with_submodule(test: unittest.TestCase, *, checkout: bool = True) -> tuple[Path, str, str, Path]:
    """``(parent, parent commit, submodule commit, submodule git dir)``: a parent repository whose ``vendor-sdk``
    submodule holds ``lib/limits.py`` and a nested ``docs/NOTES.md``."""
    base = gs.temp_root(test)
    origin = base / "origin"
    sub_commit = ss.make_repo(origin, {"lib/limits.py": "MAX = 95\nMIN = 5\n", "docs/NOTES.md": "pinned notes\n"})
    parent = base / "parent"
    ss.make_repo(parent, {"README.md": "parent\n"})
    modules = ss.add_submodule(parent, SUB, origin, sub_commit, checkout=checkout)
    gs.git(parent, "commit", "-q", "-m", "add the submodule")
    return parent, gs.git(parent, "rev-parse", "HEAD"), sub_commit, modules


@unittest.skipUnless(GIT, "git is not installed")
class SubmoduleTreeTests(unittest.TestCase):
    def test_a_path_in_a_submodule_is_read_at_the_gitlink_commit(self) -> None:
        parent, commit, sub_commit, _modules = parent_with_submodule(self)
        tree = UpstreamTree(parent, commit)
        self.assertTrue(tree.pinned)
        self.assertEqual(tree.submodule_paths(), [SUB])
        self.assertEqual(tree.read_text(f"{SUB}/lib/limits.py"), "MAX = 95\nMIN = 5\n")
        record = tree.submodules[SUB]
        self.assertEqual((record.name, record.commit, record.git_dir), (SUB, sub_commit, f".git/modules/{SUB}"))
        self.assertEqual(tree.submodule_refusals, {})
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/missing.py"))
        self.assertIsNone(tree.read_bytes(SUB), "the gitlink itself is not a file")
        self.assertIsNone(tree.read_bytes(f"{SUB}/.git"))

    def test_the_object_store_is_read_never_the_checkout(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        (parent / SUB / "lib" / "limits.py").write_text("MAX = 9999\n", encoding="utf-8")   # a dirty checkout
        tree = UpstreamTree(parent, commit)
        self.assertEqual(tree.read_text(f"{SUB}/lib/limits.py"), "MAX = 95\nMIN = 5\n")

    def test_files_and_grep_stay_those_of_the_clones_own_tree(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        tree = UpstreamTree(parent, commit)
        self.assertEqual(sorted(tree.files()), [".gitmodules", "README.md", SUB])
        self.assertFalse(tree.grep("pinned notes"))
        self.assertEqual(tree.submodules, {})

    def test_a_submodule_at_another_commit_fails_closed(self) -> None:
        parent, commit, sub_commit, _modules = parent_with_submodule(self)
        gs.git(parent / SUB, "commit", "-q", "--allow-empty", "-m", "later")
        tree = UpstreamTree(parent, commit)
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        reason = tree.refusal_for(f"{SUB}/lib/limits.py")
        self.assertIn("another commit", reason)
        self.assertIn(sub_commit[:12], reason)
        self.assertEqual(tree.submodules, {})

    def test_an_absent_or_empty_submodule_fails_closed(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self, checkout=False)
        tree = UpstreamTree(parent, commit)
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        self.assertIn("absent from the checkout", tree.refusal_for(f"{SUB}/lib/limits.py"))
        (parent / SUB).mkdir()
        tree = UpstreamTree(parent, commit)
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        self.assertIn("not checked out", tree.refusal_for(f"{SUB}/lib/limits.py"))

    def test_a_gitdir_file_that_names_another_directory_fails_closed(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        (parent / SUB / ".git").write_text("gitdir: ../.git\n", encoding="utf-8")   # the parent's own git directory
        tree = UpstreamTree(parent, commit)
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        self.assertIn("not the git directory", tree.refusal_for(f"{SUB}/lib/limits.py"))

    def test_a_symbolic_link_in_the_checkout_path_fails_closed(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        moved = parent.parent / "elsewhere"
        (parent / SUB).rename(moved)
        (parent / SUB).symlink_to(moved, target_is_directory=True)
        tree = UpstreamTree(parent, commit)
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        self.assertIn("symbolic link", tree.refusal_for(f"{SUB}/lib/limits.py"))

    def test_an_undeclared_gitlink_is_not_followed(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        gs.git(parent, "rm", "-q", "--cached", ".gitmodules")
        gs.git(parent, "commit", "-q", "-m", "drop .gitmodules")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        self.assertIsNone(tree.read_bytes(f"{SUB}/lib/limits.py"))
        self.assertEqual(tree.submodule_refusals, {})

    def test_a_declared_path_without_a_gitlink_is_refused(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self)
        with (parent / ".gitmodules").open("a", encoding="utf-8") as handle:
            handle.write('[submodule "ghost"]\n\tpath = ghost\n\turl = https://example.invalid/ghost.git\n')
        gs.git(parent, "add", ".gitmodules")
        gs.git(parent, "commit", "-q", "-m", "declare a submodule that has no gitlink")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        self.assertIsNone(tree.read_bytes("ghost/x.py"))
        self.assertIn("records no gitlink", tree.refusal_for("ghost/x.py"))
        self.assertIsNotNone(tree.read_bytes(f"{SUB}/lib/limits.py"))

    def test_a_nested_submodule_is_followed_one_level_down(self) -> None:
        base = gs.temp_root(self)
        inner_origin = base / "inner"
        inner_commit = ss.make_repo(inner_origin, {"data.txt": "inner data\n"})
        outer_origin = base / "outer"
        ss.make_repo(outer_origin, {"outer.txt": "outer\n"})
        outer_staging = base / "outer-staging"
        gs.git(base, "clone", "-q", str(outer_origin), str(outer_staging))
        ss.add_submodule(outer_staging, "inner", inner_origin, inner_commit, checkout=False)
        gs.git(outer_staging, "commit", "-q", "-m", "nest inner")
        outer_commit = gs.git(outer_staging, "rev-parse", "HEAD")
        parent = base / "parent"
        ss.make_repo(parent, {"README.md": "parent\n"})
        ss.add_submodule(parent, SUB, outer_staging, outer_commit)
        gs.git(parent, "commit", "-q", "-m", "add outer")
        ss.add_submodule(parent / SUB, "inner", inner_origin, inner_commit)
        gs.git(parent / SUB, "reset", "-q", "--hard", outer_commit)   # the nested .gitmodules entry is the pinned one
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        self.assertEqual(tree.read_text(f"{SUB}/inner/data.txt"), "inner data\n")
        self.assertEqual(sorted(tree.submodules), [SUB, f"{SUB}/inner"])
        self.assertEqual(tree.submodules[f"{SUB}/inner"].git_dir, f".git/modules/{SUB}/modules/inner")

    def test_a_module_in_a_submodule_is_found_after_the_clones_own_tree(self) -> None:
        base = gs.temp_root(self)
        origin = base / "origin"
        sub_commit = ss.make_repo(origin, {"pkg/dev.py": "class Device:\n    def stop(self):\n        pass\n"})
        parent = base / "parent"
        ss.make_repo(parent, {"README.md": "parent\n"})
        ss.add_submodule(parent, SUB, origin, sub_commit)
        gs.git(parent, "commit", "-q", "-m", "add")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        surface = class_surface(tree, "pkg.dev:Device")
        self.assertTrue(surface.found, surface.problems)
        self.assertEqual((surface.file, surface.line), (f"{SUB}/pkg/dev.py", 1))
        self.assertIn("stop", surface.names)
        self.assertIn(SUB, tree.submodules)
        # The clone's own tree wins: a module of the same name in the clone is the one read.
        (parent / "pkg").mkdir()
        (parent / "pkg" / "dev.py").write_text("class Device:\n    def start(self):\n        pass\n",
                                               encoding="utf-8")
        gs.git(parent, "add", "pkg/dev.py")
        gs.git(parent, "commit", "-q", "-m", "own pkg")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        surface = class_surface(tree, "pkg.dev:Device")
        self.assertEqual(surface.file, "pkg/dev.py")
        self.assertEqual(tree.submodules, {})

    def test_bases_are_never_looked_for_in_a_submodule_used_as_a_source_root(self) -> None:
        # Two passing packages (lw-benchhub, robocas-v0) import their native's base from a module that only a
        # submodule holds: following it would change what G7 reads for packages that never cited the submodule.
        base = gs.temp_root(self)
        origin = base / "origin"
        sub_commit = ss.make_repo(origin, {"basepkg/core.py": "class Base:\n    def step(self):\n        pass\n"})
        parent = base / "parent"
        ss.make_repo(parent, {"app/env.py": "from basepkg.core import Base\n\nclass Env(Base):\n    pass\n"})
        ss.add_submodule(parent, SUB, origin, sub_commit)
        gs.git(parent, "commit", "-q", "-m", "add")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        surface = class_surface(tree, "app.env:Env")
        self.assertTrue(surface.found, surface.problems)
        self.assertNotIn("step", surface.names)
        self.assertTrue(any("base Base of Env is not defined in the clone" in item for item in surface.open))
        self.assertEqual(tree.submodules, {})
        # An exact path into the submodule (a relative import, a citation) is still read at the gitlink.
        self.assertIn("class Base", tree.read_text(f"{SUB}/basepkg/core.py"))

    def test_a_refused_submodule_is_named_when_a_module_is_missing(self) -> None:
        parent, commit, _sub_commit, _modules = parent_with_submodule(self, checkout=False)
        tree = UpstreamTree(parent, commit)
        surface = class_surface(tree, "lib.limits:Thing")
        self.assertFalse(surface.found)
        self.assertIn("git submodules not read", surface.problems[0])

    def test_an_explicit_source_selector_reads_into_a_submodule(self) -> None:
        base = gs.temp_root(self)
        origin = base / "origin"
        sub_commit = ss.make_repo(origin, {"src/2230G.py": "class KEI2230G:\n    def output(self):\n        pass\n"})
        parent = base / "parent"
        ss.make_repo(parent, {"README.md": "parent\n"})
        ss.add_submodule(parent, SUB, origin, sub_commit)
        gs.git(parent, "commit", "-q", "-m", "add")
        tree = UpstreamTree(parent, gs.git(parent, "rev-parse", "HEAD"))
        selector = parse_selector(f"pyfile:{SUB}/src/2230G.py#KEI2230G")
        self.assertIn("class KEI2230G", regular_source(tree, selector.path))
        self.assertIn(SUB, tree.submodules)
        with self.assertRaises(ValueError):
            regular_source(tree, SUB)   # the gitlink itself is not a regular blob


class GitmodulesParserTests(unittest.TestCase):
    def test_paths_names_quotes_and_comments(self) -> None:
        text = ('# comment\n[submodule "a"]\n\tpath = third_party/a\n\turl = x\n'
                '[submodule "b"]\n\tPath = "b dir"\n; another comment\n[core]\n\tpath = not-a-submodule\n')
        paths, problems = _parse_gitmodules(text)
        self.assertEqual(paths, {"third_party/a": "a", "b dir": "b"})
        self.assertEqual(problems, [])

    def test_ambiguous_or_unsafe_entries_are_left_out(self) -> None:
        text = ('[submodule "twice"]\n\tpath = one\n\tpath = two\n'
                '[submodule "up"]\n\tpath = ../outside\n'
                '[submodule "../evil"]\n\tpath = evil\n'
                '[submodule "x"]\n\tpath = shared\n[submodule "y"]\n\tpath = shared\n'
                '[submodule "ok"]\n\tpath = fine\n')
        paths, problems = _parse_gitmodules(text)
        self.assertEqual(paths, {"fine": "ok"})
        self.assertEqual(len(problems), 4, problems)


class ReadHeadTests(unittest.TestCase):
    def test_detached_loose_and_packed_heads(self) -> None:
        root = gs.temp_root(self)
        sha = "a" * 40
        (root / "HEAD").write_text(sha + "\n", encoding="utf-8")
        self.assertEqual(_read_head(root), sha)
        (root / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertIsNone(_read_head(root))
        (root / "packed-refs").write_text(f"# pack-refs with: peeled\n{'b' * 40} refs/heads/main\n", encoding="utf-8")
        self.assertEqual(_read_head(root), "b" * 40)
        (root / "refs" / "heads").mkdir(parents=True)
        (root / "refs" / "heads" / "main").write_text("c" * 40 + "\n", encoding="utf-8")
        self.assertEqual(_read_head(root), "c" * 40)
        for bad in ("ref: refs/../../etc\n", "ref: HEAD\n", "not a commit\n"):
            (root / "HEAD").write_text(bad, encoding="utf-8")
            self.assertIsNone(_read_head(root), bad)


@unittest.skipUnless(GIT, "git is not installed")
class SubmoduleGateTests(unittest.TestCase):
    """The tutorial package whose upstream SDK lives in a submodule of its clone: G1, G4 and G7 at the gitlink."""

    def package(self) -> tuple[Path, Path, Path]:
        root, directory = gs.real_package(self)
        clone = root / "labs" / "acme" / "th1"
        origin = root / "origin-sdk"
        origin.mkdir()
        (clone / "thermo").rename(origin / "thermo")
        sub_commit = ss.make_repo(origin, {})
        gs.git(clone, "init", "-q")
        gs.git(clone, "add", "-A")
        ss.add_submodule(clone, SUB, origin, sub_commit)
        gs.git(clone, "commit", "-q", "-m", "TH-1 manual; SDK as a submodule")
        for line in ("39", "7"):
            gs.edit(directory, "driver.py", f'ref="{CONTROLLER}:{line}"', f'ref="{SUB}/{CONTROLLER}:{line}"')
        gs.pin(directory, gs.git(clone, "rev-parse", "HEAD"))
        return root, directory, clone

    def test_a_package_citing_a_submodule_passes_and_names_it(self) -> None:
        root, directory, clone = self.package()
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], report)
        notes = [item for item in report["gates"][0]["findings"] if item["code"] == "G1.SUBMODULE_SOURCE"]
        self.assertEqual(len(notes), 1, report["gates"][0])
        self.assertEqual(notes[0]["path"], SUB)
        self.assertIn(".git/modules/vendor-sdk", notes[0]["message"])
        self.assertEqual(report["gates"][0]["status"], "warn")

    def test_a_submodule_at_another_commit_fails_g4_and_g7(self) -> None:
        root, directory, clone = self.package()
        gs.git(clone / SUB, "commit", "-q", "--allow-empty", "-m", "moved on")
        report = gs.check(directory, root=root)
        missing = [item for item in report["gates"][3]["findings"] if item["code"] == "G4.REF_MISSING"]
        self.assertEqual(len(missing), 2, report["gates"][3])
        self.assertIn("another commit", missing[0]["message"])
        self.assertIn("G7.NATIVE_NOT_FOUND", gs.findings(report, "G7"))
        self.assertNotIn("G1.SUBMODULE_SOURCE", gs.findings(report, "G1", severity="warning"))

    def test_the_gitlink_is_read_not_a_dirty_submodule_checkout(self) -> None:
        root, directory, clone = self.package()
        controller = clone / SUB / CONTROLLER
        controller.write_text(controller.read_text(encoding="utf-8").replace("def heater_off(self):",
                                                                             "def heater_disable(self):"),
                              encoding="utf-8")
        report = gs.check(directory, root=root, gates=["G3", "G4", "G7"])
        self.assertEqual([gate for gate in report["failed"] if gate != "G1"], [], report)
        self.assertNotIn("G7.NOT_UPSTREAM", gs.findings(report, "G7"))


if __name__ == "__main__":
    unittest.main()
