"""Acceptance run of the src_dog package: the gate plus cases specific to this repository.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SrcDogCases(unittest.TestCase):
    def serve(self, overlay=False):
        site_limits = None
        if overlay:
            site_limits = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_reads_return_the_published_placeholders(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(len(state["joint_positions"]), 12)
        self.assertEqual(set(state["base_position"]), {"x", "y", "z"})
        self.assertEqual(set(state["imu_orientation"]), {"x", "y", "z", "w"})
        self.assertEqual(set(state["imu_angular_velocity"]), {"x", "y", "z"})
        self.assertEqual(set(state["imu_linear_acceleration"]), {"x", "y", "z"})

    def test_the_operator_required_frame_is_refused_without_an_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.sqrt81.joint_pd.v1", {"data": [0.0] * 60}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_overlay_allows_a_publication(self) -> None:
        client = self.serve(overlay=True)
        receipt = client.invoke("x-cap.sqrt81.joint_pd.v1", {"data": [0.0] * 60}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})

    def test_the_flat_frame_reaches_the_ros_transport(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        frame = [float(i) / 100.0 for i in range(60)]  # placeholder test frame
        self.assertEqual(driver.call("x-cap.sqrt81.joint_pd.v1", {"data": frame}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.publish_count, 1)
        self.assertEqual(driver.native.last_command, {"data": frame})

    def test_a_malformed_joint_state_fails_the_read(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.wrong_joint_state = True
        with self.assertRaises(Exception) as caught:
            driver.read("main", ["joint_positions"])
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.RESOURCE.STATE_INVALID")

    def test_no_acknowledged_stop_is_reported(self) -> None:
        client = self.serve(overlay=True)
        receipt = client.estop("test: no stop service in the clone", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(receipt["output"]["estop"], "software_only")
        refused = client.invoke("x-cap.sqrt81.joint_pd.v1", {"data": [0.0] * 60}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
