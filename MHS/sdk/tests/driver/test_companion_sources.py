"""Companion sources (user decision 2026-11-05): a stop may cite a locally cloned companion repository at a pinned
commit, through a reviewed card field (``companions``) and ``companion:<alias>/<path>:<LINE>`` citations.

Covered: the citation grammar (the old parser refuses it, the new one accepts only clean paths and card-form aliases);
G7 scope (the e-stop, its read-back and the declared re-enable only), declared aliases and the read-back rule (a call
other than the stop however either name is spelled); G1 (the registry card confirms the companions of task.json;
clone, git top, HEAD at the pin, unmodified tracked files before and after, version evidence); G2 (the lock repeats
the card); G4 (companion facts resolve at the pin; a bound, the physical stop and an undeclared alias are refused);
the scaffold's lock; and that a card without companions sees no new finding.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.driver.check import Gate, _Context, _g1, _g1_after, _g2, _g4, _g7
from mhs.driver.package import scaffold
from mhs.driver.ros_check import _may_name_the_same_endpoint
from mhs.driver.upstream import (CompanionSource, UpstreamTree, companion_sources, is_companion_ref, parse_ref,
                                 parse_source_ref)
from mhs.testing.recorder import RecordLog

from tests.driver import gate_support as gs

#: A gazebo_ros-like API plugin (test fixture, not upstream code): the pause, the read-back field and the unpause.
API_CPP = """// companion API plugin fixture
std::string pause_physics_service_name("pause_physics");
ros::AdvertiseServiceOptions pause_physics_aso =
  ros::AdvertiseServiceOptions::create<std_srvs::Empty>(pause_physics_service_name, cb, &queue);
std::string unpause_physics_service_name("unpause_physics");
ros::AdvertiseServiceOptions unpause_physics_aso =
  ros::AdvertiseServiceOptions::create<std_srvs::Empty>(unpause_physics_service_name, cb, &queue);
std::string get_physics_properties_service_name("get_physics_properties");
ros::AdvertiseServiceOptions get_physics_properties_aso =
  ros::AdvertiseServiceOptions::create<gazebo_msgs::GetPhysicsProperties>(get_physics_properties_service_name, cb);
bool pausePhysics(Request &req, Response &res) { world_->SetPaused(true); return true; }
bool unpausePhysics(Request &req, Response &res) { world_->SetPaused(false); return true; }
res.pause = world_->IsPaused();
res.time_step = engine->GetMaxStepSize();
"""
VERSION_TXT = "gazebo_ros 2.9.3\ndistro: ROS Noetic, catkin\n"
PACKAGE_README = "# TH-1 simulation\n\nRuns on ROS Noetic.\nBuilt with catkin.\n"
ALIAS = "sim_ros"
PAUSE = {"service": "/gazebo/pause_physics", "type": "std_srvs/Empty", "source_name": "pause_physics",
         "source_ref": f"companion:{ALIAS}/src/api.cpp:2-4", "type_ref": f"companion:{ALIAS}/src/api.cpp:4",
         "state_ref": f"companion:{ALIAS}/src/api.cpp:11", "request": {}, "success": {"path": "$", "equals": {}},
         "timeout_ms": 500}
READBACK = {"service": "/gazebo/get_physics_properties", "type": "gazebo_msgs/GetPhysicsProperties",
            "source_name": "get_physics_properties", "source_ref": f"companion:{ALIAS}/src/api.cpp:8-10",
            "type_ref": f"companion:{ALIAS}/src/api.cpp:10", "state_ref": f"companion:{ALIAS}/src/api.cpp:13",
            "request": {}, "success": {"path": "pause", "equals": True}, "timeout_ms": 500}
RESUME = {"service": "/gazebo/unpause_physics", "type": "std_srvs/Empty", "source_name": "unpause_physics",
          "source_ref": f"companion:{ALIAS}/src/api.cpp:5-7", "type_ref": f"companion:{ALIAS}/src/api.cpp:7",
          "success": {"path": "$", "equals": {}}}
WIRE = [{"op": "call_service", "service": "/gazebo/pause_physics", "type": "std_srvs/Empty"},
        {"op": "call_service", "service": "/gazebo/get_physics_properties", "type": "gazebo_msgs/GetPhysicsProperties"},
        {"op": "call_service", "service": "/gazebo/unpause_physics", "type": "std_srvs/Empty"}]


def companion_repo(test, root: Path, rel: str = "robots/acme/sim", files=None) -> tuple[Path, str]:
    clone = root / rel
    clone.mkdir(parents=True)
    for name, text in (files or {"src/api.cpp": API_CPP, "VERSION.txt": VERSION_TXT}).items():
        (clone / name).parent.mkdir(parents=True, exist_ok=True)
        (clone / name).write_text(text)
    gs.git(clone, "init", "-q")
    gs.git(clone, "add", "-A")
    gs.git(clone, "commit", "-q", "-m", "companion")
    return clone, gs.git(clone, "rev-parse", "HEAD")


def card_entry(commit: str, *, alias: str = ALIAS, rel: str = "robots/acme/sim", evidence=None) -> dict:
    return {"alias": alias, "package_id": "gh.acme/sim", "commit": commit, "profile": "ros1-noetic-gazebo11",
            "reason": "the pause, its read-back and the unpause are served by this companion (fixture)",
            "version_evidence": evidence if evidence is not None else [
                {"side": "package", "ref": "README.md:3", "token": "ROS Noetic"},
                {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"}],
            "local_path": rel, "repo_url": "https://github.com/acme/sim", "license_spdx": "Apache-2.0"}


class GrammarTests(unittest.TestCase):
    def test_the_old_parser_refuses_a_companion_citation(self) -> None:
        self.assertIsNone(parse_ref("companion:gazebo_ros_pkgs/gazebo_ros/src/api.cpp:492-498"))

    def test_the_new_parser_returns_the_alias_and_the_reference(self) -> None:
        alias, ref = parse_source_ref("companion:gazebo_ros_pkgs/gazebo_ros/src/api.cpp:492-498")
        self.assertEqual((alias, ref.path, ref.line, ref.end), ("gazebo_ros_pkgs", "gazebo_ros/src/api.cpp", 492, 498))
        self.assertTrue(is_companion_ref("companion:x/y"))

    def test_a_clone_citation_is_returned_as_parse_ref_returns_it(self) -> None:
        self.assertEqual(parse_source_ref("src/a.cpp:3-4"), (None, parse_ref("src/a.cpp:3-4")))

    def test_traversal_unclean_paths_and_bad_aliases_are_refused(self) -> None:
        for text in ("companion:ab/../x.cpp:1", "companion:ab/./x.cpp:1", "companion:ab//x.cpp:1",
                     "companion:ab/x.cpp", "companion:ab/x.cpp:0", "companion:/x.cpp:1", "companion:A/x.cpp:1",
                     "companion:a/x.cpp:1", "companion:ab/x.cpp:3-2", "companion:ab", "companion:a b/x.cpp:1",
                     "companion:ab/x.cpp:1:2", None, 7):
            with self.subTest(text=text):
                self.assertIsNone(parse_source_ref(text))

    def test_companion_sources_reads_the_card_and_reports_bad_entries(self) -> None:
        good = card_entry("a" * 40)
        sources, problems = companion_sources({"package_id": "gh.acme/th1", "companions": [good]}, Path("/nonexistent"))
        self.assertEqual(problems, [])
        self.assertIsNone(sources[ALIAS].tree)  # the clone is missing: G1 reports NO_COMPANION_CLONE
        for bad, expected in ((dict(good, alias="Bad"), "alias"), (dict(good, commit="abc"), "commit"),
                              (dict(good, package_id="gh.acme/th1"), "package_id"),
                              (dict(good, local_path="../x/y"), "local_path"), (dict(good, profile="noetic"), "profile")):
            with self.subTest(expected=expected):
                found, problems = companion_sources({"package_id": "gh.acme/th1", "companions": [bad]}, None)
                self.assertEqual(found, {})
                self.assertIn(expected, problems[0])
        _found, problems = companion_sources({"package_id": "gh.acme/th1", "companions": [good, good]}, None)
        self.assertIn("declared twice", problems[0])
        _found, problems = companion_sources({"package_id": "gh.acme/th1", "companions": [good] * 4}, None)
        self.assertIn("1 to 3", problems[0])


class RosCompanionScopeTests(unittest.TestCase):
    """Gate G7 on declared bindings: scope, declared aliases, the read-back rule."""

    def setUp(self) -> None:
        root = gs.temp_root(self)
        _clone, commit = companion_repo(self, root)
        self.package_tree = UpstreamTree(root / "robots" / "acme" / "sim", commit)  # any pinned tree will do
        (root / "pkg").mkdir()
        (root / "pkg" / "node.cpp").write_text('pub = nh.advertise<std_msgs::Float64>("level", 1);\n')
        self.tree = UpstreamTree(root / "pkg", use_git=False)
        self.companions, problems = companion_sources({"package_id": "gh.acme/th1",
                                                       "companions": [card_entry(commit)]}, root)
        self.assertEqual(problems, [])
        self.level = {"topic": "/level", "type": "std_msgs/Float64", "source_name": "level",
                      "source_ref": "node.cpp:1", "path": "data"}

    def context(self, *, commands=None, reads=None, writes=None, safety=None, reenable=None, companions=None,
                wire=WIRE):
        actions = {key: SimpleNamespace(reenable=key == reenable) for key in (commands or {})}
        declared = SimpleNamespace(commands=commands or {}, reads=reads or {}, writes=writes or {},
                                   safety_bindings=safety or {}, actions=actions, ros_version=1)
        log = RecordLog("ros fake")
        for message in wire:
            log.record("send", "call", (message,))
        return SimpleNamespace(cls=declared, tree=self.tree, logs=[log], family="ros",
                               companions=self.companions if companions is None else companions)

    def codes(self, ctx) -> list[str]:
        gate = Gate("G7", "Native surface")
        _g7(ctx, gate)
        return [finding.code for finding in gate.findings if finding.severity == "error"]

    def stop(self, **changes):
        return {"estop": dict(PAUSE, **changes.get("estop", {})), "safe_state": dict(READBACK, **changes.get("safe_state", {}))}

    def test_stop_read_back_and_declared_re_enable_may_cite_the_companion(self) -> None:
        ctx = self.context(commands={"x-cap.acme.resume.v1": RESUME}, safety=self.stop(),
                           reenable="x-cap.acme.resume.v1")
        self.assertEqual(self.codes(ctx), [])

    def test_a_companion_citation_anywhere_else_is_out_of_scope(self) -> None:
        reading = dict(self.level, source_ref=f"companion:{ALIAS}/src/api.cpp:2")
        cases = {
            "reads": dict(reads={"level": reading}, safety=self.stop()),
            "an ordinary command": dict(commands={"x-cap.acme.resume.v1": RESUME}, safety=self.stop()),
            "reset": dict(safety=dict(self.stop(), reset=RESUME)),
            "interlock": dict(safety=dict(self.stop(), interlocks=[dict(reading, id="door")])),
            "writes": dict(writes={"level": dict(RESUME)}, safety=self.stop()),
        }
        for name, case in cases.items():
            with self.subTest(name=name):
                self.assertIn("G7.ROS_COMPANION_SCOPE", self.codes(self.context(**case)))

    def test_an_undeclared_alias_is_refused(self) -> None:
        estop = dict(PAUSE, source_ref="companion:other_sim/src/api.cpp:2-4")
        self.assertIn("G7.ROS_COMPANION_UNDECLARED", self.codes(self.context(safety=self.stop(estop=estop))))
        self.assertIn("G7.ROS_COMPANION_UNDECLARED", self.codes(self.context(safety=self.stop(), companions={})))

    def test_a_companion_stop_needs_a_read_back_of_a_state_field(self) -> None:
        cases = {
            "no read-back": {"estop": PAUSE},
            "whole response": self.stop(safe_state={"success": {"path": "$", "equals": {}}}),
            "not a scalar": self.stop(safe_state={"success": {"path": "pause", "equals": {"a": 1}}}),
            "null": self.stop(safe_state={"success": {"path": "pause", "equals": None}}),
            "no read-back state_ref": {"estop": PAUSE, "safe_state": {k: v for k, v in READBACK.items()
                                                                       if k != "state_ref"}},
            "no stop state_ref": {"estop": {k: v for k, v in PAUSE.items() if k != "state_ref"},
                                  "safe_state": READBACK},
            "field not shown": self.stop(safe_state={"state_ref": f"companion:{ALIAS}/src/api.cpp:14"}),
            "a topic": self.stop(safe_state={"service": None}),
        }
        for name, safety in cases.items():
            if name == "a topic":
                safety = {"estop": PAUSE, "safe_state": {k: v for k, v in READBACK.items() if k != "service"}
                          | {"topic": "/gazebo/get_physics_properties"}}
            with self.subTest(name=name):
                self.assertIn("G7.ROS_COMPANION_READBACK", self.codes(self.context(safety=safety)))

    def readback_messages(self, safety) -> list[str]:
        gate = Gate("G7", "Native surface")
        _g7(self.context(safety=safety), gate)
        return [finding.message for finding in gate.findings if finding.code == "G7.ROS_COMPANION_READBACK"]

    def test_the_read_back_is_a_call_other_than_the_stop_however_it_is_spelled(self) -> None:
        # Everything else about this read-back is right (a scalar state field that its state_ref line shows), so
        # only the distinct-call rule can refuse it.
        same = dict(PAUSE, success={"path": "pause", "equals": True}, state_ref=f"companion:{ALIAS}/src/api.cpp:13")
        for spelling in ("/gazebo/pause_physics", "gazebo/pause_physics", "pause_physics", "~pause_physics",
                         "~/pause_physics"):
            with self.subTest(spelling=spelling):
                messages = self.readback_messages(self.stop(safe_state=dict(same, service=spelling)))
                self.assertTrue(any("distinct from the stop" in message for message in messages), messages)
                # Verification F2: a name of another kind than the stop's is never shown to be in its world either.
                self.assertEqual(len(messages), 1 if spelling.startswith("/") else 2, messages)
        self.assertEqual(self.readback_messages(self.stop(safe_state=dict(
            same, service="/gazebo/get_physics_properties"))), [])

    def test_graph_names_are_compared_after_resolving_their_spelling(self) -> None:
        for first, second in (("/gazebo/pause_physics", "/gazebo/pause_physics"),
                              ("/gazebo/pause_physics", "gazebo/pause_physics"),
                              ("/gazebo/pause_physics", "pause_physics"), ("/gazebo/pause_physics", "~pause_physics"),
                              ("~/pause_physics", "~pause_physics"), ("pause_physics", "pause_physics")):
            with self.subTest(first=first, second=second):
                self.assertTrue(_may_name_the_same_endpoint(first, second))
                self.assertTrue(_may_name_the_same_endpoint(second, first))
        for first, second in (("/gazebo/pause_physics", "/gazebo/get_physics_properties"),
                              ("/a/pause_physics", "/b/pause_physics"), ("gazebo/pause_physics", "pause_physics"),
                              ("/gazebo/pause_physics", "physics"), (None, "/gazebo/pause_physics")):
            with self.subTest(first=first, second=second):
                self.assertFalse(_may_name_the_same_endpoint(first, second))

    def test_a_companion_read_back_needs_the_stop_it_confirms(self) -> None:
        self.assertIn("G7.ROS_COMPANION_READBACK", self.codes(self.context(safety={"safe_state": READBACK})))

    def test_endpoint_and_type_literals_are_checked_in_the_companion_text(self) -> None:
        wrong_line = self.stop(estop={"source_ref": f"companion:{ALIAS}/src/api.cpp:5-7"})
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.codes(self.context(safety=wrong_line)))
        wrong_type = self.stop(estop={"type_ref": f"companion:{ALIAS}/src/api.cpp:10"})
        self.assertIn("G7.ROS_TYPE_NOT_UPSTREAM", self.codes(self.context(safety=wrong_type)))
        beyond = self.stop(estop={"state_ref": f"companion:{ALIAS}/src/api.cpp:99"})
        self.assertIn("G7.ROS_REF_LINE", self.codes(self.context(safety=beyond)))
        missing = self.stop(estop={"state_ref": f"companion:{ALIAS}/src/absent.cpp:1"})
        self.assertIn("G7.ROS_REF_MISSING", self.codes(self.context(safety=missing)))
        traversal = self.stop(estop={"source_ref": f"companion:{ALIAS}/../api.cpp:1"})
        self.assertIn("G7.ROS_REF_FORMAT", self.codes(self.context(safety=traversal)))

    def test_a_companion_not_read_at_its_pin_is_not_evidence(self) -> None:
        unpinned = dict(self.companions)
        source = unpinned[ALIAS]
        unpinned[ALIAS] = CompanionSource(source.alias, source.package_id, source.commit, source.profile,
                                          source.local_path, source.path, UpstreamTree(source.path, use_git=False))
        self.assertIn("G7.ROS_REF_MISSING", self.codes(self.context(safety=self.stop(), companions=unpinned)))

    def test_bindings_without_companion_citations_see_no_new_finding(self) -> None:
        wire = [{"op": "subscribe", "topic": "/level", "type": "std_msgs/Float64"}]
        self.assertEqual(self.codes(self.context(reads={"level": self.level}, companions={}, wire=wire)), [])


def registry_card_path(root: Path, directory: Path, track: str) -> Path:
    return root / "MHS" / "registry" / "tasks" / track / f"{directory.name}.json"


def write_card(root: Path, directory: Path, card: dict, *, registry: bool = True) -> None:
    """``task.json``, and with ``registry`` the registry card it must equal (as ``prepare.py --sync`` leaves them)."""
    text = json.dumps(card, indent=2) + "\n"
    (directory / "task.json").write_text(text)
    if registry:
        path = registry_card_path(root, directory, card["track"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


#: The companion fixture plus lines a read-back must never rest on (verification F2 of phase 3): an acknowledgement
#: (lines 15-16), the compared field set to a constant (17) or only declared (18), and a keyword argument (19).
API_CPP_F2 = API_CPP + """res.success = true;
res.status_message = "GetPhysicsProperties: got properties";
res.pause = true;  // a constant, not the world's flag
bool pause  # a message field, never assigned
return GetPhysicsPropertiesResponse(pause=self.world.paused)
"""


class CompanionReadBackMeaningTests(unittest.TestCase):
    """Verification F2 of phase 3: G7 checks what a companion read-back means, not only its form.

    The read-back is in the stop's namespace (the same simulator world), compares no acknowledgement field, and its
    ``state_ref`` line assigns the compared field from something other than a constant. The verifier's probe (an
    acknowledgement read-back ``success == True`` and a read-back under ``/other_world``) is refused.
    """

    def setUp(self) -> None:
        root = gs.temp_root(self)
        _clone, commit = companion_repo(self, root, files={"src/api.cpp": API_CPP_F2, "VERSION.txt": VERSION_TXT})
        (root / "pkg").mkdir()
        (root / "pkg" / "node.cpp").write_text('pub = nh.advertise<std_msgs::Float64>("level", 1);\n')
        self.tree = UpstreamTree(root / "pkg", use_git=False)
        self.companions, problems = companion_sources({"package_id": "gh.acme/th1",
                                                       "companions": [card_entry(commit)]}, root)
        self.assertEqual(problems, [])

    context = RosCompanionScopeTests.context
    codes = RosCompanionScopeTests.codes
    stop = RosCompanionScopeTests.stop
    readback_messages = RosCompanionScopeTests.readback_messages

    def test_the_shipped_form_still_passes(self) -> None:
        self.assertEqual(self.readback_messages(self.stop()), [])

    def test_an_acknowledgement_field_never_confirms_the_stop(self) -> None:
        for path, line in (("success", 15), ("status_message", 16), ("result.success", 15)):
            with self.subTest(path=path):
                messages = self.readback_messages(self.stop(safe_state={
                    "success": {"path": path, "equals": True if path != "status_message" else "ok"},
                    "state_ref": f"companion:{ALIAS}/src/api.cpp:{line}"}))
                self.assertTrue(any("acknowledgement of the request" in message for message in messages), messages)

    def test_the_verifier_probe_is_refused(self) -> None:
        # p3.py of the phase-3 verification (lens safety-path), on a fixture that shows 'res.success = true;'.
        acknowledgement = dict(READBACK, success={"path": "success", "equals": True},
                               state_ref=f"companion:{ALIAS}/src/api.cpp:15")
        self.assertIn("G7.ROS_COMPANION_READBACK",
                      self.codes(self.context(safety={"estop": PAUSE, "safe_state": acknowledgement})))
        other_world = dict(READBACK, service="/other_world/get_physics_properties")
        wire = [{"op": "call_service", "service": "/gazebo/pause_physics", "type": "std_srvs/Empty"},
                {"op": "call_service", "service": "/other_world/get_physics_properties",
                 "type": "gazebo_msgs/GetPhysicsProperties"}]
        messages = self.readback_messages({"estop": PAUSE, "safe_state": other_world})
        self.assertEqual(len(messages), 1, messages)
        self.assertIn("namespace of the stop", messages[0])
        self.assertIn("G7.ROS_COMPANION_READBACK",
                      self.codes(self.context(safety={"estop": PAUSE, "safe_state": other_world}, wire=wire)))

    def test_the_read_back_is_in_the_stop_s_world(self) -> None:
        for service, refused in (("/gazebo/get_physics_properties", False), ("/other_world/get_physics_properties", True),
                                 ("/gazebo/sim/get_physics_properties", True), ("/get_physics_properties", True),
                                 ("get_physics_properties", True), ("gazebo/get_physics_properties", True),
                                 ("~get_physics_properties", True)):
            with self.subTest(service=service):
                messages = self.readback_messages(self.stop(safe_state={"service": service}))
                self.assertEqual(any("namespace of the stop" in message for message in messages), refused, messages)

    def test_the_state_ref_line_assigns_the_field_from_the_stopped_state(self) -> None:
        for line, accepted in ((13, True), (17, False), (18, False), (19, True)):
            with self.subTest(line=line):
                messages = self.readback_messages(self.stop(safe_state={
                    "state_ref": f"companion:{ALIAS}/src/api.cpp:{line}"}))
                self.assertEqual(not any("from the stopped state" in message for message in messages), accepted,
                                 messages)

    def test_the_assignment_reader(self) -> None:
        from mhs.driver.ros_check import _assigned_from_state, _same_world

        for text in ("res.pause = world_->IsPaused();", "response->pause = paused;", "pause=self.world.paused)",
                     '{"pause": state.paused}', "res.pause = !running_;"):
            with self.subTest(text=text):
                self.assertTrue(_assigned_from_state("pause", text))
        for text in ("res.pause = true;", "res.pause = 1;", 'res.pause = "yes";', "res.pause == true", "bool pause",
                     "res.paused = world_->IsPaused();", "res.pause = TRUE;  // fixed", "res.pause = nullptr;"):
            with self.subTest(text=text):
                self.assertFalse(_assigned_from_state("pause", text))
        self.assertTrue(_same_world("/gazebo/a", "/gazebo/b"))
        self.assertTrue(_same_world("a", "b"))
        self.assertFalse(_same_world("/gazebo/a", "gazebo/b"))
        self.assertFalse(_same_world("/w1/a", "/w2/a"))
        self.assertFalse(_same_world(None, "/gazebo/a"))


class CompanionGateTests(unittest.TestCase):
    """G1, G2 and G4 on a real (non-synthetic) package whose card declares a companion."""

    def setUp(self) -> None:
        self.root, self.dir = gs.real_package(self)
        clone = self.root / "labs" / "acme" / "th1"
        (clone / "README.md").write_text(PACKAGE_README)
        gs.git(clone, "init", "-q")
        gs.git(clone, "add", "-A")
        gs.git(clone, "commit", "-q", "-m", "TH-1")
        gs.pin(self.dir, gs.git(clone, "rev-parse", "HEAD"))
        self.companion, self.commit = companion_repo(self, self.root)
        self.declare([card_entry(self.commit)])

    def declare(self, entries, *, lock=True, registry=True) -> None:
        card = json.loads((self.dir / "task.json").read_text())
        card["companions"] = entries
        write_card(self.root, self.dir, card, registry=registry)
        if lock:
            gs.edit_json(self.dir, "driver.lock.json",
                         companions=[{"package_id": item["package_id"], "commit": item["commit"]} for item in entries])

    def add_fact(self, ref: str) -> None:
        gs.edit(self.dir, "driver.py", "    facts = [\n",
                f"    facts = [\n        Fact('The companion pauses the world', source='upstream_code', ref={ref!r}),\n")
        gs.regenerate(self.dir)

    def run_gates(self, gates=("G1", "G2", "G4")):
        return gs.check(self.dir, gates=list(gates), root=self.root)

    def test_a_declared_companion_and_a_fact_citing_it_pass(self) -> None:
        self.add_fact(f"companion:{ALIAS}/src/api.cpp:11")
        report = self.run_gates()
        self.assertEqual([code for code in gs.findings(report) if "COMPANION" in code or "REF" in code], [], report)
        for gate in ("G1", "G2", "G4"):
            self.assertEqual(gs.findings(report, gate), [], (gate, report))

    def test_missing_clone_non_git_clone_and_head_away_from_the_pin(self) -> None:
        moved = self.root / "moved-aside"
        self.companion.rename(moved)
        self.assertIn("G1.NO_COMPANION_CLONE", gs.findings(self.run_gates(["G1"]), "G1"))
        self.companion.mkdir(parents=True)
        (self.companion / "VERSION.txt").write_text(VERSION_TXT)
        self.assertIn("G1.COMPANION_NOT_GIT", gs.findings(self.run_gates(["G1"]), "G1"))
        (self.companion / "VERSION.txt").unlink()
        self.companion.rmdir()
        moved.rename(self.companion)
        (self.companion / "NEW.txt").write_text("later\n")
        gs.git(self.companion, "add", "-A")
        gs.git(self.companion, "commit", "-q", "-m", "later")
        report = self.run_gates(["G1", "G2"])
        self.assertIn("G1.COMPANION_HEAD", gs.findings(report, "G1"))
        self.assertEqual(gs.findings(report, "G2"), [])  # the pinned commit is still in the clone

    def test_a_modified_tracked_file_and_a_write_during_the_run(self) -> None:
        (self.companion / "VERSION.txt").write_text(VERSION_TXT + "edited\n")
        self.assertIn("G1.COMPANION_MODIFIED", gs.findings(self.run_gates(["G1"]), "G1"))
        (self.companion / "VERSION.txt").write_text(VERSION_TXT)
        ctx = _Context(self.dir, "fake", self.root, None, False)
        self.addCleanup(ctx.close)
        (self.companion / "src" / "api.cpp").write_text(API_CPP + "// written during the run\n")
        gate = Gate("G1", "Layout and isolation")
        _g1_after(ctx, gate)
        self.assertIn("G1.COMPANION_WRITTEN", [finding.code for finding in gate.findings])

    def test_version_evidence_must_show_its_tokens_and_the_distro_on_both_sides(self) -> None:
        cases = {
            "token not shown": [{"side": "package", "ref": "README.md:3", "token": "ROS Melodic"},
                                {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"}],
            "no package side": [{"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"},
                                {"side": "companion", "ref": "VERSION.txt:1", "token": "2.9.3"}],
            "distro not on the companion side": [{"side": "package", "ref": "README.md:3", "token": "ROS Noetic"},
                                                 {"side": "companion", "ref": "VERSION.txt:1", "token": "2.9.3"}],
            "distro not on the package side": [{"side": "package", "ref": "README.md:4", "token": "catkin"},
                                               {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"}],
            "line beyond the file": [{"side": "package", "ref": "README.md:30", "token": "ROS Noetic"},
                                     {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"}],
            "undeclared side": [{"side": "package", "ref": "README.md:3", "token": "ROS Noetic"},
                                {"side": "companion:other_sim", "ref": "VERSION.txt:2", "token": "Noetic"}],
            "traversal": [{"side": "package", "ref": "../README.md:3", "token": "ROS Noetic"},
                          {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"}],
        }
        for name, evidence in cases.items():
            with self.subTest(name=name):
                self.declare([card_entry(self.commit, evidence=evidence)])
                self.assertIn("G1.COMPANION_VERSION", gs.findings(self.run_gates(["G1"]), "G1"))

    def test_the_lock_repeats_the_card_and_the_pin_is_in_the_clone(self) -> None:
        gs.edit_json(self.dir, "driver.lock.json", companions=[{"package_id": "gh.acme/other", "commit": self.commit}])
        self.assertIn("G2.COMPANION_MISMATCH", gs.findings(self.run_gates(["G2"]), "G2"))
        lock = json.loads((self.dir / "driver.lock.json").read_text())
        lock.pop("companions")
        (self.dir / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        self.assertIn("G2.COMPANION_MISMATCH", gs.findings(self.run_gates(["G2"]), "G2"))
        self.declare([card_entry("b" * 40)])
        report = self.run_gates(["G1", "G2"])
        self.assertIn("G2.COMPANION_COMMIT_ABSENT", gs.findings(report, "G2"))
        self.assertIn("G1.COMPANION_HEAD", gs.findings(report, "G1"))

    def test_a_lock_cannot_add_a_companion_the_card_does_not_declare(self) -> None:
        card = json.loads((self.dir / "task.json").read_text())
        card.pop("companions")
        write_card(self.root, self.dir, card)
        self.assertIn("G2.COMPANION_MISMATCH", gs.findings(self.run_gates(["G2"]), "G2"))

    def test_task_json_companions_count_only_as_the_registry_card_confirms_them(self) -> None:
        reviewed = json.loads((self.dir / "task.json").read_text())
        registry = registry_card_path(self.root, self.dir, reviewed["track"])
        # A package rewrites its companion in task.json (another simulator release, evidence that shows nothing
        # about it) and keeps the lock's [package_id, commit]: the registry card still holds the reviewed entry.
        evidence = [{"side": "package", "ref": "README.md:1", "token": "TH-1"},
                    {"side": "companion", "ref": "VERSION.txt:2", "token": "Noetic"},
                    {"side": "package", "ref": "README.md:3", "token": "Noetic"}]
        tampered = dict(card_entry(self.commit, evidence=evidence), profile="ros1-noetic-gazebo9")
        write_card(self.root, self.dir, dict(reviewed, companions=[tampered]), registry=False)
        report = self.run_gates(["G1", "G2"])
        self.assertIn("G1.CARD_EDITED", gs.findings(report, "G1"))
        self.assertEqual(gs.findings(report, "G2"), [])  # the lock alone does not see it
        # Without a registry card that confirms them, declared companions fail closed.
        registry.rename(registry.with_suffix(".moved"))
        self.assertIn("G1.COMPANION_CARD", gs.findings(self.run_gates(["G1"]), "G1"))
        registry.write_text("{not json\n")
        self.assertIn("G1.COMPANION_CARD", gs.findings(self.run_gates(["G1"]), "G1"))
        # A track that names no registry card, or would leave the registry's task cards for a copy the package
        # planted (MHS/registry/tasks/../../drivers/labs/acme__th1/acme__th1.json), confirms nothing either.
        registry.write_text(json.dumps(reviewed, indent=2) + "\n")
        planted = self.dir / f"{self.dir.name}.json"
        for track in ("robots", "../../drivers/labs/acme__th1"):
            with self.subTest(track=track):
                card = dict(reviewed, track=track)
                write_card(self.root, self.dir, card, registry=False)
                planted.write_text(json.dumps(card, indent=2) + "\n")
                self.assertIn("G1.COMPANION_CARD", gs.findings(self.run_gates(["G1"]), "G1"))
                planted.unlink()
        write_card(self.root, self.dir, reviewed, registry=False)
        self.assertEqual(gs.findings(self.run_gates(["G1"]), "G1"), [])

    def test_g4_refuses_a_companion_bound_and_physical_stop(self) -> None:
        gs.edit(self.dir, "driver.py", 'estop_physical_ref = "MANUAL.md:15"',
                f'estop_physical_ref = "companion:{ALIAS}/src/api.cpp:11"')
        gs.regenerate(self.dir)
        self.assertIn("G4.COMPANION_REF_SCOPE", gs.findings(self.run_gates(["G4"]), "G4"))
        gs.edit(self.dir, "driver.py", f'estop_physical_ref = "companion:{ALIAS}/src/api.cpp:11"',
                'estop_physical_ref = "MANUAL.md:15"')
        gs.edit(self.dir, "driver.py", 'ref="MANUAL.md:9"))\n', f'ref="companion:{ALIAS}/src/api.cpp:13"))\n')
        gs.regenerate(self.dir)
        self.assertIn("G4.COMPANION_REF_SCOPE", gs.findings(self.run_gates(["G4"]), "G4"))

    def test_g4_resolves_companion_facts_at_the_pin(self) -> None:
        for ref, code in ((f"companion:other_sim/src/api.cpp:11", "G4.COMPANION_UNDECLARED"),
                          (f"companion:{ALIAS}/src/absent.cpp:1", "G4.REF_MISSING"),
                          (f"companion:{ALIAS}/src/api.cpp:99", "G4.REF_LINE"),
                          (f"companion:{ALIAS}/../api.cpp:1", "G4.REF_FORMAT")):
            with self.subTest(ref=ref):
                self.setUp()
                self.add_fact(ref)
                self.assertIn(code, gs.findings(self.run_gates(["G4"]), "G4"))

    def test_g4_reads_the_pinned_commit_not_the_working_tree(self) -> None:
        self.add_fact(f"companion:{ALIAS}/src/later.cpp:1")
        (self.companion / "src" / "later.cpp").write_text("// untracked, not at the pin\n")
        self.assertIn("G4.REF_MISSING", gs.findings(self.run_gates(["G4"]), "G4"))

    def test_a_pin_absent_from_the_clone_is_never_read_from_the_working_tree(self) -> None:
        self.declare([card_entry("b" * 40)])
        self.add_fact(f"companion:{ALIAS}/src/api.cpp:11")  # exists in the working tree, not at the pin
        report = self.run_gates(["G2", "G4"])
        self.assertIn("G2.COMPANION_COMMIT_ABSENT", gs.findings(report, "G2"))
        self.assertIn("G4.REF_MISSING", gs.findings(report, "G4"))

    def test_without_companions_nothing_changes(self) -> None:
        card = json.loads((self.dir / "task.json").read_text())
        card.pop("companions")
        write_card(self.root, self.dir, card)
        lock = json.loads((self.dir / "driver.lock.json").read_text())
        lock.pop("companions")
        (self.dir / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        report = self.run_gates()
        self.assertEqual([code for code in gs.findings(report, severity=None) if "COMPANION" in code], [])
        self.add_fact(f"companion:{ALIAS}/src/api.cpp:11")
        self.assertIn("G4.COMPANION_UNDECLARED", gs.findings(self.run_gates(["G4"]), "G4"))

    def test_a_synthetic_tutorial_declares_no_companions(self) -> None:
        directory = gs.copy_tutorial(self)
        card = json.loads((directory / "task.json").read_text())
        card["companions"] = [card_entry(self.commit)]
        (directory / "task.json").write_text(json.dumps(card, indent=2) + "\n")
        self.assertIn("G1.COMPANION_CARD", gs.findings(gs.check(directory, gates=["G1"]), "G1"))


SCRATCH_DRIVER = """from mhs.driver import Action, Fact, Field, Limit, RosDriver

_API = "companion:sim_ros/src/api.cpp"
_PAUSE = {"service": "/gazebo/pause_physics", "type": "std_srvs/Empty", "source_name": "pause_physics",
          "source_ref": _API + ":2-4", "type_ref": _API + ":4", "state_ref": _API + ":11",
          "request": {}, "success": {"path": "$", "equals": {}}, "timeout_ms": 500}
_READBACK = {"service": "/gazebo/get_physics_properties", "type": "gazebo_msgs/GetPhysicsProperties",
             "source_name": "get_physics_properties", "source_ref": _API + ":8-10", "type_ref": _API + ":10",
             "state_ref": _API + ":13", "request": {}, "success": {"path": "pause", "equals": True},
             "timeout_ms": 500}


class SimWorld(RosDriver):
    device_id = "sim-world"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 1
    backends = {"fake": ".fake:FakeSimWorld"}
    facts = [Fact("pausePhysics sets the world's paused flag.", source="upstream_code", ref=_API + ":11"),
             Fact("The node publishes the level on the level topic.", source="upstream_code", ref="node.cpp:1")]
    safe_state = "The simulated world is paused and the read-back reported pause true (a flag, not a standstill)."
    fidelity = {"engine": "canned:test fixture", "fidelity_level": "F0",
                "determinism": {"kind": "none", "notes": "test fixture"}, "timestep_ms": 0, "realtime_factor": 0,
                "reset": "none", "snapshot_restore": False, "gaps": ["a test fixture, not a simulator"]}
    parameters = {"level": Field("number", unit="1", description="The last level the node reports")}
    reads = {"level": {"topic": "/level_state", "type": "std_msgs/Float64", "source_name": "level_state",
                       "source_ref": "node.cpp:3", "type_ref": "node.cpp:3", "path": "data", "timeout_ms": 500}}
    commands = {
        "x-cap.acme.level.v1": {"topic": "/level", "type": "std_msgs/Float64", "operation": "publish",
                                "source_name": "level", "source_ref": "node.cpp:1", "type_ref": "node.cpp:1",
                                "message": {"data": 0.0}, "args": {"data": {"from": "input.level"}}},
        "x-cap.acme.resume.v1": {"service": "/gazebo/unpause_physics", "type": "std_srvs/Empty",
                                 "source_name": "unpause_physics", "source_ref": _API + ":5-7",
                                 "type_ref": _API + ":7", "request": {}, "success": {"path": "$", "equals": {}},
                                 "result": {"acknowledged": {"value": True}}},
    }
    actions = {
        "x-cap.acme.level.v1": Action(
            name="set_level", verb="invoke", description="Publish one level setpoint",
            input={"level": Field("number", unit="1", description="Level setpoint",
                                  limit=Limit(min=0, max=10, source="upstream_code", ref="node.cpp:2"))},
            output={"published": Field("boolean", description="Handed to rosbridge"),
                    "confirmed": Field("boolean", description="Always false")}),
        "x-cap.acme.resume.v1": Action(
            name="resume", verb="invoke", reenable=True, description="Unpause the world after a reset",
            output={"acknowledged": Field("boolean", description="The unpause answered")}),
    }
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
"""

SCRATCH_FAKE = """from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSimWorld(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False
        self.level = 1.0  # placeholder

    def _respond(self, message):
        op = message.get("op")
        if op == "subscribe" and message.get("topic") == "/level_state":
            return {"op": "publish", "topic": "/level_state", "id": message.get("id"), "msg": {"data": self.level}}
        if op == "publish" and message.get("topic") == "/level":
            self.level = float((message.get("msg") or {}).get("data", 0.0))
            return None
        if op != "call_service":
            return None
        service = message.get("service")
        if service == "/gazebo/pause_physics":
            self.paused = True
            values = {}
        elif service == "/gazebo/get_physics_properties":
            values = {"pause": self.paused, "success": True, "time_step": 0.001}  # placeholder
        elif service == "/gazebo/unpause_physics":
            self.paused = False
            values = {}
        else:
            return {"op": "service_response", "service": service, "id": message.get("id"), "result": False,
                    "values": {}}
        return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                "values": values}
"""

NODE_CPP = """pub_ = nh.advertise<std_msgs::Float64>("level", 1);
const double kMaxLevel = 10.0;  // levels from 0 to 10
state_ = nh.advertise<std_msgs::Float64>("level_state", 1);
"""


class EndToEndCompanionPackageTests(unittest.TestCase):
    """A scratch RosDriver package whose stop, read-back, re-enable and a fact cite a companion: G1 to G8 pass."""

    def setUp(self) -> None:
        self.root = gs.temp_root(self)
        (self.root / "MHS" / "sdk").mkdir(parents=True)
        clone = self.root / "robots" / "acme" / "sim_world"
        clone.mkdir(parents=True)
        (clone / "node.cpp").write_text(NODE_CPP)
        (clone / "README.md").write_text(PACKAGE_README)
        gs.git(clone, "init", "-q")
        gs.git(clone, "add", "-A")
        gs.git(clone, "commit", "-q", "-m", "sim world")
        commit = gs.git(clone, "rev-parse", "HEAD")
        _companion, companion_commit = companion_repo(self, self.root)
        self.dir = self.root / "MHS" / "drivers" / "robots" / "acme__sim_world"
        self.dir.mkdir(parents=True)
        (self.dir / "driver.py").write_text(SCRATCH_DRIVER)
        (self.dir / "fake.py").write_text(SCRATCH_FAKE)
        (self.dir / "facts.md").write_text("# Facts\n\nSee driver.py.\n")
        (self.dir / "test_driver.py").write_text(
            "import unittest\nfrom pathlib import Path\nfrom mhs.testing import check_driver\n\n\n"
            "class Gate(unittest.TestCase):\n    def test_gate(self):\n"
            "        self.assertEqual(check_driver(Path(__file__).parent)['failed'], [])\n")
        entry = card_entry(companion_commit)
        card = json.loads((gs.TUTORIAL / "task.json").read_text())
        for key in ("synthetic", "notes"):
            card.pop(key, None)
        card.update({"package_id": "gh.acme/sim_world", "track": "robots", "local_path": "robots/acme/sim_world",
                     "driver_dir": "MHS/drivers/robots/acme__sim_world", "decision": "family-config",
                     "family": "ros", "helper": "RosDriver", "role": "sim-env", "entry_symbols": [],
                     "upstream": {"repo_url": "https://github.com/acme/sim_world", "commit": commit,
                                  "license_spdx": "MIT", "license_class": "permissive"},
                     "safety": {"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []},
                     "acceptance": "python3 -m mhs.driver check MHS/drivers/robots/acme__sim_world --backend fake",
                     "companions": [entry]})
        write_card(self.root, self.dir, card)
        lock = {"$schema": "https://openmhs.invalid/schema/0.9/driver-lock.schema.json", "openmhs": "0.9",
                "package_id": "gh.acme/sim_world",
                "upstream": {"repo_url": "https://github.com/acme/sim_world", "commit": commit,
                             "license_spdx": "MIT"},
                "companions": [{"package_id": "gh.acme/sim", "commit": companion_commit}],
                "backends": {"fake": ".fake:FakeSimWorld"}, "sdk_version": json.loads(
                    (gs.TUTORIAL / "driver.lock.json").read_text())["sdk_version"],
                "authored_by": {"kind": "model", "model_id": "test", "run_id": "test", "date": "2026-11-05"},
                "reviewed_by": None}
        (self.dir / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        gs.regenerate(self.dir)

    def test_gates_one_to_eight_pass(self) -> None:
        report = gs.check(self.dir, root=self.root)
        self.assertEqual(report["failed"], [], json.dumps([gate for gate in report["gates"]
                                                          if gate["status"] == "fail"], indent=1)[:3000])
        self.assertEqual([code for code in gs.findings(report, severity=None) if "COMPANION" in code], [])

    def test_an_uncited_read_back_fails_g7(self) -> None:
        gs.edit(self.dir, "driver.py", '"state_ref": _API + ":13", ', "")
        report = gs.check(self.dir, root=self.root, gates=["G7"])
        self.assertIn("G7.ROS_COMPANION_READBACK", gs.findings(report, "G7"))


class ScaffoldTests(unittest.TestCase):
    def test_new_copies_the_card_companions_into_the_lock(self) -> None:
        root = gs.temp_root(self)
        card = json.loads((gs.TUTORIAL / "task.json").read_text())
        card["companions"] = [card_entry("c" * 40)]
        (root / "card.json").write_text(json.dumps(card))
        scaffold(root / "pkg", card=root / "card.json", kind="ros")
        lock = json.loads((root / "pkg" / "driver.lock.json").read_text())
        self.assertEqual(lock["companions"], [{"package_id": "gh.acme/sim", "commit": "c" * 40}])
        self.assertEqual(list(lock)[list(lock).index("upstream") + 1], "companions")

    def test_new_without_companions_renders_the_template_unchanged(self) -> None:
        root = gs.temp_root(self)
        scaffold(root / "pkg", card=gs.TUTORIAL / "task.json", kind="ros")
        self.assertNotIn("companions", json.loads((root / "pkg" / "driver.lock.json").read_text()))


if __name__ == "__main__":
    unittest.main()
