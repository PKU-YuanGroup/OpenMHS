"""Finite declared image sources via the ordinary single-class loader and MCP."""
from __future__ import annotations

import base64
import copy
import json
import io
import random
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch

from mhs import canonical
from mhs.bridge import ros_images
from mhs.bridge.ros import RosBridge
from mhs.errors import MHSError
from mhs.evidence import verify_bundle
from mhs.driver import DriverDefinitionError
import unittest

from mhs.adapter import load
from mhs.artifacts import LocalArtifactStore
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from tests.bridges.test_ros_images import raw_message, png_rows, compressed_message, Image
from tests import test_ros_image_artifacts as image_support

CAP = "cap.sensing.image.v1"


def frames(version=1):
    samples = {
        "color": raw_message([1, 2, 3, 41, 42, 43, 99, 98] * 2, encoding="bgr8", height=2, step=8),
        "depth": raw_message(b"\x00\x00\x00\x01\xff\xffPAD", encoding="16UC1", width=3, step=9),
        "ir": raw_message(b"\x00\x01\x03\xe8\xff\xfePAD", encoding="16UC1", width=3, step=9, endian=1),
    }
    expected = {"color": (b"\0" + bytes([3, 2, 1, 43, 42, 41])) * 2,
                "depth": b"\0\x00\x00\x01\x00\xff\xff", "ir": b"\0\x00\x01\x03\xe8\xff\xfe"}
    for index, (name, sample) in enumerate(samples.items()):
        sample["header"] = ({"seq": 17 + index, "stamp": {"secs": 1 + index, "nsecs": 23456789 + index}}
                            if version == 1 else {"stamp": {"sec": -1 + index, "nanosec": 23456789 + index}})
        sample["header"]["frame_id"] = name + "_optical_frame"
    return samples, expected


def declaration(version=1):
    return {CAP: {"cameras": {name: {"topic": "/camera/" + name,
            "type": "sensor_msgs/" + ("msg/" if version == 2 else "") + "Image",
            "operation": "subscribe", "image": {}} for name in ("color", "depth", "ir")}}}


class RosMultiImageArtifactTests(unittest.TestCase):
    project = image_support.RosImageArtifactTests.project
    request = image_support.RosImageArtifactTests.request
    capture = image_support.RosImageArtifactTests.capture

    def make(self, *, version=1, commands=None, store_options=None, handler=None, tokens=None, execution_ms=2000, long_running=False, max_message_bytes=1048576):
        samples, expected = frames(version)
        state = {"samples": samples, "subscriptions": []}
        def respond(request):
            if request["op"] == "subscribe":
                name = request["topic"].rsplit("/", 1)[1]
                state["subscriptions"].append(name)
                if handler is not None:
                    return handler(request, state)
                return {"op": "publish", "topic": request["topic"], "id": request["id"],
                        "msg": copy.deepcopy(state["samples"][name])}
            return None
        transport = RecordingRosTransport(respond, max_message_bytes=max_message_bytes)
        self.addCleanup(transport.close)
        directory = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="mhs-multi-image-")))
        commands = declaration(version) if commands is None else commands
        (directory / "driver.py").write_text(
            'from mhs.driver import Action, RosDriver\n'
            'class Camera(RosDriver):\n'
            '    device_id, device_kind, mode, risk = "multi-camera", "sensor.camera", "hardware", "R0"\n'
            f'    ros_version = {version}\n'
            f'    max_message_bytes = {max_message_bytes}\n'
            f'    commands = {commands!r}\n'
            f'    actions = {{ {CAP!r}: Action(name="capture", max_duration_ms={execution_ms}, long_running={long_running}, cancellable={long_running}) }}\n')
        store = LocalArtifactStore(**(store_options or {}))
        self.addCleanup(store.close)
        server = load(directory, backend="fake", native=transport, artifact_store=store, auth_tokens=tokens)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token="token-a" if tokens else None))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], capabilities=[CAP])
        return state, expected, transport, store, server, client, device

    def test_one_loaded_class_preserves_three_complete_planes_and_exact_headers(self):
        for version in (1, 2):
            with self.subTest(version=version):
                state, expected, native, store, server, client, device = self.make(version=version)
                projection, tool = self.project(client)
                for name in ("ir", "color", "depth"):
                    _, receipt = self.capture(projection, tool, camera=name)
                    self.assertEqual(receipt["status"], "completed", receipt)
                    self.assertEqual(set(receipt["output"]), {"image_ref", "width", "height", "media_type"})
                    descriptor = receipt["artifacts"][0]
                    metadata = descriptor["x-vendor"]["openmhs.ros_image"]
                    self.assertEqual(metadata, {"camera": name, "topic": "/camera/" + name,
                        "type": "sensor_msgs/" + ("msg/" if version == 2 else "") + "Image",
                        "ros_version": version, "header": state["samples"][name]["header"]})
                    response = self.request(projection, "resources/read", {"uri": descriptor["uri"]})
                    blob = base64.b64decode(response["result"]["contents"][0]["blob"], validate=True)
                    self.assertEqual(png_rows(blob), expected[name])
                self.assertEqual(state["subscriptions"], ["ir", "color", "depth"])
                self.assertEqual(len(server.devices), 1)

    def test_selector_schema_rejects_missing_unknown_and_arbitrary_controls_before_wire(self):
        _, _, native, store, _, client, device = self.make()
        for args in ({}, {"camera": "elsewhere"}, {"camera": True}, {"camera": "/camera/color"},
                     {"camera": "color", "topic": "/arbitrary"}, {"camera": "color", "width": 1},
                     {"camera": "color", "exposure_ms": 2}, {"camera": ["color", "depth"]}):
            with self.subTest(args=args):
                receipt = client.invoke(CAP, args, device_id=device)
                self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(native.sent, [])
        self.assertEqual(store._grants, {})

    def test_finite_declarations_reject_unsafe_and_ambiguous_topologies_before_wire(self):
        source = declaration()[CAP]["cameras"]["color"]
        cases = [{}, {str(i): source for i in range(17)}, {"a" * 65: source}, {"/topic": source},
                 {"color": {**source, "resource": "other"}}, {"color": {**source, "operation": "publish"}},
                 {"color": {**source, "result": {"map": {"header": "output.header"}}}},
                 {"color": {**source, "message": {}}}, {"color": {**source, "args": {}}},
                 {"color": {**source, "safe_state": True}},
                 {"color": {**source, "topic": "/" + "x" * 513}},
                 {"color": {**source, "cameras": {"nested": source}}},
                 {"color": {key: value for key, value in source.items() if key != "image"}}]
        for sources in cases:
            with self.subTest(sources=sources):
                native = RecordingRosTransport()
                with self.assertRaises(MHSError):
                    RosBridge({"commands": {CAP: {"cameras": sources}}}, transport=native)
                self.assertEqual(native.sent, [])
                native.close()
        for override in ({"safe_state": True}, {"args": {}}, {"topic": "/other"}, {"image": {}}):
            with self.subTest(override=override), self.assertRaises(DriverDefinitionError):
                self.make(commands={CAP: {**declaration()[CAP], **override}})
        with self.assertRaises(DriverDefinitionError):
            self.make(version=2, commands=declaration(1))
        with self.assertRaises(DriverDefinitionError):
            self.make(commands={"x-cap.test.image.v1": declaration()[CAP]})

    def test_malformed_and_wrong_profile_headers_never_publish(self):
        for version in (1, 2):
            state, _, _, store, _, client, device = self.make(version=version)
            base = copy.deepcopy(state["samples"]["color"]["header"])
            sec, nsec = ("secs", "nsecs") if version == 1 else ("sec", "nanosec")
            headers = [None, {}, {**base, "extra": 1}, {**base, "frame_id": "x" * 257},
                       {**base, "frame_id": "é" * 129}, {**base, "frame_id": "bad\x00frame"},
                       {**base, "frame_id": 1}, {**base, "stamp": {sec: 1}},
                       {**base, "stamp": {sec: True, nsec: 1}},
                       {**base, "stamp": {sec: 1, nsec: 1.0}},
                       {**base, "stamp": {sec: 1, nsec: 1000000000}},
                       {**base, "stamp": {sec: 1, nsec: -1}},
                       {**base, "stamp": {sec: 2 ** 32, nsec: 0}},
                       {**base, "stamp": {sec: -(2 ** 31) - 1, nsec: 0}},
                       frames(3 - version)[0]["color"]["header"]]
            if version == 1:
                headers += [{**base, "seq": True}, {**base, "seq": -1}, {**base, "seq": 2 ** 32},
                            {key: value for key, value in base.items() if key != "seq"}]
            for header in headers:
                with self.subTest(version=version, header=header):
                    state["samples"]["color"]["header"] = header
                    receipt = client.invoke(CAP, {"camera": "color"}, device_id=device)
                    self.assertEqual(receipt["status"], "failed", receipt)
                    self.assertIsNone(receipt["output"])
                    self.assertNotIn("artifacts", receipt)
                    self.assertEqual(store._grants, {})
                    self.assertEqual(store._total_bytes, 0)
            state["samples"]["color"]["header"] = base
            receipt = client.invoke(CAP, {"camera": "color"}, device_id=device)
            self.assertEqual(receipt["status"], "completed", receipt)

    def test_header_boundaries_preserve_exact_values_without_age_or_synchronization_claim(self):
        for version in (1, 2):
            state, _, _, _, _, client, device = self.make(version=version)
            sec, nsec = ("secs", "nsecs") if version == 1 else ("sec", "nanosec")
            for seconds in ((0, 2 ** 32 - 1) if version == 1 else (-(2 ** 31), 2 ** 31 - 1)):
                header = {"stamp": {sec: seconds, nsec: 999999999}, "frame_id": "é" * 128}
                if version == 1:
                    header["seq"] = 2 ** 32 - 1
                state["samples"]["depth"]["header"] = header
                receipt = client.invoke(CAP, {"camera": "depth"}, device_id=device)
                self.assertEqual(receipt["status"], "completed", receipt)
                metadata = receipt["artifacts"][0]["x-vendor"]["openmhs.ros_image"]
                self.assertEqual(metadata["header"], header)
                self.assertEqual(set(metadata), {"camera", "topic", "type", "ros_version", "header"})

    def test_interleaved_delayed_packets_cannot_exchange_pixels_or_headers(self):
        entered = {name: threading.Event() for name in ("color", "depth")}
        requests, results = {}, {}
        def handler(request, state):
            name = request["topic"].rsplit("/", 1)[1]
            requests[name] = copy.deepcopy(request)
            entered[name].set()
        state, expected, native, _, _, client, device = self.make(handler=handler)
        def capture(name):
            results[name] = client.invoke(CAP, {"camera": name}, device_id=device, deadline_ms=2000)
        workers = [threading.Thread(target=capture, args=(name,)) for name in ("color", "depth")]
        def feed(name, *, topic=None, ident=None, sample=None):
            request = requests[name]
            native.feed({"op": "publish", "topic": topic or request["topic"], "id": ident or request["id"],
                         "msg": copy.deepcopy(sample or state["samples"][name])})
        try:
            workers[0].start(); self.assertTrue(entered["color"].wait(1))
            workers[1].start()
            feed("color", topic="/camera/depth", sample=state["samples"]["ir"])
            feed("color", ident="unknown-subscription", sample=state["samples"]["ir"])
            feed("color")
            self.assertTrue(entered["depth"].wait(1))
            feed("depth", ident=requests["color"]["id"], sample=state["samples"]["color"])
            feed("depth")
            for worker in workers: worker.join(2)
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            for name, receipt in results.items():
                self.assertEqual(receipt["status"], "completed", receipt)
                desc = receipt["artifacts"][0]
                self.assertEqual(desc["x-vendor"]["openmhs.ros_image"]["header"], state["samples"][name]["header"])
                self.assertEqual(png_rows(client.read_artifact(desc["uri"], session_id=receipt["session_id"])["data"]), expected[name])
            self.assertEqual(set(results), {"color", "depth"})
        finally:
            native.close()
            for worker in workers:
                if worker.ident is not None: worker.join(2)

    def test_identical_pixels_distinct_grants_and_headers_detach_from_sources_and_readers(self):
        state, _, _, store, _, client, device = self.make()
        state["samples"]["ir"] = copy.deepcopy(state["samples"]["depth"])
        state["samples"]["ir"]["header"]["frame_id"] = "ir_same_pixels"
        first = client.invoke(CAP, {"camera": "depth"}, device_id=device)
        second = client.invoke(CAP, {"camera": "ir"}, device_id=device)
        a, b = first["artifacts"][0], second["artifacts"][0]
        self.assertEqual(a["digest"], b["digest"])
        self.assertNotEqual(a["uri"], b["uri"])
        self.assertNotEqual(a["x-vendor"], b["x-vendor"])
        self.assertEqual(len(store._blobs), 1)
        original = copy.deepcopy(a)
        state["samples"]["depth"]["header"]["stamp"]["secs"] = 999
        a["x-vendor"]["openmhs.ros_image"]["header"]["frame_id"] = "caller mutation"
        fetched = client.read_artifact(original["uri"], session_id=first["session_id"])
        self.assertEqual(fetched["descriptor"], original)
        fetched["descriptor"]["x-vendor"].clear()
        self.assertEqual(client.read_artifact(original["uri"], session_id=first["session_id"])["descriptor"], original)

    def test_mcp_nested_receipt_mutation_does_not_poison_authorized_route(self):
        _, _, _, _, _, client, _ = self.make()
        projection, tool = self.project(client)
        _, receipt = self.capture(projection, tool, camera="color")
        descriptor = receipt["artifacts"][0]
        original = copy.deepcopy(descriptor)
        descriptor["x-vendor"]["openmhs.ros_image"]["header"]["frame_id"] = "untrusted caller"
        response = self.request(projection, "resources/read", {"uri": original["uri"]})
        self.assertIn("result", response)
        self.assertEqual(projection._artifact_routes[original["uri"]]["descriptor"], original)
        other = MHSClient(client.transport)
        other.hello()
        other_projection, _ = self.project(other)
        self.assertIn("error", self.request(other_projection, "resources/read", {"uri": original["uri"]}))

    def test_replay_ttl_principal_scope_and_cleanup_keep_original_descriptor(self):
        now = [0.0]
        tokens = {"token-a": {"id": "alice", "kind": "agent"}, "token-b": {"id": "bob", "kind": "agent"}}
        state, _, _, store, server, client, device = self.make(tokens=tokens,
            store_options={"ttl_s": 1, "clock": lambda: now[0]})
        key = canonical.ulid()
        first = client.invoke(CAP, {"camera": "color"}, device_id=device, command_id=key)
        descriptor = copy.deepcopy(first["artifacts"][0])
        state["samples"]["color"]["header"]["seq"] = 777
        replay = client.invoke(CAP, {"camera": "color"}, device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["artifacts"], [descriptor])
        self.assertEqual(state["subscriptions"], ["color"])
        other = MHSClient(InProcessTransport(server, auth_token="token-b")); other.hello()
        with self.assertRaises(MHSError):
            other.read_artifact(descriptor["uri"], session_id=first["session_id"])
        self.assertTrue(verify_bundle(client.export_evidence()).valid)
        now[0] = 2.0
        with self.assertRaises(MHSError):
            client.read_artifact(descriptor["uri"], session_id=first["session_id"])
        replay = client.invoke(CAP, {"camera": "color"}, device_id=device, command_id=key)
        self.assertEqual(replay["artifacts"], [descriptor])
        self.assertEqual(state["subscriptions"], ["color"])
        root = store._root
        close_server(server)
        self.assertFalse(root.exists())
        self.assertEqual(store._grants, {})

    def test_stop_cancel_and_execution_budget_discard_selected_source_before_publication(self):
        for interrupt in ("stop", "cancel", "deadline"):
            with self.subTest(interrupt=interrupt):
                _, _, _, store, server, client, device = self.make(
                    execution_ms=100 if interrupt == "deadline" else 2000, long_running=interrupt == "cancel")
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)
                original = ros_images.convert_image
                def blocked(*args, **kwargs):
                    entered.set()
                    if not release.wait(3): raise AssertionError("converter barrier not released")
                    return original(*args, **kwargs)
                with patch.object(ros_images, "convert_image", side_effect=blocked):
                    early = client.invoke(CAP, {"camera": "ir"}, device_id=device, deadline_ms=100)
                    self.assertTrue(entered.is_set(), early)
                    self.assertNotIn("artifacts", early)
                    operation = server._operations[early["operation_id"]]
                    if interrupt == "stop":
                        client.estop("controlled publication barrier", device_id=device, deadline_ms=100)
                    elif interrupt == "cancel":
                        client.cancel(early["operation_id"], deadline_ms=50)
                    release.set()
                    self.assertTrue(operation.done.wait(2))
                self.assertIn(operation.final_receipt["status"], ("failed", "cancelled"), operation.final_receipt)
                self.assertNotIn("artifacts", operation.final_receipt)
                self.assertEqual(store._grants, {})

    def test_pixel_and_publication_capacity_errors_publish_no_partial_metadata(self):
        state, _, _, store, _, client, device = self.make(store_options={"max_artifacts": 1})
        good = copy.deepcopy(state["samples"]["ir"])
        for change in ({"step": 1}, {"data": [1]}, {"encoding": "32FC1"}):
            state["samples"]["ir"] = {**good, **change}
            bad = client.invoke(CAP, {"camera": "ir"}, device_id=device)
            self.assertEqual(bad["status"], "failed", bad)
            self.assertEqual(store._grants, {})
        state["samples"]["ir"] = good
        first = client.invoke(CAP, {"camera": "ir"}, device_id=device)
        second = client.invoke(CAP, {"camera": "color"}, device_id=device)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "failed")
        self.assertNotIn("artifacts", second)
        self.assertEqual(len(store._grants), 1)


    @unittest.skipIf(Image is None, "optional Pillow decoder is not installed")
    def test_source_sized_complete_color_depth_ir_with_explicit_transport_and_artifact_budgets(self):
        state, _, _, _, _, client, device = self.make(execution_ms=10000,
            max_message_bytes=16 * 1024 * 1024, store_options={"max_artifact_bytes": 8 * 1024 * 1024})
        projection, tool = self.project(client)
        for index, (name, width, height, bytes_per_pixel) in enumerate(
                (("color", 1920, 1080, 3), ("depth", 512, 424, 2), ("ir", 512, 424, 2))):
            pixels = random.Random(17 + index).randbytes(width * height * bytes_per_pixel)
            sample = state["samples"][name]
            sample.update(width=width, height=height, step=width * bytes_per_pixel,
                          data=base64.b64encode(pixels).decode("ascii"), is_bigendian=0)
            result, receipt = self.capture(projection, tool, camera=name, deadline_ms=15000)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual((receipt["output"]["width"], receipt["output"]["height"]), (width, height))
            response = self.request(projection, "resources/read", {"uri": receipt["output"]["image_ref"]})
            blob = base64.b64decode(response["result"]["contents"][0]["blob"], validate=True)
            with Image.open(io.BytesIO(blob)) as decoded:
                decoded.load()
                self.assertEqual(decoded.size, (width, height))
                if name == "color":
                    with Image.frombytes("RGB", (width, height), pixels, "raw", "BGR") as source:
                        self.assertEqual(decoded.tobytes(), source.tobytes())
                else:
                    self.assertEqual(list(decoded.get_flattened_data()),
                                     [int.from_bytes(pixels[i:i + 2], "little") for i in range(0, len(pixels), 2)])
            self.assertEqual(receipt["artifacts"][0]["x-vendor"]["openmhs.ros_image"]["header"], sample["header"])

    @unittest.skipIf(Image is None, "optional Pillow decoder is not installed")
    def test_compressed_selected_source_preserves_packet_header_without_relabeling_rich_formats(self):
        commands = declaration(2)
        commands[CAP]["cameras"]["color"]["type"] = "sensor_msgs/msg/CompressedImage"
        state, _, _, store, _, client, device = self.make(version=2, commands=commands)
        header = copy.deepcopy(state["samples"]["color"]["header"])
        state["samples"]["color"] = {**compressed_message("png"), "header": header}
        good = client.invoke(CAP, {"camera": "color"}, device_id=device)
        self.assertEqual(good["status"], "completed", good)
        self.assertEqual(good["artifacts"][0]["x-vendor"]["openmhs.ros_image"]["header"], header)
        state["samples"]["color"]["format"] = "16UC1; png compressed"
        bad = client.invoke(CAP, {"camera": "color"}, device_id=device)
        self.assertEqual(bad["status"], "failed", bad)
        self.assertNotIn("artifacts", bad)
        self.assertEqual(len(store._grants), 1)



if __name__ == "__main__":
    unittest.main()
