"""Action-stop provenance remains exact and ROS version checks precede factories."""

import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from mhs.bridge.ros_actions import PendingAction
from mhs.driver import Action, RosDriver
from mhs.driver.check import Gate, _g7
from mhs.driver.upstream import UpstreamTree
from mhs.testing.recorder import RecordLog


class RosActionSafetyGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="mhs-stop-action-g7-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "stop.cpp").write_text(
            '#include <franka_gripper/StopAction.h>\n'
            'SimpleActionServer<franka_gripper::StopAction> server(nh, "stop", callback, false);\n')
        self.spec = {"action": "/franka_gripper/stop", "type": "franka_gripper/StopAction",
                     "profile": "ros1-actionlib", "source_name": "stop",
                     "source_ref": "stop.cpp:2", "type_ref": "stop.cpp:1",
                     "success": {"path": "success", "equals": True}}

    def check(self, name="estop", spec=None, frames=None):
        spec = copy.deepcopy(spec or self.spec)
        cls = SimpleNamespace(commands={}, reads={}, writes={}, safety_bindings={name: spec}, ros_version=1)
        pending = PendingAction("exact-stop-id", "/franka_gripper/stop", "franka_gripper/StopAction", "ros1-actionlib")
        messages = frames if frames is not None else pending.setup() + [pending.goal({})]
        log = RecordLog("source-shaped stop")
        for message in messages:
            log.record("send", "call", (message,))
        gate = Gate("G7", "Native surface")
        _g7(SimpleNamespace(cls=cls, family="ros", tree=UpstreamTree(self.root, use_git=False), logs=[log]), gate)
        return [finding.code for finding in gate.findings if finding.severity == "error"]

    def test_declared_fixed_safety_goals_keep_derived_wire_provenance(self):
        for name in ("estop", "safe_state"):
            self.assertEqual(self.check(name), [])

    def test_reset_action_and_invented_endpoint_are_not_authorized(self):
        self.assertIn("G7.ROS_ACTION_PROFILE", self.check("reset"))
        bad = {**self.spec, "action": "/franka_gripper/pretend_stop", "source_name": "pretend_stop"}
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.check(spec=bad))

    def test_false_type_and_broad_cancel_remain_rejected(self):
        self.assertIn("G7.ROS_TYPE_NOT_UPSTREAM", self.check(spec={**self.spec, "type": "invented/StopAction"}))
        pending = PendingAction("stop-id", "/franka_gripper/stop", "franka_gripper/StopAction", "ros1-actionlib")
        cancel = pending.cancel()
        cancel["msg"]["stamp"] = {"secs": 1, "nsecs": 0}
        self.assertIn("G7.ROS_CANCEL_SCOPE", self.check(frames=[pending.goal({}), cancel]))

    def test_safety_profile_mismatch_refuses_before_backend_factory(self):
        calls = []
        class WrongVersion(RosDriver):
            ros_version = 2
            device_id, device_kind, risk = "wrong-safety-version", "instrument", "R0"
            commands = {"x-cap.test.observe.v1": {"service": "/state", "operation": "read"}}
            actions = {"x-cap.test.observe.v1": Action(name="observe")}
            safety_bindings = {"estop": copy.deepcopy(self.spec)}
            backends = {"fake": lambda: calls.append("factory")}
        with self.assertRaises(ValueError) as caught:
            WrongVersion(backend="fake")
        self.assertIn("action profile", str(caught.exception))
        self.assertEqual(calls, [])
