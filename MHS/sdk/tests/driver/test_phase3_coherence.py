"""Coherence probes of the phase-3 composition (integrator-v3, claude-opus-5-5, a model; 2026-11-05).

Each probe pins a place where two phase-3 changes meet in one function, so that a later edit cannot quietly drop
one side of the hand-resolved merge (MERGE-LOG.json of development/integrator-v3):

* R-P3-01 / R-P3-07, ``ros_check._bindings``: p3-companion's 4-tuples (``companion_ok``) with p3-sensed-stop's
  ``safety_bindings.sensed_stop`` request steps and sources and p3-sdk-gaps-b's publish-then-step ``then.step`` and
  ``then.observe``: every binding is a 4-tuple, and only the e-stop, its read-back and the declared re-enable's own
  command may cite a companion (a sensed-stop step or source, and a then-step or then-observe, fail closed with
  ``ROS_COMPANION_SCOPE``).
* R-P3-04, ``check._g4_resolve``: p3-companion's per-citation resolver carries p3-sdk-gaps-a's git-submodule
  refusal reason in ``G4.REF_MISSING``, for the package clone and for a companion tree.
* R-P3-02, ``upstream``: p3-companion's ``companion_sources`` builds its trees through p3-sdk-gaps-a's
  ``UpstreamTree`` (``_init_state``), and both public surfaces are exported.
* R-P3-03, ``show_refs``: a package-clone citation inside a declared git submodule goes to p3-sdk-gaps-a's reader
  (``show_submodule``) and every other one to p3-companion's ``show``.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from mhs.driver import check as gate_check
from mhs.driver import ros_check, upstream

SHOW_REFS = Path(__file__).resolve().parents[3] / "handoff" / "tools" / "show_refs.py"
REENABLE = "x-cap.test.coherence-unpause.v1"


class _Gate:
    def __init__(self):
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []

    def error(self, code, message, *_args):
        self.errors.append((code, message))

    def warning(self, code, message, *_args):
        self.warnings.append((code, message))


class Composite:
    """A ROS driver class shape that uses every binding kind the three phase-3 changes add or keep."""

    commands = {
        "x-cap.test.coherence-drive.v1": {
            "topic": "/cmd_vel", "type": "geometry_msgs/msg/Twist", "source_ref": "src/teleop.py:10",
            "then": {"step": {"service": "/step", "type": "std_srvs/srv/Empty", "source_ref": "src/sim.py:20"},
                     "observe": {"topic": "/odom", "type": "nav_msgs/msg/Odometry", "source_ref": "src/sim.py:30"}},
        },
        REENABLE: {"service": "/gazebo/unpause_physics", "type": "std_srvs/srv/Empty",
                   "source_ref": "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1"},
    }
    reads = {"pose": {"topic": "/pose", "type": "geometry_msgs/msg/PoseStamped", "source_ref": "src/pose.py:5"}}
    safety_bindings = {
        "estop": {"service": "/gazebo/pause_physics", "type": "std_srvs/srv/Empty",
                  "source_ref": "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:2"},
        "safe_state": {"service": "/gazebo/get_physics_properties", "type": "gazebo_msgs/srv/GetPhysicsProperties",
                       "source_ref": "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:3"},
        "reset": {"service": "/reset", "type": "std_srvs/srv/Empty", "source_ref": "src/sim.py:40"},
        "interlocks": [{"topic": "/door", "type": "std_msgs/msg/Bool", "source_ref": "src/door.py:1"}],
        "sensed_stop": {
            "request": [{"service": "/land", "type": "std_srvs/srv/SetBool", "source_ref": "src/land.py:1"}],
            "sources": {"pose": {"topic": "/pose", "type": "geometry_msgs/msg/PoseStamped",
                                 "source_ref": "src/pose.py:5"}},
        },
    }


class BindingTupleTests(unittest.TestCase):
    """R-P3-01 and R-P3-07."""

    def test_every_binding_is_a_four_tuple_and_only_the_companion_scope_may_cite_one(self):
        rows = list(ros_check._bindings(Composite, REENABLE))
        self.assertTrue(all(len(row) == 4 for row in rows), rows)
        scope = {label: companion_ok for label, _spec, _group, companion_ok in rows}
        self.assertEqual(scope, {
            "commands['x-cap.test.coherence-drive.v1']": False,
            "commands['x-cap.test.coherence-drive.v1'].then.step": False,
            "commands['x-cap.test.coherence-drive.v1'].then.observe": False,
            f"commands['{REENABLE}']": True,
            "reads['pose']": False,
            "safety_bindings.estop": True,
            "safety_bindings.safe_state": True,
            "safety_bindings.reset": False,
            "safety_bindings.interlocks[0]": False,
            "safety_bindings.sensed_stop.request[0]": False,
            "safety_bindings.sensed_stop.sources['pose']": False,
        })
        groups = {label: group for label, _spec, group, _ok in rows}
        self.assertEqual(groups["safety_bindings.sensed_stop.request[0]"], "sensed_request")
        self.assertEqual(groups["safety_bindings.sensed_stop.sources['pose']"], "reads")
        self.assertEqual(groups["commands['x-cap.test.coherence-drive.v1'].then.step"], "commands")
        self.assertEqual(groups["commands['x-cap.test.coherence-drive.v1'].then.observe"], "reads")

    def test_without_a_declared_reenable_no_command_may_cite_a_companion(self):
        rows = list(ros_check._bindings(Composite))
        self.assertFalse(any(ok for label, _spec, _group, ok in rows if label.startswith("commands")))

    def test_a_companion_citation_outside_the_scope_fails_closed(self):
        class Ctx:
            tree = None
            companions = {}

        for label in ("safety_bindings.sensed_stop.request[0].source_ref",
                      "safety_bindings.sensed_stop.sources['pose'].source_ref",
                      "commands['x-cap.test.coherence-drive.v1'].then.step.source_ref"):
            gate = _Gate()
            text = ros_check._source_text(Ctx(), gate, "companion:gazebo_ros_pkgs/gazebo_ros/x.cpp:1", label, False)
            self.assertIsNone(text)
            self.assertEqual([code for code, _message in gate.errors], ["ROS_COMPANION_SCOPE"], label)


class _MissingTree:
    def __init__(self, reason):
        self.reason = reason

    def read_bytes(self, _path):
        return None

    def refusal_for(self, _path):
        return self.reason


class SubmoduleRefusalInG4Tests(unittest.TestCase):
    """R-P3-04."""

    def resolve(self, tree, companion):
        gate = gate_check.Gate("G4", "references")
        ref = upstream.parse_ref("third_party/lib/file.py:12")
        gate_check._g4_resolve(gate, tree, ref, "limit", "Limit max", "third_party/lib/file.py:12", None,
                               "the clone", companion=companion)
        return gate

    def test_the_refusal_reason_is_in_ref_missing_for_the_clone_and_a_companion(self):
        reason = "git submodule third_party/lib is checked out at 0123456789ab, another commit"
        for companion in (False, True):
            gate = self.resolve(_MissingTree(reason), companion)
            self.assertEqual([item.code for item in gate.findings], ["G4.REF_MISSING"])
            self.assertTrue(gate.findings[0].message.endswith(f"does not exist in the clone ({reason})"),
                            gate.findings[0].message)

    def test_without_a_refusal_the_message_is_unchanged(self):
        gate = self.resolve(_MissingTree(None), False)
        self.assertTrue(gate.findings[0].message.endswith("third_party/lib/file.py does not exist in the clone"),
                        gate.findings[0].message)


class UpstreamSurfaceTests(unittest.TestCase):
    """R-P3-02."""

    def test_both_surfaces_are_exported(self):
        for name in ("Submodule", "CompanionSource", "companion_sources", "is_companion_ref", "parse_source_ref",
                     "COMPANION_ALIAS", "COMPANION_PREFIX"):
            self.assertIn(name, upstream.__all__)
            self.assertTrue(hasattr(upstream, name), name)

    def test_a_companion_tree_is_an_upstream_tree_with_the_submodule_state(self):
        with tempfile.TemporaryDirectory() as base:
            clone = Path(base) / "robots" / "owner" / "repo"
            clone.mkdir(parents=True)
            (clone / "a.txt").write_text("pause\n", encoding="utf-8")
            card = {"package_id": "gh.someone/package", "companions": [{
                "alias": "repo_companion", "package_id": "gh.owner/repo", "commit": "0" * 40,
                "profile": "ros1-noetic-gazebo11", "local_path": "robots/owner/repo", "version_evidence": []}]}
            sources, problems = upstream.companion_sources(card, Path(base))
            self.assertEqual(problems, [])
            tree = sources["repo_companion"].tree
            self.assertIsInstance(tree, upstream.UpstreamTree)
            self.assertFalse(tree.pinned)             # a plain directory, never claimed to be the pin
            self.assertEqual(tree.submodule_paths(), [])
            self.assertEqual(tree.submodules, {})
            self.assertIsNone(tree.refusal_for("a.txt"))
            self.assertEqual(tree.read_text("a.txt"), "pause\n")


class ShowRefsRoutingTests(unittest.TestCase):
    """R-P3-03."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("show_refs_phase3_probe", SHOW_REFS)
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def test_both_readers_exist(self):
        for name in ("show", "show_submodule", "submodule_paths", "pinned_tree", "companion_headers"):
            self.assertTrue(callable(getattr(self.tool, name, None)), name)

    def test_a_submodule_citation_without_the_sdk_is_a_bad_citation_with_the_reason(self):
        lines, bad = self.tool.show_submodule(None, "third_party/lib", "third_party/lib/file.py:3", 0)
        self.assertTrue(bad)
        self.assertEqual(lines, ["  !! inside the git submodule third_party/lib: the SDK (MHS/sdk/src) that reads git "
                                 "submodules cannot be imported"])

    def test_a_submodule_citation_is_shown_from_the_tree_the_sdk_read(self):
        class Tree:
            submodules = {}

            def read_text(self, path):
                return "one\ntwo\nthree\n" if path == "third_party/lib/file.py" else None

            def refusal_for(self, _path):
                return None

        lines, bad = self.tool.show_submodule(Tree(), "third_party/lib", "third_party/lib/file.py:2-3", 0)
        self.assertFalse(bad)
        self.assertEqual(lines, ["  >    2  two", "  >    3  three"])
        lines, bad = self.tool.show_submodule(Tree(), "third_party/lib", "third_party/lib/file.py:9", 0)
        self.assertTrue(bad)
        self.assertEqual(lines, ["  !! the file has 3 lines"])


if __name__ == "__main__":
    unittest.main()
