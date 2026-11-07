"""Complete default images, calibration, metadata and the opt-in point cloud through stock paths.

The packets are controlled test data. No camera, ROS node or upstream module is imported. Pillow is an independent
PNG decoder from the SDK images extra. The package serves two typed resources of one device (``camera``,
``sensor.camera``; ``pointcloud``, ``sensor.depth``); these cases exercise the stock loader, server and client,
never a hand-built host.  The MCP projection is checked by a separately run host test, because package code does not
import the MCP runtime (gate G3).
"""
import base64
import copy
import io
import json
import random
import shutil
import struct
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from PIL import Image
from mhs import canonical
from mhs.adapter import LoadError, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import DriverDefinitionError, close_server
from mhs.errors import MHSError

HERE = Path(__file__).resolve().parent
IMAGE = "cap.sensing.image.v1"
CLOUD = "cap.sensing.point_cloud.v1"
COLOR_INFO = "x-cap.realsenseai.color_camera_info.v1"
DEPTH_INFO = "x-cap.realsenseai.depth_camera_info.v1"
COLOR_MD = "x-cap.realsenseai.color_metadata.v1"
DEPTH_MD = "x-cap.realsenseai.depth_metadata.v1"
COLOR_TOPIC = "/camera/camera/color/image_raw"
DEPTH_TOPIC = "/camera/camera/depth/image_rect_raw"
POINTS_TOPIC = "/camera/camera/depth/color/points"


def pixels(blob):
    with Image.open(io.BytesIO(blob)) as image:
        image.load()
        flat = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
        return image.mode, image.size, (image.tobytes() if image.mode == "RGB" else list(flat))


def unpack(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        assert archive.namelist() == ["pointcloud.json", "data.bin"], archive.namelist()
        return json.loads(archive.read("pointcloud.json")), archive.read("data.bin")


def cloud(width, height, point_step, row_step, *, dense, fill=0xA5):
    data = bytearray(bytes([fill]) * (row_step * height))
    for row in range(height):
        for col in range(width):
            offset = row * row_step + col * point_step
            struct.pack_into("<fff", data, offset, col * 0.25, -row * 0.5, 0.75 + row + col)
            data[offset + 12:offset + 16] = bytes((col % 256, row % 256, 200, 0))
    if width and height:
        struct.pack_into("<I", data, 0, 0x7FC01234)      # a NaN payload, never normalized
        struct.pack_into("<I", data, 4, 0x80000000)      # negative zero
    fields = [{"name": n, "offset": o, "datatype": 7, "count": 1} for n, o in (("x", 0), ("y", 4), ("z", 8), ("rgb", 12))]
    return {"header": {"stamp": {"sec": 1730000001, "nanosec": 5}, "frame_id": "camera_depth_optical_frame"},
            "height": height, "width": width, "fields": fields, "is_bigendian": False, "point_step": point_step,
            "row_step": row_step, "data": base64.b64encode(bytes(data)).decode("ascii"), "is_dense": dense}, bytes(data)


class PrimaryOutputs(unittest.TestCase):
    def serve(self, *, store_options=None, tokens=None):
        store = LocalArtifactStore(**(store_options or {}))
        self.addCleanup(store.close)
        server = load(HERE, backend="fake", artifact_store=store, auth_tokens=tokens)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token="alice-token" if tokens else None))
        device = client.hello()["devices"][0]["device_id"]
        client.open_session([device])
        return server, client, device, store, server.devices[device].bridge.native

    def subscriptions(self, peer, topic):
        return sum(1 for item in peer.sent if item.get("op") == "subscribe" and item.get("topic") == topic)

    def captures(self, peer):
        # Every receipt (refused ones included) re-reads the main resource state; captures are what must not run.
        return sum(self.subscriptions(peer, topic) for topic in (COLOR_TOPIC, DEPTH_TOPIC, POINTS_TOPIC))

    # -- composition through the stock loader ---------------------------------------------------------------
    def test_one_device_serves_two_typed_resources_through_the_stock_loader(self):
        server, client, device, _, _ = self.serve()
        manifest = client.request("mhs.devices.get", {"device_id": device})
        self.assertEqual([(r["resource_id"], r["kind"]) for r in manifest["resources"]],
                         [("camera", "sensor.camera"), ("pointcloud", "sensor.depth")])
        bound = {c["capability_id"]: c["resource"] for c in manifest["capabilities"]}
        self.assertEqual(bound[IMAGE], "camera")
        self.assertEqual(bound[CLOUD], "pointcloud")
        self.assertEqual({bound[c] for c in (COLOR_INFO, DEPTH_INFO, COLOR_MD, DEPTH_MD)}, {"camera"})
        self.assertEqual(len(server.devices), 1)
        self.assertEqual(manifest["mode"], "simulated")

    def test_wrong_resource_is_refused_before_any_subscription(self):
        _, client, device, store, peer = self.serve()
        cloud_on_camera = client.invoke(CLOUD, {}, device_id=device, resource="camera")
        image_on_cloud = client.invoke(IMAGE, {"camera": "color"}, device_id=device, resource="pointcloud")
        for receipt in (cloud_on_camera, image_on_cloud):
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.NOT_BOUND", receipt)
        self.assertEqual(self.captures(peer), 0)
        self.assertEqual(store._grants, {})
        explicit = client.invoke(CLOUD, {}, device_id=device, resource="pointcloud")
        self.assertEqual(explicit["status"], "completed", explicit)

    def test_pointcloud_resource_reads_empty_without_traffic_and_refuses_writes(self):
        _, client, device, _, peer = self.serve()
        before = len(peer.sent)
        state = client.read("pointcloud", device_id=device)
        self.assertEqual(state["state"], {})
        self.assertEqual(len(peer.sent), before)
        with self.assertRaises(MHSError):
            receipt = client.write("pointcloud", {"anything": 1}, device_id=device, check=True)
            self.assertNotEqual(receipt["status"], "completed")
        self.assertEqual(len(peer.sent), before)

    # -- complete images -----------------------------------------------------------------------------------
    def test_color_rgb8_every_pixel_padding_and_exact_header(self):
        _, client, device, store, peer = self.serve()
        width, height, step = 7, 5, 7 * 3 + 2
        rows = [bytes((x * 31 + y * 17 + c * 89) % 256 for x in range(width) for c in range(3)) + b"\xee\x01"
                for y in range(height)]
        message = copy.deepcopy(peer.images[COLOR_TOPIC])
        message.update(width=width, height=height, step=step, data=list(b"".join(rows)))
        peer.images[COLOR_TOPIC] = message
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["output"]["width"], receipt["output"]["height"]), (width, height))
        descriptor = receipt["artifacts"][0]
        self.assertEqual(descriptor["x-vendor"]["openmhs.ros_image"],
                         {"camera": "color", "topic": COLOR_TOPIC, "type": "sensor_msgs/msg/Image",
                          "ros_version": 2, "header": message["header"]})
        blob = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])["data"]
        self.assertEqual(pixels(blob), ("RGB", (width, height), b"".join(row[:width * 3] for row in rows)))
        self.assertEqual(self.subscriptions(peer, DEPTH_TOPIC), 0)
        self.assertEqual(len(store._grants), 1)

    def test_depth_16uc1_values_exact_in_both_byte_orders_with_padding(self):
        values = [0, 1, 255, 256, 4095, 65535, 32768, 1200, 77, 65534, 2, 513]
        for big in (0, 1):
            with self.subTest(is_bigendian=big):
                _, client, device, _, peer = self.serve()
                fmt = ">H" if big else "<H"
                rows = [b"".join(struct.pack(fmt, v) for v in values[y * 4:(y + 1) * 4]) + b"\x99\x98"
                        for y in range(3)]
                message = copy.deepcopy(peer.images[DEPTH_TOPIC])
                message.update(width=4, height=3, step=10, is_bigendian=big, data=list(b"".join(rows)))
                peer.images[DEPTH_TOPIC] = message
                receipt = client.invoke(IMAGE, {"camera": "depth"}, device_id=device)
                self.assertEqual(receipt["status"], "completed", receipt)
                descriptor = receipt["artifacts"][0]
                self.assertEqual(descriptor["x-vendor"]["openmhs.ros_image"]["header"], message["header"])
                self.assertEqual(descriptor["x-vendor"]["openmhs.ros_image"]["camera"], "depth")
                blob = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])["data"]
                mode, size, flat = pixels(blob)
                self.assertEqual((mode, size), ("I;16", (4, 3)))
                self.assertEqual(flat, values)  # received integers, never rescaled or converted to metres

    def test_full_default_color_frame_needs_an_explicit_store_and_keeps_every_pixel(self):
        raw = random.Random(4590).randbytes(1280 * 720 * 3)  # placeholder nonconstant complete frame
        for size, admitted in ((None, False), (4 * 1024 * 1024, True)):
            with self.subTest(store=size):
                _, client, device, store, peer = self.serve(
                    store_options={"max_artifact_bytes": size} if size else None)
                peer.images[COLOR_TOPIC].update(width=1280, height=720, step=3840,
                                                data=base64.b64encode(raw).decode("ascii"))
                receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
                if not admitted:
                    self.assertEqual(receipt["status"], "failed", receipt)
                    self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
                    self.assertEqual(store._grants, {})
                    continue
                self.assertEqual(receipt["status"], "completed", receipt)
                blob = client.read_artifact(receipt["artifacts"][0]["uri"], session_id=receipt["session_id"])["data"]
                self.assertEqual(pixels(blob), ("RGB", (1280, 720), raw))

    def test_invalid_images_and_unknown_selectors_never_grant_an_artifact(self):
        _, client, device, store, peer = self.serve()
        original = copy.deepcopy(peer.images[DEPTH_TOPIC])
        mutations = [lambda d: d.update(encoding="32FC1"), lambda d: d.update(step=2),
                     lambda d: d.update(data=[1, 2]), lambda d: d.update(width=0), lambda d: d.pop("header"),
                     lambda d: d["header"]["stamp"].update(nanosec=True),
                     lambda d: d["header"].update(frame_id="bad\x00frame"),
                     lambda d: d.update(width=4097, height=1025, step=8194)]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                peer.images[DEPTH_TOPIC] = copy.deepcopy(original)
                mutate(peer.images[DEPTH_TOPIC])
                receipt = client.invoke(IMAGE, {"camera": "depth"}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertNotIn("artifacts", receipt)
        before = self.captures(peer)
        for args in ({}, {"camera": "infra1"}, {"camera": "color", "topic": "/other"}):
            receipt = client.invoke(IMAGE, args, device_id=device)
            self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(self.captures(peer), before)
        self.assertEqual(store._grants, {})

    # -- complete calibration and metadata --------------------------------------------------------------------
    def test_complete_camera_info_of_both_streams_with_distinct_headers(self):
        _, client, device, _, peer = self.serve()
        color = peer._camera_info_message()
        color["roi"] = {"x_offset": 3, "y_offset": 5, "height": 200, "width": 400, "do_rectify": True}
        peer.overrides["/camera/camera/color/camera_info"] = color
        results = {}
        for cap in (COLOR_INFO, DEPTH_INFO):
            receipt = client.invoke(cap, {}, device_id=device)
            self.assertEqual(receipt["status"], "completed", receipt)
            results[cap] = receipt["output"]["camera_info"]
        self.assertEqual(results[COLOR_INFO], color)
        self.assertEqual(results[DEPTH_INFO], peer.depth_info)
        self.assertNotEqual(results[COLOR_INFO]["header"], results[DEPTH_INFO]["header"])
        image = client.invoke(IMAGE, {"camera": "depth"}, device_id=device)
        header = image["artifacts"][0]["x-vendor"]["openmhs.ros_image"]["header"]
        self.assertEqual(header, peer.images[DEPTH_TOPIC]["header"])  # its own packet, not a paired one

    def test_zeroed_fallback_intrinsics_and_equidistant_model_are_returned_unchanged(self):
        _, client, device, _, peer = self.serve()
        info = copy.deepcopy(peer.depth_info)
        info.update(width=0, height=0, distortion_model="equidistant", d=[0.0] * 4, k=[0.0] * 9, p=[0.0] * 12)
        info["header"]["stamp"] = {"sec": -1, "nanosec": 0}
        peer.overrides["/camera/camera/depth/camera_info"] = info
        receipt = client.invoke(DEPTH_INFO, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["camera_info"], info)

    def test_malformed_camera_info_is_refused_without_fabrication(self):
        _, client, device, _, peer = self.serve()
        mutations = [lambda d: d.pop("roi"), lambda d: d.update(k=[0.0] * 8), lambda d: d.update(r=[0.0] * 10),
                     lambda d: d.update(p=[0.0] * 11), lambda d: d.update(d=[0.0] * 65),
                     lambda d: d.update(width=True), lambda d: d.update(height=-1),
                     lambda d: d.update(binning_y=2 ** 32), lambda d: d["roi"].update(x_offset=-1),
                     lambda d: d["roi"].update(do_rectify=1),
                     lambda d: d["header"]["stamp"].update(nanosec=1_000_000_000),
                     lambda d: d["header"]["stamp"].update(sec=2 ** 31),
                     lambda d: d["header"].update(frame_id="\u00e9" * 129), lambda d: d.update(k=[True] * 9),
                     lambda d: d.update(extra="not a CameraInfo field"), lambda d: d.pop("header")]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                info = copy.deepcopy(peer.depth_info)
                mutate(info)
                peer.overrides["/camera/camera/depth/camera_info"] = info
                receipt = client.invoke(DEPTH_INFO, {}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
                self.assertIsNone(receipt["output"])

    def test_nonfinite_calibration_wire_data_is_refused_without_fabrication(self):
        # The recording transport enforces strict finite JSON at the wire boundary, as rosbridge JSON must.
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=str(value)):
                server, client, device, store, peer = self.serve()
                info = copy.deepcopy(peer.depth_info)
                info["k"][0] = value
                peer.overrides["/camera/camera/depth/camera_info"] = info
                receipt = client.invoke(DEPTH_INFO, {}, device_id=device)
                # The refused reply fails the transport send: the stock bridge reports an unknown outcome (or, once
                # the connection has failed, NOT_READY). Either way nothing is returned or granted.
                self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
                self.assertIn(receipt["error"]["mhs_code"], ("MHS.OUTCOME.UNKNOWN", "MHS.DEVICE.NOT_READY"), receipt)
                self.assertIsNone(receipt["output"])
                self.assertNotIn("artifacts", receipt)
                self.assertEqual(store._grants, {})
                close_server(server)

    def test_interleaved_captures_on_both_resources_keep_their_own_packets(self):
        _, client, device, store, peer = self.serve()
        peer.images[COLOR_TOPIC]["header"]["stamp"]["nanosec"] = 111
        peer.images[DEPTH_TOPIC]["header"]["stamp"]["nanosec"] = 222
        peer.points["header"]["stamp"]["nanosec"] = 333
        jobs = [(IMAGE, {"camera": "color"}), (CLOUD, {}), (IMAGE, {"camera": "depth"})] * 3
        receipts = [None] * len(jobs)

        def run(index, cap, args):
            receipts[index] = client.invoke(cap, args, device_id=device, wait=True, wait_timeout_s=20)
        threads = [threading.Thread(target=run, args=(i, cap, args)) for i, (cap, args) in enumerate(jobs)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        expected = {"color": 111, "depth": 222}
        for (cap, args), receipt in zip(jobs, receipts):
            self.assertEqual(receipt["status"], "completed", receipt)
            vendor = receipt["artifacts"][0]["x-vendor"]
            if cap == IMAGE:
                self.assertEqual(vendor["openmhs.ros_image"]["camera"], args["camera"])
                self.assertEqual(vendor["openmhs.ros_image"]["header"]["stamp"]["nanosec"], expected[args["camera"]])
            else:
                self.assertEqual(vendor["openmhs.ros_point_cloud"]["header"]["stamp"]["nanosec"], 333)
        self.assertEqual(len(store._grants), len(jobs))

    def test_metadata_text_and_header_are_preserved_byte_for_byte(self):
        _, client, device, _, peer = self.serve()
        text = '{"frame_number":12,"clock_domain":"global_time","frame_timestamp":1730000000125.123000,' \
               '"unknown_future_key":-1, "spaced" : 7}'
        peer.metadata_json = text
        peer.depth_metadata_json = text[::-1]  # not JSON at all: still returned exactly, never parsed
        color = client.invoke(COLOR_MD, {}, device_id=device)
        depth = client.invoke(DEPTH_MD, {}, device_id=device)
        self.assertEqual(color["output"]["metadata"]["json_data"], text)
        self.assertEqual(depth["output"]["metadata"]["json_data"], text[::-1])
        self.assertEqual(color["output"]["metadata"]["header"]["frame_id"], "camera_color_optical_frame")
        self.assertEqual(depth["output"]["metadata"]["header"]["frame_id"], "camera_depth_optical_frame")
        legacy = client.invoke("x-cap.realsenseai.frame_metadata.v1", {}, device_id=device)
        self.assertEqual(legacy["output"], {"json_data": text})
        peer.overrides["/camera/camera/depth/metadata"] = {"json_data": "{}"}
        missing = client.invoke(DEPTH_MD, {}, device_id=device)
        self.assertEqual(missing["status"], "failed", missing)

    # -- opt-in point cloud on its own resource ---------------------------------------------------------------
    def test_point_cloud_keeps_every_byte_field_flag_and_header(self):
        cases = {"unordered": cloud(3, 1, 16, 48, dense=True),
                 "organized_padded": cloud(3, 2, 20, 64, dense=False),
                 "empty": cloud(0, 1, 16, 0, dense=True)}
        for name, (message, data) in cases.items():
            with self.subTest(case=name):
                _, client, device, store, peer = self.serve()
                peer.points = message
                receipt = client.invoke(CLOUD, {}, device_id=device)
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["output"]["point_count"], message["width"] * message["height"])
                self.assertEqual(receipt["output"]["frame"], "camera_depth_optical_frame")
                descriptor = receipt["artifacts"][0]
                self.assertEqual(descriptor["x-vendor"]["openmhs.ros_point_cloud"]["header"], message["header"])
                blob = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])["data"]
                manifest, payload = unpack(blob)
                self.assertEqual(payload, data)
                for key in ("width", "height", "point_step", "row_step", "is_dense", "is_bigendian", "fields"):
                    self.assertEqual(manifest[key], message[key], key)
                self.assertEqual(manifest["topic"], POINTS_TOPIC)
                self.assertEqual(len(store._grants), 1)

    def test_disabled_point_cloud_times_out_and_budgets_refuse_whole_samples(self):
        _, client, device, store, peer = self.serve()
        peer.silent_topics.add(POINTS_TOPIC)  # pointcloud.enable left at its default false
        receipt = client.invoke(CLOUD, {}, device_id=device, wait=True, wait_timeout_s=15)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)
        self.assertNotIn("artifacts", receipt)
        peer.silent_topics.clear()
        too_many = copy.deepcopy(peer.points)
        too_many.update(width=1_048_577, row_step=16 * 1_048_577, data="")  # over the point budget: refused whole
        malformed, _ = cloud(3, 1, 16, 47, dense=True)
        bad_field, _ = cloud(3, 1, 16, 48, dense=True)
        bad_field["fields"][3]["offset"] = 13
        for message in (too_many, malformed, bad_field):
            peer.points = message
            receipt = client.invoke(CLOUD, {}, device_id=device)
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    # -- one device: shared transport, latch and lifecycle ------------------------------------------------------
    def test_one_transport_serves_both_resources_and_one_latch_stops_both(self):
        server, client, device, store, peer = self.serve()
        image = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        points = client.invoke(CLOUD, {}, device_id=device)
        self.assertEqual((image["status"], points["status"]), ("completed", "completed"))
        self.assertGreater(self.subscriptions(peer, COLOR_TOPIC), 0)
        self.assertGreater(self.subscriptions(peer, POINTS_TOPIC), 0)
        self.assertIs(server.devices[device].bridge.inner._transport, peer)
        client.estop("composition test", device_id=device)
        before = self.captures(peer)
        for cap, args in ((IMAGE, {"camera": "depth"}), (CLOUD, {})):
            receipt = client.invoke(cap, args, device_id=device)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", receipt)
        self.assertEqual(self.captures(peer), before)
        self.assertEqual(len(store._grants), 2)

    def test_close_releases_the_one_transport_and_every_artifact_once(self):
        server, client, device, store, peer = self.serve()
        closes = []
        original = peer.close
        peer.close = lambda: (closes.append(1), original())[1]
        self.assertEqual(client.invoke(CLOUD, {}, device_id=device)["status"], "completed")
        self.assertEqual(client.invoke(IMAGE, {"camera": "color"}, device_id=device)["status"], "completed")
        root = store._root
        close_server(server)
        self.assertTrue(peer.closed)
        self.assertEqual(len(closes), 1)
        self.assertFalse(root.exists())
        self.assertEqual(store._grants, {})

    def test_a_failed_transport_fails_both_resources_closed(self):
        _, client, device, store, peer = self.serve()
        peer.close()
        for cap, args in ((IMAGE, {"camera": "color"}), (CLOUD, {}), (COLOR_INFO, {})):
            receipt = client.invoke(cap, args, device_id=device)
            self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
            self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_cancel_pending_cloud_capture_and_late_packet_never_publish(self):
        server, client, device, store, peer = self.serve()
        peer.silent_topics.add(POINTS_TOPIC)
        entered, requests, original = threading.Event(), [], peer.handler

        def handler(request):
            if request.get("op") == "subscribe" and request.get("topic") == POINTS_TOPIC:
                requests.append(copy.deepcopy(request))
                entered.set()
            return original(request)
        peer.handler = handler
        early = client.invoke(CLOUD, {}, device_id=device, deadline_ms=10)
        self.assertTrue(entered.wait(1), early)
        operation = server._operations[early["operation_id"]]
        client.cancel(early["operation_id"], deadline_ms=100)
        self.assertTrue(operation.done.wait(6))
        self.assertIn(operation.final_receipt["status"], ("cancelled", "failed"))
        peer.feed({"op": "publish", "topic": POINTS_TOPIC, "id": requests[0]["id"], "msg": copy.deepcopy(peer.points)})
        self.assertEqual(store._grants, {})
        self.assertTrue(any(x.get("op") == "unsubscribe" and x.get("id") == requests[0]["id"] for x in peer.sent))

    def test_estop_during_a_pending_capture_publishes_nothing_late(self):
        server, client, device, store, peer = self.serve()
        peer.silent_topics.add(DEPTH_TOPIC)
        entered, requests, original = threading.Event(), [], peer.handler

        def handler(request):
            if request.get("op") == "subscribe" and request.get("topic") == DEPTH_TOPIC:
                requests.append(copy.deepcopy(request))
                entered.set()
            return original(request)
        peer.handler = handler
        early = client.invoke(IMAGE, {"camera": "depth"}, device_id=device, deadline_ms=10)
        self.assertTrue(entered.wait(1), early)
        operation = server._operations[early["operation_id"]]
        client.estop("stop during a pending capture", device_id=device)
        self.assertTrue(operation.done.wait(6))
        self.assertIn(operation.final_receipt["status"], ("cancelled", "failed"))
        peer.feed({"op": "publish", "topic": DEPTH_TOPIC, "id": requests[0]["id"],
                   "msg": copy.deepcopy(peer.images[DEPTH_TOPIC])})
        self.assertEqual(store._grants, {})
        later = client.invoke(CLOUD, {}, device_id=device)
        self.assertEqual(later["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", later)

    def test_session_principal_and_expiry_bound_artifacts_of_both_resources(self):
        now = [0.0]
        tokens = {"alice-token": {"id": "alice", "kind": "agent"}, "bob-token": {"id": "bob", "kind": "agent"}}
        server, client, device, store, _ = self.serve(tokens=tokens, store_options={"ttl_s": 1, "clock": lambda: now[0]})
        receipts = [client.invoke(IMAGE, {"camera": "depth"}, device_id=device), client.invoke(CLOUD, {}, device_id=device)]
        bob = MHSClient(InProcessTransport(server, auth_token="bob-token"))
        bob.hello()
        for receipt in receipts:
            self.assertEqual(receipt["status"], "completed", receipt)
            with self.assertRaises(MHSError):
                bob.read_artifact(receipt["artifacts"][0]["uri"], session_id=receipt["session_id"])
        now[0] = 2
        for receipt in receipts:
            with self.assertRaises(MHSError):
                client.read_artifact(receipt["artifacts"][0]["uri"], session_id=receipt["session_id"])

    def test_replay_returns_the_original_cloud_without_another_capture(self):
        _, client, device, store, peer = self.serve()
        command_id = canonical.ulid()
        first = client.invoke(CLOUD, {}, device_id=device, command_id=command_id)
        self.assertEqual(first["status"], "completed", first)
        captures = self.subscriptions(peer, POINTS_TOPIC)
        peer.points["header"]["stamp"]["sec"] += 99
        replay = client.invoke(CLOUD, {}, device_id=device, command_id=command_id)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["artifacts"], first["artifacts"])
        self.assertEqual(self.subscriptions(peer, POINTS_TOPIC), captures)
        self.assertEqual(len(store._grants), 1)

    # -- refusals before any transport ----------------------------------------------------------------------------
    def test_unsigned_hardware_refuses_before_any_native_connection(self):
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")

    def test_tampered_resource_declarations_fail_before_the_fake_is_constructed(self):
        tampers = [('Action(\n            name="capture_point_cloud", resource="pointcloud"',
                    'Action(\n            name="capture_point_cloud", resource="camera"'),
                   ('"sensor.depth",\n                                      "title"', '"sensor.camera",\n'
                    '                                      "title"'),
                   ('name="capture_point_cloud", resource="pointcloud"', 'name="capture_point_cloud", resource="other"'),
                   ('"timeout_ms": 5000,\n            "source_name": "~/depth/color/points"',
                    '"timeout_ms": 5000, "resource": "camera",\n            "source_name": "~/depth/color/points"')]
        for old, new in tampers:
            with self.subTest(tamper=new[:60]):
                with tempfile.TemporaryDirectory() as holder:
                    copy_dir = Path(holder) / "realsenseai__realsense-ros"
                    shutil.copytree(HERE, copy_dir, ignore=shutil.ignore_patterns("check-report.json"))
                    marker = Path(holder) / "fake-constructed"
                    source = (copy_dir / "driver.py").read_text()
                    self.assertEqual(source.count(old), 1, old)
                    (copy_dir / "driver.py").write_text(source.replace(old, new))
                    fake = (copy_dir / "fake.py").read_text().replace(
                        "    def __init__(self, **_options):\n",
                        f"    def __init__(self, **_options):\n        Path({str(marker)!r}).write_text('x')\n", 1)
                    (copy_dir / "fake.py").write_text("from pathlib import Path\n" + fake)
                    with self.assertRaises(DriverDefinitionError):
                        load(copy_dir, backend="fake")
                    self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
