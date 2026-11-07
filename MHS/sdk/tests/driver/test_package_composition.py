"""Package composition: one driver, one device, several typed resources (extra_resources + Action(resource=...)).

A stable image class binds ``sensor.camera`` and a stable point-cloud class binds ``sensor.depth``; their accepted
kinds do not intersect, so one package serves both only on two resources of one device.  These tests cover the
declaration rules (refused before any backend exists), the stock loader/server/client path, the decorated-driver
runtime, the ROS bridge routing and the acceptance gate.  Samples are controlled test data.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.artifacts import LocalArtifactStore
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import Action, Driver, DriverDefinitionError, PythonObjectDriver, RosDriver, action, close_server
from mhs.driver.build import build_manifest, build_reference
from mhs.errors import MHSError
from tests.driver import gate_support as gs

IMAGE = "cap.sensing.image.v1"
CLOUD = "cap.sensing.point_cloud.v1"
STATUS = "x-cap.test.status.v1"
IDLE = "x-cap.test.idle.v1"
IMAGE_MSG = {"header": {"stamp": {"sec": 2, "nanosec": 3}, "frame_id": "cam"}, "width": 2, "height": 1,
             "step": 6, "encoding": "rgb8", "is_bigendian": 0, "data": [1, 2, 3, 250, 251, 252]}
CLOUD_MSG = {"header": {"stamp": {"sec": 4, "nanosec": 5}, "frame_id": "depth"}, "width": 1, "height": 1,
             "point_step": 12, "row_step": 12, "is_dense": True, "is_bigendian": False,
             "fields": [{"name": n, "offset": i * 4, "datatype": 7, "count": 1} for i, n in enumerate("xyz")],
             "data": [0, 0, 128, 63, 0, 0, 0, 64, 0, 0, 64, 64]}
COMMANDS = {
    IMAGE: {"cameras": {"color": {"topic": "/image", "type": "sensor_msgs/msg/Image", "operation": "subscribe",
                                  "image": {}, "source_ref": "node.cpp:1"}}},
    CLOUD: {"topic": "/points", "type": "sensor_msgs/msg/PointCloud2", "operation": "subscribe", "point_cloud": {},
            "source_ref": "node.cpp:2"},
}


def ros_class(*, extra=None, actions=None, commands=None, kind="sensor.camera", base=RosDriver, resource_id="camera"):
    attrs = {"device_id": "composed", "device_kind": kind, "mode": "hardware", "risk": "R0", "ros_version": 2,
             "resource_id": resource_id, "commands": copy.deepcopy(commands if commands is not None else COMMANDS),
             "actions": actions if actions is not None else {CLOUD: Action(resource="depth")},
             "backends": {"fake": ".fake:Transport"}}
    if extra is not False:
        attrs["extra_resources"] = extra if extra is not None else {"depth": {"kind": "sensor.depth"}}
    return type("Composed", (base,), attrs)


def problems(cls) -> str:
    with unittest.TestCase().assertRaises(DriverDefinitionError) as caught:
        cls.driver_model()
    return " | ".join(caught.exception.problems)


class Transport(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(self.respond)

    def respond(self, request):
        if request["op"] == "subscribe":
            message = IMAGE_MSG if request["topic"] == "/image" else CLOUD_MSG
            return {"op": "publish", "topic": request["topic"], "id": request["id"], "msg": copy.deepcopy(message)}
        return None


class DeclarationRules(unittest.TestCase):
    def test_composed_ros_driver_resolves_each_binding_on_its_own_resource_kind(self):
        model = ros_class().driver_model()
        manifest = build_manifest(ros_class(), backend="fake")
        self.assertEqual([(r["resource_id"], r["kind"]) for r in manifest["resources"]],
                         [("camera", "sensor.camera"), ("depth", "sensor.depth")])
        self.assertEqual(manifest["resources"][1]["state_schema"],
                         {"type": "object", "properties": {}, "additionalProperties": False})
        self.assertEqual({c["capability_id"]: c["resource"] for c in manifest["capabilities"]},
                         {IMAGE: "camera", CLOUD: "depth"})
        self.assertEqual(model.risk, "R0")
        reference = build_reference(ros_class())
        self.assertEqual({a["cap_id"]: a["resource"] for a in reference["actions"]}, {IMAGE: "camera", CLOUD: "depth"})
        self.assertEqual(reference["device"]["kind"], "sensor.camera")
        self.assertEqual(reference["device"]["resources"],
                         [{"id": "camera", "kind": "sensor.camera"}, {"id": "depth", "kind": "sensor.depth"}])

    def test_the_single_kind_combinations_stay_refused_with_unchanged_messages(self):
        camera = problems(ros_class(extra=False, actions={}))
        self.assertIn("cap.sensing.point_cloud.v1: cap.sensing.point_cloud.v1 does not bind resource kind "
                      "'sensor.camera' (kinds: ['sensor.depth']); change device_kind or use an x-cap action", camera)
        depth = problems(ros_class(extra=False, actions={}, kind="sensor.depth"))
        self.assertIn("does not bind resource kind 'sensor.depth' (kinds: ['sensor.camera'])", depth)

    def test_wrong_kind_on_the_extra_resource_is_refused(self):
        text = problems(ros_class(extra={"depth": {"kind": "sensor.camera"}}))
        self.assertIn("does not bind resource kind 'sensor.camera' of resource 'depth'", text)

    def test_undeclared_and_malformed_binding_resources_are_refused(self):
        self.assertIn("resource 'nowhere' is not declared", problems(ros_class(actions={CLOUD: Action(resource="nowhere")})))
        self.assertIn("resource must be the id", problems(ros_class(actions={CLOUD: Action(resource=5)})))
        self.assertIn("resource must be the id", problems(ros_class(actions={CLOUD: Action(resource="Bad Id")})))

    def test_extra_resource_declarations_are_validated(self):
        cases = [({"camera": {"kind": "sensor.depth"}}, "repeats the main resource_id"),
                 ({"depth": {"kind": "sensor.depthx"}}, "is not a catalogue resource kind"),
                 ({"depth": {"kind": "Sensor Depth"}}, "must be a resource kind"),
                 ({"depth": {"kind": "sensor.depth", "port": 9090}}, "with an optional 'title'"),
                 ({"depth": "sensor.depth"}, "with an optional 'title'"),
                 ({"Depth!": {"kind": "sensor.depth"}}, "must match [a-z0-9]"),
                 ({"depth": {"kind": "sensor.depth", "title": ""}}, "title must be a non-empty string"),
                 ({"depth": {"kind": "sensor.depth", "title": "depth\ncloud"}}, "without control characters"),
                 ({"depth": {"kind": "sensor.depth", "title": "depth\x7f"}}, "without control characters"),
                 ([("depth", "sensor.depth")], "extra_resources must map resource ids"),
                 ({f"r{i}": {"kind": "sensor.depth"} for i in range(8)}, "at most 7")]
        for extra, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, problems(ros_class(extra=extra)))

    def test_an_extra_resource_without_a_binding_is_refused(self):
        text = problems(ros_class(extra={"depth": {"kind": "sensor.depth"}, "spare": {"kind": "sensor.depth"}}))
        self.assertIn("extra_resources['spare'] binds no capability", text)

    def test_a_raw_command_map_resource_is_not_authority(self):
        commands = copy.deepcopy(COMMANDS)
        commands[CLOUD]["resource"] = "camera"
        self.assertIn("but the declared binding resource is 'depth'", problems(ros_class(commands=commands)))
        commands[CLOUD]["resource"] = "depth"
        ros_class(commands=commands).driver_model()  # agreeing with the contract is accepted
        commands = copy.deepcopy(COMMANDS)
        commands[CLOUD]["resource"] = "depth"
        self.assertIn("but the declared binding resource is 'camera'",
                      problems(ros_class(commands=commands, actions={}, extra=False)))

    def test_families_that_cannot_route_resources_refuse_extra_resources(self):
        cls = type("Py", (PythonObjectDriver,), {
            "device_id": "py", "device_kind": "sensor.camera", "mode": "simulated", "risk": "R0",
            "native": "x.y:Z", "extra_resources": {"depth": {"kind": "sensor.depth"}},
            "fidelity": {"engine": "x", "fidelity_level": "F0", "determinism": {"kind": "none"}, "timestep_ms": 0,
                         "realtime_factor": 0, "reset": "none", "snapshot_restore": False, "gaps": []},
            "commands": {"x-cap.test.ping.v1": {"call": "ping"}},
            "actions": {"x-cap.test.ping.v1": Action(output={"ok": __import__("mhs").driver.Field("boolean")})}})
        self.assertIn("the python-object family serves one resource", problems(cls))

    def test_a_capability_is_still_bound_once_even_across_resources(self):
        class Twice(Driver):
            device_id, device_kind, mode, risk = "twice", "sensor.camera", "simulated", "R0"
            fidelity = {"engine": "x", "fidelity_level": "F0", "determinism": {"kind": "none"}, "timestep_ms": 0,
                        "realtime_factor": 0, "reset": "none", "snapshot_restore": False, "gaps": []}
            extra_resources = {"second": {"kind": "sensor.camera"}}

            @action(IMAGE)
            def first(self):
                return {"image_ref": "a", "width": 1, "height": 1}

            @action(IMAGE, resource="second", action_name="other")
            def second(self):
                return {"image_ref": "b", "width": 1, "height": 1}
        self.assertIn("is bound twice", problems(Twice))

    def test_single_resource_drivers_keep_their_exact_bridge_configuration(self):
        cls = ros_class(extra=False, actions={}, commands={IMAGE: COMMANDS[IMAGE]})
        config = cls.bridge_config("camera", device=False)
        self.assertEqual(config["resources"], [{"resource_id": "camera", "kind": "sensor.camera"}])
        self.assertEqual(config["commands"][IMAGE]["resource"], "camera")
        self.assertEqual(config["reads"], {"camera": {"fields": {}}})
        self.assertEqual(len(build_manifest(cls, backend="fake")["resources"]), 1)
        self.assertNotIn("resources", build_reference(cls)["device"])

    def test_configure_is_generated_for_the_main_resource_only(self):
        # Only cap.device.configure.v1 reads a resource state schema; it can never be bound on an extra resource,
        # which is why finish() resolves every binding with the main resource's state schema.
        from mhs.driver import Limit, write

        class Configured(Driver):
            device_id, device_kind, mode, risk = "configured", "sensor.temperature", "simulated", "R0"
            resource_id = "thermo"
            fidelity = {"engine": "x", "fidelity_level": "F0", "determinism": {"kind": "none"}, "timestep_ms": 0,
                        "realtime_factor": 0, "reset": "none", "snapshot_restore": False, "gaps": []}
            extra_resources = {"imu": {"kind": "sensor.imu"}}

            @write("offset", unit="Cel", limit=Limit.operator_required("test overlay"))
            def set_offset(self, value):
                return value

            @action("cap.sensing.read.v1", resource="imu")
            def motion(self):
                return {"values": {}}
        manifest = build_manifest(Configured, backend="fake")
        configure = next(c for c in manifest["capabilities"] if c["capability_id"] == "cap.device.configure.v1")
        self.assertEqual(configure["resource"], "thermo")
        self.assertEqual(manifest["resources"][1]["state_schema"]["properties"], {})

        class ConfigureOnExtra(Configured):
            @action("cap.device.configure.v1", resource="imu")
            def configure_imu(self, offset):
                return None
        self.assertIn("is generated from the @write parameters", problems(ConfigureOnExtra))


class DecoratedRuntime(unittest.TestCase):
    class Composed(Driver):
        device_id, device_kind, mode, risk = "decorated", "sensor.camera", "simulated", "R0"
        resource_id = "camera"
        fidelity = {"engine": "x", "fidelity_level": "F0", "determinism": {"kind": "none"}, "timestep_ms": 0,
                    "realtime_factor": 0, "reset": "none", "snapshot_restore": False, "gaps": []}
        extra_resources = {"depth": {"kind": "sensor.depth", "title": "Depth"}}

        @action(IMAGE)
        def capture(self):
            return {"image_ref": "mhs://x/image", "width": 1, "height": 1}

        @action(CLOUD, resource="depth")
        def cloud(self):
            return {"artifact_ref": "mhs://x/cloud", "point_count": 0}

    def test_reads_writes_resources_and_routing(self):
        driver = self.Composed(backend="fake", native=object())
        self.addCleanup(driver.close)
        self.assertEqual([r["resource_id"] for r in driver.resources()], ["camera", "depth"])
        self.assertEqual({c["capability_id"]: c["resource"] for c in driver.capabilities()},
                         {IMAGE: "camera", CLOUD: "depth"})
        self.assertEqual(driver.read("depth"), {})
        with self.assertRaises(MHSError) as caught:
            driver.write("depth", {"x": 1})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.NOT_WRITABLE")
        with self.assertRaises(MHSError) as caught:
            driver.read("elsewhere")
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.NOT_BOUND")
        self.assertEqual(driver.call(CLOUD, {}, {"resource": "depth"})["point_count"], 0)
        self.assertEqual(driver.call(CLOUD, {})["point_count"], 0)
        with self.assertRaises(MHSError) as caught:
            driver.call(CLOUD, {}, {"resource": "camera"})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.NOT_BOUND")


class DecoratedThroughTheServer(unittest.TestCase):
    class Probe(Driver):
        device_id, device_kind, mode, risk = "probe", "sensor.temperature", "simulated", "R0"
        resource_id = "thermo"
        fidelity = {"engine": "x", "fidelity_level": "F0", "determinism": {"kind": "none"}, "timestep_ms": 0,
                    "realtime_factor": 0, "reset": "none", "snapshot_restore": False, "gaps": []}
        extra_resources = {"imu": {"kind": "sensor.imu"}}

        @action("cap.measure.temperature.v1")
        def temperature(self):
            return 21.5

        @action("cap.sensing.read.v1", resource="imu")
        def motion(self):
            return {"values": {"ax": 0.25}}

    def test_strict_server_serves_each_binding_on_its_resource(self):
        from mhs.driver.build import build_server

        server = build_server(self.Probe(backend="fake", native=object()))
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        device = client.hello()["devices"][0]["device_id"]
        client.open_session([device])
        manifest = client.request("mhs.devices.get", {"device_id": device})
        self.assertEqual([(r["resource_id"], r["kind"]) for r in manifest["resources"]],
                         [("thermo", "sensor.temperature"), ("imu", "sensor.imu")])
        temperature = client.invoke("cap.measure.temperature.v1", {}, device_id=device)
        motion = client.invoke("cap.sensing.read.v1", {}, device_id=device)
        self.assertEqual(temperature["output"]["temperature"], 21.5)
        self.assertEqual(motion["output"]["values"], {"ax": 0.25})
        misrouted = client.invoke("cap.sensing.read.v1", {}, device_id=device, resource="thermo")
        self.assertEqual(misrouted["error"]["mhs_code"], "MHS.CAPABILITY.NOT_BOUND", misrouted)
        self.assertEqual(client.read("imu", device_id=device)["state"], {})


class RosBridgeRouting(unittest.TestCase):
    def config(self, **changes):
        config = {"timeout_s": 1.0, "resources": [{"resource_id": "camera", "kind": "sensor.camera"},
                                                  {"resource_id": "depth", "kind": "sensor.depth"}],
                  "commands": {IMAGE: {**copy.deepcopy(COMMANDS[IMAGE]), "resource": "camera"},
                               CLOUD: {**copy.deepcopy(COMMANDS[CLOUD]), "resource": "depth"},
                               STATUS: {"topic": "/status", "type": "std_msgs/msg/String",
                                        "operation": "subscribe", "resource": "depth"}},
                  "reads": {"camera": {"fields": {}}, "depth": {"fields": {}}}}
        config.update(changes)
        return config

    def test_bindings_must_name_declared_resources(self):
        transport = Transport()
        RosBridge(self.config(), transport=transport).close()
        bad = self.config()
        bad["commands"][CLOUD]["resource"] = "lidar"
        for config in (bad, self.config(reads={"camera": {"fields": {}}, "lidar": {"fields": {}}}),
                       self.config(resources=[{"resource_id": "camera"}, {"resource_id": "camera"}]),
                       self.config(resources=[])):
            with self.subTest(config=json.dumps(config)[:80]):
                with self.assertRaises(MHSError) as caught:
                    RosBridge(config, transport=Transport())
                self.assertEqual(caught.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertEqual(transport.sent, [])

    def test_a_call_routed_to_another_resource_is_refused_before_sending(self):
        transport = Transport()
        bridge = RosBridge(self.config(), transport=transport)
        self.addCleanup(bridge.close)
        # STATUS needs no artifact store, so only the routing check stands between the misrouted call and the wire.
        self.assertEqual(bridge.call(STATUS, {}, {"resource": "depth"})["header"]["frame_id"], "depth")
        sent = len(transport.sent)
        for capability_id in (STATUS, CLOUD):
            with self.subTest(capability_id=capability_id):
                with self.assertRaises(MHSError) as caught:
                    bridge.call(capability_id, {}, {"resource": "camera"})
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.NOT_BOUND")
                self.assertIn("is bound to resource 'depth', not 'camera'", caught.exception.message)
        self.assertEqual(len(transport.sent), sent)
        self.assertEqual(bridge.read("depth"), {})
        self.assertEqual(len(transport.sent), sent)


class StockPath(unittest.TestCase):
    def package(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="mhs-composed-")))
        (directory / "fake.py").write_text(FAKE)
        (directory / "driver.py").write_text(DRIVER)
        return directory

    def test_loader_server_client_serve_both_resources_with_one_transport(self):
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(self.package(), backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        device = client.hello()["devices"][0]["device_id"]
        client.open_session([device])
        native = server.devices[device].bridge.native
        image = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        cloud = client.invoke(CLOUD, {}, device_id=device)
        self.assertEqual((image["status"], cloud["status"]), ("completed", "completed"), (image, cloud))
        self.assertEqual(cloud["output"]["point_count"], 1)
        self.assertEqual(sorted(item["topic"] for item in native.sent if item["op"] == "subscribe"),
                         ["/image", "/points"])
        self.assertEqual(client.read("depth", device_id=device)["state"], {})
        wrong = client.invoke(CLOUD, {}, device_id=device, resource="camera")
        self.assertEqual(wrong["error"]["mhs_code"], "MHS.CAPABILITY.NOT_BOUND", wrong)
        self.assertEqual(len(store._grants), 2)
        close_server(server)
        self.assertTrue(native.closed)

    def test_a_ros_safe_state_command_on_an_extra_resource_runs_during_estop(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="mhs-composed-safe-")))
        (directory / "fake.py").write_text(SAFE_FAKE)
        (directory / "driver.py").write_text(SAFE_DRIVER)
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(directory, backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        device = client.hello()["devices"][0]["device_id"]
        client.open_session([device])
        manifest = client.request("mhs.devices.get", {"device_id": device})
        self.assertEqual({c["capability_id"]: c["resource"] for c in manifest["capabilities"]}[IDLE], "depth")
        self.assertEqual(manifest["safety"]["safe_state"]["achieved_by"], [IDLE])
        native = server.devices[device].bridge.native
        stopped = client.estop("composition safe-state probe", device_id=device)
        self.assertTrue(stopped["output"]["safe_state_achieved"], stopped)
        self.assertEqual([m["service"] for m in native.sent if m["op"] == "call_service"], ["/idle"])
        refused = client.invoke(CLOUD, {}, device_id=device)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)
        with self.assertRaises(MHSError) as caught:
            server.devices[device].bridge.call(IDLE, {}, {"resource": "camera"})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.NOT_BOUND")
        self.assertEqual([m["service"] for m in native.sent if m["op"] == "call_service"], ["/idle"])

    def test_mcp_projection_publishes_each_tool_on_its_resource(self):
        from mhs import canonical
        from mhs.mcp import MCPPolicy, MCPProjection

        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(self.package(), backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)

        def request(method, params=None):
            return projection.handle_message({"jsonrpc": "2.0", "id": canonical.ulid(), "method": method,
                                              "params": params or {}})
        request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                               "clientInfo": {"name": "composition-test", "version": "1"}})
        tools = {tool["x-mhs"]["capability_id"]: tool for tool in request("tools/list")["result"]["tools"]
                 if "x-mhs" in tool}
        self.assertEqual((tools[IMAGE]["x-mhs"]["resource"], tools[CLOUD]["x-mhs"]["resource"]), ("camera", "depth"))
        receipt = request("tools/call", {"name": tools[CLOUD]["name"], "arguments": {}})["result"]
        self.assertEqual(receipt["structuredContent"]["receipt"]["status"], "completed", receipt)
        uris = [item["uri"] for item in request("resources/list")["result"]["resources"]]
        self.assertTrue(any(uri.endswith("/resources/depth") for uri in uris), uris)


FAKE = '''import copy
from mhs.bridge.ros_transport import RecordingRosTransport
IMAGE = ''' + repr(IMAGE_MSG) + '''
CLOUD = ''' + repr(CLOUD_MSG) + '''
class Transport(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(self.respond)
    def respond(self, request):
        if request["op"] == "subscribe":
            message = IMAGE if request["topic"] == "/image" else CLOUD
            return {"op": "publish", "topic": request["topic"], "id": request["id"], "msg": copy.deepcopy(message)}
'''
DRIVER = '''from mhs.driver import Action, RosDriver
class Composed(RosDriver):
    device_id, device_kind, mode, risk = "composed-gate", "sensor.camera", "hardware", "R0"
    resource_id = "camera"
    ros_version = 2
    backends = {"fake": ".fake:Transport", "hardware": ".native:connect"}
    extra_resources = {"depth": {"kind": "sensor.depth", "title": "Depth point cloud"}}
    commands = ''' + repr(COMMANDS) + '''
    actions = {"cap.sensing.point_cloud.v1": Action(resource="depth", description="Capture one point cloud")}
'''


SAFE_FAKE = '''import copy
from mhs.bridge.ros_transport import RecordingRosTransport
CLOUD = ''' + repr(CLOUD_MSG) + '''
class Transport(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(self.respond)
    def respond(self, request):
        if request["op"] == "subscribe":
            return {"op": "publish", "topic": request["topic"], "id": request["id"], "msg": copy.deepcopy(CLOUD)}
        if request["op"] == "call_service" and request["service"] == "/idle":
            return {"op": "service_response", "service": "/idle", "id": request["id"], "result": True,
                    "values": {"success": True, "message": "idle"}}
'''
SAFE_DRIVER = '''from mhs.driver import Action, RosDriver
class Composed(RosDriver):
    device_id, device_kind, mode, risk = "composed-safe", "sensor.camera", "hardware", "R0"
    resource_id = "camera"
    ros_version = 2
    backends = {"fake": ".fake:Transport"}
    extra_resources = {"depth": {"kind": "sensor.depth"}}
    commands = {
        "x-cap.test.status.v1": {"topic": "/status", "type": "std_msgs/msg/String", "operation": "subscribe"},
        "cap.sensing.point_cloud.v1": {"topic": "/points", "type": "sensor_msgs/msg/PointCloud2",
                                       "operation": "subscribe", "point_cloud": {}},
        "x-cap.test.idle.v1": {"service": "/idle", "type": "std_srvs/srv/Trigger",
                               "success": {"path": "success", "equals": True}},
    }
    actions = {
        "x-cap.test.status.v1": Action(name="read_status", verb="read", output={}),
        "cap.sensing.point_cloud.v1": Action(resource="depth"),
        "x-cap.test.idle.v1": Action(name="idle_depth", resource="depth", safe_state=True, output={},
                                     description="Idle the depth stream"),
    }
'''


def gate_package(test, driver=DRIVER):
    directory = gs.copy_tutorial(test, name="composed")
    (directory / "driver.py").write_text(driver)
    (directory / "fake.py").write_text(FAKE)
    (directory / "native.py").write_text('def connect(**options):\n    raise AssertionError("No hardware in SDK test")\n')
    (directory / "vendor/node.cpp").write_text('publish<sensor_msgs::msg::Image>("/image");\n'
                                               'publish<sensor_msgs::msg::PointCloud2>("/points");\n')
    gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:Transport", "hardware": ".native:connect"})
    gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R0"}, entry_symbols=[],
                 driver_dir="MHS/sdk/examples/composed")
    (directory / "site-limits.example.json").rename(directory.parent / "tutorial-overlay-original.json")
    gs.regenerate(directory)
    return directory


class CompositionGate(unittest.TestCase):
    def test_composed_package_passes_every_gate_and_g6_routes_each_resource(self):
        directory = gate_package(self)
        report = gs.check(directory)
        self.assertEqual(report["failed"], [], json.dumps(report["gates"], indent=1)[:3000])
        statuses = gs.statuses(report)
        for gate in ("G3", "G4", "G5", "G6", "G7"):
            self.assertEqual(statuses[gate], "pass", gate)
        reference = json.loads((directory / "reference.json").read_text())
        self.assertEqual({a["cap_id"]: a["resource"] for a in reference["actions"]}, {IMAGE: "camera", CLOUD: "depth"})

    def test_g6_reads_every_extra_resource(self):
        driver = DRIVER + ("    def read(self, resource_id, fields=None, ctx=None):\n"
                           "        if resource_id == 'depth':\n"
                           "            return {'unexpected': 1}\n"
                           "        return super().read(resource_id, fields, ctx)\n")
        report = gs.check(gate_package(self, driver), gates=("G6",))
        coded = gs.coded(report, "G6")
        self.assertTrue(any(code in ("G6.READ_INVALID", "G6.READ_FAILED") and path == "state.depth"
                            for code, path in coded), coded)

    def test_g6_session_targets_each_binding_resource(self):
        from mhs.driver.behaviour import Session

        store = LocalArtifactStore()
        self.addCleanup(store.close)
        directory = gate_package(self)
        server = load(directory, backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        session = Session(server, next(iter(server.devices)))
        self.assertEqual(session.resource_for(CLOUD), "depth")
        self.assertEqual(session.resource_for(IMAGE), "camera")
        self.assertEqual(session.resource_for("cap.unknown.v1"), "camera")
        self.assertEqual(session.command(CLOUD, {})["status"], "completed")
        self.assertEqual(session.read("depth")["state"], {})

    def test_tampered_routing_fails_g3_definition(self):
        driver = DRIVER.replace("'point_cloud': {}, ", "'point_cloud': {}, 'resource': 'camera', ")
        self.assertNotEqual(driver, DRIVER)
        directory = gate_package(self)
        (directory / "driver.py").write_text(driver)  # tampered after the reference was generated
        report = gs.check(directory, gates=("G3",))
        self.assertIn("G3.DEFINITION", gs.findings(report))
        self.assertTrue(any("but the declared binding resource is 'depth'" in f["message"]
                            for g in report["gates"] for f in g["findings"]))


if __name__ == "__main__":
    unittest.main()
