"""A software latch cannot certify an externally retained ROS control target."""
from __future__ import annotations

import copy
import json
import queue
import unittest

from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport, WebSocketTransport
from mhs.driver import Action, Field, RosDriver, close_server
from tests.driver import support
from tests.driver.test_ros_simulation import FAKE_FIDELITY, deployment
from tests.bridges.test_ros_action_safety import (
    FrankaPeer, PROFILES, STOP_NAME, binding,
)

SET = "x-cap.test.unbound-set.v1"
STOP = "x-cap.test.unbound-stop.v1"
OBSERVE = "x-cap.test.unbound-observe.v1"
STOP_SPEC = {"service": "/stop", "type": "std_srvs/srv/Trigger",
             "success": {"path": "success", "equals": True},
             "description": "Retained test target cleared by the stop peer"}


class RetainedPeer:
    def __init__(self):
        self.target = 0.0
        self.stops = 0
        self.stop_success = True
        self.sent = []
        self.transport = RecordingRosTransport(self.handle)

    def handle(self, message):
        self.sent.append(copy.deepcopy(message))
        if message["op"] == "publish":
            self.target = message["msg"]["data"]
        elif message["op"] == "subscribe":
            return {"op": "publish", "topic": message["topic"], "msg": {"data": self.target}}
        elif message["op"] == "call_service":
            if message["service"] == "/set":
                self.target = message["args"]["value"]
            elif message["service"] == "/stop":
                self.stops += 1
                if self.stop_success:
                    self.target = 0.0
            return {"op": "service_response", "id": message["id"], "service": message["service"],
                    "result": True, "values": {"success": self.stop_success, "value": self.target}}
        return None


class TextPeer:
    """Socket-shaped JSON peer; no network connection or simulator is started."""
    def __init__(self, peer):
        self.peer = peer
        self.incoming = queue.Queue()

    def settimeout(self, timeout):
        pass

    def send(self, payload):
        response = self.peer.handle(json.loads(payload))
        if response is not None:
            self.incoming.put(json.dumps(response))

    def recv(self):
        try:
            return self.incoming.get(timeout=0.01)
        except queue.Empty:
            raise TimeoutError from None

    def close(self, **kwargs):
        pass


def set_binding(kind):
    if kind == "topic":
        return {"topic": "/target", "type": "std_msgs/msg/Float64",
                "args": {"data": {"from": "input.value"}}}
    return {"service": "/set", "type": "test/srv/Set",
            "args": {"value": {"from": "input.value"}},
            "success": {"path": "success", "equals": True}}


class RosUnboundSafetyTests(unittest.TestCase):
    def server(self, peer, *, kind="topic", backend="fake", stop=None, readonly=False):
        commands = {SET: set_binding(kind)}
        actions = {SET: Action(name="set_target", input={"value": Field("number")},
                              output=({"published": Field("boolean"), "confirmed": Field("boolean")}
                                      if kind == "topic" else {}))}
        if readonly:
            commands = {OBSERVE: ({"topic": "/state", "type": "std_msgs/msg/Float64",
                                  "operation": "subscribe"} if kind == "topic" else
                                 {"service": "/state", "type": "test/srv/State", "operation": "read"})}
            actions = {OBSERVE: Action(name="observe", verb="read",
                                      output={"data": Field("number")} if kind == "topic" else {})}
        if stop == "command":
            commands[STOP] = copy.deepcopy(STOP_SPEC)
            actions[STOP] = Action(name="stop", safe_state=True)
        cls = type("RetainedRosDriver", (RosDriver,), {
            "device_id": "ros/unbound-safety", "device_kind": "instrument",
            "mode": "simulated", "risk": "R0", "fidelity": copy.deepcopy(FAKE_FIDELITY),
            "commands": commands, "actions": actions, "timeout_s": 0.05,
            "safe_state": "The selected stop must clear the external target",
            "safety_bindings": {"estop": copy.deepcopy(STOP_SPEC)} if stop == "binding" else {},
            "backends": {"fake": lambda: peer.transport},
        })
        options = {}
        if backend == "sim":
            config = deployment("unbound-test")
            socket = TextPeer(peer)
            transport = WebSocketTransport(config["endpoint"], connector=lambda *args, **kw: socket)
            options = {"simulation_deployment": config, "native": transport}
        driver = cls(backend=backend, **options)
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        return driver, client

    def test_stock_latch_does_not_confirm_retained_published_or_service_targets(self):
        for backend in ("fake", "sim"):
            for kind in ("topic", "service"):
                with self.subTest(backend=backend, kind=kind):
                    peer = RetainedPeer()
                    driver, client = self.server(peer, kind=kind, backend=backend)
                    command = client.command(SET, {"value": 3.25})
                    self.assertEqual(command["status"], "completed", command)
                    self.assertEqual(peer.target, 3.25)
                    stop = client.estop()
                    self.assertEqual(stop["status"], "failed", stop)
                    self.assertEqual(support.code(stop), "MHS.SAFETY.SAFE_STATE_UNREACHED")
                    self.assertEqual(stop["output"]["estop"], "software_only")
                    self.assertTrue(stop["output"]["latched"])
                    self.assertFalse(stop["output"]["safe_state_achieved"])
                    self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                    self.assertEqual(peer.target, 3.25)
                    self.assertEqual(peer.stops, 0)
                    before = len(peer.sent)
                    refused = client.command(SET, {"value": 9.5})
                    self.assertEqual(support.code(refused), "MHS.SAFETY.ESTOP_ENGAGED", refused)
                    self.assertEqual(len(peer.sent), before)
                    self.assertEqual(peer.target, 3.25)

    def test_actuating_declaration_is_unconfirmed_before_first_send(self):
        peer = RetainedPeer()
        driver, client = self.server(peer)
        stop = client.estop()
        self.assertEqual(stop["status"], "failed", stop)
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        self.assertEqual(peer.transport.sent, [])

    def test_readonly_ros_surfaces_keep_software_latch_behavior(self):
        for kind in ("topic", "service"):
            with self.subTest(kind=kind):
                peer = RetainedPeer()
                driver, client = self.server(peer, kind=kind, readonly=True)
                self.assertEqual(client.command(OBSERVE)["status"], "completed")
                self.assertEqual(driver.inner.safety_status(), {})
                stop = client.estop()
                self.assertEqual(stop["status"], "completed", stop)
                self.assertEqual(stop["output"]["estop"], "software_only")
                self.assertEqual(peer.target, 0.0)
                self.assertEqual(peer.stops, 0)

    def test_acknowledged_direct_stop_remains_successful_and_failure_stays_unconfirmed(self):
        for success in (True, False):
            with self.subTest(success=success):
                peer = RetainedPeer()
                driver, client = self.server(peer, stop="binding")
                self.assertEqual(client.command(SET, {"value": 3.25})["status"], "completed")
                peer.stop_success = success
                receipt = client.estop()
                self.assertEqual(receipt["status"], "completed" if success else "failed", receipt)
                self.assertEqual(receipt["output"]["safe_state_achieved"], success)
                self.assertEqual(driver.inner.safety_status()["safe_state"]["achieved"], success)
                self.assertEqual(peer.target, 0.0 if success else 3.25)
                self.assertGreaterEqual(peer.stops, 1)

    def test_command_only_safe_state_has_current_proof_and_is_invalidated_by_new_effect(self):
        peer = RetainedPeer()
        driver, client = self.server(peer, stop="command")
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        self.assertEqual(client.command(SET, {"value": 3.25})["status"], "completed")
        self.assertEqual(client.command(STOP)["status"], "completed")
        self.assertEqual(peer.target, 0.0)
        self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
        self.assertEqual(client.command(SET, {"value": 2.5})["status"], "completed")
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        self.assertEqual(peer.target, 0.0)
        driver.close()
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])

    def test_action_only_safe_state_proof_for_both_protocols(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                cls = type("ActionStopOnly", (RosDriver,), {
                    "device_id": "ros/action-stop-only", "device_kind": "instrument", "risk": "R0",
                    "ros_version": 1 if profile == PROFILES[0] else 2,
                    "commands": {STOP: binding(profile)},
                    "actions": {STOP: Action(name="stop", safe_state=True,
                                             output={"success": Field("boolean")})},
                    "backends": {"fake": lambda: peer.transport},
                })
                driver = cls(backend="fake")
                server, client = support.serve(driver)
                self.addCleanup(close_server, server)
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                receipt = client.estop()
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertTrue(receipt["output"]["safe_state_achieved"])
                self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)

    def test_write_only_and_reset_only_profiles_do_not_certify_a_missing_stop(self):
        for cfg in ({"writes": {"main": {"params": {"target": set_binding("service")}}}},
                    {"safety_bindings": {"reset": STOP_SPEC}}):
            with self.subTest(cfg=cfg):
                peer = RetainedPeer()
                bridge = RosBridge(cfg, transport=peer.transport)
                self.addCleanup(bridge.close)
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                self.assertFalse(bridge.estop("missing stop")["safe_state_achieved"])
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                self.assertEqual(peer.transport.sent, [])


if __name__ == "__main__":
    unittest.main()
