"""The handoff and repository tools (MHS/handoff/tools, tools/): behaviour on synthetic roots, so no corpus is needed."""

import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]


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


dispatch = load("handoff_dispatch", REPO / "MHS/handoff/tools/dispatch.py")
prepare = load("handoff_prepare", REPO / "MHS/handoff/tools/prepare.py")
# The model-orchestration kit (prompt templates, harness guide, wave runner, recon checker, pilot list) ships only in
# the workspace that runs model waves; the public release leaves it out, and its tests are skipped there.
KIT = REPO / "MHS/handoff"
HAS_KIT = all((KIT / name).exists() for name in ("PROMPT.md", "MASTER-PROMPT.md", "RECON-PROMPT.md", "HARNESS.md",
                                                  "harness-system.txt", "pilot-20.json", "tools/render_prompt.py",
                                                  "tools/run_wave.py", "tools/check_recon.py"))
NO_KIT = "the model-orchestration kit is not in this tree"
render_prompt = load("handoff_render_prompt", KIT / "tools/render_prompt.py") if HAS_KIT else None
collect = load("handoff_collect", REPO / "MHS/handoff/tools/collect.py")
show_refs = load("handoff_show_refs", REPO / "MHS/handoff/tools/show_refs.py")
run_wave = load("handoff_run_wave", KIT / "tools/run_wave.py") if HAS_KIT else None
check_recon = load("handoff_check_recon", KIT / "tools/check_recon.py") if HAS_KIT else None
fetch_clone = load("tools_fetch_clone", REPO / "tools/fetch_clone.py")
build_changelog = load("tools_build_changelog", REPO / "tools/build_changelog.py")
export_check = load("tools_oss_export_check", REPO / "tools/oss_export_check.py")


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd, check=True,
                   capture_output=True)


def make_clone(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    git("init", "-q", cwd=path)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "init", cwd=path)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, check=True).stdout.strip()


def card(package_id="gh.acme/widgetron", commit="0" * 40, **over):
    owner, repo = package_id[3:].split("/")
    base = {
        "package_id": package_id, "track": "labs", "local_path": f"labs/{owner}/{repo}",
        "driver_dir": f"MHS/drivers/labs/{owner}__{repo}", "upstream": {"repo_url": f"https://example.invalid/{owner}/{repo}",
                                                                          "commit": commit, "license_spdx": "MIT"},
        "decision": "direct-driver", "family": "python-object", "helper": "PythonObjectDriver", "helper_status": "available",
        "blocked_on": [], "quarantine": False, "package_status": "none", "wave": 2, "rank": 7,
        "exemplar": "MHS/drivers/labs/exemplar__one", "entry_symbols": [], "timebox_min": 60,
        "safety": {"expected_mode": "hardware", "risk_floor": "R1"}, "needs_recon": [], "publish_review": "not_required",
    }
    base.update(over)
    return base


class SyntheticRoot:
    """A repository root with the given cards, and a real git clone for the first one."""

    def __init__(self, cards, clone_files=None):
        self.dir = Path(tempfile.mkdtemp(prefix="handoff-tools-"))
        self.cards = cards
        self.commit = None
        if clone_files is not None:
            first = cards[0]
            self.commit = make_clone(self.dir / first["local_path"], clone_files)
            first["upstream"]["commit"] = self.commit
        for c in cards:
            target = self.dir / "MHS/registry/tasks" / c["track"] / (c["package_id"][3:].replace("/", "__") + ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(c, indent=1) + "\n", encoding="utf-8")

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


class DispatchTests(unittest.TestCase):
    def test_kinds(self):
        cases = {
            "dispatch": card(),
            "done": card(package_status="pass"),
            "quarantine": card(quarantine=True),
            "recon": card(decision="untriaged", helper=None, helper_status=None, family=None),
            "recon ": card(blocked_on=["recon:entry_symbol"]),
            "waiting-helper": card(helper=None, helper_status="blocked", blocked_on=["helper:ros"]),
            "skip": card(decision="skip", helper=None, helper_status=None),
            "bridge-runtime": card(decision="bridge-runtime"),
        }
        for expected, c in cases.items():
            self.assertEqual(dispatch.kind_of(c), expected.strip(), expected)

    def test_a_blocked_or_skip_proposed_package_is_not_given_out_again(self):
        for status in ("pass", "blocked", "skip-proposed"):
            self.assertTrue(dispatch.reasons_not_dispatchable(card(package_status=status)), status)
        self.assertFalse(dispatch.reasons_not_dispatchable(card(package_status="in_progress")))

    @unittest.skipUnless(HAS_KIT, NO_KIT)
    def test_the_shipped_pilot_file_is_dispatchable(self):
        code, out, _ = run_main(dispatch, ["--check-pilot", "--root", str(REPO)])
        self.assertEqual(code, 0, out)

    def test_a_pilot_card_with_a_result_is_finished_and_any_other_reason_is_a_problem(self):
        cards = [card("gh.acme/done", wave=1, package_status="pass"), card("gh.acme/waiting", wave=1, blocked_on=["helper:ros2"])]
        root = SyntheticRoot(cards)
        self.addCleanup(root.close)
        entries = [{"package_id": c["package_id"], "card": f"MHS/registry/tasks/labs/{c['package_id'][3:].replace('/', '__')}.json",
                    "bucket": "serial-scpi"} for c in cards]
        (root.dir / dispatch.PILOT_FILE).parent.mkdir(parents=True, exist_ok=True)
        (root.dir / dispatch.PILOT_FILE).write_text(json.dumps({"count": 2, "bucket_counts": {"serial-scpi": 2}, "entries": entries}))
        code, out, _ = run_main(dispatch, ["--check-pilot", "--root", str(root.dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("finished 1 {'pass': 1}", out)
        self.assertIn("gh.acme/waiting: not dispatchable", out)
        self.assertNotIn("gh.acme/done: not dispatchable", out)

    def test_stats_and_listing_on_the_real_cards(self):
        code, out, _ = run_main(dispatch, ["--stats", "--root", str(REPO)])
        self.assertEqual(code, 0)
        stats = json.loads(out)
        self.assertEqual(stats["cards"], sum(stats["by_kind"].values()))
        # Work moves between these sets as outcomes and recon proposals are recorded.
        self.assertGreater(stats["by_kind"].get("dispatch", 0) + stats["by_kind"].get("done", 0), 300)
        code, out, _ = run_main(dispatch, ["--ids", "--limit", "3", "--root", str(REPO)])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.split()), min(3, stats["by_kind"].get("dispatch", 0)))
        code, out, _ = run_main(dispatch, ["--recon", "--ids", "--limit", "3", "--root", str(REPO)])
        self.assertEqual((code, len(out.split())), (0, min(3, stats["by_kind"].get("recon", 0))))


class TodoTests(unittest.TestCase):
    """``dispatch.py --todo``: the next card nobody has started, for a loop that cannot rely on package_status yet."""

    def setUp(self):
        self.root = SyntheticRoot([card("gh.acme/first", wave=1, rank=1), card("gh.acme/second", wave=1, rank=2),
                                   card("gh.acme/third", wave=2, rank=1),
                                   card("gh.acme/recon-one", decision="untriaged", helper=None, helper_status=None, family=None,
                                        reason_code="untriaged:weak_entry")])
        self.addCleanup(self.root.close)

    def ids(self, *extra):
        code, out, err = run_main(dispatch, ["--root", str(self.root.dir), "--ids", *extra])
        self.assertEqual(code, 0, err)
        return out.split()

    def test_started_cards_are_left_out_whatever_became_of_them(self):
        self.assertEqual(self.ids("--todo"), ["gh.acme/first", "gh.acme/second", "gh.acme/third"])
        (self.root.dir / "MHS/drivers/labs/acme__first").mkdir(parents=True)          # an unfinished attempt counts as started
        self.assertEqual(self.ids("--todo", "--limit", "1"), ["gh.acme/second"])
        done = self.root.dir / "MHS/drivers/labs/acme__second"
        done.mkdir(parents=True)
        (done / "RESULT.json").write_text("{}")
        self.assertEqual(self.ids("--todo", "--limit", "1"), ["gh.acme/third"])
        self.assertEqual(self.ids("--todo", "--wave", "1"), [])
        self.assertEqual(self.ids(), ["gh.acme/first", "gh.acme/second", "gh.acme/third"], "without --todo nothing changes")

    def test_only_keeps_one_sessions_share_so_side_by_side_sessions_never_take_the_same_card(self):
        mine = ["--only", "gh.acme/third", "gh.acme/first"]
        self.assertEqual(self.ids("--todo", "--limit", "1", *mine), ["gh.acme/first"], "in card order, not the order given")
        (self.root.dir / "MHS/drivers/labs/acme__first").mkdir(parents=True)
        self.assertEqual(self.ids("--todo", "--limit", "1", *mine), ["gh.acme/third"], "gh.acme/second belongs to another session")
        (self.root.dir / "MHS/drivers/labs/acme__third").mkdir(parents=True)
        self.assertEqual(self.ids("--todo", "--limit", "1", *mine), [])
        self.assertEqual(self.ids("--todo", "--limit", "1", "--only", "gh.acme/second"), ["gh.acme/second"])

    def test_recon_cards_are_started_by_their_proposal_file(self):
        self.assertEqual(self.ids("--recon", "--todo"), ["gh.acme/recon-one"])
        proposal = self.root.dir / "MHS/handoff/recon/acme__recon-one.json"
        proposal.parent.mkdir(parents=True)
        proposal.write_text("{}")
        self.assertEqual(self.ids("--recon", "--todo"), [])
        self.assertEqual(self.ids("--recon"), ["gh.acme/recon-one"])


@unittest.skipUnless(HAS_KIT, NO_KIT)
class RenderPromptTests(unittest.TestCase):
    def test_a_dispatchable_card_renders_without_unfilled_placeholders(self):
        root = SyntheticRoot([card()])
        template_dir = root.dir / "MHS/handoff"
        template_dir.mkdir(parents=True)
        shutil.copy(REPO / "MHS/handoff/PROMPT.md", template_dir / "PROMPT.md")
        self.addCleanup(root.close)
        code, out, _ = run_main(render_prompt, ["gh.acme/widgetron", "--model-id", "m-1", "--run-id", "r-1", "--root", str(root.dir)])
        self.assertEqual(code, 0)
        self.assertIn("MHS/drivers/labs/acme__widgetron", out)
        self.assertIn("x-cap.acme.<name>.v1", out)
        self.assertIn('"model_id": "m-1"', out)
        self.assertNotIn("{DRIVER_DIR}", out)

    def test_a_passing_package_is_refused(self):
        root = SyntheticRoot([card(package_status="pass")])
        self.addCleanup(root.close)
        shutil.copytree(REPO / "MHS/handoff", root.dir / "MHS/handoff", ignore=shutil.ignore_patterns("__pycache__"))
        code, _, err = run_main(render_prompt, ["gh.acme/widgetron", "--model-id", "m", "--run-id", "r", "--root", str(root.dir)])
        self.assertEqual(code, 1)
        self.assertIn("not dispatchable", err)


class PrepareTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_a_real_run_copies_the_card(self):
        root = SyntheticRoot([card()], clone_files={"README.md": "x\n"})
        self.addCleanup(root.close)
        args = ["gh.acme/widgetron", "--root", str(root.dir)]
        code, out, _ = run_main(prepare, args + ["--dry-run"])
        self.assertEqual(code, 0, out)
        self.assertFalse((root.dir / "MHS/drivers").exists())
        code, out, err = run_main(prepare, args + ["--sandbox"])
        self.assertEqual(code, 0, err)
        driver_dir = root.dir / "MHS/drivers/labs/acme__widgetron"
        card_path = root.dir / "MHS/registry/tasks/labs/acme__widgetron.json"
        self.assertEqual((driver_dir / "task.json").read_bytes(), card_path.read_bytes())
        src = root.dir / "work/sandbox/acme__widgetron/src"
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(head, root.commit)
        self.assertTrue((root.dir / "work/sandbox/acme__widgetron/venv").is_dir())
        code, _, err = run_main(prepare, args)
        self.assertEqual(code, 1, "an existing task.json is never overwritten without --force")

    def test_sync_refreshes_task_json_from_the_rebuilt_card_and_nothing_else(self):
        root = SyntheticRoot([card()], clone_files={"README.md": "x\n"})
        self.addCleanup(root.close)
        self.assertEqual(run_main(prepare, ["gh.acme/widgetron", "--root", str(root.dir)])[0], 0)
        driver_dir = root.dir / "MHS/drivers/labs/acme__widgetron"
        (driver_dir / "driver.py").write_text("# the author's file\n")
        # nothing moved: nothing to refresh
        code, out, _ = run_main(prepare, ["--sync", "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("0 task.json refreshed", out)
        # the registry is rebuilt: the card says pass
        card_path = root.dir / "MHS/registry/tasks/labs/acme__widgetron.json"
        rebuilt = json.loads(card_path.read_text())
        rebuilt["package_status"] = "pass"
        card_path.write_text(json.dumps(rebuilt, indent=1) + "\n")
        code, out, _ = run_main(prepare, ["--sync", "--dry-run", "--root", str(root.dir)])
        self.assertIn("would refresh MHS/drivers/labs/acme__widgetron/task.json", out)
        self.assertNotEqual((driver_dir / "task.json").read_bytes(), card_path.read_bytes(), "a dry run writes nothing")
        code, out, _ = run_main(prepare, ["--sync", "gh.acme/widgetron", "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertEqual((driver_dir / "task.json").read_bytes(), card_path.read_bytes())
        self.assertEqual((driver_dir / "driver.py").read_text(), "# the author's file\n")
        # a package without a registry card is an error
        orphan = root.dir / "MHS/drivers/labs/nobody__here"
        orphan.mkdir(parents=True)
        (orphan / "task.json").write_text("{}")
        code, _, err = run_main(prepare, ["--sync", "--root", str(root.dir)])
        self.assertEqual(code, 1)
        self.assertIn("nobody__here has no registry card", err)

    def test_a_clone_at_another_commit_is_refused(self):
        root = SyntheticRoot([card()], clone_files={"README.md": "x\n"})
        self.addCleanup(root.close)
        cards = list((root.dir / "MHS/registry/tasks/labs").glob("*.json"))
        data = json.loads(cards[0].read_text())
        data["upstream"]["commit"] = "f" * 40
        cards[0].write_text(json.dumps(data))
        code, _, err = run_main(prepare, ["gh.acme/widgetron", "--root", str(root.dir)])
        self.assertEqual(code, 1)
        self.assertIn("pinned commit", err)


class ShowRefsTests(unittest.TestCase):
    def make(self, ref_line: str):
        root = SyntheticRoot([card()], clone_files={"src/lib.py": "A = 1\nMAX = 95\nB = 3\n"})
        self.addCleanup(root.close)
        driver_dir = root.dir / "MHS/drivers/labs/acme__widgetron"
        driver_dir.mkdir(parents=True)
        shutil.copy(root.dir / "MHS/registry/tasks/labs/acme__widgetron.json", driver_dir / "task.json")
        (driver_dir / "driver.py").write_text(
            "LIB = 'src/lib.py'\n"
            "x = Limit(min=0, max=95, source='upstream_code', ref=f\"{LIB}:%s\")\n" % ref_line, encoding="utf-8")
        return root, driver_dir

    def test_a_citation_prints_the_cited_line(self):
        root, driver_dir = self.make("2")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("MAX = 95", out)
        self.assertIn("0 bad citation", out)

    def test_a_line_beyond_the_file_is_reported(self):
        root, driver_dir = self.make("40")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 1)
        self.assertIn("the file has 3 lines", out)

    def test_a_gymnasium_action_space_ref_is_listed(self):
        root, driver_dir = self.make("2")
        with (driver_dir / "driver.py").open("a", encoding="utf-8") as handle:
            handle.write("class Env:\n    action_space_ref = f\"{LIB}:3\"\n")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("action_space_ref\n  cites src/lib.py:3", out)
        self.assertIn("B = 3", out)

    def test_a_ref_built_by_a_helper_is_followed(self):
        root, driver_dir = self.make("2")
        with (driver_dir / "driver.py").open("a", encoding="utf-8") as handle:
            handle.write("def _source(line):\n    return f\"{LIB}:{line}\"\n\n\n"
                         "_ROWS = (\n    ('max', 'src/lib.py:2'),\n    ('b', LIB + ':3'),\n)\n\n\n"
                         "def _limit(name, limit_ref):\n"
                         "    return Limit(min=0, max=95, source='upstream_code', ref=limit_ref)\n\n\n"
                         "y = {name: _limit(name, ref) for name, ref in _ROWS}\n"
                         "z = Fact('A is one', source='upstream_code', ref=_source('1'))\n")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("Limit via _limit('max')\n  cites src/lib.py:2\n  >    2  MAX = 95", out)
        self.assertIn("Limit via _limit('b')\n  cites src/lib.py:3\n  >    3  B = 3", out)
        self.assertIn("Fact('A is one')\n  cites src/lib.py:1\n  >    1  A = 1", out)
        self.assertNotIn("<not a constant>", out)

    def test_a_sensed_stop_s_fill_refs_and_history_are_listed(self):
        # SAFE-049: REVIEW.md item 5 asks the reviewer to read every fill_refs line and a ROS 2 source's cited
        # publisher history; show_refs prints both next to the clone's lines.
        root, driver_dir = self.make("2")
        with (driver_dir / "driver.py").open("a", encoding="utf-8") as handle:
            handle.write("_QOS = LIB + ':3'\n"
                         "S = {'sources': {'pose': {'fill_refs': {'pose.position': f\"{LIB}:2\"},\n"
                         "                          'history': {'durability': 'volatile', 'ref': _QOS}}}}\n")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("sensed fill_ref pose.position\n  cites src/lib.py:2\n  >    2  MAX = 95", out)
        self.assertIn("sensed history\n  cites src/lib.py:3\n  >    3  B = 3", out)

    def test_task_json_is_read_against_the_registry_card(self):
        root, driver_dir = self.make("2")
        card = json.loads((driver_dir / "task.json").read_text(encoding="utf-8"))
        (driver_dir / "task.json").write_text(json.dumps(dict(card, notes="edited by the package")), encoding="utf-8")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("!! task.json differs from the registry card MHS/registry/tasks/labs/acme__widgetron.json", out)
        companion = {"alias": "sim_ros", "package_id": "gh.acme/sim", "commit": "c" * 40, "local_path": "robots/acme/sim"}
        (driver_dir / "task.json").write_text(json.dumps(dict(card, companions=[companion], track="robots")),
                                              encoding="utf-8")
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("!! no registry card MHS/registry/tasks/robots/acme__widgetron.json confirms the companions", out)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class ShowRefsSubmoduleTests(unittest.TestCase):
    """A citation inside a git submodule is read at the gitlink commit of the pinned tree, as the gate reads it."""

    def make(self, *, moved: bool = False):
        from tests.driver import gate_support as gs
        from tests.driver import submodule_support as ss

        root = SyntheticRoot([card()], clone_files={"README.md": "parent\n"})
        self.addCleanup(root.close)
        clone = root.dir / "labs/acme/widgetron"
        sub_commit = ss.make_repo(root.dir / "origin-lib", {"lib.py": "A = 1\nMAX = 95\n"})
        ss.add_submodule(clone, "third_party/lib", root.dir / "origin-lib", sub_commit)
        gs.git(clone, "commit", "-q", "-m", "add the submodule")
        commit = gs.git(clone, "rev-parse", "HEAD")
        if moved:
            gs.git(clone / "third_party/lib", "commit", "-q", "--allow-empty", "-m", "a later commit")
        driver_dir = root.dir / "MHS/drivers/labs/acme__widgetron"
        driver_dir.mkdir(parents=True)
        (driver_dir / "task.json").write_text(json.dumps(card(commit=commit)), encoding="utf-8")
        # The registry card pins the same commit as task.json, as gate G1 requires (CARD_EDITED): show_refs reads the
        # registry card since p3-companion (integrator-v3 edit E5; the card SyntheticRoot wrote pins the clone's
        # first commit, which records no gitlink).
        (root.dir / "MHS/registry/tasks/labs/acme__widgetron.json").write_text(
            json.dumps(card(commit=commit), indent=1) + "\n", encoding="utf-8")
        (driver_dir / "driver.py").write_text(
            "x = Limit(min=0, max=95, source='upstream_code', ref='third_party/lib/lib.py:2')\n"
            "y = Fact('parent', source='vendor_doc', ref='README.md:1')\n", encoding="utf-8")
        return root, driver_dir, sub_commit

    def test_a_citation_in_a_submodule_is_read_at_the_gitlink(self):
        root, driver_dir, sub_commit = self.make()
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("MAX = 95", out)
        self.assertIn(f"(git submodule third_party/lib at {sub_commit[:12]}, the gitlink of the pinned commit", out)
        self.assertIn("parent", out)

    def test_a_submodule_at_another_commit_is_a_bad_citation(self):
        root, driver_dir, _sub_commit = self.make(moved=True)
        code, out, _ = run_main(show_refs, [str(driver_dir), "--root", str(root.dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("!! inside the git submodule third_party/lib:", out)
        self.assertIn("another commit", out)
        self.assertNotIn("MAX = 95", out)
        self.assertIn("1 bad citation", out)


class CollectTests(unittest.TestCase):
    def test_exemplar_residue_is_found(self):
        root = Path(tempfile.mkdtemp(prefix="collect-"))
        self.addCleanup(shutil.rmtree, root, True)
        exemplar = root / "MHS/drivers/labs/acme__widgetron"
        exemplar.mkdir(parents=True)
        (exemplar / "task.json").write_text(json.dumps(card(entry_symbols=[{"symbol": "widgetron.dev:Widget"}])))
        (root / "MHS/drivers/EXEMPLARS.txt").write_text("MHS/drivers/labs/acme__widgetron\n")
        mine = root / "MHS/drivers/labs/other__gadget"
        mine.mkdir(parents=True)
        (mine / "driver.py").write_text("# copied from widgetron\nclass Gadget: ...\n")
        own = card("gh.other/gadget", entry_symbols=[{"symbol": "gadget.dev:Gadget"}])
        self.assertEqual(len(collect.residue(root, mine, own)), 1)
        (mine / "driver.py").write_text("class Gadget: ...\n")
        self.assertEqual(collect.residue(root, mine, own), [])


class CollectVerdictTests(unittest.TestCase):
    """What collect.py reports for one package, with the gate itself replaced by a canned report."""

    DIGEST = "sha256:" + "ab" * 32

    def package(self, *, result=None, lock=None, driver="class D(Driver): ...\n", helper=None, decision="direct-driver",
                findings=()):
        root = Path(tempfile.mkdtemp(prefix="collect-verdict-"))
        self.addCleanup(shutil.rmtree, root, True)
        directory = root / "MHS/drivers/labs/acme__widgetron"
        directory.mkdir(parents=True)
        (directory / "task.json").write_text(json.dumps(card(helper=helper, decision=decision)))
        (directory / "driver.py").write_text(driver)
        if result is not None:
            (directory / "RESULT.json").write_text(json.dumps(result))
        if lock is not None:
            (directory / "driver.lock.json").write_text(json.dumps(lock))
        report = {"passed": True, "failed": [], "gates": [{"id": "G4", "findings": list(findings)}]}
        gate = {"exit_code": 0, "report": report, "stderr": ""}
        for name, value in (("run_gate", lambda r, d: gate), ("stable_digest_of", lambda r, rep: self.DIGEST)):
            patcher = mock.patch.object(collect, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return collect.summarise(root, directory)

    def passing(self, digest=DIGEST):
        return {"status": "pass", "gate": {"digest": digest, "failed": []}}

    def test_a_clean_pass_has_no_warning(self):
        row = self.package(result=self.passing())
        self.assertEqual((row["warnings"], row["accepted_by_reviewer"]), ([], []))

    def test_a_result_digest_that_is_not_this_gate_run_is_stale(self):
        row = self.package(result=self.passing("sha256:" + "cd" * 32))
        self.assertTrue(any(w.startswith("RESULT_DIGEST_STALE") for w in row["warnings"]), row["warnings"])
        row = self.package(result={"status": "pass", "gate": {"failed": []}})
        self.assertTrue(any(w.startswith("RESULT_DIGEST_STALE") for w in row["warnings"]), "a missing digest is stale too")

    def test_a_result_json_that_breaks_its_schema_is_a_warning(self):
        for label, result in (("blocked without codes", {"status": "blocked"}),
                              ("pass without a gate", {"status": "pass"}),
                              ("an unknown member", {**self.passing(), "verdict": "great"}),
                              ("a catalogue request without a reason",
                               {**self.passing(), "catalogue_requests": [{"capability_id": "x-cap.acme.thing.v1"}]})):
            with self.subTest(label):
                row = self.package(result=result)
                self.assertTrue(any(w.startswith("RESULT_SCHEMA") for w in row["warnings"]), row["warnings"])
        row = self.package(result={**self.passing(), "catalogue_requests": [
            {"capability_id": "x-cap.acme.thing.v1", "reason": "no class fits", "verb": "invoke"}]})
        self.assertFalse(any(w.startswith("RESULT_SCHEMA") for w in row["warnings"]), row["warnings"])

    def test_a_citation_into_a_binary_file_is_not_hidden(self):
        pdf = {"code": "G4.REF_BINARY", "severity": "warning", "path": "cap.x.v1 volume", "ref": "docs/manual.pdf:12"}
        value = {"code": "G4.REF_VALUE", "severity": "warning", "path": "cap.y.v1 port", "ref": "pkg/models.py:441-444"}
        row = self.package(result=self.passing(), findings=[pdf, value])
        text = "\n".join(row["warnings"])
        self.assertIn("UNVERIFIABLE_CITATION: cap.x.v1 volume: docs/manual.pdf:12", text)
        self.assertIn("UNSOURCED_LIMIT_GATE_WARNING: cap.y.v1 port: a reviewer must read pkg/models.py:441-444", text)

    def test_signing_reviewed_by_accepts_exactly_those_two_kinds(self):
        pdf = {"code": "G4.REF_BINARY", "severity": "warning", "path": "cap.x.v1 volume", "ref": "docs/manual.pdf:12"}
        value = {"code": "G4.REF_VALUE", "severity": "warning", "path": "cap.y.v1 port", "ref": "pkg/models.py:441"}
        lock = {"reviewed_by": {"reviewer": "A. Person", "date": "2026-11-02", "scope": "contract"}}
        row = self.package(result=self.passing(), lock=lock, findings=[pdf, value])
        self.assertEqual(row["warnings"], [])
        self.assertEqual(len(row["accepted_by_reviewer"]), 2)
        self.assertEqual(row["reviewer"], "A. Person")
        row = self.package(result=self.passing("sha256:" + "cd" * 32), lock=lock, findings=[value])
        self.assertTrue(row["warnings"], "a reviewer does not accept a stale RESULT.json")

    def test_other_gate_warnings_are_notes_that_never_fail_strict(self):
        warn = {"code": "G8.NO_UNIT", "severity": "warning", "path": "ticks"}
        row = self.package(result=self.passing(), findings=[warn, warn])
        self.assertEqual(row["warnings"], [])
        self.assertIn("gate warnings: G8.NO_UNIT x2", " ".join(row["notes"]))

    def test_a_submodule_source_is_a_note_that_never_fails_strict(self):
        source = {"code": "G1.SUBMODULE_SOURCE", "severity": "warning", "path": "third_party/lib",
                  "message": "third_party/lib/ is the git submodule 'lib': the gates read it at " + "e" * 40}
        row = self.package(result=self.passing(), findings=[source])
        self.assertEqual(row["warnings"], [])
        notes = " ".join(row["notes"])
        self.assertIn("SUBMODULE_SOURCE: third_party/lib/ is the git submodule 'lib'", notes)
        self.assertNotIn("gate warnings", notes)

    def test_a_family_config_card_written_as_a_direct_driver_is_a_note(self):
        row = self.package(result=self.passing(), helper="SerialDriver", decision="family-config")
        self.assertTrue(any(n.startswith("DECISION_DEVIATION") for n in row["notes"]), row["notes"])
        self.assertEqual(row["warnings"], [])
        row = self.package(result=self.passing(), helper="SerialDriver", decision="family-config",
                           driver="class D(SerialDriver): ...\n")
        self.assertEqual(row["notes"], [])
        row = self.package(result=self.passing(), helper="PythonObjectDriver", decision="direct-driver")
        self.assertEqual(row["notes"], [], "a direct-driver card may use Driver or its family helper")


class CollectResidueTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="collect-residue-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        exemplar = self.root / "MHS/drivers/robots/farama__gymnasium"
        exemplar.mkdir(parents=True)
        (exemplar / "task.json").write_text(json.dumps(card("gh.farama/gymnasium", entry_symbols=[
            {"symbol": "gymnasium.envs.classic_control.cartpole:CartPoleEnv"}], family="gymnasium", helper="GymnasiumDriver")))
        (exemplar / "driver.py").write_text('class Cart(GymnasiumDriver):\n    device_id = "cartpole"\n    env_id = "CartPole-v1"\n'
                                           '    native = "gymnasium.envs.classic_control.cartpole:CartPoleEnv"\n')
        (self.root / "MHS/drivers/EXEMPLARS.txt").write_text("MHS/drivers/robots/farama__gymnasium\n")
        self.mine = self.root / "MHS/drivers/robots/hf__gym-aloha"
        self.mine.mkdir(parents=True)
        self.own = card("gh.hf/gym-aloha", family="gymnasium", helper="GymnasiumDriver",
                        entry_symbols=[{"symbol": "gym_aloha.env:AlohaEnv"}])

    def test_the_family_vocabulary_of_an_exemplar_is_not_residue(self):
        (self.mine / "driver.py").write_text("from mhs.driver import GymnasiumDriver\nenv = 'gymnasium.make'  # a Gymnasium environment\n")
        (self.mine / "fake.py").write_text("# mujoco and gymnasium are named as the bridge families\n")
        self.assertEqual(collect.residue(self.root, self.mine, self.own), [])

    def test_the_exemplars_device_identity_is_residue_in_any_text_file(self):
        (self.mine / "driver.py").write_text("class A(GymnasiumDriver): ...\n")
        (self.mine / "site-limits.example.json").write_text('{"note": "CartPole-v1 push"}')
        found = collect.residue(self.root, self.mine, self.own)
        self.assertEqual(len(found), 1, found)
        self.assertIn("site-limits.example.json", found[0])
        (self.mine / "site-limits.example.json").unlink()
        (self.mine / "fixtures").mkdir()
        (self.mine / "fixtures" / "session.json").write_text('{"native": "CartPoleEnv"}')
        self.assertIn("fixtures/session.json", collect.residue(self.root, self.mine, self.own)[0])

    def test_a_name_that_a_cited_upstream_line_shows_is_not_residue(self):
        # robust-gymnasium registers its own CartPole-v1, and the package cites that registration (wave B).
        clone = self.root / self.own["local_path"] / "gym_aloha"
        clone.mkdir(parents=True)
        (clone / "__init__.py").write_text("register(\n    id='CartPole-v1',\n    max_episode_steps=500,\n)\n")
        (self.mine / "driver.py").write_text('class A(GymnasiumDriver):\n    env_id = "CartPole-v1"\n')
        self.assertEqual(len(collect.residue(self.root, self.mine, self.own)), 1, "nothing cited yet")
        (self.mine / "reference.json").write_text(json.dumps({"facts": [{"ref": "gym_aloha/__init__.py:1-4",
                                                                          "text": "CartPole-v1 is registered"}]}))
        self.assertEqual(collect.residue(self.root, self.mine, self.own), [])
        (self.mine / "reference.json").write_text(json.dumps({"facts": [{"ref": "gym_aloha/__init__.py:3"}]}))
        self.assertEqual(len(collect.residue(self.root, self.mine, self.own)), 1, "a line that does not show it")

    def test_generated_and_prose_files_are_not_scanned(self):
        for name in ("RESULT.json", "reference.json", "REFERENCE.md", "driver.lock.json", "check-report.json"):
            (self.mine / name).write_text("CartPole-v1 CartPoleEnv cartpole")
        self.assertEqual(collect.residue(self.root, self.mine, self.own), [])


@unittest.skipUnless(HAS_KIT, NO_KIT)
class RunWaveTests(unittest.TestCase):
    """The batch loop with a stub agent: it writes RESULT.json (or misbehaves) and the runner records what happened."""

    def setUp(self):
        self.root = SyntheticRoot([card()], clone_files={"README.md": "x\n"})
        self.addCleanup(self.root.close)
        (self.root.dir / "MHS/handoff").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "MHS/handoff/PROMPT.md", self.root.dir / "MHS/handoff/PROMPT.md")
        self.stub = self.root.dir / "stub_agent.py"
        self.stub.write_text(
            "import json, sys, time\n"
            "prompt, driver_dir, mode = sys.argv[1:4]\n"
            "text = open(prompt, encoding='utf-8').read()\n"
            "assert 'gh.acme/widgetron' in text and 'MODEL-X' in text, text[:200]\n"
            "if mode == 'hang':\n    time.sleep(30)\n"
            "if mode == 'crash':\n    sys.exit(3)\n"
            "if mode in ('git', 'git-scrubbed'):\n"
            "    import os, re, subprocess\n"
            "    env = dict(os.environ)\n"
            "    if mode == 'git-scrubbed':  # the DeepSeek Harness drops credential-shaped names from its tools' environment\n"
            "        env = {k: v for k, v in env.items() if not re.search('KEY|PASSWORD|SECRET|TOKEN', k, re.I)}\n"
            "    hooks = subprocess.run(['git', 'config', '--get', 'core.hooksPath'], capture_output=True, text=True, env=env)\n"
            "    open(driver_dir + '/hooks.txt', 'w').write(hooks.stdout.strip() or hooks.stderr.strip())\n"
            "json.dump({'status': 'blocked', 'blocked_on': ['NOT_A_DEVICE'], 'notes': 'stub'}, open(driver_dir + '/RESULT.json', 'w'))\n",
            encoding="utf-8")

    def args(self, mode="ok", *extra):
        command = shlex.join([sys.executable, str(self.stub), "{PROMPT_FILE}", "{DRIVER_DIR}", mode])
        return ["--root", str(self.root.dir), "--model-id", "MODEL-X", "--batch", "b1", "--agent-cmd", command, *extra]

    def summary(self):
        path = self.root.dir / "work/handoff-runs/b1/summary.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_dry_run_prints_the_command_and_creates_nothing(self):
        code, out, err = run_main(run_wave, self.args("ok", "--dry-run"))
        self.assertEqual(code, 0, err)
        self.assertIn("would prepare MHS/drivers/labs/acme__widgetron", out)
        self.assertIn("work/handoff-runs/b1/acme__widgetron.prompt.txt", out)
        self.assertFalse((self.root.dir / "MHS/drivers").exists())
        self.assertFalse((self.root.dir / "work").exists())

    def test_a_run_prepares_renders_runs_the_agent_and_records_the_outcome(self):
        code, out, err = run_main(run_wave, self.args("ok"))
        self.assertEqual(code, 0, out + err)
        rows = self.summary()
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual((row["package_id"], row["outcome"], row["result_json_status"], row["agent_exit"]),
                         ("gh.acme/widgetron", "blocked", "blocked", 0))
        self.assertEqual(row["run_id"], "b1-001")
        driver_dir = self.root.dir / "MHS/drivers/labs/acme__widgetron"
        self.assertEqual((driver_dir / "task.json").read_bytes(), (self.root.dir / "MHS/registry/tasks/labs/acme__widgetron.json").read_bytes())
        self.assertIn("MODEL-X", (self.root.dir / "work/handoff-runs/b1/acme__widgetron.prompt.txt").read_text())
        self.assertTrue((self.root.dir / "work/handoff-runs/b1/acme__widgetron.agent.log").exists())

    def test_an_existing_directory_is_skipped_and_redo_moves_it_aside(self):
        driver_dir = self.root.dir / "MHS/drivers/labs/acme__widgetron"
        driver_dir.mkdir(parents=True)
        (driver_dir / "keep.txt").write_text("earlier work")
        code, out, _ = run_main(run_wave, self.args("ok"))
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)
        self.assertEqual(self.summary(), [])
        self.assertEqual((driver_dir / "keep.txt").read_text(), "earlier work")
        code, out, err = run_main(run_wave, self.args("ok", "--redo"))
        self.assertEqual(code, 0, out + err)
        moved = list((self.root.dir / "work/handoff-runs/b1/moved-aside").glob("acme__widgetron-*/keep.txt"))
        self.assertEqual(len(moved), 1, "the old directory is moved, never deleted")
        self.assertFalse((driver_dir / "keep.txt").exists())
        self.assertEqual(len(self.summary()), 1)

    def test_a_crashing_and_a_hanging_agent_need_attention(self):
        code, out, _ = run_main(run_wave, self.args("crash"))
        self.assertEqual(code, 1)
        self.assertEqual(self.summary()[-1]["outcome"], "agent_error")
        self.assertEqual(self.summary()[-1]["agent_exit"], 3)
        code, out, _ = run_main(run_wave, self.args("hang", "--redo", "--timeout-min", "0.02"))
        self.assertEqual(code, 1)
        self.assertEqual(self.summary()[-1]["outcome"], "agent_timeout")
        self.assertTrue(self.summary()[-1]["agent_timed_out"])

    def test_the_agent_runs_git_with_the_hooks_of_the_run_not_of_a_clone(self):
        # Recon wave B: a git status over an LFS file let git-lfs install its hooks into a clone's .git/hooks.
        code, out, err = run_main(run_wave, self.args("git"))
        self.assertEqual(code, 0, out + err)
        hooks = self.root.dir / "work/handoff-runs/b1/git-hooks"
        self.assertTrue(hooks.is_dir())
        told = Path((self.root.dir / "MHS/drivers/labs/acme__widgetron/hooks.txt").read_text())
        self.assertEqual(told.resolve(), hooks.resolve())

    def test_the_hooks_setting_survives_a_harness_that_drops_credential_shaped_names(self):
        # Wave D: GIT_CONFIG_KEY_0 was dropped, GIT_CONFIG_COUNT kept, and every git command of the agents failed.
        code, out, err = run_main(run_wave, self.args("git-scrubbed"))
        self.assertEqual(code, 0, out + err)
        told = (self.root.dir / "MHS/drivers/labs/acme__widgetron/hooks.txt").read_text()
        self.assertEqual(Path(told).resolve(), (self.root.dir / "work/handoff-runs/b1/git-hooks").resolve(), told)

    def test_a_card_that_cannot_be_given_out_is_refused_before_anything_runs(self):
        code, _, err = run_main(run_wave, self.args("ok", "--ids", "gh.nobody/nothing"))
        self.assertEqual(code, 2)
        self.assertIn("no such card", err)
        self.assertFalse((self.root.dir / "work").exists())
        code, _, err = run_main(run_wave, ["--root", str(self.root.dir), "--model-id", "M", "--agent-cmd", "x 'unclosed"])
        self.assertEqual(code, 2)
        self.assertIn("--agent-cmd", err)


@unittest.skipUnless(HAS_KIT, NO_KIT)
class ParallelRunWaveTests(unittest.TestCase):
    """--jobs: cards run side by side, each row records the tokens its agent reported, and stray writes are listed."""

    NAMES = ("widgetron", "gadget", "doohickey")
    STEPS = [{"inputTokens": 100, "outputTokens": 10, "cacheReadTokens": 900, "totalTokens": 1010},
             {"inputTokens": 50, "outputTokens": 5, "cacheReadTokens": 950, "totalTokens": 1005}]

    def setUp(self):
        cards = [card(f"gh.acme/{name}", rank=number) for number, name in enumerate(self.NAMES)]
        self.root = SyntheticRoot(cards, clone_files={"README.md": "x\n"})
        self.addCleanup(self.root.close)
        for extra in cards[1:]:
            extra["upstream"]["commit"] = make_clone(self.root.dir / extra["local_path"], {"README.md": "x\n"})
            target = self.root.dir / "MHS/registry/tasks/labs" / (extra["package_id"][3:].replace("/", "__") + ".json")
            target.write_text(json.dumps(extra, indent=1) + "\n", encoding="utf-8")
        (self.root.dir / "MHS/handoff").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "MHS/handoff/PROMPT.md", self.root.dir / "MHS/handoff/PROMPT.md")
        self.stub = self.root.dir / "stub_agent.py"
        self.stub.write_text(
            "import json, os, sys, time\n"
            "driver_dir, mode, root = sys.argv[1:4]\n"
            "barrier = os.path.join(root, 'barrier')\n"
            "os.makedirs(barrier, exist_ok=True)\n"
            "open(os.path.join(barrier, os.path.basename(driver_dir)), 'w').close()\n"
            "deadline = time.time() + 20\n"
            "while mode == 'together' and len(os.listdir(barrier)) < 3 and time.time() < deadline:\n    time.sleep(0.05)\n"
            "if mode == 'together' and len(os.listdir(barrier)) < 3:\n    sys.exit(4)\n"
            "if mode == 'hang':\n    time.sleep(60)\n"
            "if mode == 'stray' and driver_dir.endswith('gadget'):\n"
            "    open(os.path.join(root, 'MHS', 'registry', 'stray.txt'), 'w').write('x')\n"
            "if mode == 'gitinfo' and driver_dir.endswith('gadget'):\n"
            "    attributes = os.path.join(root, 'labs', 'acme', 'gadget', '.git', 'info', 'attributes')\n"
            "    os.makedirs(os.path.dirname(attributes), exist_ok=True)\n"
            "    open(attributes, 'w').write('* binary\\n')\n"
            "    os.remove(attributes)\n"
            f"for usage in {self.STEPS!r}:\n"
            "    print(json.dumps({'type': 'status', 'phase': 'step_end', 'usage': usage}))\n"
            "json.dump({'status': 'blocked', 'blocked_on': ['NOT_A_DEVICE'], 'notes': 'stub'}, open(driver_dir + '/RESULT.json', 'w'))\n",
            encoding="utf-8")

    def run_wave(self, mode, *extra):
        command = shlex.join([sys.executable, str(self.stub), "{DRIVER_DIR}", mode, str(self.root.dir)])
        return run_main(run_wave, ["--root", str(self.root.dir), "--model-id", "M", "--batch", "b2", "--agent-cmd", command,
                                   "--ids", *(f"gh.acme/{name}" for name in self.NAMES), *extra])

    def summary(self):
        path = self.root.dir / "work/handoff-runs/b2/summary.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_three_jobs_run_three_cards_at_the_same_time(self):
        code, out, err = self.run_wave("together", "--jobs", "3")
        self.assertEqual(code, 0, out + err)
        rows = self.summary()
        self.assertEqual(sorted(row["package_id"] for row in rows), sorted(f"gh.acme/{name}" for name in self.NAMES))
        self.assertEqual({row["agent_exit"] for row in rows}, {0}, "each agent saw the other two running")
        self.assertEqual(sorted(row["run_id"] for row in rows), ["b2-001", "b2-002", "b2-003"])
        self.assertIn("3 at a time", out)

    def test_each_row_records_the_tokens_its_agent_reported(self):
        code, out, err = self.run_wave("alone", "--jobs", "2")
        self.assertEqual(code, 0, out + err)
        for row in self.summary():
            self.assertEqual(row["usage"], {"inputTokens": 150, "outputTokens": 15, "cacheReadTokens": 1850,
                                            "totalTokens": 2015, "steps": 2})
        self.assertIn("tokens of 3 card(s): 0.0M tokens, 92% cached (450 input, 5,550 cache read, 45 output)", out)

    def test_a_file_written_outside_the_cards_directories_needs_attention(self):
        code, out, err = self.run_wave("stray", "--jobs", "3")
        self.assertEqual(code, 1, out + err)
        listed = (self.root.dir / "work/handoff-runs/b2/outside-writes.txt").read_text().split()
        self.assertEqual(listed, ["MHS/registry/stray.txt"], "the cards' own driver directories are not listed")
        self.assertIn("1 file(s) changed outside", out)

    def test_a_git_setting_written_in_a_clone_and_removed_needs_attention(self):
        # git attributes decide what `git status` reports, so the gate's clone check would not see a file they hide
        code, out, err = self.run_wave("gitinfo", "--jobs", "3")
        self.assertEqual(code, 1, out + err)
        listed = (self.root.dir / "work/handoff-runs/b2/outside-writes.txt").read_text().split()
        self.assertEqual(listed, ["labs/acme/gadget/.git/info"])

    def test_jobs_below_one_is_a_usage_error(self):
        code, _, err = self.run_wave("alone", "--jobs", "0")
        self.assertEqual(code, 2)
        self.assertIn("--jobs", err)

    def test_an_interrupt_stops_the_agents_and_redo_unfinished_resumes(self):
        command = shlex.join([sys.executable, str(self.stub), "{DRIVER_DIR}", "hang", str(self.root.dir)])
        runner_command = shlex.join([sys.executable, str(REPO / "MHS/handoff/tools/run_wave.py"), "--root", str(self.root.dir),
                                     "--model-id", "M", "--batch", "b2", "--agent-cmd", command, "--jobs", "2",
                                     "--ids", *(f"gh.acme/{name}" for name in self.NAMES)])
        # Started with SIGINT ignored, as a background job of a non-interactive shell starts it: SIGINT still stops it.
        runner = subprocess.Popen(["/bin/sh", "-c", f"trap '' INT; exec {runner_command}"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: runner.poll() is None and runner.kill())
        barrier = self.root.dir / "barrier"
        deadline = time.monotonic() + 30
        while (not barrier.is_dir() or len(list(barrier.iterdir())) < 2) and time.monotonic() < deadline:
            time.sleep(0.05)
        runner.send_signal(signal.SIGINT)  # to the runner alone: it must stop its agents itself
        out, err = runner.communicate(timeout=60)
        self.assertEqual(runner.returncode, 130, out + err)
        self.assertNotIn("Traceback", err)
        rows = self.summary()
        self.assertEqual([row["outcome"] for row in rows], ["interrupted", "interrupted"], rows)
        self.assertIn("--redo-unfinished", out)
        drivers = self.root.dir / "MHS/drivers/labs"
        self.assertFalse((drivers / "acme__doohickey").exists(), "the third card never started")

        (drivers / "acme__gadget" / "RESULT.json").write_text('{"status": "blocked", "blocked_on": ["NOT_A_DEVICE"], "notes": "x"}')
        code, out, err = self.run_wave("alone", "--jobs", "3", "--redo-unfinished")
        self.assertEqual(code, 0, out + err)
        self.assertIn("gh.acme/gadget: skipped", out, "a directory with a RESULT.json is kept")
        again = {row["package_id"]: row["outcome"] for row in self.summary()[2:]}
        self.assertEqual(again, {"gh.acme/widgetron": "blocked", "gh.acme/doohickey": "blocked"})
        self.assertEqual(len(list((self.root.dir / "work/handoff-runs/b2/moved-aside").iterdir())), 1)


RECON_CLONE = {"README.md": "# Widgetron\nA pump driver.\n",
               "widgetron/pump.py": "import serial\n\nclass Pump:\n    def __init__(self, port):\n        self.port = serial.Serial(port)\n"}


@unittest.skipUnless(HAS_KIT, NO_KIT)
class ReconTests(unittest.TestCase):
    """Recon proposals: the prompt, the checker, the override draft and the runner's recon mode."""

    def setUp(self):
        self.root = SyntheticRoot([card(decision="untriaged", helper=None, helper_status=None, family=None,
                                        reason_code="untriaged:weak_entry", timebox_min=30)], clone_files=RECON_CLONE)
        self.addCleanup(self.root.close)
        for name in ("MHS/handoff/RECON-PROMPT.md",):
            (self.root.dir / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / name, self.root.dir / name)
        (self.root.dir / "MHS/registry/schema").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "MHS/registry/schema/overrides.schema.json", self.root.dir / "MHS/registry/schema/overrides.schema.json")
        self.recon_dir = self.root.dir / "MHS/handoff/recon"
        self.recon_dir.mkdir(parents=True, exist_ok=True)

    def proposal(self, **over):
        doc = {"package_id": "gh.acme/widgetron",
               "proposed": {"strategy": "direct-driver", "role": "device-driver", "family": "python-object"},
               "entry_symbols": [{"symbol": "widgetron.pump:Pump", "file": "widgetron/pump.py", "line": 3}],
               "evidence": ["widgetron/pump.py:5 the constructor opens the serial port", "README.md:2 says it is a pump driver"],
               "notes": "A syringe pump driven through pyserial by one class. The port is the only constructor argument."}
        doc.update(over)
        return doc

    def write(self, doc, name="acme__widgetron.json"):
        path = self.recon_dir / name
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
        return path

    def check(self, *paths, extra=()):
        return run_main(check_recon, [*(str(p) for p in paths), "--root", str(self.root.dir), *extra])

    def test_a_good_proposal_passes_and_becomes_an_override_entry(self):
        path = self.write(self.proposal())
        draft = self.root.dir / "draft.json"
        code, out, err = self.check(path, extra=["--emit-overrides", str(draft), "--show"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("OK   ", out)
        self.assertIn("widgetron/pump.py:3  class Pump:", out)
        entry = json.loads(draft.read_text())["overrides"]
        self.assertEqual(entry, [{"package_id": "gh.acme/widgetron", "strategy": "direct-driver", "role": "device-driver",
                                  "family": "python-object", "reason_code": "override:recon",
                                  "entry_symbols": [{"symbol": "widgetron.pump:Pump", "file": "widgetron/pump.py", "line": 3}],
                                  "justification": "A syringe pump driven through pyserial by one class."}])
        # the draft is a valid override file
        from mhs.schema import SchemaStore
        store = SchemaStore(str(REPO / "MHS/schema"), extra_roots=[str(REPO / "MHS/registry/schema")])
        self.assertEqual(store.validate(json.loads(draft.read_text()), "overrides.schema.json"), [])

    def test_an_entry_file_outside_the_pinned_tree_is_refused(self):
        # Recon wave B: an entry class in a submodule passed the working-tree check, but the gate reads the pinned tree.
        clone = self.root.dir / "labs/acme/widgetron"
        (clone / "widgetron/extra.py").write_text("class Pump:\n    pass\n", encoding="utf-8")  # never committed
        path = self.write(self.proposal(entry_symbols=[{"symbol": "widgetron.extra:Pump", "file": "widgetron/extra.py",
                                                        "line": 1}]))
        code, out, err = self.check(path)
        self.assertEqual(code, 1, out + err)
        self.assertIn("not in the clone's tree at the pinned commit", out + err)

    def test_every_kind_of_defect_is_named(self):
        cases = {
            "unknown member": (self.proposal(verdict="yes"), "unknown member"),
            "bad strategy": (self.proposal(proposed={"strategy": "driver", "role": "device-driver"}), "proposed.strategy"),
            "no family": (self.proposal(proposed={"strategy": "family-config", "role": "device-driver"}), "proposed.family is required"),
            "role": (self.proposal(proposed={"strategy": "direct-driver", "role": "tooling", "family": "python-object"}), "not 'tooling'"),
            "skip as driver role": (self.proposal(proposed={"strategy": "skip", "role": "device-driver"}), "a skip cannot have the role"),
            "no symbol": (self.proposal(entry_symbols=[]), "needs at least one entry symbol"),
            "wrong line": (self.proposal(entry_symbols=[{"symbol": "widgetron.pump:Pump", "file": "widgetron/pump.py", "line": 5}]), "not defined at"),
            "line out": (self.proposal(entry_symbols=[{"symbol": "widgetron.pump:Pump", "file": "widgetron/pump.py", "line": 99}]), "outside"),
            "no file": (self.proposal(entry_symbols=[{"symbol": "w.x:Pump", "file": "w/x.py", "line": 1}]), "not a file of the clone"),
            "evidence path": (self.proposal(evidence=["nowhere.py:1 something"]), "not a file of the clone"),
            "evidence shape": (self.proposal(evidence=["it is a pump"]), "must start with path:LINE"),
            "evidence line": (self.proposal(evidence=["README.md:40 beyond the end"]), "outside README.md"),
            "empty evidence": (self.proposal(evidence=[]), "evidence must be"),
            "short notes": (self.proposal(notes="Pump."), "notes must be"),
            "non-English notes": (self.proposal(notes="A syringe pump (\u6ce8\u5c04\u6cf5) driven through pyserial by one class."), "English only"),
            "non-English evidence": (self.proposal(evidence=["README.md:2 the title is \u6ce8\u5c04\u6cf5"]), "English only"),
            "home path": (self.proposal(evidence=["README.md:2 the README cites C:/" + "Users/someone/pump"]), "home-directory path"),
            "unknown card": (self.proposal(package_id="gh.nobody/nothing"), "is not a task card"),
        }
        for name, (doc, expected) in cases.items():
            with self.subTest(name):
                code, out, _ = self.check(self.write(doc))
                self.assertEqual(code, 1, out)
                self.assertIn(expected, out)
        code, out, _ = self.check(self.write("{not json"))
        self.assertEqual(code, 1)
        self.assertIn("not readable JSON", out)

    def test_the_file_name_and_the_state_of_the_card_are_checked(self):
        code, out, _ = self.check(self.write(self.proposal(), name="wrong-name.json"))
        self.assertEqual(code, 1)
        self.assertIn("must be named acme__widgetron.json", out)
        card_path = self.root.dir / "MHS/registry/tasks/labs/acme__widgetron.json"
        moved = json.loads(card_path.read_text())
        moved.update(decision="direct-driver", helper="PythonObjectDriver", helper_status="available")
        card_path.write_text(json.dumps(moved))
        path = self.write(self.proposal())
        code, out, _ = self.check(path)
        self.assertIn("not a recon card", out)
        self.assertEqual(self.check(path, extra=["--force"])[0], 0)

    def test_the_file_is_named_after_the_driver_directory_of_the_card(self):
        card_path = self.root.dir / "MHS/registry/tasks/labs/acme__widgetron.json"
        renamed = json.loads(card_path.read_text())
        renamed["driver_dir"] = "MHS/drivers/labs/acme__widgetron-"  # a clone directory with a trailing dash
        card_path.write_text(json.dumps(renamed))
        code, out, _ = self.check(self.write(self.proposal()))
        self.assertEqual(code, 1)
        self.assertIn("must be named acme__widgetron-.json", out)
        self.assertEqual(self.check(self.write(self.proposal(), name="acme__widgetron-.json"))[0], 0)
        code, out, err = run_main(render_prompt, ["gh.acme/widgetron", "--recon", "--root", str(self.root.dir), "--model-id", "M", "--run-id", "R"])
        self.assertEqual(code, 0, err)
        self.assertIn("MHS/handoff/recon/acme__widgetron-.json", out)

    def test_all_checks_every_file_and_exit_code_two_means_nothing_to_check(self):
        self.write(self.proposal())
        code, out, _ = self.check(extra=["--all"])
        self.assertEqual(code, 0, out)
        self.write("{}", name="other__thing.json")
        self.assertEqual(self.check(extra=["--all"])[0], 1)
        for item in self.recon_dir.glob("*.json"):
            item.unlink()
        self.assertEqual(self.check(extra=["--all"])[0], 2)

    def test_the_recon_prompt_is_for_recon_cards_only(self):
        args = ["gh.acme/widgetron", "--root", str(self.root.dir), "--model-id", "MODEL-X", "--run-id", "run-7"]
        code, out, err = run_main(render_prompt, [*args, "--recon"])
        self.assertEqual(code, 0, err)
        self.assertIn("MHS/handoff/recon/acme__widgetron.json", out)
        self.assertIn("labs/acme/widgetron is a read-only upstream clone", out)
        self.assertNotIn("{PACKAGE_ID}", out)
        self.assertIn('"reason_code": "untriaged:weak_entry"', out)
        code, _, err = run_main(render_prompt, args)
        self.assertEqual(code, 1, "a recon card is not a driver task")
        shutil.copy(REPO / "MHS/handoff/PROMPT.md", self.root.dir / "MHS/handoff/PROMPT.md")
        driver_card = SyntheticRoot([card("gh.other/gadget")])
        self.addCleanup(driver_card.close)
        (driver_card.dir / "MHS/handoff").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "MHS/handoff/RECON-PROMPT.md", driver_card.dir / "MHS/handoff/RECON-PROMPT.md")
        code, _, err = run_main(render_prompt, ["gh.other/gadget", "--recon", "--root", str(driver_card.dir), "--model-id", "M", "--run-id", "R"])
        self.assertEqual(code, 1)
        self.assertIn("not a recon card", err)

    def test_the_runner_in_recon_mode_runs_the_agent_and_checks_the_proposal(self):
        stub = self.root.dir / "stub_recon.py"
        stub.write_text("import json, sys\nprompt, out, mode = sys.argv[1:4]\n"
                        "assert 'RECON task' in open(prompt, encoding='utf-8').read() or 'recon task' in open(prompt, encoding='utf-8').read()\n"
                        "if mode == 'ok':\n    json.dump(" + repr(self.proposal()) + ", open(out, 'w'))\n"
                        "elif mode == 'bad':\n    json.dump({'package_id': 'gh.acme/widgetron'}, open(out, 'w'))\n", encoding="utf-8")
        def args(mode, *extra):
            command = shlex.join([sys.executable, str(stub), "{PROMPT_FILE}", "{RECON_FILE}", mode])
            return ["--root", str(self.root.dir), "--model-id", "MODEL-X", "--batch", "r1", "--recon", "--agent-cmd", command, *extra]

        def summary():
            return [json.loads(line) for line in (self.root.dir / "work/handoff-runs/r1/summary.jsonl").read_text().splitlines()]

        code, out, err = run_main(run_wave, args("ok"))
        self.assertEqual(code, 0, out + err)
        row = summary()[-1]
        self.assertEqual((row["kind"], row["outcome"], row["recon_valid"]), ("recon", "recon_valid", True))
        self.assertEqual(row["override"]["strategy"], "direct-driver")
        self.assertTrue((self.recon_dir / "acme__widgetron.json").exists())
        code, out, _ = run_main(run_wave, args("bad", "--redo"))
        self.assertEqual(code, 1)
        row = summary()[-1]
        self.assertEqual((row["outcome"], row["recon_valid"]), ("recon_invalid", False))
        self.assertTrue(any("missing member" in problem for problem in row["problems"]))
        self.assertEqual(len(list((self.root.dir / "work/handoff-runs/r1/moved-aside").glob("acme__widgetron-*.json"))), 1)


@unittest.skipUnless(HAS_KIT, NO_KIT)
class MasterPromptTests(unittest.TestCase):
    """The prompt typed into an interactive harness: filled in, and made only of commands the kit really has."""

    def master(self, *extra):
        code, out, err = run_main(render_prompt, ["--master", "--model-id", "deepseek-test", "--root", str(REPO), *extra])
        self.assertEqual(code, 0, err)
        return out

    def test_the_driver_prompt_is_filled_in(self):
        out = self.master("--batch", "pilot1", "--batch-size", "4", "--select", "--wave 2 --publishable", "--report-language", "Chinese")
        self.assertIn("Model id to record: deepseek-test", out)
        self.assertIn("Repository limit for this session: 4", out)
        self.assertIn("work/handoff-runs/pilot1/progress.txt", out)
        self.assertIn("dispatch.py --todo --ids --limit 1 --wave 2 --publishable`", out)
        self.assertIn("FINAL MESSAGE (Chinese)", out)
        self.assertNotRegex(out, r"\{[A-Z_]{4,}\}")
        self.assertNotIn("--recon", out)

    def test_the_default_selection_is_the_pilot_for_drivers_and_none_for_recon(self):
        self.assertIn("--limit 1 --pilot`", self.master())
        recon = self.master("--recon")
        self.assertIn("dispatch.py --recon --todo --ids --limit 1`", recon)
        self.assertIn("render_prompt.py PKG --recon", recon)
        self.assertIn("check_recon.py PROPOSAL", recon)
        self.assertNotIn("prepare.py", recon)

    def test_every_command_the_prompts_name_exists_with_those_options(self):
        for recon in (False, True):
            text = self.master(*(["--recon"] if recon else []))
            for script, args in re.findall(r"python3 MHS/handoff/tools/([a-z_]+\.py)([^`]*)`", text):
                path = REPO / "MHS/handoff/tools" / script
                self.assertTrue(path.is_file(), script)
                help_text = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True, check=True).stdout
                for option in re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", args):
                    self.assertIn(option, help_text, f"{script} has no {option}")

    def test_the_commands_the_page_shows_run(self):
        """The two commands of MASTER-PROMPT.md, as written there, with a model name filled in."""
        page = (REPO / "MHS/handoff/MASTER-PROMPT.md").read_text(encoding="utf-8")
        block = re.search(r"```sh\n(.*?)```", page, re.S).group(1)
        commands = [line for line in block.splitlines() if "render_prompt.py" in line]
        self.assertEqual(len(commands), 2)
        for line in commands:
            words = shlex.split(line.split(">", 1)[0].replace("<MODEL_NAME>", "deepseek-test"))
            code, out, err = run_main(render_prompt, [*words[2:], "--root", str(REPO)])
            self.assertEqual(code, 0, f"{line}: {err}")
            self.assertIn("SYSTEM", out)

    def test_bad_arguments_are_refused(self):
        for extra in (["gh.a/b"], ["--batch", "../x"], ["--batch-size", "0"], ["--run-id", "r"]):
            with self.subTest(extra):
                code, _out, _err = run_main(render_prompt, ["--master", "--model-id", "m", "--root", str(REPO), *extra])
                self.assertEqual(code, 2)

    def test_both_per_repository_prompts_ask_for_english_files(self):
        for name in ("PROMPT.md", "RECON-PROMPT.md"):
            self.assertIn("English only", (REPO / "MHS/handoff" / name).read_text(encoding="utf-8"), name)


@unittest.skipUnless(HAS_KIT, NO_KIT)
class HarnessDocTests(unittest.TestCase):
    def test_the_system_prompt_file_is_the_text_the_harness_guide_shows(self):
        text = (REPO / "MHS/handoff/harness-system.txt").read_text(encoding="utf-8").strip()
        guide = (REPO / "MHS/handoff/HARNESS.md").read_text(encoding="utf-8")
        self.assertIn(text, guide, "HARNESS.md must reproduce harness-system.txt verbatim")
        self.assertNotRegex(text, r"[{}]", "the system prompt has no placeholder")

    def test_the_commands_the_guide_shows_use_options_run_wave_has(self):
        guide = (REPO / "MHS/handoff/HARNESS.md").read_text(encoding="utf-8")
        help_text = subprocess.run([sys.executable, str(REPO / "MHS/handoff/tools/run_wave.py"), "--help"], capture_output=True,
                                   text=True, check=True).stdout
        for line in guide.splitlines():
            if "run_wave.py" in line and line.lstrip().startswith("python3"):
                for option in re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", line.split("--agent-cmd", 1)[0]):
                    self.assertIn(option, help_text, f"{option} in the guide is not an option of run_wave.py")

    def test_every_document_the_kit_readme_links_exists(self):
        readme = (REPO / "MHS/handoff/README.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([A-Za-z0-9_./-]+\.(?:md|txt|json|py))\)", readme):
            self.assertTrue((REPO / "MHS/handoff" / target).is_file(), target)


class NoBytecodeTests(unittest.TestCase):
    """The tools import each other: a run without PYTHONDONTWRITEBYTECODE must not leave a __pycache__ in the kit."""

    def test_running_a_tool_leaves_no_bytecode_behind(self):
        copy = Path(tempfile.mkdtemp(prefix="kit-tools-"))
        self.addCleanup(shutil.rmtree, copy, True)
        for source in (REPO / "MHS/handoff/tools").glob("*.py"):
            shutil.copy(source, copy / source.name)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        for tool in ("prepare", "render_prompt", "run_wave", "check_recon", "collect", "show_refs", "dispatch"):
            if not (copy / f"{tool}.py").exists():
                continue
            subprocess.run([sys.executable, str(copy / f"{tool}.py"), "--help"], env=env, capture_output=True, check=True)
        self.assertEqual([p.name for p in copy.rglob("__pycache__")], [], "a tool wrote bytecode next to itself")


class FetchCloneTests(unittest.TestCase):
    def test_fetch_from_a_local_source_then_a_second_call_is_a_no_op(self):
        source = Path(tempfile.mkdtemp(prefix="fetch-src-"))
        self.addCleanup(shutil.rmtree, source, True)
        commit = make_clone(source / "up", {"a.txt": "hello\n"})
        root = SyntheticRoot([card(commit=commit)])
        self.addCleanup(root.close)
        args = ["gh.acme/widgetron", "--root", str(root.dir)]
        code, out, err = run_main(fetch_clone, args + ["--source", str(source / "up")])
        self.assertEqual(code, 0, err)
        dest = root.dir / "labs/acme/widgetron"
        self.assertEqual(subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True).stdout.strip(), commit)
        code, out, _ = run_main(fetch_clone, args)
        self.assertEqual(code, 0)
        self.assertIn("already at", out)


class ChangelogTests(unittest.TestCase):
    def test_a_new_fragment_makes_check_fail_until_rebuilt(self):
        root = Path(tempfile.mkdtemp(prefix="changelog-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "MHS/changes").mkdir(parents=True)
        (root / "MHS/changes/WP-01.md").write_text("# WP-01 — First\n\nThe first paragraph.\n\n- a bullet\n")
        (root / "CHANGELOG.md").write_text(f"# Changelog\n\n{build_changelog.BEGIN}\n{build_changelog.END}\n")
        self.assertEqual(run_main(build_changelog, ["--check", "--root", str(root)])[0], 1)
        self.assertEqual(run_main(build_changelog, ["--root", str(root)])[0], 0)
        self.assertEqual(run_main(build_changelog, ["--check", "--root", str(root)])[0], 0)
        text = (root / "CHANGELOG.md").read_text()
        self.assertIn("### WP-01 — First", text)
        self.assertIn("The first paragraph.", text)
        (root / "MHS/changes/WP-02.md").write_text("# WP-02 — Second\n\nMore.\n")
        self.assertEqual(run_main(build_changelog, ["--check", "--root", str(root)])[0], 1)

    def test_the_shipped_changelog_lists_every_fragment(self):
        self.assertEqual(run_main(build_changelog, ["--check", "--root", str(REPO)])[0], 0)


class ExportCheckTests(unittest.TestCase):
    """Check export structure and local path leaks without editorial restrictions."""

    def problems(self, extra=None):
        files = {rel: "text\n" for rel in export_check.REQUIRED}
        files.update(extra or {})
        root = Path(tempfile.mkdtemp(prefix="export-"))
        self.addCleanup(shutil.rmtree, root, True)
        for rel, text in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return export_check.static_checks(root, sorted(files))

    def test_a_clean_tree_has_no_problem(self):
        self.assertEqual(self.problems(), [])

    def test_local_paths_and_private_inputs_are_found(self):
        home = "/" + "Users" + "/someone/project"
        self.assertTrue(any("home-directory" in p for p in self.problems({"MHS/notes.md": home})))
        scratch = "/private/" + "tmp/x"
        self.assertTrue(any("home-directory" in p for p in self.problems({"MHS/notes.md": scratch})))
        self.assertTrue(any("allowlist" in p for p in self.problems({"labs/x/y.py": "x\n"})))

    def test_publication_accepts_language_domain_and_project_headings(self):
        text = chr(0x4E2D) + chr(0x6587)
        self.assertEqual(self.problems({
            "MHS/notes.md": text,
            "README.md": "# OpenMHS — Model Hardware Standard\n",
            "MHS/site/deploy/CNAME": "mhs.openai4s.org\n",
        }), [])


if __name__ == "__main__":
    unittest.main()
