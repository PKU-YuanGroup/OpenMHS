"""The gate on E1 (stall read-back) and E4 (list-element read-back) packages (companion preflight 2, 2026-11-05).

Two scratch ROS 2 packages whose stop, read-back and re-enable cite a companion fixture: a world pause confirmed by a
``get_model_list`` stamp that no longer advances (E1), and a controller switch confirmed by the ``list_controllers``
element of the switched controller (E4). Covered: both pass G1 to G8; G3 refuses a stall whose worst case exceeds the
e-stop budget; G7 refuses a stall without a companion-cited stop (``ROS_STALL_SCOPE``), without a companion fact, or
whose ``state_ref`` does not show the stalled field, and a list read-back whose ``state_ref`` does not show the
selected field and keys; G6 ``STALL_FAIL_OPEN`` catches a bridge that would confirm the stop from one answer.
"""

from __future__ import annotations

import json
import unittest

from mhs.bridge import ros as ros_bridge

from tests.driver import gate_support as gs
from tests.driver import test_companion_sources as base

INIT_CPP = """// companion world plugin fixture (ROS 2), not upstream code
pause_service_ = node->create_service<std_srvs::srv::Empty>(
  "pause_physics", std::bind(&OnPause, this));
unpause_service_ = node->create_service<std_srvs::srv::Empty>(
  "unpause_physics", std::bind(&OnUnpause, this));
void OnPause() { world_->SetPaused(true); }
void OnUnpause() { world_->SetPaused(false); }
model_list_service_ = node->create_service<gazebo_msgs::srv::GetModelList>(
  "get_model_list", std::bind(&GetModelList, this));
res->header.stamp = Convert<builtin_interfaces::msg::Time>(world_->SimTime());
res->success = true;
if (!this->IsPaused() || this->dataPtr->stepInc > 0) { this->dataPtr->simTime += stepTime; }
switch_service_ = create_service<controller_manager_msgs::srv::SwitchController>(
  "~/switch_controller", cb);
list_service_ = create_service<controller_manager_msgs::srv::ListControllers>(
  "~/list_controllers", cb);
controller_state.name = controllers[i].info.name;
controller_state.state = controllers[i].c->get_state().label();
response->ok = true;
controller_state.kind = controllers[i].info.type;
"""
VERSION_TXT = "gazebo_ros 3.9.0\ndistro: ROS Humble, ament\n"
README = "# Scratch world\n\nRuns on ROS Humble.\nBuilt with ament.\n"
NODE_CPP = """pub_ = create_publisher<std_msgs::msg::Float64>("level", 1);
const double kMaxLevel = 10.0;  // levels from 0 to 10
state_ = create_publisher<std_msgs::msg::Float64>("level_state", 1);
"""

STALL_DRIVER = """from mhs.driver import Action, Fact, Field, Limit, RosDriver

_API = "companion:sim_ros/src/init.cpp"
_PAUSE = {"service": "/pause_physics", "type": "std_srvs/srv/Empty", "source_name": "pause_physics",
          "source_ref": _API + ":2-3", "type_ref": _API + ":2", "state_ref": _API + ":6",
          "request": {}, "success": {"path": "$", "equals": {}}, "timeout_ms": 300}
_READBACK = {"service": "/get_model_list", "type": "gazebo_msgs/srv/GetModelList", "source_name": "get_model_list",
             "source_ref": _API + ":8-9", "type_ref": _API + ":8", "state_ref": _API + ":10", "request": {},
             "success": {"path": "success", "equals": True}, "timeout_ms": 300,
             "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 150, "unchanged": True}}


class StallWorld(RosDriver):
    device_id = "stall-world"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 2
    estop_latency_ms = 1500
    backends = {"fake": ".fake:FakeStallWorld"}
    facts = [Fact("OnPause sets the world's paused flag.", source="upstream_code", ref=_API + ":6"),
             Fact("World::Step advances sim time only when the world is not paused or a step is pending.",
                  source="upstream_code", ref=_API + ":12"),
             Fact("The node publishes the level on the level topic.", source="upstream_code", ref="node.cpp:1")]
    safe_state = "The world is paused: two get_model_list answers 150 ms apart carried the same sim-time stamp."
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
        "x-cap.acme.resume.v1": {"service": "/unpause_physics", "type": "std_srvs/srv/Empty",
                                 "source_name": "unpause_physics", "source_ref": _API + ":4-5",
                                 "type_ref": _API + ":4", "request": {}, "success": {"path": "$", "equals": {}},
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

STALL_FAKE = """from mhs.bridge.ros_transport import RecordingRosTransport


class FakeStallWorld(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False
        self.sim_ns = 1000  # placeholder
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
        values = {}
        if service == "/pause_physics":
            self.paused = True
        elif service == "/unpause_physics":
            self.paused = False
        elif service == "/get_model_list":
            if not self.paused:
                self.sim_ns += 1000
            values = {"header": {"stamp": {"sec": 0, "nanosec": self.sim_ns}, "frame_id": ""},
                      "model_names": ["ground_plane"], "success": True}
        else:
            return {"op": "service_response", "service": service, "result": False, "values": {}}
        return {"op": "service_response", "service": service, "result": True, "values": values}
"""

LIST_DRIVER = """from mhs.driver import Action, Fact, Field, RosDriver

_API = "companion:sim_ros/src/init.cpp"
_JTC = "joint_trajectory_controller"
_SWITCH = {"service": "/controller_manager/switch_controller", "type": "controller_manager_msgs/srv/SwitchController",
           "source_name": "~/switch_controller", "source_ref": _API + ":13-14", "type_ref": _API + ":13",
           "state_ref": _API + ":19", "request": {"deactivate_controllers": [_JTC], "strictness": 2},
           "success": {"path": "ok", "equals": True}, "timeout_ms": 400}
_LIST = {"service": "/controller_manager/list_controllers", "type": "controller_manager_msgs/srv/ListControllers",
         "source_name": "~/list_controllers", "source_ref": _API + ":15-16", "type_ref": _API + ":15",
         "state_ref": _API + ":17-18", "request": {},
         "success": {"path": "controller", "where": {"name": _JTC}, "field": "state", "equals": "inactive"},
         "timeout_ms": 400}


class ListArm(RosDriver):
    device_id = "list-arm"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 2
    backends = {"fake": ".fake:FakeListArm"}
    facts = [Fact("list_controllers reports each controller's name and state.", source="upstream_code",
                  ref=_API + ":17-18")]
    safe_state = "The trajectory controller is inactive, as list_controllers reports."
    fidelity = {"engine": "canned:test fixture", "fidelity_level": "F0",
                "determinism": {"kind": "none", "notes": "test fixture"}, "timestep_ms": 0, "realtime_factor": 0,
                "reset": "none", "snapshot_restore": False, "gaps": ["a test fixture, not a simulator"]}
    commands = {
        "x-cap.acme.activate.v1": {"service": "/controller_manager/switch_controller",
                                   "type": "controller_manager_msgs/srv/SwitchController",
                                   "source_name": "~/switch_controller", "source_ref": _API + ":13-14",
                                   "type_ref": _API + ":13", "request": {"activate_controllers": [_JTC], "strictness": 2},
                                   "success": {"path": "ok", "equals": True},
                                   "result": {"acknowledged": {"value": True}}},
    }
    actions = {
        "x-cap.acme.activate.v1": Action(
            name="activate", verb="invoke", reenable=True, description="Re-activate the controller after a reset",
            output={"acknowledged": Field("boolean", description="The switch answered ok")}),
    }
    safety_bindings = {"estop": _SWITCH, "safe_state": _LIST}
"""

LIST_FAKE = """from mhs.bridge.ros_transport import RecordingRosTransport


class FakeListArm(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.state = "active"

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        service = message.get("service")
        request = message.get("args") or {}
        if service == "/controller_manager/switch_controller":
            if "joint_trajectory_controller" in (request.get("deactivate_controllers") or []):
                self.state = "inactive"
            if "joint_trajectory_controller" in (request.get("activate_controllers") or []):
                self.state = "active"
            values = {"ok": True}
        elif service == "/controller_manager/list_controllers":
            values = {"controller": [{"name": "joint_state_broadcaster", "state": "active"},
                                     {"name": "joint_trajectory_controller", "state": self.state}]}
        else:
            return {"op": "service_response", "service": service, "result": False, "values": {}}
        return {"op": "service_response", "service": service, "result": True, "values": values}
"""


def scratch_package(test: unittest.TestCase, name: str, driver: str, fake: str):
    """A scratch ROS 2 package ``robots/acme/<name>`` whose card declares the companion fixture ``sim_ros``."""
    root = gs.temp_root(test)
    (root / "MHS" / "sdk").mkdir(parents=True)
    clone = root / "robots" / "acme" / name
    clone.mkdir(parents=True)
    (clone / "node.cpp").write_text(NODE_CPP)
    (clone / "README.md").write_text(README)
    gs.git(clone, "init", "-q")
    gs.git(clone, "add", "-A")
    gs.git(clone, "commit", "-q", "-m", name)
    commit = gs.git(clone, "rev-parse", "HEAD")
    _companion, companion_commit = base.companion_repo(
        test, root, files={"src/init.cpp": INIT_CPP, "VERSION.txt": VERSION_TXT})
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
    entry["profile"] = "ros2-humble-gazebo11"
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
    lock = {"$schema": "https://mhs.openai4s.org/schema/0.9/driver-lock.schema.json", "openmhs": "0.9",
            "package_id": f"gh.acme/{name}",
            "upstream": {"repo_url": f"https://github.com/acme/{name}", "commit": commit, "license_spdx": "MIT"},
            "companions": [{"package_id": "gh.acme/sim", "commit": companion_commit}],
            "backends": {"fake": f".fake:{fake.split('class ')[1].split('(')[0]}"},
            "sdk_version": json.loads((gs.TUTORIAL / "driver.lock.json").read_text())["sdk_version"],
            "authored_by": {"kind": "model", "model_id": "test", "run_id": "test", "date": "2026-11-05"},
            "reviewed_by": None}
    (directory / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    gs.regenerate(directory)
    return root, directory


def failed(report) -> str:
    return json.dumps([gate for gate in report["gates"] if gate["status"] == "fail"], indent=1)[:3000]


class StallGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root, self.dir = scratch_package(self, "stall_world", STALL_DRIVER, STALL_FAKE)

    def check(self, gates=None):
        return gs.check(self.dir, root=self.root, **({"gates": gates} if gates else {}))

    def test_gates_one_to_eight_pass(self) -> None:
        report = self.check()
        self.assertEqual(report["failed"], [], failed(report))
        self.assertEqual([code for code in gs.findings(report, severity=None) if "STALL" in code
                          or "COMPANION" in code], [])

    def test_g3_refuses_a_worst_case_beyond_the_budget(self) -> None:
        gs.edit(self.dir, "driver.py", "    estop_latency_ms = 1500\n", "")
        report = self.check(["G3"])
        problems = [finding["message"] for gate in report["gates"] if gate["id"] == "G3"
                    for finding in gate.get("findings") or [] if finding["code"] == "G3.DEFINITION"]
        self.assertTrue(any("worst case 1050 ms" in text and "budget 1000 ms" in text for text in problems), problems)

    def test_g7_refuses_a_stall_without_its_scope_fact_or_field(self) -> None:
        cases = {
            "a stall on a stop that cites no companion": (
                ('"source_ref": _API + ":2-3", "type_ref": _API + ":2", "state_ref": _API + ":6"',
                 '"source_ref": "node.cpp:1", "type_ref": "node.cpp:1"'), "G7.ROS_STALL_SCOPE"),
            "no companion fact": (
                ('    facts = [Fact("OnPause sets the world\'s paused flag.", source="upstream_code", ref=_API + ":6"),\n'
                 '             Fact("World::Step advances sim time only when the world is not paused or a step is '
                 'pending.",\n                  source="upstream_code", ref=_API + ":12"),\n',
                 '    facts = [\n'), "G7.ROS_COMPANION_READBACK"),
            "state_ref without the stalled field": (('"state_ref": _API + ":10"', '"state_ref": _API + ":11"'),
                                                    "G7.ROS_COMPANION_READBACK"),
        }
        for name, ((old, new), code) in cases.items():
            with self.subTest(name=name):
                root, directory = scratch_package(self, "stall_world", STALL_DRIVER.replace(old, new), STALL_FAKE)
                report = gs.check(directory, root=root, gates=["G7"])
                self.assertIn(code, gs.findings(report, "G7"), failed(report))

    def test_g6_catches_a_bridge_that_confirms_the_stall_from_one_answer(self) -> None:
        original = ros_bridge.RosBridge._stall_read_back

        def one_answer(bridge, spec, context):
            return bridge._invoke(spec, {}, context, safety=True)

        ros_bridge.RosBridge._stall_read_back = one_answer
        self.addCleanup(setattr, ros_bridge.RosBridge, "_stall_read_back", original)
        report = self.check(["G6"])
        self.assertIn("G6.STALL_FAIL_OPEN", gs.findings(report, "G6"), failed(report))


class ListGateTests(unittest.TestCase):
    def test_gates_one_to_eight_pass(self) -> None:
        root, directory = scratch_package(self, "list_arm", LIST_DRIVER, LIST_FAKE)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], failed(report))

    def test_g7_refuses_a_state_ref_without_the_selected_field_and_keys(self) -> None:
        driver = LIST_DRIVER.replace('"state_ref": _API + ":17-18"', '"state_ref": _API + ":19"')
        root, directory = scratch_package(self, "list_arm", driver, LIST_FAKE)
        report = gs.check(directory, root=root, gates=["G7"])
        messages = [finding["message"] for gate in report["gates"] if gate["id"] == "G7"
                    for finding in gate.get("findings") or [] if finding["code"] == "G7.ROS_COMPANION_READBACK"]
        self.assertTrue(any("'state'" in text for text in messages), messages)
        self.assertTrue(any("'name'" in text for text in messages), messages)


MULTI_DRIVER = """from mhs.driver import Action, Fact, Field, RosDriver

_API = "companion:sim_ros/src/init.cpp"
_ARM = "joint_trajectory_controller"
_GRIP = "gripper_controller"
_SWITCH = {"service": "/controller_manager/switch_controller", "type": "controller_manager_msgs/srv/SwitchController",
           "source_name": "~/switch_controller", "source_ref": _API + ":13-14", "type_ref": _API + ":13",
           "state_ref": _API + ":19", "request": {"deactivate_controllers": [_ARM, _GRIP], "strictness": 2},
           "success": {"path": "ok", "equals": True}, "timeout_ms": 400}
_LIST = {"service": "/controller_manager/list_controllers", "type": "controller_manager_msgs/srv/ListControllers",
         "source_name": "~/list_controllers", "source_ref": _API + ":15-16", "type_ref": _API + ":15",
         "state_ref": _API + ":17-20", "request": {},
         "success": {"path": "controller", "where": [{"name": _ARM}, {"kind": "gripper"}],
                     "field": "state", "equals": "inactive"},
         "timeout_ms": 400}


class MultiArm(RosDriver):
    device_id = "multi-arm"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R1"
    ros_version = 2
    backends = {"fake": ".fake:FakeMultiArm"}
    facts = [Fact("list_controllers reports each controller's name, state and kind.", source="upstream_code",
                  ref=_API + ":17-20")]
    safe_state = "The arm and gripper controllers are both inactive, as list_controllers reports."
    fidelity = {"engine": "canned:test fixture", "fidelity_level": "F0",
                "determinism": {"kind": "none", "notes": "test fixture"}, "timestep_ms": 0, "realtime_factor": 0,
                "reset": "none", "snapshot_restore": False, "gaps": ["a test fixture, not a simulator"]}
    commands = {
        "x-cap.acme.note.v1": {"topic": "/level", "type": "std_msgs/msg/Float64", "operation": "publish",
                               "source_name": "level", "source_ref": "node.cpp:1", "type_ref": "node.cpp:1",
                               "message": {"data": 0.0}},
    }
    actions = {
        "x-cap.acme.note.v1": Action(name="note", verb="invoke", description="Publish a level the fixture ignores",
                                     output={"published": Field("boolean", description="Handed to rosbridge"),
                                             "confirmed": Field("boolean", description="Always false")}),
    }
    safety_bindings = {"estop": _SWITCH, "safe_state": _LIST}
"""

MULTI_FAKE = """from mhs.bridge.ros_transport import RecordingRosTransport


class FakeMultiArm(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.arm = "active"
        self.gripper = "active"

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        service = message.get("service")
        request = message.get("args") or {}
        if service == "/controller_manager/switch_controller":
            names = request.get("deactivate_controllers") or []
            if "joint_trajectory_controller" in names:
                self.arm = "inactive"
            if "gripper_controller" in names:
                self.gripper = "inactive"
            values = {"ok": True}
        elif service == "/controller_manager/list_controllers":
            values = {"controller": [{"name": "joint_trajectory_controller", "state": self.arm, "kind": "arm"},
                                     {"name": "gripper_controller", "state": self.gripper, "kind": "gripper"}]}
        else:
            return {"op": "service_response", "service": service, "result": False, "values": {}}
        return {"op": "service_response", "service": service, "result": True, "values": values}
"""


class MultiListGateTests(unittest.TestCase):
    def test_gates_one_to_eight_pass_for_several_selectors(self) -> None:
        root, directory = scratch_package(self, "multi_arm", MULTI_DRIVER, MULTI_FAKE)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], failed(report))

    def test_g7_requires_a_key_that_only_a_later_selector_uses(self) -> None:
        driver = MULTI_DRIVER.replace('"state_ref": _API + ":17-20"', '"state_ref": _API + ":17-18"')
        root, directory = scratch_package(self, "multi_arm", driver, MULTI_FAKE)
        report = gs.check(directory, root=root, gates=["G7"])
        messages = [finding["message"] for gate in report["gates"] if gate["id"] == "G7"
                    for finding in gate.get("findings") or [] if finding["code"] == "G7.ROS_COMPANION_READBACK"]
        self.assertTrue(any("'kind'" in text for text in messages), messages)


if __name__ == "__main__":
    unittest.main()
