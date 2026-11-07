"""ROS action provenance, generated wire types and exact cancellation at G7."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.driver.check import Gate, _g7
from mhs.driver.upstream import UpstreamTree
from mhs.testing.recorder import RecordLog
from tests.driver import gate_support as gs


class RosActionGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mhs-action-gate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "ros1.py").write_text(
            "from control_msgs.msg import FollowJointTrajectoryAction\n"
            "client = SimpleActionClient('follow_joint_trajectory', FollowJointTrajectoryAction)\n")
        (self.root / "ros2.py").write_text(
            "from pyrobosim_msgs.action import ExecuteTaskAction\n"
            "server = ActionServer(node, ExecuteTaskAction, 'execute_action', callback)\n")
        self.spec1 = {"action": "/arm/follow_joint_trajectory", "source_name": "follow_joint_trajectory",
                      "type": "control_msgs/FollowJointTrajectoryAction", "profile": "ros1-actionlib",
                      "source_ref": "ros1.py:2", "type_ref": "ros1.py:1",
                      "success": {"path": "error_code", "equals": 0}}
        self.spec2 = {"action": "/world/execute_action", "source_name": "execute_action",
                      "type": "pyrobosim_msgs/action/ExecuteTaskAction", "profile": "ros2-native",
                      "source_ref": "ros2.py:2", "type_ref": "ros2.py:1",
                      "success": {"path": "execution_result.status", "equals": 0}}

    def check(self, spec, messages, *, version=None, group="commands"):
        cls = SimpleNamespace(commands={}, reads={}, writes={}, safety_bindings={},
                              ros_version=version or (1 if spec.get("profile") == "ros1-actionlib" else 2))
        setattr(cls, group, {"execute": spec})
        log = RecordLog("action fake")
        for message in messages:
            log.record("send", "call", (message,))
        gate = Gate("G7", "Native surface")
        _g7(SimpleNamespace(cls=cls, tree=UpstreamTree(self.root, use_git=False), logs=[log], family="ros"), gate)
        return [finding.code for finding in gate.findings if finding.severity == "error"]

    def ros2_goal(self, **changes):
        return {"op": "send_action_goal", "action": self.spec2["action"], "action_type": self.spec2["type"],
                "id": "goal-1", "args": {}, **changes}

    def ros1_goal(self):
        return {"op": "publish", "topic": self.spec1["action"] + "/goal",
                "msg": {"goal_id": {"id": "goal-1", "stamp": {"secs": 0, "nsecs": 0}}, "goal": {}}}

    def ros1_cancel(self, identifier="goal-1", stamp=None):
        return {"op": "publish", "topic": self.spec1["action"] + "/cancel",
                "msg": {"id": identifier, "stamp": {"secs": 0, "nsecs": 0} if stamp is None else stamp}}

    def test_ros1_source_derives_wrapper_topics_without_invented_references(self):
        endpoint = self.spec1["action"]
        messages = [
            {"op": "subscribe", "topic": endpoint + "/result", "type": "control_msgs/FollowJointTrajectoryActionResult"},
            {"op": "subscribe", "topic": endpoint + "/status", "type": "actionlib_msgs/GoalStatusArray"},
            {"op": "subscribe", "topic": endpoint + "/feedback", "type": "control_msgs/FollowJointTrajectoryActionFeedback"},
            {"op": "advertise", "topic": endpoint + "/goal", "type": "control_msgs/FollowJointTrajectoryActionGoal"},
            {"op": "advertise", "topic": endpoint + "/cancel", "type": "actionlib_msgs/GoalID"},
            self.ros1_goal(), self.ros1_cancel(),
            {"op": "unsubscribe", "topic": endpoint + "/result"},
            {"op": "unadvertise", "topic": endpoint + "/goal"},
        ]
        self.assertEqual(self.check(self.spec1, messages), [])

    def test_ros2_goal_and_matching_cancel_use_action_type(self):
        self.assertEqual(self.check(self.spec2, [self.ros2_goal(),
            {"op": "cancel_action_goal", "action": self.spec2["action"], "id": "goal-1"}]), [])

    def test_action_type_is_required_and_cannot_be_replaced_by_type(self):
        message = self.ros2_goal()
        message["type"] = message.pop("action_type")
        self.assertIn("G7.ROS_WIRE_TYPE", self.check(self.spec2, [message]))
        self.assertIn("G7.ROS_WIRE_TYPE", self.check(self.spec2, [
            self.ros2_goal(action_type="pyrobosim_msgs/action/ExecuteTaskPlan")]))

    def test_wrong_profile_version_or_binding_group_fails(self):
        for spec in (dict(self.spec1, profile="ros2-native"), dict(self.spec2, profile="guess")):
            with self.subTest(spec=spec):
                self.assertTrue(self.check(spec, []))
        self.assertIn("G7.ROS_ACTION_PROFILE", self.check(self.spec1, [], version=2))
        self.assertIn("G7.ROS_ACTION_PROFILE", self.check(self.spec2, [], group="reads"))

    def test_profiles_require_their_exact_type_notation(self):
        for spec, candidate in ((self.spec1, "control_msgs/msg/FollowJointTrajectoryAction"),
                                (self.spec1, "control_msgs/FollowJointTrajectory"),
                                (self.spec2, "pyrobosim_msgs/ExecuteTaskAction")):
            with self.subTest(candidate=candidate):
                self.assertIn("G7.ROS_TYPE", self.check(dict(spec, type=candidate), []))

    def test_source_must_show_the_exact_action_name_and_type(self):
        self.assertIn("G7.ROS_TYPE_NOT_UPSTREAM", self.check(
            dict(self.spec2, type="other_msgs/action/ExecuteTaskAction"), []))
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.check(
            dict(self.spec2, action="/world/invented", source_name="invented"), []))
        self.assertIn("G7.ROS_REF_FORMAT", self.check(dict(self.spec1, source_ref=None), []))

    def test_derived_wrapper_names_and_directions_are_exact(self):
        endpoint = self.spec1["action"]
        for message, code in (({"op": "subscribe", "topic": endpoint + "/result",
                               "type": "control_msgs/FollowJointTrajectoryResult"}, "ROS_WIRE_TYPE"),
                              ({"op": "publish", "topic": endpoint + "/result", "msg": {}}, "ROS_WIRE_UNDECLARED"),
                              ({"op": "subscribe", "topic": endpoint + "/goal",
                                "type": "control_msgs/FollowJointTrajectoryActionGoal"}, "ROS_WIRE_UNDECLARED")):
            with self.subTest(message=message):
                self.assertIn("G7." + code, self.check(self.spec1, [message]))

    def test_goal_identifiers_must_be_nonempty(self):
        for identifier in (None, "", 4):
            with self.subTest(identifier=identifier):
                self.assertIn("G7.ROS_GOAL_ID", self.check(self.spec2, [self.ros2_goal(id=identifier)]))
                message = self.ros1_goal()
                message["msg"]["goal_id"]["id"] = identifier
                self.assertIn("G7.ROS_GOAL_ID", self.check(self.spec1, [message]))

    def test_ros1_cancel_never_targets_all_or_timestamp_selected_goals(self):
        for cancel in (self.ros1_cancel(""), self.ros1_cancel("foreign"),
                       self.ros1_cancel(stamp={"secs": 1, "nsecs": 0}),
                       self.ros1_cancel(stamp={})):
            with self.subTest(cancel=cancel):
                self.assertTrue(self.check(self.spec1, [self.ros1_goal(), cancel]))
        self.assertIn("G7.ROS_CANCEL_SCOPE", self.check(self.spec1, [self.ros1_cancel()]))

    def test_ros2_cancel_requires_a_goal_seen_on_the_same_action(self):
        cancel = {"op": "cancel_action_goal", "action": self.spec2["action"], "id": "foreign"}
        self.assertIn("G7.ROS_CANCEL_SCOPE", self.check(self.spec2, [self.ros2_goal(), cancel]))

    def test_service_or_topic_does_not_authorize_native_action_operation(self):
        spec = copy.deepcopy(self.spec2)
        spec["topic"] = spec.pop("action")
        spec["type"] = "pyrobosim_msgs/msg/ExecuteTaskAction"
        self.assertIn("G7.ROS_WIRE_UNDECLARED", self.check(spec, [self.ros2_goal()]))

    def test_complete_action_package_gate_and_mcp_projection_for_both_profiles(self):
        for version in (1, 2):
            with self.subTest(version=version):
                directory = gs.copy_tutorial(self)
                source = (self.root / f"ros{version}.py").read_text()
                source += "node.create_service(std_srvs.srv.Trigger, '/stop', stop_callback)\n"
                source += "# Synthetic source contract: normalized target range is [-1, 1].\n"
                (directory / "vendor" / "action_node.py").write_text(source)
                spec = copy.deepcopy(self.spec1 if version == 1 else self.spec2)
                spec.update(source_ref="action_node.py:2", type_ref="action_node.py:1",
                            request={}, args={"target": {"from": "input.target"}},
                            success={"path": "ok", "equals": True},
                            result={"map": {"ok": "output.ok", "target": "output.target"}})
                stop = {"service": "/stop", "type": "std_srvs/srv/Trigger",
                        "source_ref": "action_node.py:3", "success": {"path": "success", "equals": True}}
                (directory / "driver.py").write_text(
                    "from mhs.driver import RosDriver, Action, Field, Limit\n"
                    "class ActionEndpoint(RosDriver):\n"
                    "    device_id, device_kind, mode, risk = 'action-endpoint', 'instrument', 'hardware', 'R0'\n"
                    f"    ros_version = {version}\n"
                    "    safe_state = 'Independent stop service acknowledged'\n"
                    "    backends = {'fake': '.fake:FakeActionTransport'}\n"
                    f"    commands = {{'x-cap.openmhs-tutorial.goal.v1': {spec!r}}}\n"
                    f"    safety_bindings = {{'estop': {stop!r}}}\n"
                    "    actions = {'x-cap.openmhs-tutorial.goal.v1': Action(name='execute_goal', "
                    "description='Execute the declared test goal', input={'target': Field('number', unit='1', "
                    "description='Normalized target', limit=Limit(min=-1,max=1,source='upstream_code', "
                    "ref='action_node.py:4'))}, output={'ok': Field('boolean', "
                    "description='Application success'), 'target': Field('number', unit='1', "
                    "description='Target confirmed in the native result')}, "
                    "long_running=True, cancellable=True, max_duration_ms=1000)}\n")
                (directory / "fake.py").write_text(
                    "from mhs.bridge.ros_transport import RecordingRosTransport\n"
                    "class FakeActionTransport(RecordingRosTransport):\n"
                    "    def __init__(self):\n        super().__init__(handler=self.reply)\n"
                    "    def reply(self, message):\n"
                    "        if message['op'] == 'call_service':\n"
                    "            return {'op':'service_response','id':message['id'],'service':message['service'],"
                    "'result':True,'values':{'success':True}}\n"
                    "        if message['op'] == 'send_action_goal':\n"
                    "            return {'op':'action_result','id':message['id'],'action':message['action'],"
                    "'result':True,'status':4,'values':{'ok':True,'target':message['args']['target']}}\n"
                    "        if message['op'] == 'publish' and message.get('topic','').endswith('/goal'):\n"
                    "            return {'op':'publish','topic':message['topic'][:-5]+'/result','msg':"
                    "{'status':{'goal_id':message['msg']['goal_id'],'status':3},'result':"
                    "{'ok':True,'target':message['msg']['goal']['target']}}}\n")
                gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R0",
                             "limit_hints": []}, family="ros", helper="RosDriver", decision="family-config")
                gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:FakeActionTransport"})
                gs.edit_json(directory, "site-limits.example.json", devices={
                    "mhs://localhost/action-endpoint": {"x-cap.openmhs-tutorial.goal.v1": {
                        "target": {"min": -0.8, "max": 0.8, "unit": "1", "source": "operator",
                                   "reason": "Synthetic test overlay"}}}})
                gs.regenerate(directory)
                report = gs.check(directory)
                self.assertTrue(report["passed"], report)
                self.assertEqual(gs.statuses(report)["G8"], "pass")


if __name__ == "__main__":
    unittest.main()
