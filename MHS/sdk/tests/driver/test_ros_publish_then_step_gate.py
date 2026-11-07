"""G7 and the RosDriver family for publish-then-step commands: every stage is a cited declaration of its own."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.driver import Action, DriverDefinitionError, Field, RosDriver
from mhs.driver.check import Gate, _g7
from mhs.driver.upstream import UpstreamTree
from mhs.testing.recorder import RecordLog

CPP = '''#include <sim/Action.h>
#include <sim/Step.h>
#include <sim/State.h>
ros::Subscriber actions = n.subscribe("/sim/action", 1, onAction);
ros::ServiceServer step = n.advertiseService("/sim/step", onStep);
ros::Publisher state = n.advertise<sim::State>("/sim/state", 1);
'''

CAP = "x-cap.test.act.v1"


def command(**then_overrides):
    step = {"service": "/sim/step", "type": "sim/Step", "source_ref": "node.cpp:5", "type_ref": "node.cpp:2",
            "request": {}, "success": {"path": "$", "equals": {}}}
    observe = {"topic": "/sim/state", "type": "sim/State", "source_ref": "node.cpp:6", "type_ref": "node.cpp:3",
               "path": "position"}
    then = {"step": step, "observe": observe}
    then.update(then_overrides)
    return {"topic": "/sim/action", "type": "sim/Action", "operation": "publish", "source_ref": "node.cpp:4",
            "type_ref": "node.cpp:1", "message": {"value": 0.0}, "args": {"value": {"from": "input.value"}},
            "then": then, "result": {"map": {"position": "output.observation"}}}


WIRE = [
    {"op": "advertise", "topic": "/sim/action", "type": "sim/Action"},
    {"op": "publish", "topic": "/sim/action", "msg": {"value": 1.0}},
    {"op": "call_service", "service": "/sim/step", "type": "sim/Step", "args": {}},
    {"op": "subscribe", "topic": "/sim/state", "type": "sim/State"},
    {"op": "unsubscribe", "topic": "/sim/state"},
]


class PublishThenStepSourceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mhs-ros-then-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "node.cpp").write_text(CPP)
        self.tree = UpstreamTree(root, use_git=False)

    def check(self, spec, messages=WIRE):
        declared = SimpleNamespace(commands={CAP: spec}, reads={}, writes={}, safety_bindings={})
        log = RecordLog("ros fake")
        for message in messages:
            log.record("send", "call", (message,))
        gate = Gate("G7", "Native surface")
        _g7(SimpleNamespace(cls=declared, tree=self.tree, logs=[log], family="ros"), gate)
        return gate

    def errors(self, gate):
        return [(finding.code, finding.path) for finding in gate.findings if finding.severity == "error"]

    def test_each_stage_is_checked_against_its_own_citation_and_allows_its_wire_operations(self) -> None:
        self.assertEqual(self.check(command()).findings, [])

    def test_a_step_citation_that_does_not_show_its_endpoint_is_an_error(self) -> None:
        step = dict(command()["then"]["step"], source_ref="node.cpp:4")
        errors = self.errors(self.check(command(step=step)))
        self.assertIn(("G7.ROS_ENDPOINT_NOT_UPSTREAM", f"commands[{CAP!r}].then.step"), errors)

    def test_an_observation_type_that_the_citation_does_not_show_is_an_error(self) -> None:
        observe = dict(command()["then"]["observe"], type="sim/Other")
        errors = self.errors(self.check(command(observe=observe)))
        self.assertIn(("G7.ROS_TYPE_NOT_UPSTREAM", f"commands[{CAP!r}].then.observe"), errors)

    def test_stages_allow_only_their_own_operations(self) -> None:
        # The step endpoint is a service: publishing to it was declared nowhere; the observed topic is read only.
        for message in ({"op": "publish", "topic": "/sim/step", "msg": {}},
                        {"op": "advertise", "topic": "/sim/state", "type": "sim/State"}):
            with self.subTest(message=message):
                errors = self.errors(self.check(command(), WIRE + [message]))
                self.assertIn(("G7.ROS_WIRE_UNDECLARED", "send"), errors)

    def test_an_undeclared_step_is_not_allowed_on_the_wire(self) -> None:
        spec = command()
        del spec["then"]
        errors = self.errors(self.check(spec))
        self.assertIn(("G7.ROS_WIRE_UNDECLARED", "send"), errors)


class World:
    def __init__(self, **_options):
        from mhs.bridge.ros_transport import RecordingRosTransport

        self.target = 0.0
        self.position = 0.0
        self.transport = RecordingRosTransport(self.handle)

    def handle(self, message):
        if message.get("op") == "publish" and message.get("topic") == "/sim/action":
            self.target = message["msg"]["value"]
        elif message.get("op") == "call_service" and message.get("service") == "/sim/step":
            self.position = self.target
            return {"op": "service_response", "id": message["id"], "service": "/sim/step", "result": True,
                    "values": {}}
        elif message.get("op") == "subscribe" and message.get("topic") == "/sim/state":
            return {"op": "publish", "topic": "/sim/state", "id": message["id"], "msg": {"position": self.position}}
        return None


def fake_transport(**options):
    return World(**options).transport


class PublishThenStepFamilyTests(unittest.TestCase):
    def driver_class(self, spec):
        class Stepper(RosDriver):
            device_id, device_kind, mode, risk = "stepper", "world.sim", "simulated", "R0"
            ros_version = 1
            backends = {"fake": fake_transport}
            safe_state = "No acknowledged stop is declared for this test device"
            commands = {CAP: spec}
            actions = {CAP: Action(name="act", verb="invoke", description="Act, step and read",
                                   input={"value": Field("number", unit="1", description="Target")},
                                   output={"position": Field("number", unit="1", description="Position")})}
        return Stepper

    def test_a_driver_serves_the_composite_command(self) -> None:
        driver = self.driver_class(command())(backend="fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(CAP, {"value": 2.5}), {"position": 2.5})

    def test_an_invalid_then_is_a_definition_problem(self) -> None:
        spec = command(step={"topic": "/sim/step", "type": "sim/Step", "operation": "publish"})
        with self.assertRaises(DriverDefinitionError) as caught:
            self.driver_class(spec).driver_model()
        self.assertIn("then.step must be an acknowledged service call", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
