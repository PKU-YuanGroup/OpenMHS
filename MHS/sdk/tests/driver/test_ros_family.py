"""RosDriver serving, source-independent contracts and pre-I/O hardware review enforcement."""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from mhs.adapter import LoadError, load_driver
from mhs.bridge.ros_transport import RecordingRosTransport, WebSocketTransport
from mhs.driver import Action, DriverDefinitionError, Field, Limit, RosDriver, build_manifest, close_server
from mhs.driver.loader import review_problem
from mhs.driver.package import _family_of, card_kind
from mhs.driver.scaffold import default_values, render

from tests.driver import support


class SensorTransport(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)

    def _respond(self, message):
        if message.get("op") == "subscribe":
            return {"op": "publish", "topic": "/status", "msg": {"data": "ready"}}
        return None


class Sensor(RosDriver):
    device_id, device_kind, mode, risk = "ros/sensor", "instrument", "hardware", "R0"
    endpoint = "ws://never-contact.invalid:9090"
    backends = {"fake": SensorTransport}
    parameters = {"status": Field("string")}
    reads = {"status": {"topic": "/status", "type": "std_msgs/msg/String", "path": "data"}}
    commands = {"x-cap.test.status.v1": {"topic": "/status", "type": "std_msgs/msg/String",
                                        "operation": "subscribe", "path": "data",
                                        "result": {"map": {"status": "output.$"}}}}
    actions = {"x-cap.test.status.v1": Action(name="status", output={"status": Field("string")})}


class RosFamilyTests(unittest.TestCase):
    def test_action_only_resource_is_readable_without_transport_io(self):
        native = RecordingRosTransport(lambda message: {
            "op": "service_response", "service": message["service"], "id": message["id"],
            "result": True, "values": {},
        })

        class ActionOnly(Sensor):
            parameters = {}
            reads = {}
            backends = {"fake": lambda: native}
            commands = {"x-cap.test.pause.v1": {
                "service": "/pause", "type": "std_srvs/srv/Empty",
                "success": {"path": "$", "equals": {}},
            }}
            actions = {"x-cap.test.pause.v1": Action(name="pause")}

        driver = ActionOnly(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(driver.inner.config["reads"], {"main": {"fields": {}}})
        self.assertEqual(client.read()["state"], {})
        self.assertEqual(native.sent, [])
        # The stock server also snapshots the declared resource around actions.
        # An empty resource must not add a topic read that stalls after pause.
        receipt = client.command("x-cap.test.pause.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual([message["op"] for message in native.sent], ["call_service"])
        self.assertEqual(client.read()["state"], {})
        self.assertEqual(len(native.sent), 1)

    def test_server_enforces_limits_interlocks_latch_and_safe_state_on_wire(self):
        state = {"setpoint": 0.0, "closed": True, "stops": 0}

        def respond(message):
            if message["op"] != "call_service":
                return None
            service = message["service"]
            if service == "/set":
                state["setpoint"] = message["args"]["value"]
                values = {"success": True, "setpoint": state["setpoint"]}
            elif service == "/stop":
                state["stops"] += 1
                values = {"success": True, "stopped": True}
            else:
                values = {"closed": state["closed"]}
            return {"op": "service_response", "service": service, "id": message["id"],
                    "result": True, "values": values}

        native = RecordingRosTransport(respond)
        stop_spec = {"service": "/stop", "type": "test/srv/Stop", "success": {"path": "success", "equals": True}}

        class Actuator(RosDriver):
            device_id, device_kind, mode, risk = "ros/actuator", "instrument", "hardware", "R2"
            safe_state = "output disabled by acknowledged stop service"
            backends = {"fake": lambda: native}
            commands = {
                "x-cap.test.set.v1": {"service": "/set", "type": "test/srv/Set",
                    "args": {"value": {"from": "input.value"}}, "success": {"path": "success", "equals": True},
                    "result": {"map": {"setpoint": "output.setpoint"}}},
                "x-cap.test.stop.v1": {**stop_spec, "result": {"map": {"stopped": "output.stopped"}}},
            }
            actions = {
                "x-cap.test.set.v1": Action(name="setpoint", input={"value": Field("number", unit="V",
                    limit=Limit(min=0, max=10, source="upstream_code", ref="synthetic.py:1"))},
                    output={"setpoint": Field("number", unit="V")}),
                "x-cap.test.stop.v1": Action(name="stop", safe_state=True, output={"stopped": Field("boolean")}),
            }
            safety_bindings = {"estop": stop_spec, "interlocks": [{"id": "lid", "service": "/lid",
                "type": "test/srv/Lid", "path": "closed", "closed_when": True,
                "blocks": ["x-cap.test.set.v1"]}]}

        driver = Actuator(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        self.assertEqual(client.command("x-cap.test.set.v1", {"value": 4})["status"], "completed")
        actuations = lambda: [m for m in native.sent if m.get("service") == "/set"]
        before = len(actuations())
        self.assertEqual(support.code(client.command("x-cap.test.set.v1", {"value": 11})),
                         "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(len(actuations()), before)
        state["closed"] = False
        self.assertEqual(support.code(client.command("x-cap.test.set.v1", {"value": 5})), "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertEqual(len(actuations()), before)
        state["closed"] = True
        self.assertEqual(client.estop()["output"]["estop"], "engaged")
        stops = state["stops"]
        receipt = client.command("x-cap.test.stop.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertGreater(state["stops"], stops)
        self.assertEqual(support.code(client.command("x-cap.test.set.v1", {"value": 6})), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(len(actuations()), before)

    def test_model_and_fake_observation_never_connect(self):
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect", side_effect=AssertionError("network")):
            manifest = build_manifest(Sensor)
            self.assertEqual(manifest["mode"], "hardware")
            driver = Sensor(backend="fake")
            server, client = support.serve(driver)
            self.addCleanup(close_server, server)
            self.assertEqual(client.read()["state"], {"status": "ready"})
            receipt = client.command("x-cap.test.status.v1")
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"], {"status": "ready"})
            self.assertTrue(driver.native.sent)
            self.assertFalse(any(m["op"] in ("publish", "call_service") for m in driver.native.sent))
            self.assertNotIn("endpoint", driver.inner.config)

    def test_fake_none_cannot_fall_back_to_hardware_endpoint(self):
        class NoTransport(Sensor):
            backends = {"fake": lambda: None}

        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            driver = NoTransport(backend="fake")
            self.addCleanup(driver.close)
            with self.assertRaises(Exception) as caught:
                driver.open()
            self.assertIn("produced no transport", str(caught.exception))
            connect.assert_not_called()

    def test_hardware_without_review_never_calls_factory_at_any_risk_or_authorship(self):
        root = support.temp_dir(self)
        for risk in ("R0", "R1", "R2", "R3"):
            for author in ("model", "human"):
                factory = Mock(return_value=SensorTransport())
                cls = type("Unsigned", (Sensor,), {"risk": risk, "backends": {"hardware": factory}})
                lock = support.lock_document(kind=author)
                with self.subTest(risk=risk, author=author), \
                        patch("mhs.driver.loader.read_lock", return_value=(lock, [])), \
                        patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
                    with self.assertRaises(PermissionError):
                        cls(backend="hardware", base_dir=root)
                    factory.assert_not_called()
                    connect.assert_not_called()

    def test_supplied_native_does_not_skip_review(self):
        native = SensorTransport()
        with patch("mhs.driver.loader.read_lock", return_value=(None, [])):
            with self.assertRaises(PermissionError):
                Sensor(backend="hardware", native=native)
        self.assertEqual(native.sent, [])

    def test_fake_and_sim_reject_injected_or_factory_live_transport_including_recorders(self):
        from mhs.testing import Recorder

        for backend in ("fake", "sim"):
            for wrap in (lambda value: value, Recorder):
                connector = Mock(side_effect=AssertionError("live connector must not run"))
                live = WebSocketTransport("ws://127.0.0.1:9090", connector=connector)
                candidate = wrap(live)
                with self.subTest(backend=backend, wrapper=wrap):
                    injected = Sensor(backend=backend, native=candidate)
                    self.addCleanup(injected.close)
                    with self.assertRaises(Exception) as caught:
                        injected.open()
                    self.assertIn("cannot use the live WebSocket", str(caught.exception))
                    cls = type("BadFakeFactory", (Sensor,), {"backends": {backend: lambda: candidate}})
                    produced = cls(backend=backend)
                    self.addCleanup(produced.close)
                    with self.assertRaises(Exception):
                        produced.open()
                    connector.assert_not_called()

    def test_adapter_checks_review_before_backend_and_preserves_reason(self):
        root = support.write_package(support.temp_dir(self) / "sensor", {"driver.py": "# Synthetic test package\n"})
        factory = Mock(return_value=SensorTransport())
        cls = type("UnsignedAdapter", (Sensor,), {"backends": {"hardware": factory}})
        with patch("mhs.adapter.driver_class", return_value=cls), \
                patch("mhs.adapter.read_lock", return_value=(support.lock_document(), [])), \
                patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            with self.assertRaises(LoadError) as caught:
                load_driver(root, "hardware", allow_hardware=True, state_dir=root / "state")
            self.assertEqual(caught.exception.reason, "review_required")
            factory.assert_not_called()
            connect.assert_not_called()

    def test_review_policy_checks_scope_and_schema_and_keeps_non_ros_behavior(self):
        # These are synthetic documents in memory, never signatures on driver packages.
        valid = support.lock_document(reviewed=True)
        self.assertIsNone(review_problem(valid, [], risk="R0", require_human=True))
        self.assertIsNotNone(review_problem(valid, ["invalid signature schema"], risk="R0", require_human=True))
        valid["reviewed_by"]["scope"] = "contract"
        self.assertIsNotNone(review_problem(valid, [], risk="R0", require_human=True))
        self.assertIsNone(review_problem(None, [], risk="R0"))
        self.assertIsNone(review_problem(support.lock_document(kind="human"), [], risk="R2"))

    def test_reviewed_hardware_can_use_injected_fake_without_network(self):
        native = SensorTransport()
        factory = Mock(return_value=native)
        cls = type("Reviewed", (Sensor,), {"backends": {"hardware": factory}})
        with patch("mhs.driver.loader.read_lock", return_value=(support.lock_document(reviewed=True), [])), \
                patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            driver = cls(backend="hardware")
            self.addCleanup(driver.close)
            driver.open()
            self.assertEqual(driver.read("main"), {"status": "ready"})
            factory.assert_called_once()
            connect.assert_not_called()

    def test_simulated_driver_has_no_hardware_backend_even_with_review(self):
        class Simulated(Sensor):
            mode = "simulated"

        with patch("mhs.driver.loader.read_lock", return_value=(support.lock_document(reviewed=True), [])):
            with self.assertRaises(Exception) as caught:
                Simulated(backend="hardware")
        self.assertIn("no hardware backend", str(caught.exception))

    def test_ros_version_export_and_scaffolding(self):
        self.assertEqual(_family_of(Sensor), "ros2")
        class RosOne(Sensor):
            ros_version = 1
        self.assertEqual(_family_of(RosOne), "ros1")
        self.assertEqual(card_kind({"helper": "RosDriver"}), "ros")
        files = render("ros", default_values("ros"))
        self.assertIn("RosDriver", files["driver.py"])
        self.assertNotIn("native =", files["driver.py"])
        self.assertIn("RecordingRosTransport", files["fake.py"])
        self.assertIsNone(json.loads(files["driver.lock.json"])["reviewed_by"])
        class WrongVersion(Sensor):
            ros_version = True
        with self.assertRaises(DriverDefinitionError):
            WrongVersion.driver_model()


if __name__ == "__main__":
    unittest.main()
