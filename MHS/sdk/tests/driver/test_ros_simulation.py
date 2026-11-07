"""Explicit ROS simulation deployment: honest contracts and lazy, isolated transports."""

from __future__ import annotations

import copy
import json
import queue
import unittest
from unittest.mock import Mock, patch

from mhs.bridge.ros_transport import RecordingRosTransport, WebSocketTransport
from mhs.driver import Action, Field, RosDriver, build_manifest, build_reference, close_server
from mhs.errors import MHSError
from mhs.testing import Recorder

from tests.driver import support


FAKE_FIDELITY = {
    "engine": "recording", "fidelity_level": "F0", "determinism": {"kind": "none"},
    "timestep_ms": 0, "realtime_factor": 0, "reset": "none", "snapshot_restore": False,
    "gaps": ["Recording fake; no dynamics or simulator process."],
}
DEPLOYED_FIDELITY = {
    "engine": "synthetic test simulator", "fidelity_level": "F1", "determinism": {"kind": "none"},
    "timestep_ms": 5, "realtime_factor": 1, "clock": "free_running", "reset": "none",
    "snapshot_restore": False, "gaps": ["Synthetic contract; no live ROS or physics validation."],
}


def deployment(identifier="test-world", **changes):
    result = {"endpoint": "ws://127.0.0.1:9090", "deployment_id": identifier,
              "fidelity": copy.deepcopy(DEPLOYED_FIDELITY)}
    result.update(changes)
    return result


def response(message):
    if message.get("op") == "call_service":
        return {"op": "service_response", "service": message["service"], "id": message["id"],
                "result": True, "values": {"paused": True}}
    return None


class SimWorld(RosDriver):
    device_id, device_kind, mode, risk = "ros/world", "world.sim", "simulated", "R0"
    # A class default must never silently enable a live simulation connection.
    endpoint = "ws://never-contact.invalid:9090"
    fidelity = FAKE_FIDELITY
    backends = {"fake": lambda: RecordingRosTransport(response)}
    commands = {"x-cap.test.state.v1": {
        "service": "/state", "type": "test/srv/State", "operation": "read",
        "result": {"map": {"paused": "output.paused"}},
    }}
    actions = {"x-cap.test.state.v1": Action(name="get_state", verb="read",
                                           output={"paused": Field("boolean")})}


class Peer:
    """Text-JSON loopback peer; no socket or ROS runtime is created."""

    def __init__(self):
        self.incoming = queue.Queue()
        self.sent = []
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def send(self, payload):
        message = json.loads(payload)
        self.sent.append(message)
        reply = response(message)
        if reply is not None:
            self.incoming.put(json.dumps(reply))

    def recv(self):
        try:
            return self.incoming.get(timeout=0.02)
        except queue.Empty:
            raise TimeoutError from None

    def close(self, **kwargs):
        self.closed = True


class RosSimulationTests(unittest.TestCase):
    def test_complete_deployment_is_lazy_and_distinct_from_fake(self):
        cached = SimWorld.driver_model()
        original = copy.deepcopy(cached.fidelity)
        before = build_reference(SimWorld)
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            driver = SimWorld(backend="sim", simulation_deployment=deployment())
            self.addCleanup(driver.close)
            live = build_manifest(driver)
            self.assertEqual(live["device_id"], "mhs://localhost/ros/world/sim/test-world")
            self.assertEqual(driver.device_id, live["device_id"])
            self.assertEqual(live["fidelity"], DEPLOYED_FIDELITY)
            self.assertEqual(live["mode"], "simulated")
            self.assertIsNot(driver._model, cached)
            self.assertIs(SimWorld.driver_model(), cached)
            self.assertEqual(cached.fidelity, original)
            self.assertEqual(build_reference(SimWorld), before)
            fake = SimWorld(backend="fake")
            self.addCleanup(fake.close)
            self.assertEqual(build_manifest(fake)["device_id"], "mhs://localhost/ros/world")
            self.assertEqual(build_manifest(fake)["fidelity"], FAKE_FIDELITY)
            connect.assert_not_called()

    def test_deployments_and_returned_manifests_do_not_share_mutable_fidelity(self):
        first_config = deployment("first")
        second_config = deployment("second")
        second_config["fidelity"]["timestep_ms"] = 10
        first = SimWorld(backend="sim", simulation_deployment=first_config)
        second = SimWorld(backend="sim", simulation_deployment=second_config)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        first_config["endpoint"] = "ws://changed.invalid:9090"
        first_config["deployment_id"] = "changed"
        first_config["fidelity"]["gaps"].append("caller mutation")
        first_config["fidelity"]["determinism"]["kind"] = "exact"
        manifest = build_manifest(first)
        manifest["fidelity"]["gaps"].append("manifest mutation")
        self.assertEqual(build_manifest(first)["fidelity"], DEPLOYED_FIDELITY)
        self.assertEqual(build_manifest(second)["fidelity"]["timestep_ms"], 10)
        self.assertNotEqual(first.device_id, second.device_id)
        first.open()
        self.assertEqual(first.inner.config["endpoint"], "ws://127.0.0.1:9090")
        self.assertTrue(first.device_id.endswith("/sim/first"))
        self.assertEqual(SimWorld.fidelity, FAKE_FIDELITY)

    def test_loopback_websocket_native_runs_through_stock_server_without_ros(self):
        for wrapper in (lambda transport: transport, Recorder):
            with self.subTest(wrapper=wrapper):
                peer = Peer()
                connector = Mock(return_value=peer)
                transport = WebSocketTransport(deployment()["endpoint"], connector=connector)
                driver = SimWorld(backend="sim", simulation_deployment=deployment(), native=wrapper(transport))
                driver.open()
                connector.assert_not_called()
                self.assertEqual(driver.read("main"), {})
                connector.assert_not_called()
                server, client = support.serve(driver)
                try:
                    receipt = client.command("x-cap.test.state.v1")
                    self.assertEqual(receipt["status"], "completed", receipt)
                    self.assertEqual(receipt["output"], {"paused": True})
                    self.assertEqual(receipt["mode"], "simulated")
                    self.assertEqual(receipt["device_id"], driver.device_id)
                    connector.assert_called_once()
                    self.assertEqual(connector.call_args.args, (deployment()["endpoint"],))
                    self.assertEqual([frame["service"] for frame in peer.sent], ["/state"])
                finally:
                    close_server(server)
                self.assertTrue(peer.closed)

    def test_sdk_constructed_transport_uses_deployment_not_fake_factory_or_class_endpoint(self):
        fake_factory = Mock(side_effect=AssertionError("fake fallback"))
        cls = type("OwnedTransport", (SimWorld,), {"backends": {"fake": fake_factory}})
        peer = Peer()
        connector = Mock(return_value=peer)
        websocket_module = Mock(create_connection=connector)
        driver = cls(backend="sim", simulation_deployment=deployment())
        self.addCleanup(driver.close)
        driver.open()
        with patch("mhs.bridge.ros_transport.importlib.import_module", return_value=websocket_module) as imports:
            self.assertEqual(driver.call("x-cap.test.state.v1"), {"paused": True})
            imports.assert_called_once_with("websocket")
        fake_factory.assert_not_called()
        connector.assert_called_once()
        self.assertEqual(connector.call_args.args, (deployment()["endpoint"],))

    def test_missing_deployment_never_uses_endpoint_or_fake_factory(self):
        factory = Mock(side_effect=AssertionError("fake fallback"))
        cls = type("NoFallback", (SimWorld,), {"backends": {"fake": factory}})
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            driver = cls(backend="sim", options={"endpoint": deployment()["endpoint"]})
            self.addCleanup(driver.close)
            with self.assertRaises(MHSError) as caught:
                driver.open()
            self.assertIn("declares no 'sim' backend", str(caught.exception))
            factory.assert_not_called()
            connect.assert_not_called()

    def test_deployment_refused_for_fake_and_hardware_before_factory_or_connector(self):
        for backend in ("fake", "hardware"):
            factory = Mock(side_effect=AssertionError("factory before validation"))
            cls = type("WrongBackend", (SimWorld,), {"backends": {backend: factory}})
            with self.subTest(backend=backend), patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
                with self.assertRaisesRegex(ValueError, "backend='sim'"):
                    cls(backend=backend, simulation_deployment=deployment())
                factory.assert_not_called()
                connect.assert_not_called()

    def test_hardware_class_cannot_be_relabelled_as_live_simulation(self):
        for risk in ("R0", "R1", "R2", "R3"):
            factory = Mock(side_effect=AssertionError("factory before validation"))
            cls = type("Hardware", (SimWorld,), {"mode": "hardware", "risk": risk,
                                                  "fidelity": None, "backends": {"sim": factory}})
            with self.subTest(risk=risk), patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
                with self.assertRaisesRegex(ValueError, "mode='simulated'"):
                    cls(backend="sim", simulation_deployment=deployment())
                factory.assert_not_called()
                connect.assert_not_called()

    def test_hardware_review_still_runs_before_any_factory_at_every_risk(self):
        for risk in ("R0", "R1", "R2", "R3"):
            for author in ("model", "human"):
                factory = Mock(side_effect=AssertionError("unsigned hardware factory"))
                cls = type("UnsignedHardware", (SimWorld,), {"mode": "hardware", "risk": risk,
                        "fidelity": None, "backends": {"hardware": factory}})
                with self.subTest(risk=risk, author=author), \
                        patch("mhs.driver.loader.read_lock", return_value=(support.lock_document(kind=author), [])), \
                        patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
                    with self.assertRaises(PermissionError):
                        cls(backend="hardware")
                    factory.assert_not_called()
                    connect.assert_not_called()

    def test_ambiguous_factories_endpoint_overrides_and_device_ids_are_rejected(self):
        factory = Mock(side_effect=AssertionError("ambiguous factory"))
        cls = type("SimFactory", (SimWorld,), {"backends": {"sim": factory}})
        variants = [(cls, {}), (SimWorld, {"options": {"endpoint": deployment()["endpoint"]}}),
                    (SimWorld, {"device_id": "mhs://localhost/fake-world"})]
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            for driver_class, kwargs in variants:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    driver_class(backend="sim", simulation_deployment=deployment(), **kwargs)
            factory.assert_not_called()
            connect.assert_not_called()

    def test_native_must_be_matching_websocket_and_is_rechecked_before_bridge_creation(self):
        connector = Mock(side_effect=AssertionError("refused native connected"))
        wrong_endpoint = WebSocketTransport("ws://other.invalid:9090", connector=connector)
        self.addCleanup(wrong_endpoint.close)
        recording = RecordingRosTransport(response)
        for candidate in (None, recording, wrong_endpoint, Recorder(wrong_endpoint)):
            with self.subTest(candidate=type(candidate).__name__), self.assertRaisesRegex(ValueError, "exact endpoint"):
                SimWorld(backend="sim", simulation_deployment=deployment(), native=candidate)
        native = WebSocketTransport(deployment()["endpoint"], connector=connector)
        driver = SimWorld(backend="sim", simulation_deployment=deployment(), native=native)
        self.addCleanup(driver.close)
        native.url = "ws://mutated.invalid:9090"
        with self.assertRaisesRegex(ValueError, "exact endpoint"):
            driver.open()
        connector.assert_not_called()

    def test_invalid_deployment_shape_endpoint_or_id_never_connects(self):
        configs = [[], {}, deployment(extra=True), deployment(endpoint="http://localhost:9090"),
                   deployment(endpoint="ws://user:secret@localhost:9090"), deployment(endpoint="ws://localhost:99999"),
                   deployment(endpoint=None), deployment("../alias"), deployment("x/y"), deployment(""),
                   deployment("a" * 65)]
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            for config in configs:
                with self.subTest(config=config), self.assertRaises(ValueError):
                    SimWorld(backend="sim", simulation_deployment=config)
            connect.assert_not_called()

    def test_incomplete_or_invalid_fidelity_is_rejected_before_io(self):
        invalid = [None, {}, {**DEPLOYED_FIDELITY, "extra": True},
                   {**DEPLOYED_FIDELITY, "engine": "  "},
                   {**DEPLOYED_FIDELITY, "timestep_ms": -1},
                   {**DEPLOYED_FIDELITY, "snapshot_restore": 0},
                   {**DEPLOYED_FIDELITY, "determinism": {"kind": "seeded"}},
                   {**DEPLOYED_FIDELITY, "fidelity_level": "F3", "validation": {"metrics": {"rmse": 0}}}]
        for required in DEPLOYED_FIDELITY:
            if required == "clock":
                continue  # clock remains optional in the MHS fidelity contract.
            value = copy.deepcopy(DEPLOYED_FIDELITY)
            del value[required]
            invalid.append(value)
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            for fidelity in invalid:
                with self.subTest(fidelity=fidelity), self.assertRaises(MHSError) as caught:
                    SimWorld(backend="sim", simulation_deployment=deployment(fidelity=fidelity))
                self.assertEqual(caught.exception.code, "MHS.FIDELITY.CONTRACT_REQUIRED")
            connect.assert_not_called()

    def test_nonfinite_fidelity_is_rejected_before_io(self):
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            for number in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(number=number), self.assertRaisesRegex(ValueError, "finite JSON"):
                    SimWorld(backend="sim", simulation_deployment=deployment(
                        fidelity={**DEPLOYED_FIDELITY, "timestep_ms": number}))
            connect.assert_not_called()

    def test_projection_hook_rejects_other_backends_without_mutating_the_class(self):
        driver = SimWorld(backend="sim", simulation_deployment=deployment())
        self.addCleanup(driver.close)
        driver._validate_backend_projection(None)
        driver._validate_backend_projection("sim")
        for backend in ("fake", "hardware"):
            with self.subTest(backend=backend), self.assertRaisesRegex(ValueError, "another backend"):
                driver._validate_backend_projection(backend)
        self.assertEqual(build_manifest(SimWorld, backend="fake")["fidelity"], FAKE_FIDELITY)

    def test_fake_still_refuses_websocket_even_with_simulation_like_options(self):
        connector = Mock(side_effect=AssertionError("fake connected"))
        transport = WebSocketTransport(deployment()["endpoint"], connector=connector)
        driver = SimWorld(backend="fake", native=Recorder(transport),
                          options={"simulation_deployment": deployment(), "endpoint": deployment()["endpoint"]})
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.open()
        self.assertIn("cannot use the live WebSocket", str(caught.exception))
        connector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
