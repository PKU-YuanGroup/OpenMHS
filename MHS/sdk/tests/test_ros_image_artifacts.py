"""Stock RosDriver/server/client/MCP image artifacts with controlled peers only."""
import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.artifacts import ArtifactPublisher, LocalArtifactStore
from mhs.bridge import ros_images
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import Action, DriverDefinitionError, Field, RosDriver, build_server, close_server
from mhs.errors import MHSError
from mhs.evidence import verify_bundle
from mhs.mcp import MAX_FRAME_BYTES, MCPPolicy, MCPProjection
from mhs.schema.store import default_store
from tests.bridges.test_ros_images import RAW, COMPRESSED, Image, compressed_message, png_rows, raw_message

CAP = "cap.sensing.image.v1"


class RosImageArtifactTests(unittest.TestCase):
    def make(self, message=None, *, ros_type=RAW, with_store=True, tokens=None,
             long_running=False, store_options=None, execution_ms=None, version=2):
        state = {"message": message if message is not None else raw_message(), "subscriptions": 0}
        def respond(request):
            if request["op"] == "subscribe":
                state["subscriptions"] += 1
                return {"op": "publish", "topic": "/image", "id": request["id"],
                        "msg": copy.deepcopy(state["message"])}
            return None
        transport = RecordingRosTransport(respond)
        class Camera(RosDriver):
            device_id, device_kind, mode, risk = "camera", "sensor.camera", "hardware", "R0"
            ros_version = version
            backends = {"fake": lambda: transport}
            commands = {CAP: {"topic": "/image", "type": ros_type, "operation": "subscribe", "image": {}}}
        if long_running or execution_ms is not None:
            Camera.actions = {CAP: Action(name="capture", long_running=long_running,
                                          cancellable=long_running, max_duration_ms=execution_ms or 4000)}
        store = LocalArtifactStore(**(store_options or {})) if with_store else None
        server = build_server(Camera(backend="fake"), artifact_store=store, auth_tokens=tokens)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token="token-a" if tokens else None))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], capabilities=[CAP])
        return state, transport, store, server, client, device

    def project(self, client):
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)
        response = projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                             "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                                        "clientInfo": {"name": "image-test", "version": "1"}}})
        self.assertIn("result", response)
        tools = self.request(projection, "tools/list")["result"]["tools"]
        capture = next(item["name"] for item in tools if item["name"].endswith("sensing_image"))
        return projection, capture

    def request(self, projection, method, params=None):
        return projection.handle_message({"jsonrpc": "2.0", "id": canonical.ulid(),
                                          "method": method, "params": params or {}})

    def capture(self, projection, name, **arguments):
        response = self.request(projection, "tools/call", {"name": name, "arguments": arguments})
        self.assertIn("result", response)
        result = response["result"]
        receipt = result["structuredContent"]["receipt"]
        return result, receipt

    def test_stock_capture_to_host_blob_and_schema_evidence(self):
        state, native, store, server, client, device = self.make()
        projection, tool = self.project(client)
        result, receipt = self.capture(projection, tool)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(default_store().validate(dict(receipt), "receipt.schema.json"), [])
        self.assertEqual(set(receipt["output"]), {"image_ref", "width", "height", "media_type"})
        descriptor = receipt["artifacts"][0]
        links = [item for item in result["content"] if item["type"] == "resource_link"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["uri"], descriptor["uri"])
        response = self.request(projection, "resources/read", {"uri": descriptor["uri"]})
        blob = base64.b64decode(response["result"]["contents"][0]["blob"], validate=True)
        self.assertEqual(png_rows(blob), b"\0\xff\0\0\0\xff\0")
        self.assertEqual("sha256:" + hashlib.sha256(blob).hexdigest(), descriptor["digest"])
        self.assertEqual(len(blob), descriptor["size_bytes"])
        self.assertLess(len(json.dumps(response).encode()), MAX_FRAME_BYTES)
        evidence = client.export_evidence()
        self.assertTrue(verify_bundle(evidence).valid)
        self.assertEqual(state["subscriptions"], 1, "state hashing must not acquire an image")
        self.assertEqual(client.read("main", device_id=device)["state"], {})
        self.assertEqual(state["subscriptions"], 1)

    @unittest.skipIf(Image is None, "optional Pillow decoder is not installed")
    def test_stock_jpeg_and_png_capture_are_complete_images(self):
        for codec in ("jpeg", "png"):
            with self.subTest(codec=codec):
                state, native, store, server, client, device = self.make(compressed_message(codec), ros_type=COMPRESSED)
                projection, tool = self.project(client)
                _, receipt = self.capture(projection, tool)
                self.assertEqual(receipt["status"], "completed", receipt)
                response = self.request(projection, "resources/read", {"uri": receipt["output"]["image_ref"]})
                data = base64.b64decode(response["result"]["contents"][0]["blob"])
                self.assertEqual(receipt["output"]["media_type"], "image/png")
                with Image.open(io.BytesIO(base64.b64decode(state["message"]["data"]))) as source:
                    source_pixels = source.tobytes()
                with Image.open(io.BytesIO(data)) as decoded:
                    decoded.load()
                    self.assertEqual(decoded.size, (3, 2))
                    self.assertEqual(decoded.tobytes(), source_pixels)

    def test_fixed_stream_controls_and_missing_store_fail_before_wire(self):
        state, native, store, server, client, device = self.make()
        for value in ({"width": 640}, {"exposure_ms": 10}, {"format": "jpeg"}, {"camera": "other"}):
            receipt = client.invoke(CAP, value, device_id=device)
            self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(native.sent, [])
        state, native, store, server, client, device = self.make(with_store=False)
        receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(native.sent, [])

    def test_missing_decoder_fails_before_subscription(self):
        _, native, store, server, client, device = self.make({"format": "jpeg", "data": "AAAA"}, ros_type=COMPRESSED)
        with patch.object(ros_images, "require_decoder", side_effect=ValueError("missing decoder")):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(native.sent, [])
        self.assertEqual(store._grants, {})

    def test_malformed_frame_and_capacity_failure_have_no_usable_reference(self):
        state, native, store, server, client, device = self.make()
        for value in ({"data": [True] * 6}, {"data": [1]}, {"encoding": "32FC1"}, {"step": 5}):
            state["message"] = {**raw_message(), **value}
            receipt = client.invoke(CAP, {}, device_id=device)
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertNotIn("artifacts", receipt)
            self.assertIsNone(receipt["output"])
            self.assertEqual(store._grants, {})
        state["message"] = raw_message()
        first = client.invoke(CAP, {}, device_id=device)
        store.max_artifacts = 1
        second = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(second["status"], "failed", second)
        self.assertEqual(len(store._grants), 1)
        self.assertTrue(client.read_artifact(first["output"]["image_ref"], session_id=client.session_id)["data"])

    def test_exact_session_and_bearer_principal_authorization(self):
        tokens = {"token-a": {"id": "alice", "kind": "agent"}, "token-b": {"id": "bob", "kind": "agent"}}
        _, _, store, server, client, device = self.make(tokens=tokens)
        original = client.session_id
        receipt = client.invoke(CAP, {}, device_id=device)
        uri = receipt["output"]["image_ref"]
        for token in (None, "invalid", "token-b"):
            other = MHSClient(InProcessTransport(server, auth_token=token))
            with self.subTest(token=token), self.assertRaises(MHSError):
                other.read_artifact(uri, session_id=original)
        client.open_session([device], capabilities=[CAP])
        with self.assertRaises(MHSError):
            client.read_artifact(uri, session_id=client.session_id)
        self.assertTrue(client.read_artifact(uri, session_id=original)["data"])
        client.close_session(original)
        with self.assertRaises(MHSError):
            client.read_artifact(uri, session_id=original)

    def test_mcp_foreign_projection_policy_hardware_and_session_renewal(self):
        _, _, store, server, client, device = self.make()
        projection, tool = self.project(client)
        _, receipt = self.capture(projection, tool)
        uri = receipt["output"]["image_ref"]
        other_client = MHSClient(server)
        other_client.hello()
        other, _ = self.project(other_client)
        self.assertIn("error", self.request(other, "resources/read", {"uri": uri}))
        projection.policy.enabled = False
        self.assertIn("error", self.request(projection, "resources/read", {"uri": uri}))
        projection.policy.enabled = True
        with patch.object(projection, "_is_hardware", return_value=True):
            self.assertIn("error", self.request(projection, "resources/read", {"uri": uri}))
        old = receipt["session_id"]
        client.close_session(old)
        self.assertIn("error", self.request(projection, "resources/read", {"uri": uri}))
        self.assertEqual(projection._owned(old).session_id, old, "reading must not silently reopen a session")
        projection._drop(old)
        projection._session_for_device(device, CAP)
        self.assertIn("error", self.request(projection, "resources/read", {"uri": uri}))

    def test_replay_keeps_reference_and_expiry_without_recapture(self):
        now = [0.0]
        state, _, store, server, client, device = self.make(store_options={"ttl_s": 1, "clock": lambda: now[0]})
        command = canonical.ulid()
        first = client.invoke(CAP, {}, device_id=device, command_id=command)
        replay = client.invoke(CAP, {}, device_id=device, command_id=command)
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["artifacts"], replay["artifacts"])
        self.assertEqual(state["subscriptions"], 1)
        now[0] = 2.0
        with self.assertRaises(MHSError):
            client.read_artifact(first["output"]["image_ref"], session_id=client.session_id)
        replay = client.invoke(CAP, {}, device_id=device, command_id=command)
        self.assertEqual(first["artifacts"], replay["artifacts"])
        self.assertEqual(state["subscriptions"], 1)

    def test_early_running_receipt_late_images_and_queued_commands_stay_separate(self):
        state, _, store, server, client, device = self.make(long_running=True)
        projection, tool = self.project(client)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = ArtifactPublisher.publish
        staged = []
        def blocked(publisher, *args, **kwargs):
            descriptor = original(publisher, *args, **kwargs)
            staged.append(descriptor)
            if len(staged) == 1:
                entered.set()
                if not release.wait(3):
                    raise AssertionError("controlled image publication was not released")
            return descriptor
        with patch.object(ArtifactPublisher, "publish", blocked):
            first_result, first = self.capture(projection, tool, deadline_ms=100)
            self.assertTrue(entered.is_set())
            self.assertIn(first["status"], ("running", "accepted"), first)
            self.assertNotIn("artifacts", first)
            frozen = copy.deepcopy(first)
            with self.assertRaises(MHSError):
                client.read_artifact(staged[0]["uri"], session_id=first["session_id"])
            state["message"] = raw_message([0,0,255,0,0,255])
            _, second = self.capture(projection, tool, deadline_ms=100)
            self.assertNotIn("artifacts", second)
            release.set()
            for receipt in (first, second):
                self.assertTrue(server._operations[receipt["operation_id"]].done.wait(2))
        finals = []
        for early in (first, second):
            response = self.request(projection, "tools/call", {"name": "mhs__operations", "arguments": {
                "operation_id": early["operation_id"], "device_id": device}})
            final = response["result"]["structuredContent"]["operations"]
            self.assertEqual(final["status"], "completed", final)
            finals.append(final)
            blob = self.request(projection, "resources/read", {"uri": final["output"]["image_ref"]})
            self.assertIn("result", blob)
        self.assertNotEqual(finals[0]["artifacts"][0]["uri"], finals[1]["artifacts"][0]["uri"])
        self.assertNotEqual(finals[0]["artifacts"][0]["digest"], finals[1]["artifacts"][0]["digest"])
        self.assertEqual(first, frozen)
        self.assertEqual(state["subscriptions"], 2)

    def test_execution_deadline_and_cancel_discard_late_frames(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                _, _, store, server, client, device = self.make(long_running=cancel, execution_ms=4000 if cancel else 100)
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)
                original = ros_images.convert_image
                def blocked(*args, **kwargs):
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("controlled converter was not released")
                    return original(*args, **kwargs)
                with patch.object(ros_images, "convert_image", side_effect=blocked):
                    early = client.invoke(CAP, {}, device_id=device, deadline_ms=100)
                    self.assertTrue(entered.is_set())
                    frozen = copy.deepcopy(dict(early))
                    operation = server._operations[early["operation_id"]]
                    if cancel:
                        operation.cancel_event.set()
                    release.set()
                    self.assertTrue(operation.done.wait(2))
                self.assertIn(operation.final_receipt["status"], ("failed", "cancelled"))
                self.assertEqual(store._grants, {})
                self.assertNotIn("artifacts", operation.final_receipt)
                self.assertEqual(dict(early), frozen)

    def test_publication_followed_by_invalid_result_is_aborted(self):
        _, _, store, server, client, device = self.make()
        original = ArtifactPublisher.publish
        def wrong_reference(publisher, *args):
            descriptor = original(publisher, *args)
            descriptor["uri"] = "mhs+artifact://foreign/01AAAAAAAAAAAAAAAAAAAAAAAA"
            return descriptor
        with patch.object(ArtifactPublisher, "publish", wrong_reference):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_unknown_receipt_contains_no_staged_grant_and_final_reconciles(self):
        _, _, store, server, client, device = self.make(execution_ms=4000)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = ArtifactPublisher.publish
        staged = []
        def blocked(publisher, *args):
            descriptor = original(publisher, *args)
            staged.append(descriptor)
            entered.set()
            if not release.wait(3):
                raise AssertionError("staged image was not released")
            return descriptor
        with patch.object(ArtifactPublisher, "publish", blocked):
            early = client.invoke(CAP, {}, device_id=device, deadline_ms=100)
            self.assertTrue(entered.is_set())
            self.assertEqual(early["status"], "unknown", early)
            frozen = copy.deepcopy(dict(early))
            self.assertNotIn("artifacts", early)
            with self.assertRaises(MHSError):
                client.read_artifact(staged[0]["uri"], session_id=client.session_id)
            release.set()
            operation = server._operations[early["operation_id"]]
            self.assertTrue(operation.done.wait(2))
        final = client.get_operation(early["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(final["x-vendor"]["reconciles"]["receipt_id"], early["receipt_id"])
        self.assertTrue(client.read_artifact(final["output"]["image_ref"], session_id=client.session_id)["data"])
        self.assertEqual(dict(early), frozen)
        self.assertTrue(verify_bundle(client.export_evidence()).valid)

    def test_evidence_recording_failure_never_activates_grant(self):
        _, _, store, server, client, device = self.make()
        record = server._record_receipt
        attempted = []
        def fail_completed(receipt):
            if receipt.get("artifacts"):
                attempted.append(receipt["artifacts"][0])
                with self.assertRaises(MHSError):
                    client.read_artifact(attempted[-1]["uri"], session_id=client.session_id)
                raise OSError("controlled evidence write failure")
            return record(receipt)
        with patch.object(server, "_record_receipt", side_effect=fail_completed):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(len(attempted), 1)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})
        with self.assertRaises(MHSError):
            client.read_artifact(attempted[0]["uri"], session_id=client.session_id)

    def test_abandoned_unknown_worker_pending_bytes_expire_without_grant(self):
        now = [0.0]
        _, _, store, server, client, device = self.make(execution_ms=4000,
            store_options={"ttl_s": 1, "clock": lambda: now[0]})
        release = threading.Event()
        self.addCleanup(release.set)
        original = ArtifactPublisher.publish
        staged = []
        def blocked(publisher, *args):
            descriptor = original(publisher, *args)
            staged.append(descriptor)
            if not release.wait(3):
                raise AssertionError("controlled publisher was not released")
            return descriptor
        with patch.object(ArtifactPublisher, "publish", blocked):
            early = client.invoke(CAP, {}, device_id=device, deadline_ms=100)
            self.assertEqual(early["status"], "unknown", early)
            now[0] = 2
            with self.assertRaises(MHSError):
                client.read_artifact(staged[0]["uri"], session_id=client.session_id)
            self.assertEqual((store._total_bytes, len(store._grants)), (0, 0))
            operation = server._operations[early["operation_id"]]
            self.assertFalse(operation.done.is_set())
            release.set()
            self.assertTrue(operation.done.wait(2))
        self.assertEqual(operation.final_receipt["status"], "failed")
        self.assertNotIn("artifacts", operation.final_receipt)

    def test_retention_failure_after_recording_still_aborts_grant(self):
        _, _, store, server, client, device = self.make()
        retain = server._retain_receipt
        attempted = []
        def fail_completed(key, digest, receipt, **kwargs):
            if receipt.get("artifacts"):
                attempted.append(receipt["artifacts"][0])
                with self.assertRaises(MHSError):
                    client.read_artifact(attempted[-1]["uri"], session_id=client.session_id)
                raise OSError("controlled retention write failure")
            return retain(key, digest, receipt, **kwargs)
        with patch.object(server, "_retain_receipt", side_effect=fail_completed):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(len(attempted), 1)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_conflicting_idempotent_input_has_no_new_grant(self):
        state, _, store, server, client, device = self.make()
        command = canonical.ulid()
        original = client.invoke(CAP, {}, device_id=device, command_id=command)
        conflict = client.invoke(CAP, {"width": 1}, device_id=device, command_id=command)
        self.assertEqual(conflict["status"], "rejected", conflict)
        self.assertNotIn("artifacts", conflict)
        self.assertEqual((state["subscriptions"], len(store._grants)), (1, 1))
        self.assertTrue(client.read_artifact(original["output"]["image_ref"], session_id=client.session_id)["data"])

    def test_stock_ros1_and_ros2_depth_keep_exact_endian_samples(self):
        for version in (1, 2):
            for endian in (0, 1):
                with self.subTest(version=version, endian=endian):
                    samples = [0, 256, 65535]
                    data = b"".join(n.to_bytes(2, "big" if endian else "little") for n in samples) + b"PAD"
                    message = raw_message(data, width=3, step=9, encoding="16UC1", endian=endian)
                    ros_type = "sensor_msgs/Image" if version == 1 else RAW
                    _, _, store, server, client, device = self.make(message, ros_type=ros_type, version=version)
                    projection, tool = self.project(client)
                    _, receipt = self.capture(projection, tool)
                    self.assertEqual(receipt["status"], "completed", receipt)
                    response = self.request(projection, "resources/read", {"uri": receipt["output"]["image_ref"]})
                    blob = base64.b64decode(response["result"]["contents"][0]["blob"])
                    self.assertEqual(png_rows(blob), b"\0\0\0\1\0\xff\xff")

    def test_old_topic_subscription_id_cannot_supply_new_image(self):
        state, native, store, server, client, device = self.make()
        first = client.invoke(CAP, {}, device_id=device)
        previous = next(item["id"] for item in native.sent if item["op"] == "subscribe")
        def respond(request):
            if request["op"] == "subscribe":
                return [{"op": "publish", "topic": "/image", "id": previous, "msg": raw_message()},
                        {"op": "publish", "topic": "/image", "id": request["id"],
                         "msg": raw_message([0, 0, 255, 0, 0, 255])}]
        native.handler = respond
        second = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(second["status"], "completed", second)
        blob = client.read_artifact(second["output"]["image_ref"], session_id=client.session_id)["data"]
        self.assertEqual(png_rows(blob), b"\0\0\0\xff\0\0\xff")

    def test_session_expiry_after_staging_aborts_before_receipt(self):
        _, _, store, server, client, device = self.make()
        original = ArtifactPublisher.publish
        def expire(publisher, *args):
            descriptor = original(publisher, *args)
            server._sessions[client.session_id].expires_at = 1
            return descriptor
        with patch.object(ArtifactPublisher, "publish", expire):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_bad_output_schema_aborts_staged_bytes(self):
        _, _, store, server, client, device = self.make()
        original = ros_images.convert_image
        def invalid_dimensions(*args, **kwargs):
            data, width, height, media = original(*args, **kwargs)
            return data, None, height, media
        with patch.object(ros_images, "convert_image", side_effect=invalid_dimensions):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_external_session_cannot_register_projection_artifact(self):
        _, _, store, server, client, device = self.make()
        receipt = client.invoke(CAP, {}, device_id=device)
        projection, _ = self.project(client)
        projection.policy.allow_external_sessions = True
        self.assertEqual(projection._register_artifacts(receipt), [])
        self.assertIn("error", self.request(projection, "resources/read", {"uri": receipt["output"]["image_ref"]}))

    def test_source_gate_rejects_image_conversion_in_reads_services_or_wrong_capability(self):
        from mhs.bridge.ros import RosBridge
        bad = [
            {"reads": {"main": {"topic": "/image", "type": RAW, "image": {}}}},
            {"commands": {CAP: {"service": "/image", "type": RAW, "operation": "read", "image": {}}}},
            {"commands": {"x-cap.test.image.v1": {"topic": "/image", "type": RAW, "operation": "subscribe", "image": {}}}},
            {"commands": {CAP: {"topic": "/image", "type": RAW, "operation": "subscribe", "image": {}, "path": "data"}}},
        ]
        for config in bad:
            with self.subTest(config=config):
                native = RecordingRosTransport()
                self.addCleanup(native.close)
                with self.assertRaises(Exception):
                    RosBridge(config, transport=native)
                self.assertEqual(native.sent, [])

    def test_cli_opt_in_passes_store_to_loader_and_closes_owned_files(self):
        from mhs import cli
        stores = []
        def load_fixture(*args, **kwargs):
            store = kwargs["artifact_store"]
            stores.append(store)
            # The launcher delegates to adapter.load normally. This focused
            # configuration test uses the same stock family/server construction.
            native = RecordingRosTransport(lambda request: {"op": "publish", "topic": "/image",
                "id": request["id"], "msg": raw_message()} if request["op"] == "subscribe" else None)
            class Camera(RosDriver):
                device_id, device_kind, mode, risk = "camera", "sensor.camera", "hardware", "R0"
                backends = {"fake": lambda: native}
                commands = {CAP: {"topic": "/image", "type": RAW, "operation": "subscribe", "image": {}}}
            return build_server(Camera(backend="fake"), artifact_store=store)
        def serve(projection):
            projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "cli-test", "version": "1"}}})
            tools = self.request(projection, "tools/list")["result"]["tools"]
            tool = next(t["name"] for t in tools if t["name"].endswith("sensing_image"))
            _, receipt = self.capture(projection, tool)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertIn("result", self.request(projection, "resources/read", {"uri": receipt["output"]["image_ref"]}))
            return 0
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            with patch("mhs.adapter.load", side_effect=load_fixture), patch("mhs.mcp.serve_stdio", side_effect=serve):
                self.assertEqual(cli.main(["serve", directory, "--mcp", "--artifacts"]), 0)
            self.assertEqual(cli.main(["serve", directory, "--stdio", "--artifacts"]), cli.EXIT_USAGE)
        self.assertEqual(len(stores), 1)
        self.assertTrue(stores[0]._closed)
        self.assertFalse(stores[0]._root.exists())

    def test_remote_transport_has_no_arbitrary_uri_fallback(self):
        class Remote:
            kind = "http"
            def request(self, *args, **kwargs):
                raise AssertionError("no remote request is defined")
            def close(self):
                pass
        client = MHSClient(transport=Remote())
        with self.assertRaises(MHSError):
            client.read_artifact("file:///private/secret", session_id="anything")

    def test_model_refuses_ros_version_mismatch_and_camera_control_claim(self):
        for type_name, action in (("sensor_msgs/Image", Action()),
                                  (RAW, Action(input={"width": Field("integer")}))):
            with self.subTest(type_name=type_name):
                class Invalid(RosDriver):
                    device_id, device_kind, mode, risk = "camera", "sensor.camera", "hardware", "R0"
                    backends = {"fake": lambda: RecordingRosTransport()}
                    commands = {CAP: {"topic": "/image", "type": type_name, "operation": "subscribe", "image": {}}}
                    actions = {CAP: action}
                with self.assertRaises(DriverDefinitionError):
                    build_server(Invalid(backend="fake"))


    def test_postcommit_notification_failure_cannot_revoke_replayed_image(self):
        _, _, store, server, client, device = self.make()
        key, sid = canonical.ulid(), client.session_id
        entered, release = threading.Event(), threading.Event()
        results = []
        original = server._notify
        def notify(*args, **kwargs):
            saved = server._receipts.get((device, key))
            if args[0] == "state" and saved and saved[1].get("artifacts"):
                entered.set()
                self.assertTrue(release.wait(2))
                raise OSError("notification failed after publication")
            return original(*args, **kwargs)
        def capture():
            results.append(client.invoke(CAP, {}, device_id=device, session_id=sid,
                                         command_id=key, deadline_ms=3000))
        worker = threading.Thread(target=capture)
        try:
            with patch.object(server, "_notify", side_effect=notify), self.assertLogs("mhs.server", level="ERROR"):
                worker.start(); self.assertTrue(entered.wait(1))
                other = MHSClient(InProcessTransport(server)); other.hello()
                replay = other.invoke(CAP, {}, device_id=device, session_id=sid, command_id=key)
                self.assertEqual(replay["status"], "completed")
                uri = replay["output"]["image_ref"]
                before = other.read_artifact(uri, session_id=sid)["data"]
                release.set(); worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results[0]["status"], "completed")
            self.assertEqual(other.read_artifact(uri, session_id=sid)["data"], before)
            self.assertTrue(store._grants)
        finally:
            release.set(); worker.join(2)

    def test_failed_artifact_commit_has_no_completed_evidence_or_grant(self):
        _, _, store, server, client, device = self.make()
        with patch.object(ArtifactPublisher, "commit", side_effect=OSError("precommit failure")):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})
        bundle = client.export_evidence()
        self.assertTrue(verify_bundle(bundle).valid)
        self.assertNotIn("mhs+artifact://", json.dumps(bundle))

    def test_precommit_evidence_retention_failure_exports_no_completed_image(self):
        for target in ("_record_receipt", "_retain_receipt"):
            with self.subTest(target=target):
                _, _, store, server, client, device = self.make()
                original = getattr(server, target)
                def fail(*args, **kwargs):
                    receipt = args[0] if target == "_record_receipt" else args[2]
                    if receipt.get("artifacts"):
                        raise OSError("controlled precommit failure")
                    return original(*args, **kwargs)
                with patch.object(server, target, side_effect=fail):
                    receipt = client.invoke(CAP, {}, device_id=device)
                self.assertEqual(receipt["status"], "failed")
                self.assertEqual(store._grants, {})
                self.assertNotIn("mhs+artifact://", json.dumps(client.export_evidence()))

    def test_evidence_export_and_blob_reads_wait_for_publication_without_blocking_estop(self):
        _, _, store, server, client, device = self.make()
        key, sid = canonical.ulid(), client.session_id
        recorded, release, exported, read_done = (threading.Event() for _ in range(4))
        receipts, bundles, blobs = [], [], []
        original = server._record_receipt
        def record(receipt):
            result = original(receipt)
            if receipt.get("artifacts"):
                recorded.set()
                self.assertTrue(release.wait(3))
            return result
        def capture():
            receipts.append(client.invoke(CAP, {}, device_id=device, session_id=sid,
                                          command_id=key, deadline_ms=4000))
        other = MHSClient(InProcessTransport(server)); other.hello()
        exporter = MHSClient(InProcessTransport(server)); exporter.hello()
        reader = MHSClient(InProcessTransport(server)); reader.hello()
        def export():
            bundles.append(exporter.export_evidence(session_id=sid)); exported.set()
        def read():
            descriptor = next(iter(store._grants.values())).descriptor
            blobs.append(reader.read_artifact(descriptor["uri"], session_id=sid)); read_done.set()
        workers = [threading.Thread(target=capture), threading.Thread(target=export), threading.Thread(target=read)]
        try:
            with patch.object(server, "_record_receipt", side_effect=record):
                workers[0].start(); self.assertTrue(recorded.wait(1))
                self.assertNotIn((device, key), server._receipts)
                workers[1].start(); workers[2].start()
                # Same-session replay sees only the existing in-flight operation.
                replay = other.invoke(CAP, {}, device_id=device, session_id=sid, command_id=key, deadline_ms=40)
                self.assertNotEqual(replay["status"], "completed")
                self.assertNotIn("artifacts", replay)
                visible = other.get_operation(replay["operation_id"], session_id=sid)
                self.assertNotEqual(visible["status"], "completed")
                self.assertNotIn("artifacts", visible)
                self.assertFalse(exported.is_set()); self.assertFalse(read_done.is_set())
                stopped = other.estop("publication lock probe", device_id=device, session_id=sid, deadline_ms=150)
                self.assertTrue(server._latched[device])
                self.assertFalse(release.is_set(), "e-stop cannot wait for artifact publication")
                release.set()
                for worker in workers: worker.join(2)
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            self.assertEqual(receipts[0]["status"], "completed")
            self.assertTrue(blobs[0]["data"])
            self.assertTrue(verify_bundle(bundles[0]).valid)
        finally:
            release.set()
            for worker in workers:
                if worker.ident is not None: worker.join(2)

    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_compressed_image_trailing_streams_are_not_publishable(self):
        import struct
        import zlib
        from mhs.bridge.ros_images import _chunk
        jpg = base64.b64decode(compressed_message("jpeg")["data"])
        png = base64.b64decode(compressed_message("png")["data"])
        def png_extra(extra):
            offset, parts, inserted = 8, [png[:8]], False
            while offset < len(png):
                length = struct.unpack_from(">I", png, offset)[0]
                kind = png[offset + 4:offset + 8]
                data = png[offset + 8:offset + 8 + length]
                if kind == b"IDAT" and not inserted:
                    data += extra; inserted = True
                parts.append(_chunk(kind, data)); offset += length + 12
            return b"".join(parts)
        for codec, payload in (("jpeg", jpg + jpg), ("jpeg", jpg + b"TAIL\xff\xd9"),
                               ("png", png_extra(b"TAIL")), ("png", png_extra(zlib.compress(b"extra")))):
            with self.subTest(codec=codec, size=len(payload)):
                _, _, store, server, client, device = self.make(
                    {"format": codec, "data": base64.b64encode(payload).decode()}, ros_type=COMPRESSED)
                projection, tool = self.project(client)
                _, receipt = self.capture(projection, tool)
                self.assertEqual(receipt["status"], "failed")
                self.assertNotIn("artifacts", receipt)
                self.assertEqual(store._grants, {})

    def test_full_size_opaque_capture_requires_explicit_bound_and_roundtrips_mcp_stdio(self):
        from mhs.driver import Driver, action, FAKE_FIDELITY
        from mhs.artifacts import publisher_from_context
        from mhs.mcp import serve_stdio, MAX_ARTIFACT_RESPONSE_BYTES
        size = 2448 * 2048 * 2
        payload = (bytes(range(256)) * ((size + 255) // 256))[:size]
        media = "application/vnd.thorlabs.tlbc2.raw16"
        class OpaqueCamera(Driver):
            device_id, device_kind, mode, risk = "opaque-camera", "sensor.camera", "simulated", "R0"
            fidelity = FAKE_FIDELITY
            backends = {"fake": lambda: object()}
            @action(cap=CAP)
            def capture(self):
                pub = publisher_from_context(self.ctx)
                descriptor = pub.publish(payload, media)
                return {"image_ref": descriptor["uri"], "width": 2448, "height": 2048, "media_type": media}
        for ceiling in (None, size):
            with self.subTest(ceiling=ceiling):
                store = LocalArtifactStore(**({} if ceiling is None else {"max_artifact_bytes": ceiling}))
                server = build_server(OpaqueCamera(), artifact_store=store)
                self.addCleanup(close_server, server)
                client = MHSClient(InProcessTransport(server)); client.hello()
                projection, tool = self.project(client)
                _, receipt = self.capture(projection, tool)
                if ceiling is None:
                    self.assertEqual(receipt["status"], "failed")
                    self.assertEqual(store._grants, {})
                    continue
                self.assertEqual(receipt["status"], "completed", receipt)
                uri = receipt["output"]["image_ref"]
                sid = receipt["session_id"]
                self.assertEqual(client.read_artifact(uri, session_id=sid)["data"], payload)
                response = self.request(projection, "resources/read", {"uri": uri})
                self.assertEqual(response["result"]["contents"][0]["mimeType"], media)
                blob = base64.b64decode(response["result"]["contents"][0]["blob"])
                self.assertEqual(blob, payload)
                request = {"jsonrpc": "2.0", "id": "large", "method": "resources/read", "params": {"uri": uri}}
                output = io.BytesIO()
                serve_stdio(projection, stdin=io.BytesIO((json.dumps(request) + "\n").encode()), stdout=output)
                wire = output.getvalue()
                self.assertGreater(len(wire), MAX_FRAME_BYTES)
                self.assertLessEqual(len(wire), MAX_ARTIFACT_RESPONSE_BYTES)
                result = json.loads(wire)
                self.assertEqual(base64.b64decode(result["result"]["contents"][0]["blob"]), payload)

    def test_large_artifact_option_does_not_raise_ordinary_or_inbound_mcp_limit(self):
        from mhs.mcp import serve_stdio
        _, _, store, server, client, device = self.make(store_options={"max_artifact_bytes": 16 * 1024 * 1024})
        projection, _ = self.project(client)
        output = io.BytesIO()
        with patch.object(projection, "handle_message", return_value={"jsonrpc": "2.0", "id": 1,
                         "result": {"text": "a" * (MAX_FRAME_BYTES + 1)}}):
            serve_stdio(projection, stdin=io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'), stdout=output)
        self.assertIn("error", json.loads(output.getvalue()))
        client = MHSClient(InProcessTransport(server)); client.hello()
        projection, _ = self.project(client)
        output = io.BytesIO()
        request = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {"oversize": "a" * MAX_FRAME_BYTES}}
        with patch.object(projection, "handle_message", wraps=projection.handle_message) as handle:
            serve_stdio(projection, stdin=io.BytesIO((json.dumps(request) + "\n").encode()), stdout=output)
        self.assertEqual(handle.call_count, 0)
        self.assertIn("error", json.loads(output.getvalue()))

    def test_postcommit_journal_failure_keeps_grant_and_releases_reservation(self):
        _, _, store, server, client, device = self.make()
        key = canonical.ulid()
        with patch.object(server, "_journal_retained_receipt", side_effect=OSError("journal failed")), \
                self.assertLogs("mhs.server", level="ERROR"):
            receipt = client.invoke(CAP, {}, device_id=device, command_id=key)
        self.assertEqual(receipt["status"], "completed")
        self.assertNotIn((device, key), server._inflight)
        self.assertTrue(client.read_artifact(receipt["output"]["image_ref"], session_id=client.session_id)["data"])

    def test_safe_action_and_catalog_stop_finish_while_image_publication_is_held(self):
        for stop_cap in ("x-cap.test.stop.v1", "cap.motion.stop.v1"):
            with self.subTest(capability=stop_cap):
                sent, entered, release, finished = (threading.Event() for _ in range(4))
                results = {}
                def respond(request):
                    if request["op"] == "subscribe":
                        return {"op": "publish", "topic": "/image", "id": request["id"], "msg": raw_message()}
                    if request["op"] == "call_service":
                        self.assertEqual(request["service"], "/stop")
                        sent.set()
                        return {"op": "service_response", "service": "/stop", "id": request["id"],
                                "result": True, "values": {"success": True, "stopped": True}}
                stop_binding = {"service": "/stop", "type": "test/srv/Stop",
                                "success": {"path": "success", "equals": True},
                                "source_ref": "controlled_peer.py:1", "type_ref": "controlled_peer.py:1"}
                class Camera(RosDriver):
                    device_id, device_kind, mode, risk = "camera", "sensor.camera", "hardware", "R0"
                    backends = {"fake": lambda: RecordingRosTransport(respond)}
                    commands = {CAP: {"topic": "/image", "type": RAW, "operation": "subscribe", "image": {}}}
                class Stop(RosDriver):
                    device_id, device_kind, mode, risk = "axis", "motion.axis", "hardware", "R1"
                    backends = {"fake": lambda: RecordingRosTransport(respond)}
                    commands = {stop_cap: {**stop_binding, "result": {"map": {"stopped": "output.stopped"}}}}
                    actions = {stop_cap: (Action(name="stop", safe_state=True,
                                                 output={"stopped": Field("boolean")})
                                          if stop_cap.startswith("x-") else Action(name="stop"))}
                    safety_bindings = {"estop": stop_binding}
                    safe_state = "Controlled acknowledged stop; no hardware execution"
                # Extension safe-state uses the same bridge/device as capture;
                # the catalogued stop uses its proper motion-axis device kind.
                if stop_cap.startswith("x-"):
                    Camera.commands = {**Camera.commands, **Stop.commands}
                    Camera.actions = Stop.actions
                    Camera.safety_bindings = Stop.safety_bindings
                    Camera.safe_state = Stop.safe_state
                    drivers = [Camera(backend="fake")]
                else:
                    drivers = [Camera(backend="fake"), Stop(backend="fake")]
                store = LocalArtifactStore()
                server = build_server(drivers, artifact_store=store)
                self.addCleanup(close_server, server)
                client = MHSClient(InProcessTransport(server)); client.hello()
                devices = list(server.devices)
                camera_device = next(d for d in devices if "/camera" in d)
                stop_device = camera_device if stop_cap.startswith("x-") else next(d for d in devices if "/axis" in d)
                sid = client.open_session(devices)["session_id"]
                original = server._record_receipt
                def record(receipt):
                    value = original(receipt)
                    if receipt.get("artifacts"):
                        entered.set()
                        self.assertTrue(release.wait(3))
                    return value
                def capture():
                    results["capture"] = client.invoke(CAP, {}, device_id=camera_device, session_id=sid,
                                                        deadline_ms=4000)
                def stop():
                    try:
                        results["stop"] = client.invoke(stop_cap, {}, device_id=stop_device, session_id=sid,
                                                       deadline_ms=2000)
                    finally:
                        finished.set()
                workers = [threading.Thread(target=capture), threading.Thread(target=stop)]
                try:
                    with patch.object(server, "_record_receipt", side_effect=record):
                        workers[0].start(); self.assertTrue(entered.wait(1))
                        workers[1].start()
                        self.assertTrue(sent.wait(1), "native /stop dispatch waited for artifact storage")
                        self.assertTrue(finished.wait(1), "empty publisher cleanup delayed stop completion")
                        stopped = results["stop"]
                        self.assertEqual(stopped["status"], "completed", stopped)
                        self.assertTrue(server._operations[stopped["operation_id"]].done.is_set())
                        self.assertFalse(release.is_set())
                        self.assertTrue(workers[0].is_alive())
                        release.set()
                        for worker in workers: worker.join(2)
                    self.assertEqual(results["capture"]["status"], "completed")
                finally:
                    release.set()
                    for worker in workers:
                        if worker.ident is not None: worker.join(2)
