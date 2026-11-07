"""ROS-free wire, response-correlation and safety regressions for RosBridge."""

from __future__ import annotations

import copy
import threading
import time
import unittest
from unittest import mock

from mhs import signals
from mhs.errors import MHSError
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RosBridge, RecordingRosTransport, WebSocketTransport
from mhs.bridge.transcript import TranscriptDivergence
from mhs.server import Resource
from tests.bridges import support

CAP = "x-cap.test.move.v1"
STOP = "x-cap.test.stop.v1"


def response(message, values=None, *, result=True):
    return {"op": "service_response", "id": message["id"], "service": message["service"],
            "values": {"success": True} if values is None else values, "result": result}


def config():
    return {"timeout_s": 0.2, "commands": {CAP: {
        "service": "/move", "type": "example/srv/Move", "request": {"mode": "absolute"},
        "args": {"position.x": {"from": "input.x", "type": "number"}},
        "success": {"path": "success", "equals": True},
        "result": {"map": {"position": "output.position"}},
    }}, "safety_bindings": {"estop": {
        "service": "/stop", "type": "std_srvs/srv/Trigger", "request": {},
        "success": {"path": "success", "equals": True}, "description": "native motion stopped",
    }}}


class RosBridgeTests(unittest.TestCase):
    def bridge(self, cfg=None, handler=None, transport=None):
        transport = transport or RecordingRosTransport(handler)
        bridge = RosBridge(config() if cfg is None else cfg, transport=transport,
                           capability_schemas={STOP:{"output_schema":{"type":"object"}}})
        self.addCleanup(bridge.close)
        return bridge, transport

    def test_no_connection_import_or_io_during_construction_and_close(self):
        with mock.patch("mhs.bridge.ros_transport.importlib.import_module", side_effect=AssertionError("imported")):
            bridge = RosBridge({"endpoint": "ws://127.0.0.1:9090"})
            bridge.close()

    def test_service_maps_nested_request_and_output(self):
        def handle(message):
            self.assertEqual(message["args"], {"mode": "absolute", "position": {"x": 4}})
            return response(message, {"success": True, "position": 4})
        bridge, transport = self.bridge(handler=handle)
        self.assertEqual(bridge.call(CAP, {"x": 4}), {"position": 4})
        self.assertEqual(transport.sent[0]["type"], "example/srv/Move")

    def test_strict_replay_and_divergence(self):
        transport = RecordingRosTransport(exchanges=[{
            "send": {"op": "call_service", "service": "/move", "type": "example/srv/Move",
                     "args": {"mode": "absolute", "position": {"x": 2}}},
            "recv": {"op": "service_response", "service": "/move", "result": True,
                     "values": {"success": True, "position": 2}},
        }])
        bridge, _ = self.bridge(transport=transport)
        self.assertEqual(bridge.call(CAP, {"x": 2}), {"position": 2})
        transport.assert_complete()
        with self.assertRaises(TranscriptDivergence):
            bridge.call(CAP, {"x": 3})

    def test_invalid_application_success_is_never_success(self):
        for value in (False, 1, "true", None):
            with self.subTest(value=value):
                bridge, _ = self.bridge(handler=lambda msg: response(msg, {"success": value, "position": 4}))
                with self.assertRaises(signals.DriverFailed):
                    bridge.call(CAP, {"x": 4})

    def test_missing_application_success_fails(self):
        bridge, _ = self.bridge(handler=lambda msg: response(msg, {"position": 4}))
        with self.assertRaises(signals.DriverFailed):
            bridge.call(CAP, {"x": 4})

    def test_rosbridge_failure_is_driver_failure(self):
        bridge, _ = self.bridge(handler=lambda msg: response(msg, "native failed", result=False))
        with self.assertRaises(signals.DriverFailed):
            bridge.call(CAP, {"x": 4})

    def test_mismatched_service_or_nonboolean_protocol_result_is_unknown(self):
        for mutation in ({"service": "/other"}, {"result": "true"}, {"values": []}):
            with self.subTest(mutation=mutation):
                bridge, _ = self.bridge(handler=lambda msg: {**response(msg), **mutation})
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(CAP, {"x": 4})

    def test_wrong_and_malformed_ids_cannot_complete_request(self):
        bridge, _ = self.bridge(handler=lambda msg: [{**response(msg), "id": []},
                                                     {**response(msg), "id": "old-request"}])
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"x": 4}, {"deadline_ms": 30})

    def test_deadline_before_send_writes_nothing(self):
        bridge, transport = self.bridge()
        with self.assertRaises(Exception) as caught:
            bridge.call(CAP, {"x": 4}, {"deadline_ms": 0})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(transport.sent, [])

    def test_timeout_after_send_is_unknown_and_does_not_replay(self):
        bridge, transport = self.bridge()
        started = time.monotonic()
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"x": 4}, {"deadline_ms": 30})
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(len(transport.sent), 1)

    def test_late_response_does_not_satisfy_the_next_request(self):
        bridge, transport = self.bridge()
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"x": 4}, {"deadline_ms": 20})
        old = transport.sent[0]
        with self.assertRaises(MHSError):
            bridge.call(CAP, {"x": 9})
        transport.feed(response(old, {"success": True, "position": 4}))
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(lambda:bridge._pending[old["id"]].event.is_set(), 1))
        transport.handler = lambda msg: response(msg)
        bridge.reset()
        transport.handler = lambda msg: [response(old, {"success": True, "position": 4}),
                                         response(msg, {"success": True, "position": 9})]
        self.assertEqual(bridge.call(CAP, {"x": 9}), {"position": 9})

    def test_disconnect_after_send_is_unknown(self):
        bridge, transport = self.bridge()
        transport.handler = lambda msg: transport.close()
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"x": 4})

    def test_missing_mapped_output_fails(self):
        bridge, _ = self.bridge(handler=lambda msg: response(msg))
        with self.assertRaises(signals.DriverFailed) as caught:
            bridge.call(CAP, {"x": 4})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_publish_reports_unconfirmed_transmission(self):
        cfg = {"commands": {CAP: {"topic": "/cmd_vel", "type": "geometry_msgs/msg/Twist",
                                 "message": {"angular": {"z": 0}},
                                 "args": {"linear.x": {"from": "input.speed"}}}}}
        bridge, transport = self.bridge(cfg)
        self.assertEqual(bridge.call(CAP, {"speed": 0.2}), {"published": True, "confirmed": False})
        self.assertEqual([x["op"] for x in transport.sent], ["advertise", "publish"])
        self.assertEqual(transport.sent[-1]["msg"], {"angular": {"z": 0}, "linear": {"x": 0.2}})

    def test_topic_read_receives_fresh_interleaved_observation(self):
        cfg = {"reads": {"main": {"fields": {"temperature": {
            "topic": "/temperature", "type": "std_msgs/Float64", "path": "data"}}}}}
        def handle(msg):
            if msg["op"] == "subscribe":
                return [{"op": "publish", "topic": "/unrelated", "msg": {"data": 100}},
                        {"op": "publish", "topic": "/temperature", "msg": {"data": 22.5}}]
        bridge, transport = self.bridge(cfg, handle)
        self.assertEqual(bridge.read("main"), {"temperature": 22.5})
        self.assertEqual([x["op"] for x in transport.sent], ["subscribe", "unsubscribe"])
        transport.handler = None
        with self.assertRaises(Exception):
            bridge.read("main", ctx={"deadline_ms": 20})  # old cache is not a fresh sample

    def test_subscription_command_maps_observation_without_publishing(self):
        cfg = {"commands": {CAP: {"topic": "/camera_info", "type": "sensor_msgs/CameraInfo",
                                 "operation": "subscribe", "path": "width",
                                 "result": {"map": {"width": "output.$"}}}}}
        bridge, transport = self.bridge(cfg, lambda msg: {"op": "publish", "topic": "/camera_info",
                                                         "msg": {"width": 640}} if msg["op"] == "subscribe" else None)
        self.assertEqual(bridge.call(CAP), {"width": 640})
        self.assertEqual([x["op"] for x in transport.sent], ["subscribe", "unsubscribe"])

    def test_explicit_parameter_service_mapping_and_success(self):
        cfg = {"writes": {"main": {"params": {"gain": {
            "service": "/node/set_gain", "request": {"name": "gain"},
            "args": {"value": {"from": "input.value"}},
            "success": {"path": "successful", "equals": True},
        }}}}}
        bridge, transport = self.bridge(cfg, lambda msg: response(msg, {"successful": True}))
        self.assertEqual(bridge.call("cap.device.configure.v1", {"gain": 2}), {"applied": {"gain": 2}})
        self.assertEqual(transport.sent[0]["args"], {"name": "gain", "value": 2})

    def test_estop_bypasses_pending_service_and_fences_queued_command(self):
        sent = threading.Event()
        def handle(msg):
            if msg["service"] == "/move":
                sent.set()
                return None
            return response(msg)
        bridge, transport = self.bridge(handler=handle)
        failures = []
        def run():
            try:
                bridge.call(CAP, {"x": 4}, {"deadline_ms": 1000})
            except BaseException as exc:
                failures.append(exc)
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(sent.wait(1))
        queued = threading.Thread(target=run)
        queued.start()
        time.sleep(0.02)
        started = time.monotonic()
        result = bridge.estop()
        self.assertLess(time.monotonic() - started, 0.15)
        worker.join(1)
        queued.join(1)
        self.assertFalse(worker.is_alive() or queued.is_alive())
        self.assertFalse(result["safe_state_achieved"])
        self.assertEqual([m["service"] for m in transport.sent], ["/move", "/stop"])
        self.assertEqual(len(failures), 2)
        self.assertTrue(any(isinstance(exc, signals.OutcomeUnknown) for exc in failures))
        self.assertTrue(any(getattr(exc, "code", None) == "MHS.SAFETY.ESTOP_ENGAGED" for exc in failures))

    def test_safe_state_action_bypasses_pending_command_lock(self):
        cfg = config()
        cfg["commands"][STOP] = {**cfg["safety_bindings"]["estop"], "safe_state": True}
        bridge, transport = self.bridge(cfg, lambda msg: response(msg) if msg["service"] == "/stop" else None)
        errors = []
        def run():
            try:
                bridge.call(CAP, {"x": 4})
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=run)
        worker.start()
        deadline = time.monotonic() + 1
        while not transport.sent and time.monotonic() < deadline:
            time.sleep(0.005)
        started = time.monotonic()
        with self.assertRaises(signals.DriverFailed):
            bridge.call(STOP)
        self.assertTrue(any(m.get("service") == "/stop" for m in transport.sent))
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.assertLess(time.monotonic() - started, 0.15)
        worker.join(1)

    def test_empty_stop_response_is_valid_only_with_explicit_empty_predicate(self):
        cfg = config()
        cfg["safety_bindings"]["estop"]["success"] = {"path": "$", "equals": {}}
        bridge, _ = self.bridge(cfg, lambda msg: response(msg, {}))
        self.assertTrue(bridge.estop()["safe_state_achieved"])

    def test_failed_stop_does_not_claim_safe_state(self):
        bridge, _ = self.bridge(handler=lambda msg: response(msg, {"success": False}))
        with self.assertRaises(signals.DriverFailed) as caught:
            bridge.estop()
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_interlock_requires_strict_scalar_and_gates_reset(self):
        cfg = config()
        cfg["safety_bindings"]["interlocks"] = [{"id": "door", "service": "/door", "path": "closed"}]
        cfg["safety_bindings"]["reset"] = {"service": "/reset", "success": {"path": "success", "equals": True}}
        bridge, transport = self.bridge(cfg, lambda msg: response(msg, {"closed": 1}))
        self.assertEqual(bridge.interlocks()[0]["state"], "unknown")
        with self.assertRaises(Exception) as caught:
            bridge.reset()
        self.assertEqual(caught.exception.code, "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertFalse(any(msg["service"] == "/reset" for msg in transport.sent))

    def test_invalid_configs_fail_before_io(self):
        candidates = [
            {"timeout_s": float("nan")},
            {"commands": {CAP: {"service": "relative"}}},
            {"commands": {CAP: {"service": "/go", "topic": "/topic"}}},
            {"commands": {CAP: {"topic": "/go"}}},
            {"commands": {CAP: {"service": "/go", "typo": True}}},
            {"commands": {CAP: {"service": "/go"}}},
            {"commands": {CAP: {"service": "/go", "safe_state": True}}},
            {"safety_bindings": {"estop": {"topic": "/stop", "type": "std_msgs/Bool"}}},
            {"safety_bindings": {"estop": {"service": "/stop"}}},
            {"writes": {"main": {"params": {"x": {"service": "/set"}}}}},
            {"commands": {CAP: {"topic": "/go", "type": "std_msgs/Bool", "operation": "subscribe", "message": {}}}},
        ]
        for cfg in candidates:
            with self.subTest(cfg=cfg):
                transport = RecordingRosTransport()
                with self.assertRaises(Exception) as caught:
                    RosBridge(cfg, transport=transport)
                self.assertEqual(caught.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")
                self.assertEqual(transport.sent, [])

    def test_observation_service_command_is_explicit(self):
        cfg = {"commands": {CAP: {"service": "/get_state", "operation": "read",
                                 "result": {"map": {"state": "output.state"}}}}}
        bridge, _ = self.bridge(cfg, lambda msg: response(msg, {"state": "idle"}))
        self.assertEqual(bridge.call(CAP), {"state": "idle"})

    def test_late_subscription_id_cannot_satisfy_new_read(self):
        cfg = {"reads": {"main": {"fields": {"state": {"topic": "/state", "path": "value"}}}}}
        old_id = []
        def handler(msg):
            if msg["op"] == "subscribe":
                ident = old_id[0] if old_id else msg["id"]
                old_id.append(msg["id"])
                return {"op": "publish", "topic": "/state", "id": ident, "msg": {"value": len(old_id)}}
        bridge, _ = self.bridge(cfg, handler)
        self.assertEqual(bridge.read("main"), {"state": 1})
        with self.assertRaises(Exception):
            bridge.read("main", ctx={"deadline_ms": 20})

    def test_success_reply_after_slow_send_deadline_is_unknown(self):
        def handler(msg):
            time.sleep(0.04)
            return response(msg, {"success": True, "position": 4})
        bridge, _ = self.bridge(handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"x": 4}, {"deadline_ms": 20})

    def test_idless_event_during_prepare_cannot_satisfy_unsent_subscription(self):
        preparing, release, consumed_old = threading.Event(), threading.Event(), threading.Event()
        class DelayedPrepare(RecordingRosTransport):
            block_next = False

            def prepare(self, *, timeout_s=None):
                if self.block_next:
                    self.block_next = False
                    preparing.set()
                    release.wait(1)

            def recv(self, *, timeout_s=None):
                message = super().recv(timeout_s=timeout_s)
                if message.get("msg", {}).get("value") == 999:
                    consumed_old.set()
                return message

        cfg = {"reads": {"main": {"fields": {"state": {"topic": "/state", "path": "value"}}}}}
        transport = DelayedPrepare(lambda msg: {"op": "publish", "topic": "/state", "msg": {"value": 1}}
                                   if msg["op"] == "subscribe" else None)
        bridge, _ = self.bridge(cfg, transport=transport)
        self.assertEqual(bridge.read("main"), {"state": 1})
        transport.handler = None
        transport.block_next = True
        outcomes = []
        def read():
            try:
                outcomes.append(bridge.read("main", ctx={"deadline_ms": 150}))
            except BaseException as exc:
                outcomes.append(exc)
        worker = threading.Thread(target=read)
        worker.start()
        try:
            self.assertTrue(preparing.wait(1))
            transport.feed({"op": "publish", "topic": "/state", "msg": {"value": 999}})
            self.assertTrue(consumed_old.wait(1))
        finally:
            release.set()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], BaseException, outcomes)

    def test_estop_during_initial_connection_never_sends_old_motion(self):
        from tests.bridges.test_ros_transport import Peer
        connecting, release = threading.Event(), threading.Event()
        peer = Peer()
        def connector(*args, **kwargs):
            connecting.set()
            release.wait(1)
            return peer
        transport = WebSocketTransport("ws://localhost", connector=connector)
        cfg = config()
        cfg["timeout_s"] = 0.5
        cfg["safety_bindings"]["estop"]["timeout_ms"] = 20
        bridge, _ = self.bridge(cfg, transport=transport)
        errors = []
        def move():
            try:
                bridge.call(CAP, {"x": 4})
            except BaseException as exc:
                errors.append(exc)
        worker = threading.Thread(target=move)
        worker.start()
        self.assertTrue(connecting.wait(1))
        with self.assertRaises(signals.DriverFailed):
            bridge.estop()
        release.set()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(peer.sent, [], "a motion must be refused after the e-stop even if connect completed late")
        self.assertEqual(errors[0].code, "MHS.SAFETY.ESTOP_ENGAGED")

    def test_estop_has_reserved_pending_capacity(self):
        cfg = config()
        cfg["reads"] = {"main": {"fields": {"value": {"service": "/status", "path": "value"}}}}
        cfg["timeout_s"] = 2
        bridge, transport = self.bridge(cfg, lambda msg: response(msg) if msg["service"] == "/stop" else None)
        # Fill real in-flight read slots rather than modifying the private map.
        errors = []
        def read():
            try:
                bridge.read("main")
            except BaseException as exc:
                errors.append(exc)
        workers = [threading.Thread(target=read) for _ in range(128)]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + 2
        while len(transport.sent) < 128 and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(len(transport.sent), 128)
        self.assertTrue(bridge.estop()["safe_state_achieved"])
        self.assertEqual(transport.sent[-1]["service"], "/stop")
        bridge.close()
        for worker in workers:
            worker.join(1)
        self.assertFalse(any(worker.is_alive() for worker in workers))

    def test_server_reports_timeout_as_unknown_not_completed(self):
        bridge, transport = self.bridge()
        device = support.simulated_device("mhs://localhost:7799/ros/test", resources=[Resource("main", "robot.arm")],
                                          capabilities=[support.open_capability(CAP, "main")], bridge=bridge)
        harness = support.Harness(device)
        result = harness.command(CAP, {"x": 4}, deadline_ms=1000)
        self.assertEqual(result["status"], "unknown", result)
        self.assertEqual(result["error"]["mhs_code"], "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(len(transport.sent), 1)


if __name__ == "__main__":
    unittest.main()
