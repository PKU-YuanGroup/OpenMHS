"""ROS G7 uses pinned endpoint/type evidence and recorded messages, not a fictional Python class."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.driver.check import Gate, _Context, _g7, static_findings
from mhs.driver.families import RosDriver
from mhs.driver.upstream import UpstreamTree
from mhs.testing.recorder import RecordLog, Recorder, log_of

from tests.driver import gate_support as gs


CPP = '''#include <std_srvs/srv/trigger.hpp>
node->create_service<std_srvs::srv::Trigger>("~/stop", callback);
node->create_publisher<std_msgs::msg::Float64>("temperature", 10);
node->create_subscription<geometry_msgs::msg::Twist>("cmd_vel", 10, callback);
'''


class RosSourceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mhs-ros-gate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "node.cpp").write_text(CPP)
        self.tree = UpstreamTree(self.root, use_git=False)
        self.stop = {"service": "/robot/stop", "type": "std_srvs/srv/Trigger", "source_name": "~/stop",
                     "source_ref": "node.cpp:2", "success": {"path": "success", "equals": True}}
        self.temperature = {"topic": "/robot/temperature", "type": "std_msgs/msg/Float64",
                            "source_name": "temperature", "source_ref": "node.cpp:3", "path": "data"}
        self.velocity = {"topic": "/robot/cmd_vel", "type": "geometry_msgs/msg/Twist",
                         "source_name": "cmd_vel", "source_ref": "node.cpp:4"}

    def context(self, *, commands=None, reads=None, writes=None, safety=None, messages=None):
        declared = SimpleNamespace(commands=commands or {}, reads=reads or {}, writes=writes or {},
                                   safety_bindings=safety or {})
        log = RecordLog("ros fake")
        for message in messages or []:
            log.record("send", "call", (message,))
        return SimpleNamespace(cls=declared, tree=self.tree, logs=[log], family="ros")

    def check(self, ctx):
        gate = Gate("G7", "Native surface")
        _g7(ctx, gate)
        return gate

    def codes(self, gate, *, severity="error"):
        return [finding.code for finding in gate.findings if finding.severity == severity]

    def test_ros_family_is_detected_without_a_python_native_symbol(self) -> None:
        class Device(RosDriver):
            pass

        context = object.__new__(_Context)
        context.cls = Device
        self.assertEqual(context.family, "ros")
        self.assertTrue(context.transport_family)

    def test_real_package_context_uses_ros_evidence_without_importable_upstream_class(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "vendor" / "node.cpp").write_text(CPP)
        (directory / "driver.py").write_text('''from mhs.driver import Action, Field, RosDriver
class Sensor(RosDriver):
    device_id, device_kind, risk = "temperature-sensor", "thermal.zone", "R0"
    commands = {"x-cap.sensor.sample.v1": {
        "topic": "/robot/temperature", "type": "std_msgs/msg/Float64",
        "source_name": "temperature", "source_ref": "node.cpp:3", "operation": "subscribe",
        "path": "data", "result": {"map": {"temperature": "output.$"}}}}
    actions = {"x-cap.sensor.sample.v1": Action(name="sample", verb="read", output={"temperature": Field("number", unit="Cel")})}
''')
        context = _Context(directory, "fake", None, None, False)
        self.addCleanup(context.close)
        self.assertIsNone(context.import_error)
        self.assertIsNone(context.model_error)
        self.assertEqual(context.family, "ros")
        self.assertEqual(self.codes(self.check(context)), [])

    def test_cpp_service_and_topic_evidence_with_explicit_namespaces(self) -> None:
        context = self.context(commands={"move": self.velocity}, reads={"temperature": self.temperature},
                               safety={"estop": self.stop}, messages=[
            {"op": "call_service", "service": "/robot/stop", "type": "std_srvs/srv/Trigger"},
            {"op": "subscribe", "topic": "/robot/temperature", "type": "std_msgs/msg/Float64"},
            {"op": "unsubscribe", "topic": "/robot/temperature"},
            {"op": "advertise", "topic": "/robot/cmd_vel", "type": "geometry_msgs/msg/Twist"},
            {"op": "publish", "topic": "/robot/cmd_vel", "msg": {"linear": {"x": 0.0}}},
        ])
        self.assertEqual(self.check(context).findings, [])

    def test_ros1_types_and_python_import_type_reference(self) -> None:
        (self.root / "node.py").write_text('from std_srvs.srv import Trigger\nrospy.Service("~stop", Trigger, stop)\n')
        stop = dict(self.stop, type="std_srvs/Trigger", source_name="~stop", source_ref="node.py:2",
                    type_ref="node.py:1")
        gate = self.check(self.context(safety={"estop": stop}, messages=[
            {"op": "call_service", "service": "/robot/stop"}]))
        self.assertEqual(gate.findings, [])

    def test_separate_cpp_include_reference_is_supported(self) -> None:
        stop = dict(self.stop, type_ref="node.cpp:1")
        self.assertEqual(self.codes(self.check(self.context(safety={"estop": stop}))), [])

    def test_cpp_include_preserves_an_acronym_in_generated_file_names(self) -> None:
        (self.root / "tf.cpp").write_text('#include <tf2_msgs/msg/tf_message.hpp>\nsubscribe("/tf", callback);\n')
        reading = {"topic": "/tf", "type": "tf2_msgs/msg/TFMessage", "source_ref": "tf.cpp:2",
                   "type_ref": "tf.cpp:1"}
        self.assertEqual(self.codes(self.check(self.context(reads={"tf": reading}))), [])

    def test_service_and_message_types_cannot_be_interchanged(self) -> None:
        stop = dict(self.stop, type="std_srvs/msg/Trigger")
        self.assertIn("G7.ROS_TYPE", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_missing_type_is_an_error_even_if_rosbridge_could_infer_it(self) -> None:
        stop = {key: value for key, value in self.stop.items() if key != "type"}
        self.assertIn("G7.ROS_TYPE", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_each_binding_group_requires_its_own_evidence(self) -> None:
        bad = {key: value for key, value in self.stop.items() if key != "source_ref"}
        cases = [dict(commands={"stop": bad}), dict(reads={"stopped": bad}), dict(writes={"stopped": bad}),
                 dict(safety={"estop": bad}), dict(safety={"safe_state": bad}), dict(safety={"reset": bad}),
                 dict(safety={"interlocks": [dict(bad, id="door")]})]
        for case in cases:
            with self.subTest(case=case):
                self.assertIn("G7.ROS_REF_FORMAT", self.codes(self.check(self.context(**case))))

    def test_missing_binary_out_of_range_and_escaping_references_fail(self) -> None:
        (self.root / "manual.pdf").write_bytes(b"PDF\0not text")
        for reference, code in (("absent.cpp:1", "ROS_REF_MISSING"), ("node.cpp:999", "ROS_REF_LINE"),
                                ("../node.cpp:2", "ROS_REF_FORMAT"), ("manual.pdf:1", "ROS_REF_MISSING")):
            with self.subTest(reference=reference):
                gate = self.check(self.context(safety={"estop": dict(self.stop, source_ref=reference)}))
                self.assertIn("G7." + code, self.codes(gate))

    def test_arbitrary_existing_line_is_not_endpoint_evidence(self) -> None:
        stop = dict(self.stop, source_ref="node.cpp:1")
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_relative_name_needs_an_exact_literal_not_an_arbitrary_word(self) -> None:
        (self.root / "README.md").write_text('Use stop to stop a robot. std_srvs/srv/Trigger\n')
        stop = dict(self.stop, source_name="stop", source_ref="README.md:1")
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_wrong_namespace_suffix_and_absolute_remapping_fail(self) -> None:
        for stop in (dict(self.stop, service="/robot/not_stop"), dict(self.stop, source_name="/stop")):
            with self.subTest(stop=stop):
                self.assertIn("G7.ROS_SOURCE_NAME", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_endpoint_prefix_is_not_a_match(self) -> None:
        (self.root / "README.md").write_text('The endpoint `/robot/stop_extra` uses std_srvs/srv/Trigger.\n')
        stop = {key: value for key, value in dict(self.stop, source_ref="README.md:1").items()
                if key != "source_name"}
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_wrong_type_name_or_package_is_not_supported_by_same_short_name(self) -> None:
        for ros_type in ("std_srvs/srv/SetBool", "other_srvs/srv/Trigger", "std_srvs/srv/Trig"):
            gate = self.check(self.context(safety={"estop": dict(self.stop, type=ros_type)}))
            self.assertIn("G7.ROS_TYPE_NOT_UPSTREAM", self.codes(gate))

    def test_wrong_type_reference_cannot_borrow_from_source_reference(self) -> None:
        stop = dict(self.stop, type_ref="node.cpp:3")
        self.assertIn("G7.ROS_TYPE_NOT_UPSTREAM", self.codes(self.check(self.context(safety={"estop": stop}))))

    def test_wire_undeclared_endpoint_or_operation_fails(self) -> None:
        for message in ({"op": "call_service", "service": "/robot/unlisted"},
                        {"op": "publish", "topic": "/robot/stop", "msg": {}},
                        {"op": "set_param", "topic": "/robot/stop"}):
            gate = self.check(self.context(safety={"estop": self.stop}, messages=[message]))
            self.assertIn("G7.ROS_WIRE_UNDECLARED", self.codes(gate))

    def test_wire_type_mismatch_and_non_object_messages_fail(self) -> None:
        gate = self.check(self.context(safety={"estop": self.stop}, messages=[
            {"op": "call_service", "service": "/robot/stop", "type": "std_srvs/srv/SetBool"}]))
        self.assertIn("G7.ROS_WIRE_TYPE", self.codes(gate))
        for payload in ('{"op":"call_service"}', None, [], 1):
            gate = self.check(self.context(safety={"estop": self.stop}, messages=[payload]))
            self.assertIn("G7.ROS_WIRE_FORMAT", self.codes(gate))

    def test_observation_command_permits_subscription_but_never_publication(self) -> None:
        observation = dict(self.temperature, operation="subscribe")
        gate = self.check(self.context(commands={"sample": observation}, messages=[
            {"op": "subscribe", "topic": "/robot/temperature", "type": "std_msgs/msg/Float64"}]))
        self.assertEqual(gate.findings, [])
        gate = self.check(self.context(commands={"sample": observation}, messages=[
            {"op": "publish", "topic": "/robot/temperature", "msg": {"data": 12.0}}]))
        self.assertIn("G7.ROS_WIRE_UNDECLARED", self.codes(gate))

    def test_subscription_must_carry_the_declared_type(self) -> None:
        gate = self.check(self.context(reads={"temperature": self.temperature}, messages=[
            {"op": "subscribe", "topic": "/robot/temperature"}]))
        self.assertIn("G7.ROS_WIRE_TYPE", self.codes(gate))

    def test_no_wire_traffic_is_explicitly_reported_as_not_exercised(self) -> None:
        gate = self.check(self.context(safety={"estop": self.stop}))
        self.assertEqual(self.codes(gate), [])
        self.assertEqual(self.codes(gate, severity="warning"), ["G7.ROS_NO_MESSAGES"])

    def test_source_checks_read_the_pin_not_a_repaired_worktree(self) -> None:
        gs.git(self.root, "init", "-q")
        gs.git(self.root, "add", "node.cpp")
        gs.git(self.root, "commit", "-qm", "pinned endpoint")
        commit = gs.git(self.root, "rev-parse", "HEAD")
        (self.root / "node.cpp").write_text(CPP.replace('"~/stop"', '"~/invented"'))
        self.tree = UpstreamTree(self.root, commit)
        self.assertTrue(self.tree.pinned)
        self.assertEqual(self.codes(self.check(self.context(safety={"estop": self.stop}))), [])
        invented = dict(self.stop, service="/robot/invented", source_name="~/invented")
        self.assertIn("G7.ROS_ENDPOINT_NOT_UPSTREAM", self.codes(self.check(self.context(safety={"estop": invented}))))

    def test_package_cannot_import_the_ros_gate_implementation(self) -> None:
        package = self.root / "driver"
        package.mkdir()
        (package / "driver.py").write_text('from mhs.driver.ros_check import check_ros_surface\n')
        self.assertTrue(any(f[0] == "G3.FORBIDDEN" for f in static_findings(package)))

    def test_receive_polling_is_observation_while_send_and_refusal_remain_visible(self) -> None:
        from mhs import signals
        from mhs.bridge.base import BridgeContext
        from mhs.bridge.ros import RosBridge
        from mhs.bridge.ros_transport import RecordingRosTransport

        class Device(RosDriver):
            pass

        class PolledTransport(RecordingRosTransport):
            def recv(self, *, timeout_s=None):
                polled.set()
                return super().recv(timeout_s=timeout_s)

        def response(message):
            return {"op": "service_response", "service": message["service"], "result": True,
                    "values": {"success": True}}

        context = object.__new__(_Context)
        context.cls = Device
        context.model = SimpleNamespace(params=[], interlocks=[], estop=None, reset_attr=None)
        polled = threading.Event()
        native = Recorder(PolledTransport(handler=response))
        log = log_of(native)
        log.phase_codes.update(context.phase_codes())
        bridge = RosBridge({"commands": {"move": self.stop}, "timeout_s": 0.2}, transport=native)
        self.addCleanup(bridge.close)
        bridge.call("move", {})
        self.assertTrue(any(call.name == "send" for call in log.actuations()))
        polled.clear()
        with log.window("act"):
            self.assertTrue(polled.wait(0.5), "receive thread did not poll")
        receives = [call for call in log.calls if call.kind == "call" and call.name == "recv"]
        self.assertTrue(receives)
        self.assertEqual({call.phase for call in receives}, {"read"})
        sends_before = len([call for call in log.calls if call.name == "send"])
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(signals.Cancelled):
            bridge.call("move", {}, BridgeContext(cancel_event=cancelled))
        self.assertEqual(len([call for call in log.calls if call.name == "send"]), sends_before)


if __name__ == "__main__":
    unittest.main()
