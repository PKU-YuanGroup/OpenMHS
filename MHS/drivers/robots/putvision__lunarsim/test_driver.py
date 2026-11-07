"""Acceptance run of the LunarSim ROS package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DRIVE = "x-cap.putvision.cmd_vel.v1"
POSE = "x-cap.putvision.gt_pose.v1"
IMU = "x-cap.putvision.imu.v1"
IMAGE = "cap.sensing.image.v1"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"

#: An example operator overlay; these values are test data, not device facts.
SITE_LIMITS = {
    "$schema": "https://mhs.openai4s.org/schema/0.9/site-limits.schema.json",
    "openmhs": "0.9",
    "site": "LunarSim unit-test overlay",
    "issued_by": {"id": "operator:unit-test"},
    "devices": {
        "mhs://localhost/lunarsim": {
            DRIVE: {
                "linear_velocity": {"min": -1.0, "max": 1.0, "unit": "m/s",
                                    "source": "operator", "reason": "unit-test example envelope"},
                "angular_velocity": {"min": -1.0, "max": 1.0, "unit": "rad/s",
                                     "source": "operator", "reason": "unit-test example envelope"},
            },
        },
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LunarSimCases(unittest.TestCase):
    def serve(self, *, site_limits=None, artifact_store=None):
        options = {"artifact_store": artifact_store} if artifact_store is not None else {}
        server = load(HERE, backend="fake", site_limits=site_limits, **options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_drive_publication_reaches_cmd_vel(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(DRIVE, {"linear_velocity": 0.2, "angular_velocity": 0.1})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_twist["linear"]["x"], 0.2)
        self.assertEqual(driver.native.last_twist["angular"]["z"], 0.1)

    def test_operator_required_velocity_bounds_refuse_until_the_overlay_is_supplied(self) -> None:
        client = self.serve()
        refused = client.invoke(DRIVE, {"linear_velocity": 0.2, "angular_velocity": 0.1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET)
        self.assertIsNone(refused.get("output"))

    def test_the_pose_observation_returns_the_documented_fields(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(POSE, {})
        self.assertEqual(output["frame_id"], "map")
        self.assertEqual(set(output["position"]), {"x", "y", "z"})
        self.assertEqual(set(output["orientation"]), {"x", "y", "z", "w"})
        self.assertEqual(set(output["stamp"]), {"sec", "nanosec"})

    def test_the_imu_observation_is_converted_to_the_catalogue_arrays(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(IMU, {"frame": "body"})
        self.assertEqual(output["linear_acceleration"], [0.0, 0.0, 9.81])
        self.assertEqual(output["angular_velocity"], [0.0, 0.0, 0.1])
        self.assertEqual(output["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertTrue(output["sampled_at"].endswith("Z"))

    def test_a_raw_camera_capture_returns_an_image_artifact(self) -> None:
        store = LocalArtifactStore()
        client = self.serve(artifact_store=store)
        receipt = client.invoke(IMAGE, {"camera": "left"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["width"], 4)
        self.assertEqual(receipt["output"]["height"], 2)
        self.assertTrue(receipt["output"]["image_ref"].startswith("mhs+artifact://"))

    def test_the_stock_estop_reports_the_missing_stop_path(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)


if __name__ == "__main__":
    unittest.main()
