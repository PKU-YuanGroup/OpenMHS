"""Acceptance run of the Ouster OS-x ROS 2 point-cloud package.

The suite keeps the stock ``check_driver`` case and adds package-specific
positive and negative recording-fake cases.  No ROS graph, lidar or hardware
is contacted.
"""

import io
import json
import struct
import unittest
import zipfile
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.artifacts import LocalArtifactStore
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
POINTS = "cap.sensing.point_cloud.v1"
ENDPOINT = "/points"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OusterLidarCases(unittest.TestCase):
    def serve(self, **options):
        store = LocalArtifactStore()
        server = load(HERE, backend="fake", options=options or None, artifact_store=store)
        self.addCleanup(store.close)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.server = server
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_a_capture_returns_a_bounded_artifact_and_its_native_frame(self) -> None:
        client = self.serve()
        receipt = client.invoke(POINTS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["point_count"], 1)
        self.assertEqual(output["frame"], "laser_data_frame")
        self.assertTrue(output["artifact_ref"].startswith("mhs+artifact://"))
        artifact = receipt["artifacts"][0]
        self.assertEqual(artifact["media_type"], "application/zip")
        descriptor = artifact["x-vendor"]["openmhs.ros_point_cloud"]
        self.assertEqual(descriptor["format"], "openmhs.ros-pointcloud2.v1")
        self.assertEqual(descriptor["topic"], ENDPOINT)
        self.assertEqual(descriptor["type"], "sensor_msgs/msg/PointCloud2")
        self.assertEqual(descriptor["ros_version"], 2)
        self.assertEqual(descriptor["header"]["frame_id"], "laser_data_frame")

    def test_the_artifact_contains_the_complete_received_pointcloud(self) -> None:
        client = self.serve()
        receipt = client.invoke(POINTS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        artifact = self.server.read_artifact(receipt["output"]["artifact_ref"],
                                             session_id=self.ids["session_id"])
        archive = zipfile.ZipFile(io.BytesIO(artifact["data"]))
        self.assertEqual(archive.namelist(), ["pointcloud.json", "data.bin"])
        manifest = json.loads(archive.read("pointcloud.json"))
        self.assertEqual(manifest["format"], "openmhs.ros-pointcloud2.v1")
        self.assertEqual(manifest["width"], 1)
        self.assertEqual(manifest["height"], 1)
        self.assertEqual(manifest["point_step"], 12)
        self.assertEqual([field["name"] for field in manifest["fields"]], ["x", "y", "z"])
        data = archive.read("data.bin")
        self.assertEqual(len(data), 12)
        self.assertEqual(struct.unpack("<fff", data), (1.0, 2.0, 3.0))

    def test_each_capture_subscribes_again_with_the_declared_type(self) -> None:
        client = self.serve()
        first = client.invoke(POINTS, {}, **self.ids)
        second = client.invoke(POINTS, {}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        device_id = self.ids["device_id"]
        sent = self.server.devices[device_id].bridge.native.sent
        subscriptions = [message for message in sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscriptions), 2)
        for message in subscriptions:
            self.assertEqual(message["topic"], ENDPOINT)
            self.assertEqual(message["type"], "sensor_msgs/msg/PointCloud2")
            self.assertEqual(message["queue_length"], 1)
        self.assertNotEqual(first["artifacts"][0]["digest"], second["artifacts"][0]["digest"])

    def test_a_silent_publisher_times_out_without_inventing_a_cloud(self) -> None:
        client = self.serve(silent=True)
        receipt = client.invoke(POINTS, {}, deadline_ms=80, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})
        self.assertIsNone(receipt.get("output"))

    def test_a_malformed_pointcloud_is_refused_before_publication(self) -> None:
        client = self.serve(malformed=True)
        receipt = client.invoke(POINTS, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))
        self.assertFalse(receipt.get("artifacts"))


if __name__ == "__main__":
    unittest.main()
