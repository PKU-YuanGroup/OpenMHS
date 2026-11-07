"""Complete primary pixels, calibration and owned stock artifact paths.

The packets are controlled test data. No camera, ROS node or upstream module is
imported. Pillow is an independent PNG decoder from the SDK images extra.
"""
import base64
import copy
import io
import random
import threading
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from mhs import canonical
from mhs.adapter import LoadError, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from mhs.errors import MHSError

HERE = Path(__file__).resolve().parent
IMAGE = "cap.sensing.image.v1"
CALIBRATION = "x-cap.klintan.camera_calibration.v1"


def rgb_from_bgr(data, width, height, step):
    # Independent direct sample-order oracle, excluding transport row padding.
    return bytes(data[y*step+x*3+c] for y in range(height) for x in range(width) for c in (2, 1, 0))


class PrimaryOutputCases(unittest.TestCase):
    def serve(self, *, store_options=None, tokens=None):
        store = LocalArtifactStore(**(store_options or {}))
        self.addCleanup(store.close)
        server = load(HERE, backend="fake", artifact_store=store, auth_tokens=tokens)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server, auth_token="alice-token" if tokens else None))
        device = client.hello()["devices"][0]["device_id"]
        client.open_session([device])
        # Configure only the controlled transport owned by the loaded device.
        driver = server.devices[device].bridge
        return server, client, device, store, driver.native

    def pixels(self, blob):
        with Image.open(io.BytesIO(blob)) as image:
            image.load()
            self.assertEqual(image.mode, "RGB")
            return image.size, image.tobytes()

    def test_full_default_geometry_pixels_header_and_artifact_ownership(self):
        server, client, device, store, peer = self.serve(store_options={"max_artifact_bytes": 4*1024*1024})
        raw = random.Random(1729).randbytes(1280*720*3)  # placeholder nonconstant complete frame
        peer.image.update(width=1280, height=720, step=1280*3, data=base64.b64encode(raw).decode())
        original_header = copy.deepcopy(peer.image["header"])
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        descriptor = copy.deepcopy(receipt["artifacts"][0])
        self.assertEqual(receipt["output"]["width"], 1280)
        self.assertEqual(receipt["output"]["height"], 720)
        metadata = descriptor["x-vendor"]["openmhs.ros_image"]
        self.assertEqual(metadata, {"camera": "color", "topic": "/image", "type": "sensor_msgs/msg/Image",
                                    "ros_version": 2, "header": original_header})
        png = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])["data"]
        self.assertEqual(self.pixels(png), ((1280, 720), rgb_from_bgr(raw, 1280, 720, 1280*3)))
        # Public receipt mutation cannot replace the stored metadata or pixels.
        receipt["artifacts"][0]["x-vendor"].clear()
        peer.image["header"]["frame_id"] = "later frame"
        fetched = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])
        self.assertEqual(fetched["descriptor"], descriptor)
        self.assertEqual(fetched["data"], png)
        self.assertEqual(len(store._grants), 1)
        self.assertEqual(len(server.devices), 1)

    def test_padded_rows_preserve_every_pixel_and_exact_replay(self):
        _, client, device, store, peer = self.serve()
        raw = bytes(peer.image["data"][:9]) + b"PAD" + bytes(peer.image["data"][9:]) + b"END"
        peer.image.update(step=12, data=list(raw))
        command_id = canonical.ulid()
        first = client.invoke(IMAGE, {"camera": "color"}, device_id=device, command_id=command_id)
        self.assertEqual(first["status"], "completed", first)
        desc = copy.deepcopy(first["artifacts"][0])
        blob = client.read_artifact(desc["uri"], session_id=first["session_id"])["data"]
        self.assertEqual(self.pixels(blob), ((3, 2), rgb_from_bgr(raw, 3, 2, 12)))
        captures = sum(x.get("topic") == "/image" and x["op"] == "subscribe" for x in peer.sent)
        peer.image["header"]["stamp"]["sec"] = 999
        replay = client.invoke(IMAGE, {"camera": "color"}, device_id=device, command_id=command_id)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["artifacts"], [desc])
        self.assertEqual(sum(x.get("topic") == "/image" and x["op"] == "subscribe" for x in peer.sent), captures)
        self.assertEqual(len(store._grants), 1)

    def test_complete_calibration_including_roi_and_distinct_header(self):
        _, client, device, _, peer = self.serve()
        expected = peer.camera_info()
        expected["header"]["stamp"] = {"sec": 11, "nanosec": 987654321}
        expected["roi"] = {"x_offset": 3, "y_offset": 5, "height": 200, "width": 400, "do_rectify": True}
        peer.camera_info_override = copy.deepcopy(expected)
        receipt = client.invoke(CALIBRATION, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"camera_info": expected})
        image = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        self.assertEqual(image["status"], "completed", image)
        actual = image["artifacts"][0]["x-vendor"]["openmhs.ros_image"]["header"]
        self.assertEqual(actual, peer.image["header"])
        self.assertNotEqual(actual, expected["header"])
        self.assertNotIn("synchronized", receipt["output"])

    def test_uncalibrated_zero_matrices_and_different_geometry_are_not_rewritten(self):
        _, client, device, _, peer = self.serve()
        info = peer.camera_info()
        info.update(width=640, height=480, d=[], k=[0.0]*9, r=[0.0]*9, p=[0.0]*12)
        info["header"]["stamp"] = {"sec": -1, "nanosec": 0}
        peer.camera_info_override = info
        receipt = client.invoke(CALIBRATION, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["camera_info"], info)

    def test_malformed_calibration_shapes_types_and_wire_ranges_are_refused(self):
        _, client, device, store, peer = self.serve()
        mutations = [
            lambda d: d.pop("roi"), lambda d: d.update(k=[0.0]*8), lambda d: d.update(r=[0.0]*10),
            lambda d: d.update(p=[0.0]*11), lambda d: d.update(d=[0.0]*65), lambda d: d.update(width=True),
            lambda d: d.update(height=-1), lambda d: d.update(binning_y=2**32),
            lambda d: d["roi"].update(x_offset=-1), lambda d: d["roi"].update(do_rectify=1),
            lambda d: d["header"]["stamp"].update(nanosec=1_000_000_000),
            lambda d: d["header"]["stamp"].update(sec=2**31),
            lambda d: d["header"].update(frame_id="é"*129),
            lambda d: d["header"].update(frame_id="bad\x00frame"),
            lambda d: d.update(k=[True]*9), lambda d: d.update(extra="not a CameraInfo field"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                info = peer.camera_info(); mutate(info); peer.camera_info_override = info
                receipt = client.invoke(CALIBRATION, {}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertIsNone(receipt["output"])
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
                self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_invalid_image_or_header_never_grants_an_artifact(self):
        _, client, device, store, peer = self.serve()
        original = copy.deepcopy(peer.image)
        mutations = [lambda d: d.update(encoding="32FC1"), lambda d: d.update(step=2),
                     lambda d: d.update(data=[1, 2]), lambda d: d.update(width=0),
                     lambda d: d.pop("header"), lambda d: d["header"]["stamp"].update(nanosec=True),
                     lambda d: d["header"].update(frame_id="bad\x00frame")]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                peer.image = copy.deepcopy(original); mutate(peer.image)
                receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertIsNone(receipt["output"])
                self.assertNotIn("artifacts", receipt)
                self.assertEqual(store._grants, {})
                self.assertEqual(store._total_bytes, 0)

    def test_default_store_refuses_full_noncompressible_sample_without_grants(self):
        _, client, device, store, peer = self.serve()
        raw = random.Random(1729).randbytes(1280*720*3)
        peer.image.update(width=1280, height=720, step=3840, data=base64.b64encode(raw).decode())
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
        self.assertEqual(store._grants, {})
        self.assertEqual(store._total_bytes, 0)

    def test_no_store_and_unknown_selector_refuse_before_image_subscription(self):
        driver = load_driver(HERE, "fake"); self.addCleanup(driver.close)
        with self.assertRaises(MHSError): driver.call(IMAGE, {"camera": "color"})
        self.assertFalse(any(x.get("topic") == "/image" for x in driver.native.sent))
        _, client, device, store, peer = self.serve()
        for args in ({}, {"camera": "depth"}, {"camera": "color", "topic": "/other"}):
            receipt = client.invoke(IMAGE, args, device_id=device)
            self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertFalse(any(x.get("topic") == "/image" for x in peer.sent))
        self.assertEqual(store._grants, {})

    def test_session_principal_expiry_and_close_keep_owned_resource_boundary(self):
        now = [0.0]
        tokens = {"alice-token": {"id": "alice", "kind": "agent"}, "bob-token": {"id": "bob", "kind": "agent"}}
        server, client, device, store, _ = self.serve(tokens=tokens, store_options={"ttl_s": 1, "clock": lambda: now[0]})
        first = client.invoke(IMAGE, {"camera": "color"}, device_id=device)
        self.assertEqual(first["status"], "completed", first)
        uri = first["artifacts"][0]["uri"]
        bob = MHSClient(InProcessTransport(server, auth_token="bob-token")); bob.hello()
        with self.assertRaises(MHSError): bob.read_artifact(uri, session_id=first["session_id"])
        now[0] = 2
        with self.assertRaises(MHSError): client.read_artifact(uri, session_id=first["session_id"])
        root = store._root
        close_server(server)
        self.assertFalse(root.exists())
        self.assertEqual(store._grants, {})

    def test_cancel_pending_capture_and_late_packet_never_publish(self):
        server, client, device, store, peer = self.serve()
        peer.silent_topics.add("/image")
        entered = threading.Event(); requests = []; original = peer.handler
        def handler(request):
            if request.get("op") == "subscribe" and request.get("topic") == "/image":
                requests.append(copy.deepcopy(request)); entered.set()
            return original(request)
        peer.handler = handler
        early = client.invoke(IMAGE, {"camera": "color"}, device_id=device, deadline_ms=10)
        self.assertTrue(entered.wait(1), early)
        operation = server._operations[early["operation_id"]]
        client.cancel(early["operation_id"], deadline_ms=100)
        self.assertTrue(operation.done.wait(2))
        self.assertIn(operation.final_receipt["status"], ("cancelled", "failed"))
        peer.feed({"op": "publish", "topic": "/image", "id": requests[0]["id"], "msg": copy.deepcopy(peer.image)})
        self.assertEqual(store._grants, {})
        self.assertTrue(any(x.get("op") == "unsubscribe" and x.get("id") == requests[0]["id"] for x in peer.sent))

    def test_nonfinite_calibration_wire_data_is_refused_without_fabrication(self):
        # RecordingRosTransport enforces strict finite JSON at the wire boundary.
        # A refused injected reply must not become a valid calibration result.
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=str(value)):
                server, client, device, store, peer = self.serve()
                info = peer.camera_info(); info["d"][0] = value
                peer.camera_info_override = info
                receipt = client.invoke(CALIBRATION, {}, device_id=device)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
                self.assertIsNone(receipt["output"])
                self.assertNotIn("artifacts", receipt)
                self.assertEqual(store._grants, {})
                close_server(server)

    def test_close_wakes_pending_capture_and_releases_all_owned_artifacts(self):
        server, client, device, store, peer = self.serve()
        peer.silent_topics.add("/image")
        entered = threading.Event(); original = peer.handler
        def handler(request):
            if request.get("op") == "subscribe" and request.get("topic") == "/image":
                entered.set()
            return original(request)
        peer.handler = handler
        early = client.invoke(IMAGE, {"camera": "color"}, device_id=device, deadline_ms=10)
        self.assertTrue(entered.wait(1), early)
        operation = server._operations[early["operation_id"]]
        root = store._root
        # Endpoint close ends evidence recording immediately; it is not the
        # session cancellation path. Require worker retirement/no publication,
        # matching the stock SDK close contract, not a receipt after log close.
        with self.assertLogs("mhs.server", level="ERROR"):
            close_server(server)
            self.assertTrue(operation.done.wait(1))
        self.assertEqual(operation.state, "failed")
        self.assertIsNone(operation.final_receipt)
        self.assertFalse(root.exists())
        self.assertEqual(store._grants, {})
        self.assertTrue(peer.closed)

    def test_unsigned_hardware_refuses_before_any_native_connection(self):
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
