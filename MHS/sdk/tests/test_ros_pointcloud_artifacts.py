"""Complete binary PointCloud2 data through the stock loader, server and MCP."""
from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from mhs import canonical
from mhs.adapter import load
from mhs.artifacts import ArtifactPublisher, LocalArtifactStore
from mhs.bridge import ros_pointcloud
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import DriverDefinitionError, close_server
from mhs.errors import MHSError
from mhs.evidence import verify_bundle
from mhs.mcp import MAX_ARTIFACT_RESPONSE_BYTES, MAX_FRAME_BYTES, MCPPolicy, MCPProjection, serve_stdio
from mhs.schema.store import default_store

CAP = "cap.sensing.point_cloud.v1"


def cloud(version=2, big=False):
    """Independent explicit Ouster-shaped layout, with point and row padding."""
    fields = [("x", 0, 7), ("y", 4, 7), ("z", 8, 7), ("intensity", 16, 7),
              ("t", 20, 6), ("reflectivity", 24, 4), ("ring", 26, 2),
              ("ambient", 28, 4), ("range", 32, 6)]
    data = bytearray(b"\xa5" * (152 * 2))
    endian = ">" if big else "<"
    for row in range(2):
        for col in range(3):
            i = row * 3 + col
            offset = row * 152 + col * 48
            for location, value in [(0, i + .5), (4, -i - .25), (8, i * 2.5), (16, i * 11.25)]:
                struct.pack_into(endian + "f", data, offset + location, value)
            struct.pack_into(endian + "I", data, offset + 20, 100_000 + i)
            struct.pack_into(endian + "H", data, offset + 24, 500 + i)
            struct.pack_into("B", data, offset + 26, i)
            struct.pack_into(endian + "H", data, offset + 28, 65_000 - i)
            struct.pack_into(endian + "I", data, offset + 32, 4000 + i)
    # Keep a specific NaN payload and negative-zero bit pattern; never normalize.
    struct.pack_into(endian + "I", data, 0, 0x7FC01234)
    struct.pack_into(endian + "I", data, 4, 0x80000000)
    header = {"stamp": {"secs": 17, "nsecs": 456789012}, "seq": 43} if version == 1 else {
        "stamp": {"sec": -17, "nanosec": 456789012}}
    header["frame_id"] = "laser_data_frame"
    return {"header": header, "width": 3, "height": 2,
            "fields": [{"name": n, "offset": o, "datatype": t, "count": 1} for n, o, t in fields],
            "is_bigendian": big, "point_step": 48, "row_step": 152,
            "is_dense": False, "data": base64.b64encode(data).decode("ascii")}, bytes(data)


def unpack(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if archive.namelist() != ["pointcloud.json", "data.bin"]:
            raise AssertionError("unexpected artifact members")
        if any(info.compress_type != zipfile.ZIP_STORED for info in archive.infolist()):
            raise AssertionError("point data must not depend on a decompressor")
        if archive.testzip() is not None:
            raise AssertionError("invalid archive CRC")
        return json.loads(archive.read("pointcloud.json")), archive.read("data.bin")


class RosPointCloudArtifactTests(unittest.TestCase):
    def make(self, *, version=2, message=None, big=False, store_options=None,
             with_store=True, commands=None, tokens=None, handler=None,
             long_running=False, execution_ms=3000, max_message_bytes=1_048_576):
        sample, expected = cloud(version, big)
        state = {"message": sample if message is None else message, "subscriptions": 0}
        def respond(request):
            if request["op"] == "subscribe":
                state["subscriptions"] += 1
                if handler:
                    return handler(request, state)
                return {"op": "publish", "topic": request["topic"], "id": request["id"],
                        "msg": copy.deepcopy(state["message"])}
            return None
        transport = RecordingRosTransport(respond, max_message_bytes=max_message_bytes)
        self.addCleanup(transport.close)
        directory = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="mhs-cloud-")))
        ros_type = "sensor_msgs/" + ("msg/" if version == 2 else "") + "PointCloud2"
        commands = commands if commands is not None else {CAP: {"topic": "/points", "type": ros_type,
                    "operation": "subscribe", "point_cloud": {"max_input_bytes": 16 * 1024 * 1024}}}
        (directory / "driver.py").write_text(
            'from mhs.driver import Action, RosDriver\n'
            'class Cloud(RosDriver):\n'
            '    device_id, device_kind, mode, risk = "cloud", "sensor.depth", "hardware", "R0"\n'
            f'    ros_version = {version}\n'
            f'    max_message_bytes = {max_message_bytes}\n'
            f'    commands = {commands!r}\n'
            f'    actions = {{{CAP!r}: Action(name="capture", max_duration_ms={execution_ms}, '
            f'long_running={long_running}, cancellable={long_running})}}\n')
        store = LocalArtifactStore(**(store_options or {})) if with_store else None
        if store:
            self.addCleanup(store.close)
        server = load(directory, backend="fake", native=transport, artifact_store=store, auth_tokens=tokens)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token="token-a" if tokens else None))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], capabilities=[CAP])
        return state, expected, transport, store, server, client, device

    def request(self, projection, method, params=None):
        return projection.handle_message({"jsonrpc": "2.0", "id": canonical.ulid(),
                                          "method": method, "params": params or {}})

    def projection(self, client):
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)
        self.assertIn("result", self.request(projection, "initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "pointcloud-test", "version": "1"}}))
        tools = self.request(projection, "tools/list")["result"]["tools"]
        return projection, next(tool["name"] for tool in tools if tool["name"].endswith("sensing_point_cloud"))

    def test_complete_binary_fields_padding_endianness_and_headers_through_mcp(self):
        for version in (1, 2):
            for big in (False, True):
                with self.subTest(version=version, big=big):
                    state, expected, _, _, _, client, _ = self.make(version=version, big=big)
                    projection, name = self.projection(client)
                    result = self.request(projection, "tools/call", {"name": name, "arguments": {}})["result"]
                    receipt = result["structuredContent"]["receipt"]
                    self.assertEqual(receipt["status"], "completed", receipt)
                    self.assertEqual(default_store().validate(dict(receipt), "receipt.schema.json"), [])
                    self.assertEqual(receipt["output"]["point_count"], 6)
                    descriptor = receipt["artifacts"][0]
                    self.assertEqual(descriptor["media_type"], "application/zip")
                    blob = base64.b64decode(self.request(projection, "resources/read", {
                        "uri": descriptor["uri"]})["result"]["contents"][0]["blob"], validate=True)
                    manifest, data = unpack(blob)
                    self.assertEqual(data, expected)
                    self.assertEqual(manifest["data_sha256"], hashlib.sha256(expected).hexdigest())
                    for key in set(state["message"]) - {"data"}:
                        self.assertEqual(manifest[key], state["message"][key], key)
                    self.assertEqual(manifest["format"], "openmhs.ros-pointcloud2.v1")
                    self.assertEqual(descriptor["x-vendor"]["openmhs.ros_point_cloud"]["header"], manifest["header"])
                    self.assertEqual(descriptor["digest"], "sha256:" + hashlib.sha256(blob).hexdigest())
                    self.assertEqual(descriptor["size_bytes"], len(blob))
                    self.assertTrue(verify_bundle(client.export_evidence()).valid)
                    self.assertEqual(state["subscriptions"], 1)

    def test_all_pointfield_types_counts_and_overlapping_views_preserve_bytes(self):
        message, _ = cloud()
        fields, offset = [], 0
        for datatype, size in enumerate((1, 1, 2, 2, 4, 4, 4, 8), 1):
            fields.append({"name": "kind_" + str(datatype), "offset": offset, "datatype": datatype, "count": 2})
            offset += size * 2
        fields.append({"name": "shared_bytes", "offset": 0, "datatype": 2, "count": 2})
        data = bytes(range(offset))
        message.update(width=1, height=1, fields=fields, point_step=offset, row_step=offset, data=list(data))
        _, _, _, _, _, client, device = self.make(message=message)
        receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        manifest, restored = unpack(client.read_artifact(receipt["output"]["artifact_ref"], session_id=receipt["session_id"])["data"])
        self.assertEqual(restored, data)
        self.assertEqual(manifest["fields"], fields)

    def test_empty_default_and_filtered_clouds_are_explicit_zero_count(self):
        for default in (False, True):
            message, _ = cloud()
            message.update(width=0, height=0 if default else 1, row_step=0, data=[])
            if default:
                message.update(point_step=0, fields=[])
            _, _, _, _, _, client, device = self.make(message=message)
            receipt = client.invoke(CAP, {}, device_id=device)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"]["point_count"], 0)
            manifest, data = unpack(client.read_artifact(receipt["output"]["artifact_ref"], session_id=receipt["session_id"])["data"])
            self.assertEqual(data, b"")
            self.assertEqual(manifest["height"], message["height"])

    def test_all_primary_layout_failures_leave_no_grant(self):
        state, _, _, store, _, client, device = self.make()
        original = copy.deepcopy(state["message"])
        changes = [{"width": True}, {"height": -1}, {"width": 2 ** 32}, {"point_step": 0},
                   {"row_step": 143}, {"row_step": 153}, {"data": "AAAA"}, {"data": [True] * 304},
                   {"is_dense": 1}, {"is_bigendian": 0}, {"fields": []}, {"unexpected": 1},
                   {"width": 0}, {"height": 0}, {"data": original["data"] + "="},
                   {"header": {"stamp": {"secs": 17, "nsecs": 1}, "frame_id": "wrong-version"}}]
        for field in ({"datatype": 9}, {"datatype": True}, {"count": 0}, {"count": 100},
                      {"offset": 47}, {"offset": -1}, {"name": "bad\x00field"}, {"name": "a" * 129}):
            fields = copy.deepcopy(original["fields"])
            fields[0].update(field)
            changes.append({"fields": fields})
        changes.append({"fields": original["fields"] + [original["fields"][0]]})
        for change in changes:
            with self.subTest(change=change):
                state["message"] = {**original, **change}
                receipt = client.invoke(CAP, {}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertNotIn("artifacts", receipt)
                self.assertIsNone(receipt["output"])
                self.assertEqual(store._grants, {})
                self.assertEqual(store._total_bytes, 0)

    def test_closed_controls_and_missing_store_refuse_before_any_subscription(self):
        _, _, native, _, _, client, device = self.make()
        for arguments in ({"frame": "map"}, {"min_range": 0}, {"max_range": 5}, {"max_points": 1},
                          {"topic": "/elsewhere"}, {"fields": ["x", "y", "z"]}):
            receipt = client.invoke(CAP, arguments, device_id=device)
            self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(native.sent, [])
        _, _, native, _, _, client, device = self.make(with_store=False)
        self.assertEqual(client.invoke(CAP, {}, device_id=device)["status"], "failed")
        self.assertEqual(native.sent, [])

    def test_wrong_profiles_and_ambiguous_declarations_refuse_before_wire(self):
        base = {"topic": "/points", "type": "sensor_msgs/msg/PointCloud2", "operation": "subscribe", "point_cloud": {}}
        cases = [{"type": "sensor_msgs/msg/Image"}, {"operation": "publish"}, {"image": {}},
                 {"args": {}}, {"result": {}}, {"message": {}}, {"path": "data"}, {"safe_state": True},
                 {"point_cloud": {"max_input_bytes": True}}, {"point_cloud": {"max_fields": 129}},
                 {"point_cloud": {"max_points": 0}}, {"point_cloud": {"unknown": 1}}]
        for change in cases:
            with self.subTest(change=change):
                native = RecordingRosTransport()
                self.addCleanup(native.close)
                with self.assertRaises(MHSError):
                    RosBridge({"commands": {CAP: {**base, **change}}}, transport=native)
                self.assertEqual(native.sent, [])
        with self.assertRaises(DriverDefinitionError):
            self.make(version=1, commands={CAP: base})
        with self.assertRaises(MHSError):
            RosBridge({"commands": {"cap.sensing.image.v1": base}}, transport=RecordingRosTransport())

    def test_long_frame_remains_complete_in_artifact_without_invalid_short_output_field(self):
        message, _ = cloud()
        message["header"]["frame_id"] = "f" * 200
        _, _, _, _, _, client, device = self.make(message=message)
        receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertNotIn("frame", receipt["output"])
        manifest, _ = unpack(client.read_artifact(receipt["output"]["artifact_ref"], session_id=receipt["session_id"])["data"])
        self.assertEqual(manifest["header"], message["header"])

    def test_exact_size_limits_before_publication_and_no_capacity_leak(self):
        message, _ = cloud()
        config = ros_pointcloud.pointcloud_config({}, "sensor_msgs/msg/PointCloud2")
        blob, _, _, _ = ros_pointcloud.convert_pointcloud(message, "sensor_msgs/msg/PointCloud2", config,
                                                         topic="/points", max_output_bytes=2 * 1024 * 1024)
        for limit, status in [(len(blob) - 1, "failed"), (len(blob), "completed")]:
            _, _, _, store, _, client, device = self.make(store_options={"max_artifact_bytes": limit})
            receipt = client.invoke(CAP, {}, device_id=device)
            self.assertEqual(receipt["status"], status, receipt)
            self.assertEqual(len(store._grants), status == "completed")
        _, _, _, store, _, client, device = self.make(store_options={"max_artifacts": 1})
        self.assertEqual(client.invoke(CAP, {}, device_id=device)["status"], "completed")
        receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(len(store._grants), 1)

    def test_replay_expiry_authorization_and_detached_metadata(self):
        now = [0.0]
        tokens = {"token-a": {"id": "alice", "kind": "agent"}, "token-b": {"id": "bob", "kind": "agent"}}
        state, _, _, store, server, client, device = self.make(tokens=tokens,
            store_options={"ttl_s": 1, "clock": lambda: now[0]})
        key = canonical.ulid()
        first = client.invoke(CAP, {}, device_id=device, command_id=key)
        descriptor = copy.deepcopy(first["artifacts"][0])
        data = client.read_artifact(descriptor["uri"], session_id=first["session_id"])["data"]
        state["message"]["header"]["frame_id"] = "later-source"
        first["artifacts"][0]["x-vendor"].clear()
        replay = client.invoke(CAP, {}, device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["artifacts"], [descriptor])
        self.assertEqual(client.read_artifact(descriptor["uri"], session_id=first["session_id"])["data"], data)
        client.open_session([device], capabilities=[CAP])
        with self.assertRaises(MHSError):
            client.read_artifact(descriptor["uri"], session_id=client.session_id)
        other = MHSClient(InProcessTransport(server, auth_token="token-b")); other.hello()
        with self.assertRaises(MHSError):
            other.read_artifact(descriptor["uri"], session_id=first["session_id"])
        now[0] = 2
        with self.assertRaises(MHSError):
            client.read_artifact(descriptor["uri"], session_id=first["session_id"])
        self.assertEqual(state["subscriptions"], 1)
        root = store._root
        close_server(server)
        self.assertFalse(root.exists())

    def test_stop_cancel_deadline_and_close_discard_late_conversion(self):
        for interrupt in ("stop", "cancel", "deadline", "close"):
            with self.subTest(interrupt=interrupt):
                _, _, _, store, server, client, device = self.make(
                    execution_ms=100 if interrupt == "deadline" else 2500,
                    long_running=interrupt == "cancel")
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)
                original = ros_pointcloud.convert_pointcloud
                def blocked(*args, **kwargs):
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("conversion barrier not released")
                    return original(*args, **kwargs)
                # Explicit server.close ends evidence recording immediately.
                # That branch proves worker retirement/no grants, not a final
                # recorded receipt after the evidence log has been closed.
                close_logs = self.assertLogs("mhs.server", level="ERROR") if interrupt == "close" else contextlib.nullcontext()
                with close_logs, patch.object(ros_pointcloud, "convert_pointcloud", side_effect=blocked):
                    early = client.invoke(CAP, {}, device_id=device, deadline_ms=100)
                    self.assertTrue(entered.is_set(), early)
                    self.assertNotIn("artifacts", early)
                    operation = server._operations[early["operation_id"]]
                    if interrupt == "stop":
                        client.estop("controlled conversion barrier", device_id=device, deadline_ms=100)
                    elif interrupt == "cancel":
                        client.cancel(early["operation_id"], deadline_ms=50)
                    elif interrupt == "close":
                        close_server(server)
                    release.set()
                    self.assertTrue(operation.done.wait(2))
                if operation.final_receipt is not None:
                    self.assertNotIn(operation.final_receipt["status"], ("completed", "running"))
                    self.assertNotIn("artifacts", operation.final_receipt)
                else:
                    self.assertEqual(interrupt, "close")
                    self.assertEqual(operation.state, "failed")
                self.assertEqual(store._grants, {})

    def test_commit_failure_removes_staged_bytes_and_grant(self):
        _, _, _, store, _, client, device = self.make()
        with patch.object(ArtifactPublisher, "commit", side_effect=RuntimeError("controlled commit failure")):
            receipt = client.invoke(CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})
        self.assertEqual(store._total_bytes, 0)

    def test_source_sized_cloud_keeps_all_bytes_with_explicit_budgets(self):
        message, _ = cloud()
        # A controlled 128 x 2048 layout using the explicit 48-byte test stride;
        # this does not claim that an unexecuted PCL runtime has this ABI size.
        raw = random.Random(20261104).randbytes(128 * 2048 * 48)
        message.update(width=2048, height=128, row_step=2048 * 48,
                       data=base64.b64encode(raw).decode("ascii"))
        _, _, _, _, _, client, device = self.make(message=message, execution_ms=15000,
            max_message_bytes=24 * 1024 * 1024, store_options={"max_artifact_bytes": 16 * 1024 * 1024})
        projection, name = self.projection(client)
        result = self.request(projection, "tools/call", {"name": name, "arguments": {"deadline_ms": 20000}})["result"]
        receipt = result["structuredContent"]["receipt"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["point_count"], 128 * 2048)
        response = self.request(projection, "resources/read", {"uri": receipt["output"]["artifact_ref"]})
        blob = base64.b64decode(response["result"]["contents"][0]["blob"], validate=True)
        manifest, restored = unpack(blob)
        self.assertEqual(restored, raw)
        self.assertEqual(manifest["fields"], message["fields"])
        request = {"jsonrpc": "2.0", "id": "large-cloud", "method": "resources/read",
                   "params": {"uri": receipt["output"]["artifact_ref"]}}
        output = io.BytesIO()
        serve_stdio(projection, stdin=io.BytesIO((json.dumps(request) + "\n").encode()), stdout=output)
        wire = output.getvalue()
        self.assertGreater(len(wire), MAX_FRAME_BYTES)
        self.assertLessEqual(len(wire), MAX_ARTIFACT_RESPONSE_BYTES)
        self.assertEqual(base64.b64decode(json.loads(wire)["result"]["contents"][0]["blob"],
                                         validate=True), blob)
        _, _, _, store, _, client, device = self.make(message=message, execution_ms=15000,
            max_message_bytes=24 * 1024 * 1024)
        receipt = client.invoke(CAP, {}, device_id=device, deadline_ms=20000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})


if __name__ == "__main__":
    unittest.main()
