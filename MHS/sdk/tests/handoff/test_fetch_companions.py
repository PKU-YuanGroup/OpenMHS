"""tools/fetch_companions.py, and the fetched-companion (``lock``) parts of show_refs.py and collect.py (DESIGN-2 of the
companion preflight, 2026-11-05), on synthetic roots with tiny git repositories: no corpus and no network.

fetch_companions: ``--from`` a clone or a bundle (offline) gives a verified read-only clone and a merged LOCK.json, and
a second call only verifies; a LOCK.json entry that would re-pin, or widen ``needed_by``, is refused; an existing
writable or dirty destination is refused and left as it is; a copy at another commit is never moved into place;
nothing is fetched without ``--network`` (the git calls are recorded); the network step is the depth-1 fetch of the
pinned commit (recorded, and answered by the test instead of git); git runs hardened (no hooks, credential helper,
prompt, LFS smudge, system or global configuration).  show_refs: the LOCK.json lines of a companion header, ``!! LOCK
mismatch``, ``!! writable work tree``, ``!! clone missing`` and ``--companions-root``.  collect: the COMPANION_SOURCE
note of a present and of a missing fetched clone.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
PACKAGE = "gh.acme/th1"
ALIAS = "acme__sim@v1.0"
PROFILE = "ros1-kinetic-gazebo7"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


fetch = load("tools_fetch_companions", REPO / "tools/fetch_companions.py")
show_refs = load("fetch_companions_show_refs", REPO / "MHS/handoff/tools/show_refs.py")
collect = load("fetch_companions_collect", REPO / "MHS/handoff/tools/collect.py")


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd, check=True,
                   capture_output=True)


def make_repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    git("init", "-q", cwd=path)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "init", cwd=path)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True,
                          check=True).stdout.strip()


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def modes(tree: Path) -> dict[str, tuple[int, bytes | None]]:
    """Mode and content of every work-tree entry (``.git`` left out): what "left as it is" compares."""
    found = {}
    for path in sorted(tree.rglob("*")):
        if ".git" in path.relative_to(tree).parts:
            continue
        found[path.relative_to(tree).as_posix()] = (stat.S_IMODE(os.lstat(path).st_mode),
                                                    path.read_bytes() if path.is_file() else None)
    return found


class Root:
    """A repository root with one driver package whose card names a fetched companion, and the companion's clone in
    another workspace's ``work/companions`` (``self.source``), not yet in this root."""

    def __init__(self, test: unittest.TestCase):
        self.dir = Path(tempfile.mkdtemp(prefix="fetch-companions-")).resolve()  # the tools print resolved paths
        test.addCleanup(self.close)
        self.package_commit = make_repo(self.dir / "robots/acme/th1", {"README.md": "Tested on ROS Kinetic.\n"})
        self.source = self.dir / "elsewhere" / "work" / "companions"
        self.commit = make_repo(self.source / "staging", {
            "sim/api.cpp": "bool pause() {\n  world->SetPaused(true);\n  return true;\n}\n",
            "package.xml": "<version>2.5.21</version>\n"})
        self.name = f"acme__sim@{self.commit[:12]}"
        (self.source / "staging").rename(self.source / self.name)
        self.companions = self.dir / "work" / "companions"
        self.driver = self.dir / "MHS/drivers/robots/acme__th1"
        self.driver.mkdir(parents=True)
        self.card = {"package_id": PACKAGE, "track": "robots", "local_path": "robots/acme/th1",
                     "upstream": {"repo_url": "https://github.com/acme/th1", "commit": self.package_commit},
                     "companions": [self.item()]}
        self.write_card(self.card)
        (self.driver / "driver.py").write_text('_API = "companion:sim_ros/sim/api.cpp"\n'
                                               'facts = [Fact("pause sets the flag", source="upstream_code", '
                                               'ref=f"{_API}:2")]\n', encoding="utf-8")
        (self.driver / "reference.json").write_text(json.dumps(
            {"facts": [{"text": "pause sets the flag", "source": "upstream_code",
                        "ref": "companion:sim_ros/sim/api.cpp:2"}]}), encoding="utf-8")

    def item(self) -> dict:
        return {"alias": "sim_ros", "package_id": "gh.acme/sim", "commit": self.commit, "profile": PROFILE,
                "reason": "the world pause is the stop",
                "version_evidence": [{"side": "package", "ref": "README.md:1", "token": "Kinetic"},
                                     {"side": "companion", "ref": "package.xml:1", "token": "2.5.21"}],
                "lock": ALIAS, "ref": "v1.0", "local_path": f"work/companions/{self.name}",
                "repo_url": "https://github.com/acme/sim.git", "license_spdx": "Apache-2.0"}

    def lock_entry(self, **changes) -> dict:
        entry = {"alias": ALIAS, "repo_url": "https://github.com/acme/sim.git", "ref": "v1.0", "commit": self.commit,
                 "path": f"work/companions/{self.name}", "profile": PROFILE, "licence": "Apache-2.0",
                 "needed_by": [PACKAGE]}
        entry.update(changes)
        return entry

    def write_lock(self, *entries: dict, where: Path | None = None) -> Path:
        target = (where or self.companions) / "LOCK.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"clones": list(entries)}, indent=1) + "\n", encoding="utf-8")
        return target

    def write_card(self, card: dict) -> None:
        (self.driver / "task.json").write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
        registry = self.dir / "MHS/registry/tasks/robots/acme__th1.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")

    def install(self) -> Path:
        """The clone placed read-only under this root's work/companions with its LOCK.json (as a fetch leaves it)."""
        self.companions.mkdir(parents=True, exist_ok=True)
        clone = self.companions / self.name
        shutil.copytree(self.source / self.name, clone, symlinks=True)
        fetch.make_read_only(clone)
        self.write_lock(self.lock_entry())
        return clone

    def close(self) -> None:
        for directory, _dirs, names in os.walk(self.dir):
            os.chmod(directory, stat.S_IMODE(os.lstat(directory).st_mode) | 0o700)
            for name in names:
                full = os.path.join(directory, name)
                if not os.path.islink(full):
                    os.chmod(full, stat.S_IMODE(os.lstat(full).st_mode) | 0o600)
        shutil.rmtree(self.dir, ignore_errors=True)


class FetchCompanionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Root(self)
        self.args = [str(self.root.driver), "--root", str(self.root.dir)]

    def test_from_a_clone_gives_a_verified_read_only_clone_and_a_lock_entry(self) -> None:
        code, out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 0, err)
        dest = self.root.companions / self.root.name
        self.assertIn(f"copied  {ALIAS}: {dest}", out)
        self.assertEqual(fetch.head_of(dest), self.root.commit)
        self.assertEqual(fetch.writable_entries(dest), [])
        self.assertEqual(fetch.verify(dest, self.root.commit, Path(os.devnull), fsck=True), [])
        self.assertEqual(sorted(path.name for path in self.root.companions.iterdir()), ["LOCK.json", self.root.name],
                         "no staged copy is left beside the clone")
        lock = json.loads((self.root.companions / "LOCK.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["count"], 1)
        entry = lock["clones"][0]
        self.assertEqual({key: entry[key] for key in self.root.lock_entry()}, self.root.lock_entry())
        self.assertTrue(entry["worktree_read_only"])
        self.assertEqual(entry["source"], f"from:{self.root.source.resolve() / self.root.name}")
        before = (self.root.companions / "LOCK.json").read_text(encoding="utf-8")
        code, out, err = run_main(fetch, self.args)
        self.assertEqual(code, 0, err)
        self.assertIn(f"ok      {ALIAS}: {dest} is at {self.root.commit[:12]}, clean and read-only", out)
        self.assertEqual((self.root.companions / "LOCK.json").read_text(encoding="utf-8"), before)

    def test_from_a_bundle(self) -> None:
        bundles = self.root.dir / "bundles"
        bundles.mkdir()
        git("bundle", "create", str(bundles / f"{self.root.name}.bundle"), "--all", cwd=self.root.source / self.root.name)
        code, out, err = run_main(fetch, self.args + ["--from", str(bundles)])
        self.assertEqual(code, 0, err)
        dest = self.root.companions / self.root.name
        self.assertEqual(fetch.head_of(dest), self.root.commit)
        self.assertEqual(fetch.writable_entries(dest), [])
        self.assertEqual((dest / "sim/api.cpp").read_text(encoding="utf-8").splitlines()[1], "  world->SetPaused(true);")
        entry = json.loads((self.root.companions / "LOCK.json").read_text(encoding="utf-8"))["clones"][0]
        self.assertTrue(entry["source"].endswith(f"{self.root.name}.bundle"), entry["source"])

    def test_a_lock_entry_that_would_re_pin_is_refused(self) -> None:
        for change in ({"commit": "f" * 40}, {"profile": "ros1-noetic-gazebo11"}, {"ref": "v1.1"},
                       {"repo_url": "https://github.com/acme/other.git"}):
            with self.subTest(change=change):
                lock = self.root.write_lock(self.root.lock_entry(**change))
                before = lock.read_text(encoding="utf-8")
                code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
                self.assertEqual(code, 1)
                self.assertIn("this tool never re-pins", err)
                self.assertFalse((self.root.companions / self.root.name).exists())
                self.assertEqual(lock.read_text(encoding="utf-8"), before)

    def test_needed_by_is_never_widened(self) -> None:
        lock = self.root.write_lock(self.root.lock_entry(needed_by=["gh.other/pkg"]))
        before = lock.read_text(encoding="utf-8")
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 1)
        self.assertIn(f"needed_by does not list ['{PACKAGE}']; widening it is a reviewed LOCK.json edit", err)
        self.assertFalse((self.root.companions / self.root.name).exists())
        self.assertEqual(lock.read_text(encoding="utf-8"), before)

    def test_a_needed_by_that_is_not_a_list_is_refused(self) -> None:
        # integrator edit I3 (Claude Sonnet safety F3 of p3-companion-2): an existing entry whose needed_by is the
        # package id as a bare string (a substring test would accept it) or is missing is refused, nothing is copied
        for value in (PACKAGE, None):
            with self.subTest(needed_by=value):
                lock = self.root.write_lock(self.root.lock_entry(needed_by=value))
                before = lock.read_text(encoding="utf-8")
                code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
                self.assertEqual(code, 1)
                self.assertIn(f"needed_by {value!r} is not a list", err)
                self.assertFalse((self.root.companions / self.root.name).exists())
                self.assertEqual(lock.read_text(encoding="utf-8"), before)
        listed = self.root.dir / "LOCK-copy.json"
        listed.write_text(json.dumps({"clones": [self.root.lock_entry(needed_by=PACKAGE)]}), encoding="utf-8")
        code, _out, err = run_main(fetch, ["--root", str(self.root.dir), "--lock", str(listed),
                                           "--from", str(self.root.source)])
        self.assertEqual(code, 2)
        self.assertIn("is not a list", err)
        self.assertFalse((self.root.companions / self.root.name).exists())

    def test_an_existing_writable_or_dirty_destination_is_left_as_it_is(self) -> None:
        dest = self.root.companions / self.root.name
        self.root.companions.mkdir(parents=True)
        shutil.copytree(self.root.source / self.root.name, dest, symlinks=True)  # at the pin, but writable
        before = modes(dest)
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 1)
        self.assertIn("write bits in the work tree", err)
        self.assertIn("(the existing directory is left as it is)", err)
        self.assertEqual(modes(dest), before)
        self.assertFalse((self.root.companions / "LOCK.json").exists())
        (dest / "notes.txt").write_text("an untracked file\n", encoding="utf-8")
        fetch.make_read_only(dest)
        before = modes(dest)
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 1)
        self.assertIn("the work tree is not clean", err)
        self.assertEqual(modes(dest), before)

    def test_a_copy_at_another_commit_is_never_moved_into_place(self) -> None:
        source = self.root.source / self.root.name
        (source / "sim/later.cpp").write_text("// a later commit\n", encoding="utf-8")
        git("add", "-A", cwd=source)
        git("commit", "-q", "-m", "later", cwd=source)
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 1)
        self.assertIn(f"not the pinned {self.root.commit[:12]}", err)
        self.assertIn("the staged copy stays in", err)
        self.assertFalse((self.root.companions / self.root.name).exists())
        self.assertFalse((self.root.companions / "LOCK.json").exists())

    def test_nothing_is_fetched_without_network(self) -> None:
        calls = []
        real = fetch.git

        def recording(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        with mock.patch.object(fetch, "git", recording):
            code, _out, err = run_main(fetch, self.args)
            self.assertEqual(code, 1)
            self.assertIn("is missing; pass --from DIR", err)
            self.assertFalse((self.root.companions / self.root.name).exists())
            code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
            self.assertEqual(code, 0, err)
        self.assertTrue(calls, "the copy is verified with git")
        self.assertEqual([call for call in calls if call[0] in ("fetch", "clone", "remote", "pull")], [])

    def test_the_network_step_fetches_the_pinned_commit_at_depth_one(self) -> None:
        calls = []
        real = fetch.git

        def answered(*args, **kwargs):
            calls.append(args)
            if args[0] == "fetch":  # never run: the test answers in place of the network
                return subprocess.CompletedProcess(["git", *args], 128, "", "fatal: answered by the test")
            return real(*args, **kwargs)

        with mock.patch.object(fetch, "git", answered):
            code, _out, err = run_main(fetch, self.args + ["--network"])
        self.assertEqual(code, 1)
        self.assertIn("git fetch failed for https://github.com/acme/sim.git", err)
        self.assertIn(("remote", "add", "origin", "https://github.com/acme/sim.git"), calls)
        self.assertIn(("fetch", "--quiet", "--depth", "1", "--no-tags", "origin", self.root.commit), calls)
        self.assertFalse((self.root.companions / self.root.name).exists())
        self.assertFalse((self.root.companions / "LOCK.json").exists())

    def test_git_runs_hardened(self) -> None:
        seen = {}

        def fake_run(command, **kwargs):
            seen["command"], seen["env"] = command, kwargs.get("env")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.dict(os.environ, {"GIT_CONFIG_PARAMETERS": "'core.hooksPath=/somewhere'"}), \
                mock.patch.object(fetch.subprocess, "run", fake_run):
            fetch.git("status", cwd=self.root.dir)
        command, env = seen["command"], seen["env"]
        self.assertEqual(command[:2], ["git", "--no-optional-locks"])
        self.assertIn(f"core.hooksPath={os.devnull}", command)
        self.assertIn("credential.helper=", command)
        self.assertIn("core.fsmonitor=false", command)  # integrator edit I4
        for key, value in {"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1", "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0"}.items():
            self.assertEqual(env.get(key), value, key)
        self.assertNotIn("GIT_CONFIG_PARAMETERS", env)
        injected = {"GIT_DIR": "/elsewhere/.git", "GIT_WORK_TREE": "/elsewhere", "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "/elsewhere/hook"}
        with mock.patch.dict(os.environ, injected), mock.patch.object(fetch.subprocess, "run", fake_run):
            fetch.git("status", cwd=self.root.dir)
        for key in injected:
            self.assertNotIn(key, seen["env"])

    def test_a_card_without_lock_companions_is_nothing_to_do(self) -> None:
        card = dict(self.root.card, companions=[{key: value for key, value in self.root.item().items()
                                                 if key not in ("lock", "ref")}])
        self.root.write_card(card)
        code, out, err = run_main(fetch, self.args)
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)


class CopiedConfigTests(unittest.TestCase):
    """Integrator edit I4 (Claude Sonnet safety F4 of p3-companion-2): the repository-local git configuration of a
    copied clone (or of an existing destination) never runs code. A marker script records every run: before the edit,
    ``git status`` in a copy ran the clone's ``core.fsmonitor`` hook and its ``filter`` clean command."""

    def setUp(self) -> None:
        self.root = Root(self)
        self.args = [str(self.root.driver), "--root", str(self.root.dir)]
        self.marker = self.root.dir / "marker"
        self.script = self.root.dir / "hostile.sh"
        self.script.write_text(f"#!/bin/sh\necho ran >> '{self.marker}'\ncat\n", encoding="utf-8")
        self.script.chmod(0o755)
        self.clone = self.root.source / self.root.name

    def configure(self, text: str, *, attributes: bool = False) -> None:
        with (self.clone / ".git" / "config").open("a", encoding="utf-8") as handle:
            handle.write(text)
        if attributes:
            (self.clone / ".git" / "info").mkdir(exist_ok=True)
            (self.clone / ".git" / "info" / "attributes").write_text("* filter=hostile\n", encoding="utf-8")

    def refused(self, needle: str) -> None:
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 1, err)
        self.assertIn(needle, err)
        self.assertIn("git was not run there", err)
        self.assertFalse(self.marker.exists(), "the clone's own configuration ran code")
        self.assertFalse((self.root.companions / self.root.name).exists())
        self.assertFalse((self.root.companions / "LOCK.json").exists())

    def test_a_copied_fsmonitor_hook_never_runs(self) -> None:
        self.configure(f"[core]\n\tfsmonitor = {self.script}\n")
        self.refused("fsmonitor")

    def test_a_copied_filter_driver_never_runs(self) -> None:
        self.configure(f'[filter "hostile"]\n\tclean = {self.script}\n\tsmudge = {self.script}\n', attributes=True)
        self.refused("is not allowed in a companion clone")

    def test_other_configuration_that_moves_or_extends_git_is_refused(self) -> None:
        cases = {"core.worktree": "[core]\n\tworktree = /elsewhere\n",
                 "core.hooksPath": "[core]\n\thooksPath = /elsewhere\n",
                 "an include": "[include]\n\tpath = /elsewhere/config\n",
                 "a bare repository": "[core]\n\tbare = true\n",
                 "a credential helper": "[credential]\n\thelper = store\n",
                 "a worktree configuration": "[extensions]\n\tworktreeConfig = true\n",
                 "a remote's upload command": '[remote "origin"]\n\tuploadpack = /elsewhere/hook\n',
                 "a legacy section": "[core.hostile]\n\tkey = 1\n",
                 "a key after a header": "[core] fsmonitor = /elsewhere/hook\n",
                 "a continued line": "[core]\n\tlogallrefupdates = \\\n\ttrue\n"}
        original = (self.clone / ".git" / "config").read_text(encoding="utf-8")
        for name, text in cases.items():
            with self.subTest(case=name):
                (self.clone / ".git" / "config").write_text(original, encoding="utf-8")
                self.configure(text)
                self.refused("companion clone" if name != "a continued line" else "continues a line")
        (self.clone / ".git" / "config").write_text(original, encoding="utf-8")
        (self.clone / ".git" / "commondir").write_text("/elsewhere/.git\n", encoding="utf-8")
        self.refused("commondir exists")
        (self.clone / ".git" / "commondir").unlink()
        # a .git that is a symbolic link to a git directory elsewhere (whose configuration this check never read)
        elsewhere = self.root.dir / "elsewhere-gitdir"
        (self.clone / ".git").rename(elsewhere)
        (self.clone / ".git").symlink_to(elsewhere, target_is_directory=True)
        self.refused(".git is not a plain directory")

    def test_an_existing_destination_with_a_hostile_configuration_is_left_as_it_is(self) -> None:
        self.configure(f"[core]\n\tfsmonitor = {self.script}\n")
        dest = self.root.install()
        before = modes(dest)
        code, _out, err = run_main(fetch, self.args)
        self.assertEqual(code, 1, err)
        self.assertIn("fsmonitor", err)
        self.assertIn("(the existing directory is left as it is)", err)
        self.assertFalse(self.marker.exists(), "the destination's own configuration ran code")
        self.assertEqual(modes(dest), before)

    def test_fsmonitor_is_off_even_where_a_configuration_slips_through(self) -> None:
        # the second layer on its own: git() itself never starts a repository's fsmonitor hook
        self.configure(f"[core]\n\tfsmonitor = {self.script}\n")
        os.utime(self.clone / "sim" / "api.cpp")  # a stat change makes git status look at the file
        done = fetch.git("status", "--porcelain", cwd=self.clone, hooks=Path(os.devnull))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(self.marker.exists())

    def test_a_clean_clone_still_copies(self) -> None:
        self.assertEqual(fetch.repository_problems(self.clone), [])
        code, _out, err = run_main(fetch, self.args + ["--from", str(self.root.source)])
        self.assertEqual(code, 0, err)


class ShowRefsLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Root(self)
        self.clone = self.root.install()
        self.args = [str(self.root.driver), "--root", str(self.root.dir)]

    def test_a_fetched_companion_header_and_its_citation(self) -> None:
        code, out, _err = run_main(show_refs, self.args)
        self.assertEqual(code, 0, out)
        self.assertIn(f"  lock   {ALIAS} (ref v1.0) in {self.root.companions / 'LOCK.json'}", out)
        self.assertIn("  LOCK   https://github.com/acme/sim.git ref v1.0 fetched None, licence Apache-2.0, "
                      f"needed_by ['{PACKAGE}']", out)
        self.assertIn("world->SetPaused(true);", out)
        self.assertIn("0 bad citation(s)", out)

    def test_a_lock_mismatch(self) -> None:
        self.root.write_lock(self.root.lock_entry(profile="ros1-noetic-gazebo11"))
        code, out, _err = run_main(show_refs, self.args)
        self.assertEqual(code, 1, out)
        self.assertIn(f"!! LOCK mismatch: profile 'ros1-noetic-gazebo11' != card '{PROFILE}'", out)
        self.root.write_lock(self.root.lock_entry(needed_by=["gh.other/pkg"]))
        code, out, _err = run_main(show_refs, self.args)
        self.assertEqual(code, 1, out)
        self.assertIn(f"!! LOCK mismatch: {PACKAGE} is not in needed_by", out)
        # integrator edit I3: a needed_by that is not a list (here the package id as a bare string, which a substring
        # test would accept) is a mismatch, as the gate refuses it
        for value in (PACKAGE, None):
            with self.subTest(needed_by=value):
                self.root.write_lock(self.root.lock_entry(needed_by=value))
                code, out, _err = run_main(show_refs, self.args)
                self.assertEqual(code, 1, out)
                self.assertIn(f"!! LOCK mismatch: needed_by {value!r} is not a list", out)

    def test_a_writable_work_tree(self) -> None:
        cited = self.clone / "sim" / "api.cpp"
        os.chmod(cited, stat.S_IMODE(os.lstat(cited).st_mode) | 0o200)
        code, out, _err = run_main(show_refs, self.args)
        self.assertEqual(code, 1, out)
        self.assertIn("!! writable work tree: ['sim/api.cpp']", out)

    def test_a_missing_clone_and_companions_root(self) -> None:
        moved = self.root.dir / "moved"
        self.root.companions.rename(moved)
        code, out, _err = run_main(show_refs, self.args)
        self.assertEqual(code, 1, out)
        self.assertIn(f"!! clone missing: {self.root.companions / self.root.name} (fetch it with "
                      "tools/fetch_companions.py)", out)
        code, out, _err = run_main(show_refs, self.args + ["--companions-root", str(moved)])
        self.assertEqual(code, 0, out)
        self.assertIn("0 bad citation(s)", out)


class CollectLockNoteTests(unittest.TestCase):
    def test_the_companion_source_note_names_the_lock_alias_or_the_missing_clone(self) -> None:
        root = Root(self)
        root.install()
        item = root.card["companions"][0]
        self.assertEqual(collect.companion_clone(root.dir, item), root.companions / root.name)
        self.assertEqual(collect.companion_clone(root.dir, item, root.dir / "other"), root.dir / "other" / root.name)
        notes = collect.companion_notes(root.dir, root.driver, root.card)
        self.assertEqual(notes, [f"COMPANION_SOURCE: sim_ros = {ALIAS}@{root.commit[:12]} ({PROFILE}): 1 fact "
                                 "citation(s); read them, the stop's binding citations and the version evidence with "
                                 "show_refs.py (REVIEW.md item 13)"])
        empty = root.dir / "empty"
        empty.mkdir()
        notes = collect.companion_notes(root.dir, root.driver, root.card, empty)
        self.assertEqual(notes, [f"COMPANION_SOURCE: sim_ros = {ALIAS}@{root.commit[:12]} ({PROFILE}): clone missing "
                                 f"at {empty / root.name}; fetch with tools/fetch_companions.py "
                                 "MHS/drivers/robots/acme__th1 [--from DIR]"])


if __name__ == "__main__":
    unittest.main()
