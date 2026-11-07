"""RosBridge publish-then-step commands: a publication, an acknowledged step service, an optional fresh read.

The publication is transmission only; once it was sent every later failure, refusal, cancellation or interruption
is an unknown outcome (the node may hold the published command), never a failure that invites a blind retry.
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs import signals
from mhs.errors import MHSError
from mhs.bridge.ros import RosBridge, RecordingRosTransport

CAP = "x-cap.test.act.v1"


def step_binding(**overrides):
    return {"service": "/sim/step", "type": "sim/Step", "request": {"ticks": 1},
            "success": {"path": "ok", "equals": True}, **overrides}


def observe_binding(**overrides):
    return {"topic": "/sim/state", "type": "sim/State", "path": "position", **overrides}


def command(then=None, **overrides):
    spec = {"topic": "/sim/action", "type": "sim/Action", "operation": "publish", "message": {"value": 0.0},
            "args": {"value": {"from": "input.value"}},
            "then": {"step": step_binding(), "observe": observe_binding()} if then is None else then}
    spec.update(overrides)
    return spec


class World:
    """A ROS-free node: the action sets a target, a step moves the position to it, a sample reports it."""

    def __init__(self):
        self.target = 0.0
        self.position = 0.0
        self.step_ok = True
        self.step_result = True
        self.answer_step = True
        self.publish_samples = True
        self.on_publish = None

    def handle(self, message):
        op = message.get("op")
        if op == "publish" and message.get("topic") == "/sim/action":
            self.target = message["msg"]["value"]
            if self.on_publish is not None:
                self.on_publish()
            return None
        if op == "call_service" and message.get("service") == "/sim/step":
            if not self.answer_step:
                return None
            self.position = self.target
            return {"op": "service_response", "id": message["id"], "service": "/sim/step",
                    "result": self.step_result, "values": {"ok": self.step_ok}}
        if op == "call_service" and message.get("service") == "/sim/where":
            return {"op": "service_response", "id": message["id"], "service": "/sim/where", "result": True,
                    "values": {"position": self.position}}
        if op == "subscribe" and message.get("topic") == "/sim/state" and self.publish_samples:
            return {"op": "publish", "topic": "/sim/state", "id": message["id"],
                    "msg": {"position": self.position}}
        return None


class PublishThenStepTests(unittest.TestCase):
    def bridge(self, spec=None, *, timeout_s=0.3):
        self.world = World()
        self.transport = RecordingRosTransport(self.world.handle)
        bridge = RosBridge({"timeout_s": timeout_s, "commands": {CAP: command() if spec is None else spec}},
                           transport=self.transport)
        self.addCleanup(bridge.close)
        return bridge

    def wire(self):
        return [(message["op"], message.get("topic") or message.get("service")) for message in self.transport.sent]

    def test_publication_then_step_then_a_fresh_sample_in_that_order(self) -> None:
        bridge = self.bridge(command(result={"map": {"position": "output.observation"}}))
        self.assertEqual(bridge.call(CAP, {"value": 1.5}), {"position": 1.5})
        self.assertEqual(bridge.call(CAP, {"value": -2.0}), {"position": -2.0})
        self.assertEqual(self.wire()[:5], [("advertise", "/sim/action"), ("publish", "/sim/action"),
                                           ("call_service", "/sim/step"), ("subscribe", "/sim/state"),
                                           ("unsubscribe", "/sim/state")])
        step = next(message for message in self.transport.sent if message["op"] == "call_service")
        self.assertEqual(step["args"], {"ticks": 1})
        self.assertEqual(step["type"], "sim/Step")

    def test_raw_output_names_each_stage(self) -> None:
        bridge = self.bridge()
        self.assertEqual(bridge.call(CAP, {"value": 3.0}),
                         {"published": True, "confirmed": False, "step": {"ok": True}, "stepped": True,
                          "observation": 3.0})

    def test_a_step_without_an_observation_reads_nothing(self) -> None:
        bridge = self.bridge(command(then={"step": step_binding()}))
        self.assertEqual(bridge.call(CAP, {"value": 1.0}),
                         {"published": True, "confirmed": False, "step": {"ok": True}, "stepped": True})
        self.assertNotIn("subscribe", [op for op, _name in self.wire()])

    def test_an_observational_service_can_be_the_read_after_the_step(self) -> None:
        then = {"step": step_binding(), "observe": {"service": "/sim/where", "type": "sim/Where",
                                                    "operation": "read", "path": "position"}}
        bridge = self.bridge(command(then=then))
        self.assertEqual(bridge.call(CAP, {"value": 4.0})["observation"], 4.0)
        self.assertEqual(self.wire()[2:4], [("call_service", "/sim/step"), ("call_service", "/sim/where")])

    def assert_unknown(self, call, *, stage, stepped):
        with self.assertRaises(signals.OutcomeUnknown) as caught:
            call()
        details = (caught.exception.data or {}).get("details") or {}
        self.assertEqual(details.get("stage"), stage)
        self.assertIs(details.get("published"), True)
        self.assertIs(details.get("stepped"), stepped)
        return details

    def test_a_failed_step_after_the_publication_is_unknown_and_reads_nothing(self) -> None:
        bridge = self.bridge()
        self.world.step_result = False
        details = self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="step", stepped=False)
        self.assertEqual(details.get("cause"), "MHS.ADAPTER.SHIM_FAILED")
        self.assertNotIn(("subscribe", "/sim/state"), self.wire())

    def test_a_refused_step_application_after_the_publication_is_unknown(self) -> None:
        bridge = self.bridge()
        self.world.step_ok = False
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="step", stepped=False)
        self.assertNotIn(("subscribe", "/sim/state"), self.wire())

    def test_an_unanswered_step_is_unknown_and_fences_the_next_command_until_reset(self) -> None:
        bridge = self.bridge()
        self.world.answer_step = False
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="step", stepped=False)
        sent = len(self.transport.sent)
        with self.assertRaises(MHSError) as caught:
            bridge.call(CAP, {"value": 2.0})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        self.assertEqual(len(self.transport.sent), sent, "a fenced command sends nothing")

    def test_no_sample_after_the_step_is_unknown(self) -> None:
        bridge = self.bridge()
        self.world.publish_samples = False
        started = time.monotonic()
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="observe", stepped=True)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(self.world.position, 1.0, "the step took effect although no sample arrived")

    def test_a_result_that_cannot_be_mapped_after_the_step_is_unknown_not_failed(self) -> None:
        # The publication and the acknowledged step were sent: a mapping failure must not read as a plain failure.
        bridge = self.bridge(command(result={"map": {"ok": "output.step.missing"}}))
        details = self.assert_unknown(lambda: bridge.call(CAP, {"value": 2.5}), stage="result", stepped=True)
        self.assertEqual(details.get("cause"), "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertEqual(self.wire()[:4], [("advertise", "/sim/action"), ("publish", "/sim/action"),
                                           ("call_service", "/sim/step"), ("subscribe", "/sim/state")])
        self.assertEqual(self.world.position, 2.5, "the step took effect before the mapping failed")

    def test_an_estop_after_the_publication_stops_the_step_from_being_sent(self) -> None:
        bridge = self.bridge()
        self.world.on_publish = lambda: bridge.estop("test")
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="step", stepped=False)
        self.assertNotIn(("call_service", "/sim/step"), self.wire())
        self.assertEqual(self.world.position, 0.0)

    def test_a_cancellation_after_the_publication_stops_the_step_from_being_sent(self) -> None:
        bridge = self.bridge()
        cancel = threading.Event()
        self.world.on_publish = cancel.set
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}, {"cancel_event": cancel}),
                            stage="step", stepped=False)
        self.assertNotIn(("call_service", "/sim/step"), self.wire())

    def test_an_expired_budget_before_the_publication_is_a_timeout_with_nothing_sent(self) -> None:
        bridge = self.bridge()
        with self.assertRaises(MHSError) as caught:
            bridge.call(CAP, {"value": 1.0}, {"deadline_ms": 0})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(self.transport.sent, [])

    def test_a_command_queued_before_an_estop_sends_nothing_afterwards(self) -> None:
        # The server owns the latch; the bridge's wire epoch refuses a command admitted before the e-stop.
        bridge = self.bridge()
        outcome = {}
        bridge._txn_lock.acquire()
        try:
            worker = threading.Thread(target=lambda: outcome.setdefault("error", self.capture(bridge)))
            worker.start()
            time.sleep(0.05)
            bridge.estop("test")
        finally:
            bridge._txn_lock.release()
        worker.join(2)
        self.assertEqual(getattr(outcome.get("error"), "code", None), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(self.transport.sent, [])

    @staticmethod
    def capture(bridge):
        try:
            bridge.call(CAP, {"value": 1.0}, {"deadline_ms": 1000})
        except Exception as exc:  # noqa: BLE001 - the test inspects it
            return exc
        return None

    def test_the_whole_sequence_shares_the_command_budget(self) -> None:
        # The command's timeout_ms bounds publication, step and read together; a stage keeps its own bound too.
        bridge = self.bridge(command(timeout_ms=150, then={"step": step_binding(timeout_ms=5000),
                                                           "observe": observe_binding(timeout_ms=5000)}),
                             timeout_s=5.0)
        self.world.publish_samples = False
        started = time.monotonic()
        self.assert_unknown(lambda: bridge.call(CAP, {"value": 1.0}), stage="observe", stepped=True)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_safety_status_reports_the_publication_as_an_unconfirmed_control_surface(self) -> None:
        bridge = self.bridge()
        status = bridge.safety_status()
        self.assertEqual(status["estop"], {"native": None})
        self.assertFalse(status["safe_state"]["achieved"])


class PublishThenStepDeclarationTests(unittest.TestCase):
    def refused(self, config):
        with self.assertRaises(MHSError) as caught:
            RosBridge(config, transport=RecordingRosTransport())
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")
        return str(caught.exception)

    def test_then_belongs_only_to_an_ordinary_publication_command(self) -> None:
        then = {"step": step_binding()}
        for spec in (
            {"service": "/sim/move", "type": "sim/Move", "success": {"path": "ok", "equals": True}, "then": then},
            {"topic": "/sim/state", "type": "sim/State", "operation": "subscribe", "then": then},
        ):
            with self.subTest(spec=spec):
                self.refused({"commands": {CAP: spec}})
        self.refused({"reads": {"main": {"fields": {"x": dict(observe_binding(), then=then)}}}})
        self.refused({"writes": {"main": {"params": {"x": dict(step_binding(), then=then)}}}})
        self.refused({"safety_bindings": {"estop": dict(step_binding(), then=then)}})

    def test_then_needs_a_step_and_allows_only_step_and_observe(self) -> None:
        self.refused({"commands": {CAP: command(then={"observe": observe_binding()})}})
        self.refused({"commands": {CAP: command(then={"step": step_binding(), "extra": step_binding()})}})
        self.refused({"commands": {CAP: command(then=[step_binding()])}})

    def test_the_step_is_an_acknowledged_service_call_with_a_fixed_request(self) -> None:
        for step in (
            {"topic": "/sim/step", "type": "sim/Tick", "operation": "publish"},
            step_binding(operation="read"),
            {key: value for key, value in step_binding().items() if key != "success"},
            step_binding(args={"ticks": {"from": "input.ticks"}}),
            step_binding(result={"map": {"ok": "output.ok"}}),
            step_binding(resource="main"),
            step_binding(safe_state=True),
            step_binding(then={"step": step_binding()}),
            {"action": "/sim/step", "type": "sim/StepAction", "profile": "ros1-actionlib",
             "success": {"path": "ok", "equals": True}},
        ):
            with self.subTest(step=step):
                self.refused({"commands": {CAP: command(then={"step": step})}})

    def test_the_result_reads_only_fields_the_raw_output_carries(self) -> None:
        # A rule whose first field the raw output never carries could only fail after the publication and the step.
        no_observe = {"step": step_binding()}
        for then, result in (
            (no_observe, {"map": {"position": "output.observation"}}),
            (no_observe, {"position": {"from": "observation.x"}}),
            (None, {"map": {"x": "output.stpe"}}),
            (None, {"map": {"x": "output[0]"}}),
            (None, {"map": {"x": "$.observation"}}),
            (None, {"map": {"x": "output.observation[1"}}),
        ):
            with self.subTest(then=then, result=result):
                self.refused({"commands": {CAP: command(then=then, result=result)}})
        for then, result in (
            (None, {"map": {"all": "output", "same": "output.$", "ok": "output.step.ok", "p": "output.observation",
                            "pub": "output.published", "conf": "output.confirmed", "st": "output.stepped"}}),
            (no_observe, {"stepped": {"from": "stepped"}, "fixed": {"value": True}}),
        ):
            with self.subTest(then=then, result=result):
                RosBridge({"commands": {CAP: command(then=then, result=result)}},
                          transport=RecordingRosTransport()).close()

    def test_the_observation_is_a_read(self) -> None:
        for observe in (
            {"topic": "/sim/state", "type": "sim/State", "operation": "publish"},
            observe_binding(message={"x": 1}),
            observe_binding(resource="main"),
            {"service": "/sim/where", "type": "sim/Where", "operation": "call",
             "success": {"path": "ok", "equals": True}},
        ):
            with self.subTest(observe=observe):
                self.refused({"commands": {CAP: command(then={"step": step_binding(), "observe": observe})}})


if __name__ == "__main__":
    unittest.main()
