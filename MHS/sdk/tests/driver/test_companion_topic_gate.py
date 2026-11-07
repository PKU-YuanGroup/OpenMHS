"""The gate on E2 (fresh-sample topic read-back) and E3 (operator-run bridges) packages (companion preflight 2,
2026-11-05).

A scratch ROS 2 package whose stop, read-back and re-enable cite a gz-sim-like companion fixture: a WorldControl pause
whose reply confirms nothing, confirmed by ``WorldStatistics.paused`` on the world's stats topic in fresh samples, with
both endpoints carried by ros_gz bridges the operator runs. Covered: the parameter_bridge argument parser; the package
passes G1 to G8 and its reference file lists the bridges; G3 refuses a worst case beyond the e-stop budget and a
malformed bridge; G7 refuses a fresh read-back without a companion-cited stop (``ROS_FRESH_SCOPE``), one that compares
an acknowledgement field, reads another world or whose ``state_ref`` does not show the flag, a companion endpoint that
no bridge carries (``ROS_OPERATOR_BRIDGE_MISSING``), a bridge whose citation does not show its type
(``ROS_OPERATOR_BRIDGE_REF``) and a bridge no binding uses (``ROS_OPERATOR_BRIDGE_UNUSED``); G6 ``FRESH_FAIL_OPEN``
catches a bridge that would confirm the stop without fresh samples.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from mhs.bridge import ros as ros_bridge
from mhs.driver.ros_check import parse_operator_bridge

from tests.driver import gate_support as gs
from tests.driver import test_companion_sources as base
from tests.driver import test_companion_stall_gate as stall

#: A gz-sim-like world runner and a ros_gz-like bridge README (test fixtures, not upstream code).
RUNNER_CC = """// companion world runner fixture (gz-sim like), not upstream code
std::string ns{"/world/" + this->worldName};
this->node->Advertise("control", &SimulationRunner::OnWorldControl, this);
this->statsPub = this->node->Advertise<msgs::WorldStatistics>("stats", advertOpts);
msg.set_paused(this->currentInfo.paused);
void SimulationRunner::SetPaused(const bool _paused) { this->currentInfo.paused = _paused; }
this->SetPaused(control.pause);
_res.set_data(true);
if (!this->currentInfo.paused) { this->currentInfo.simTime += this->stepSize; }
"""
BRIDGE_README = """# ros_gz bridge fixture
| ros_gz_interfaces/msg/WorldStatistics | gz.msgs.WorldStatistics |
| ros_gz_interfaces/srv/ControlWorld | gz.msgs.WorldControl | gz.msgs.Boolean |
parameter_bridge /world/shapes/control@ros_gz_interfaces/srv/ControlWorld
"""
VERSION_TXT = "gz-sim 8 with ros_gz\ndistro: ROS Humble, ament\n"

TOPIC_DRIVER = """from mhs.driver import Action, Fact, Field, Limit, RosDriver

_RUN = "companion:sim_ros/src/runner.cc"
_BRIDGE = "companion:sim_ros/bridge/README.md"
_PAUSE = {"service": "/world/w/control", "type": "ros_gz_interfaces/srv/ControlWorld", "source_name": "control",
          "source_ref": _RUN + ":3", "type_ref": _BRIDGE + ":3", "state_ref": _RUN + ":7",
          "request": {"world_control": {"pause": True}}, "success": {"path": "success", "equals": True},
          "timeout_ms": 300}
_STATS = {"topic": "/world/w/stats", "type": "ros_gz_interfaces/msg/WorldStatistics", "operation": "subscribe",
          "source_name": "stats", "source_ref": _RUN + ":4", "type_ref": _BRIDGE + ":2", "state_ref": _RUN + ":5",
          "success": {"path": "paused", "equals": True},
          "fresh": {"after_request": True, "discard_first": True, "consecutive": 2, "within_ms": 800,
                    "min_interval_ms": 20}}


class TopicWorld(RosDriver):
    device_id = "topic-world"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 2
    estop_latency_ms = 1500
    backends = {"fake": ".fake:FakeTopicWorld"}
    operator_bridges = [
        {"args": "/world/w/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE + ":4",
         "description": "The world control service: the e-stop and the resume."},
        {"args": "/world/w/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
         "ref": _BRIDGE + ":2"},
    ]
    facts = [Fact("SetPaused stores the world's paused flag.", source="upstream_code", ref=_RUN + ":6"),
             Fact("Sim time advances only while the world is not paused.", source="upstream_code", ref=_RUN + ":9"),
             Fact("The node publishes the level on the level topic.", source="upstream_code", ref="node.cpp:1")]
    safe_state = "The world is paused: two fresh stats samples 20 ms or more apart reported paused true."
    fidelity = {"engine": "canned:test fixture", "fidelity_level": "F0",
                "determinism": {"kind": "none", "notes": "test fixture"}, "timestep_ms": 0, "realtime_factor": 0,
                "reset": "none", "snapshot_restore": False, "gaps": ["a test fixture, not a simulator"]}
    parameters = {"level": Field("number", unit="1", description="The last level the node reports")}
    reads = {"level": {"topic": "/level_state", "type": "std_msgs/msg/Float64", "source_name": "level_state",
                       "source_ref": "node.cpp:3", "type_ref": "node.cpp:3", "path": "data", "timeout_ms": 500}}
    commands = {
        "x-cap.acme.level.v1": {"topic": "/level", "type": "std_msgs/msg/Float64", "operation": "publish",
                                "source_name": "level", "source_ref": "node.cpp:1", "type_ref": "node.cpp:1",
                                "message": {"data": 0.0}, "args": {"data": {"from": "input.level"}}},
        "x-cap.acme.resume.v1": {"service": "/world/w/control", "type": "ros_gz_interfaces/srv/ControlWorld",
                                 "source_name": "control", "source_ref": _RUN + ":3", "type_ref": _BRIDGE + ":3",
                                 "request": {"world_control": {"pause": False}},
                                 "success": {"path": "success", "equals": True},
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
            output={"acknowledged": Field("boolean", description="The world control request answered")}),
    }
    safety_bindings = {"estop": _PAUSE, "safe_state": _STATS}
"""

TOPIC_FAKE = """import time

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeTopicWorld(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False
        self.pending = None
        self.period = 0.05  # placeholder publication period
        self.subscriptions = set()
        self.last = 0.0
        self.level = 1.0  # placeholder

    def _respond(self, message):
        op = message.get("op")
        if op == "subscribe" and message.get("topic") == "/world/w/stats":
            self.subscriptions.add(message.get("id"))
            return None
        if op == "subscribe" and message.get("topic") == "/level_state":
            return {"op": "publish", "topic": "/level_state", "id": message.get("id"), "msg": {"data": self.level}}
        if op == "unsubscribe" and message.get("topic") == "/world/w/stats":
            self.subscriptions.discard(message.get("id"))
            return None
        if op == "publish" and message.get("topic") == "/level":
            self.level = float((message.get("msg") or {}).get("data", 0.0))
            return None
        if op != "call_service":
            return None
        service = message.get("service")
        if service == "/world/w/control":
            self.pending = bool(((message.get("args") or {}).get("world_control") or {}).get("pause"))
            return {"op": "service_response", "service": service, "result": True, "values": {"success": True}}
        return {"op": "service_response", "service": service, "result": False, "values": {}}

    def recv(self, *, timeout_s=None):
        now = time.monotonic()
        if self.subscriptions and now - self.last >= self.period:
            self.last = now
            message = {"op": "publish", "topic": "/world/w/stats", "msg": {"paused": self.paused, "iterations": 3}}
            if self.pending is not None:
                self.paused, self.pending = self.pending, None
            return message
        return super().recv(timeout_s=min(timeout_s or 0.01, 0.01))
"""


def scratch_package(test: unittest.TestCase, driver: str = TOPIC_DRIVER, fake: str = TOPIC_FAKE):
    """A scratch ROS 2 package ``robots/acme/topic_world`` whose card declares the companion fixture ``sim_ros``."""
    name = "topic_world"
    root = gs.temp_root(test)
    (root / "MHS" / "sdk").mkdir(parents=True)
    clone = root / "robots" / "acme" / name
    clone.mkdir(parents=True)
    (clone / "node.cpp").write_text(stall.NODE_CPP)
    (clone / "README.md").write_text(stall.README)
    gs.git(clone, "init", "-q")
    gs.git(clone, "add", "-A")
    gs.git(clone, "commit", "-q", "-m", name)
    commit = gs.git(clone, "rev-parse", "HEAD")
    _companion, companion_commit = base.companion_repo(
        test, root, files={"src/runner.cc": RUNNER_CC, "bridge/README.md": BRIDGE_README, "VERSION.txt": VERSION_TXT})
    directory = root / "MHS" / "drivers" / "robots" / f"acme__{name}"
    directory.mkdir(parents=True)
    (directory / "driver.py").write_text(driver)
    (directory / "fake.py").write_text(fake)
    (directory / "facts.md").write_text("# Facts\n\nSee driver.py.\n")
    (directory / "test_driver.py").write_text(
        "import unittest\nfrom pathlib import Path\nfrom mhs.testing import check_driver\n\n\n"
        "class Gate(unittest.TestCase):\n    def test_gate(self):\n"
        "        self.assertEqual(check_driver(Path(__file__).parent)['failed'], [])\n")
    entry = base.card_entry(companion_commit, evidence=[
        {"side": "package", "ref": "README.md:3", "token": "ROS Humble"},
        {"side": "companion", "ref": "VERSION.txt:2", "token": "Humble"}])
    entry["profile"] = "ros2-humble-gzsim8"
    card = json.loads((gs.TUTORIAL / "task.json").read_text())
    for key in ("synthetic", "notes"):
        card.pop(key, None)
    card.update({"package_id": f"gh.acme/{name}", "track": "robots", "local_path": f"robots/acme/{name}",
                 "driver_dir": f"MHS/drivers/robots/acme__{name}", "decision": "family-config",
                 "family": "ros", "helper": "RosDriver", "role": "sim-env", "entry_symbols": [],
                 "upstream": {"repo_url": f"https://github.com/acme/{name}", "commit": commit,
                              "license_spdx": "MIT", "license_class": "permissive"},
                 "safety": {"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []},
                 "acceptance": f"python3 -m mhs.driver check MHS/drivers/robots/acme__{name} --backend fake",
                 "companions": [entry]})
    base.write_card(root, directory, card)
    lock = {"$schema": "https://openmhs.invalid/schema/0.9/driver-lock.schema.json", "openmhs": "0.9",
            "package_id": f"gh.acme/{name}",
            "upstream": {"repo_url": f"https://github.com/acme/{name}", "commit": commit, "license_spdx": "MIT"},
            "companions": [{"package_id": "gh.acme/sim", "commit": companion_commit}],
            "backends": {"fake": ".fake:FakeTopicWorld"},
            "sdk_version": json.loads((gs.TUTORIAL / "driver.lock.json").read_text())["sdk_version"],
            "authored_by": {"kind": "model", "model_id": "test", "run_id": "test", "date": "2026-11-05"},
            "reviewed_by": None}
    (directory / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    gs.regenerate(directory)
    return root, directory


def messages(report, gate: str, code: str) -> list[str]:
    return [finding["message"] for item in report["gates"] if item["id"] == gate
            for finding in item.get("findings") or [] if finding["code"] == code]


class OperatorBridgeParserTests(unittest.TestCase):
    def test_the_parameter_bridge_forms(self) -> None:
        self.assertEqual(parse_operator_bridge("/world/w/control@ros_gz_interfaces/srv/ControlWorld"),
                         {"name": "/world/w/control", "kind": "service", "ros_type": "ros_gz_interfaces/srv/ControlWorld",
                          "direction": "service", "gz_types": ()})
        self.assertEqual(parse_operator_bridge("/world/w/control@ros_gz_interfaces/srv/ControlWorld@gz.msgs.WorldControl"
                                               "@gz.msgs.Boolean")["gz_types"], ("gz.msgs.WorldControl", "gz.msgs.Boolean"))
        for symbol, direction in (("@", "both"), ("[", "gz_to_ros"), ("]", "ros_to_gz")):
            parsed = parse_operator_bridge(f"/world/w/stats@ros_gz_interfaces/msg/WorldStatistics{symbol}"
                                           "ignition.msgs.WorldStatistics")
            self.assertEqual((parsed["kind"], parsed["direction"]), ("topic", direction))

    def test_anything_else_is_refused(self) -> None:
        for text in ("world/w/control@ros_gz_interfaces/srv/ControlWorld", "/world/w/control",
                     "/world/w/control@ros_gz_interfaces/ControlWorld", "/world/w/stats@ros_gz_interfaces/msg/X",
                     "/world/w/control@ros_gz_interfaces/srv/ControlWorld[gz.msgs.WorldControl",
                     "/world/w/control@ros_gz_interfaces/srv/ControlWorld]gz.msgs.WorldControl@gz.msgs.Boolean",
                     "/world/w/control@ros_gz_interfaces/srv/ControlWorld@gz.msgs.WorldControl",
                     "/world/w/stats@ros_gz_interfaces/msg/X[std_msgs.Float", "/world/w/stats@a/msg/X[gz.msgs.X@y",
                     "/world/w/stats@a/msg/X[gz.msgs.X --ros-args", "", None, 7, "/a@b/msg/C[gz.msgs.D]gz.msgs.E"):
            with self.subTest(text=text):
                self.assertIsNone(parse_operator_bridge(text))


class TopicGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root, self.dir = scratch_package(self)

    def check(self, gates=None):
        return gs.check(self.dir, root=self.root, **({"gates": gates} if gates else {}))

    def test_gates_one_to_eight_pass_and_the_reference_lists_the_bridges(self) -> None:
        report = self.check()
        self.assertEqual(report["failed"], [], stall.failed(report))
        self.assertEqual([code for code in gs.findings(report, severity=None) if "FRESH" in code
                          or "OPERATOR" in code or "COMPANION" in code], [])
        reference = json.loads((self.dir / "reference.json").read_text())
        self.assertEqual([item["args"] for item in reference["safety"]["operator_bridges"]],
                         ["/world/w/control@ros_gz_interfaces/srv/ControlWorld",
                          "/world/w/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics"])
        markdown = (self.dir / "REFERENCE.md").read_text()
        self.assertIn("## Operator must run", markdown)
        self.assertIn("`/world/w/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics`", markdown)
        self.assertIn("The world control service: the e-stop and the resume.", markdown)

    def test_g3_refuses_a_worst_case_beyond_the_budget_and_a_malformed_bridge(self) -> None:
        gs.edit(self.dir, "driver.py", "    estop_latency_ms = 1500\n", "")
        report = self.check(["G3"])
        problems = messages(report, "G3", "G3.DEFINITION")
        self.assertTrue(any("worst case 1100 ms" in text and "budget 1000 ms" in text for text in problems), problems)
        root, directory = scratch_package(self)
        gs.edit(directory, "driver.py", '"/world/w/control@ros_gz_interfaces/srv/ControlWorld", "ref"',
                '"control@ros_gz_interfaces", "ref"')
        problems = messages(gs.check(directory, root=root, gates=["G3"]), "G3", "G3.DEFINITION")
        self.assertTrue(any("operator_bridges[0].args" in text for text in problems), problems)

    def test_g7_refuses_a_fresh_read_back_out_of_scope_or_of_the_wrong_field_or_world(self) -> None:
        cases = {
            "a fresh read-back on a stop that cites no companion": (
                ('"source_ref": _RUN + ":3", "type_ref": _BRIDGE + ":3", "state_ref": _RUN + ":7"',
                 '"source_ref": "node.cpp:1", "type_ref": "node.cpp:1"'), "G7.ROS_FRESH_SCOPE", None),
            "an acknowledgement field": (('"success": {"path": "paused", "equals": True}',
                                          '"success": {"path": "success", "equals": True}'),
                                         "G7.ROS_COMPANION_READBACK", "acknowledgement"),
            "another world": (('"topic": "/world/w/stats"', '"topic": "/world/other/stats"'),
                              "G7.ROS_COMPANION_READBACK", "namespace"),
            "state_ref without the flag": (('"state_ref": _RUN + ":5"', '"state_ref": _RUN + ":4"'),
                                           "G7.ROS_COMPANION_READBACK", "'paused'"),
        }
        for name, ((old, new), code, word) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(TOPIC_DRIVER.count(old), 1, old)
                root, directory = scratch_package(self, TOPIC_DRIVER.replace(old, new))
                report = gs.check(directory, root=root, gates=["G7"])
                self.assertIn(code, gs.findings(report, "G7"), stall.failed(report))
                if word is not None:
                    self.assertTrue(any(word in text for text in messages(report, "G7", code)),
                                    messages(report, "G7", code))

    def test_g7_refuses_a_non_boolean_flag_and_accepts_an_implicit_subscription(self) -> None:
        # The bridge refuses a non-boolean flag at definition (G3); G7 refuses it on its own as well.
        root, directory = scratch_package(self)
        gs.edit(directory, "driver.py", '"success": {"path": "paused", "equals": True},\n          "fresh"',
                '"success": {"path": "paused", "equals": 1},\n          "fresh"')
        report = gs.check(directory, root=root, gates=["G7"])
        self.assertTrue(any("boolean" in text for text in messages(report, "G7", "G7.ROS_COMPANION_READBACK")),
                        stall.failed(report))
        # Without an explicit operation the read-back still subscribes, and G7 allows the recorded subscription.
        root, directory = scratch_package(self, TOPIC_DRIVER.replace('"operation": "subscribe",\n          "source_name": '
                                                                     '"stats"', '"source_name": "stats"'))
        report = gs.check(directory, root=root, gates=["G6", "G7"])
        self.assertEqual(gs.findings(report, "G7", severity=None), [], stall.failed(report))

    def test_g7_checks_the_operator_bridges(self) -> None:
        control = ('        {"args": "/world/w/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE + ":4",\n'
                   '         "description": "The world control service: the e-stop and the resume."},\n')
        cases = {
            "no bridge for the stop and the resume": ((control, ""), "G7.ROS_OPERATOR_BRIDGE_MISSING", 2),
            "a citation that does not show the type": (('"ref": _BRIDGE + ":4"', '"ref": _BRIDGE + ":1"'),
                                                       "G7.ROS_OPERATOR_BRIDGE_REF", 1),
            "a bridge that no binding uses": (
                (control, control + '        {"args": "/world/w/clock@ros_gz_interfaces/msg/WorldStatistics'
                                    '[gz.msgs.WorldStatistics", "ref": _BRIDGE + ":2"},\n'),
                "G7.ROS_OPERATOR_BRIDGE_UNUSED", 1),
            "a stats bridge towards Gazebo": (('WorldStatistics[gz.msgs.WorldStatistics"',
                                               'WorldStatistics]gz.msgs.WorldStatistics"'),
                                              "G7.ROS_OPERATOR_BRIDGE_MISSING", 1),
        }
        for name, ((old, new), code, count) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(TOPIC_DRIVER.count(old), 1, old)
                root, directory = scratch_package(self, TOPIC_DRIVER.replace(old, new))
                report = gs.check(directory, root=root, gates=["G7"])
                self.assertEqual(gs.findings(report, "G7").count(code), count, stall.failed(report))

    def test_g7_binds_a_bridge_only_of_the_binding_ros_type(self) -> None:
        # integrator v4 (2026-11-05; Claude Sonnet safety lens F1 of p3-companion-3): the right name and a service
        # bridge, but another ROS type, serve no binding: the bridge is unused, and the stop and the resume miss theirs.
        old = '"/world/w/control@ros_gz_interfaces/srv/ControlWorld", "ref"'
        self.assertEqual(TOPIC_DRIVER.count(old), 1, old)
        root, directory = scratch_package(self, TOPIC_DRIVER.replace(old, '"/world/w/control@std_srvs/srv/Empty", "ref"'))
        report = gs.check(directory, root=root, gates=["G7"])
        found = gs.findings(report, "G7")
        self.assertEqual(found.count("G7.ROS_OPERATOR_BRIDGE_UNUSED"), 1, stall.failed(report))
        self.assertEqual(found.count("G7.ROS_OPERATOR_BRIDGE_MISSING"), 2, stall.failed(report))

    def test_g6_catches_a_bridge_that_confirms_without_fresh_samples(self) -> None:
        original = ros_bridge.RosBridge._topic_read_back
        ros_bridge.RosBridge._topic_read_back = lambda bridge, spec, context: {}
        self.addCleanup(setattr, ros_bridge.RosBridge, "_topic_read_back", original)
        report = self.check(["G6"])
        found = messages(report, "G6", "G6.FRESH_FAIL_OPEN")
        self.assertEqual(len(found), 3, stall.failed(report))
        self.assertTrue(any("replayed on subscribe" in text for text in found), found)

    def test_g6_catches_a_bridge_that_counts_a_replayed_burst(self) -> None:
        original = ros_bridge.RosBridge._topic_read_back

        def burst_counts(bridge, spec, context):
            fresh = dict(spec["fresh"], min_interval_ms=0.0)
            return original(bridge, dict(spec, fresh=fresh), context)

        ros_bridge.RosBridge._topic_read_back = burst_counts
        self.addCleanup(setattr, ros_bridge.RosBridge, "_topic_read_back", original)
        found = messages(self.check(["G6"]), "G6", "G6.FRESH_FAIL_OPEN")
        self.assertEqual(len(found), 1, found)
        self.assertIn("replayed on subscribe", found[0])


class ShowRefsOperatorBridgeTests(unittest.TestCase):
    def test_an_operator_bridge_citation_is_listed(self) -> None:
        path = Path(__file__).resolve().parents[3] / "handoff" / "tools" / "show_refs.py"
        spec = importlib.util.spec_from_file_location("show_refs_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = gs.temp_root(self)
        driver = root / "driver.py"
        driver.write_text('_BRIDGE = "companion:ros_gz/ros_gz_bridge/README.md"\n'
                          'operator_bridges = [\n'
                          '    {"args": "/world/w/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE + ":86"},\n'
                          ']\n'
                          'commands = {"x": {"topic": "/a", "args": {"data": {"from": "input.a"}}, "ref": "no"}}\n')
        found = module.citations(driver)
        self.assertEqual([(what, ref) for _line, what, ref in found],
                         [("operator bridge '/world/w/control@ros_gz_interfaces/srv/ControlWorld'",
                           "companion:ros_gz/ros_gz_bridge/README.md:86")])


if __name__ == "__main__":
    unittest.main()
