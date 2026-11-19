"""Acceptance run of the MRPT Taobotics IMU package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The other cases run on the fake backend (fake.py); nothing here
touched a serial device, the MRPT Python binding or an IMU.  The fake's measurements and sample time are
placeholders.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAP = "cap.sensing.imu.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TaoboticsImuCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.imu = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return self.client

    def read_imu(self, frame="body"):
        return self.client.invoke(CAP, {"frame": frame}, **self.ids)

    def test_a_read_returns_the_three_vectors_and_a_timestamp(self) -> None:
        self.serve()
        receipt = self.read_imu()
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["linear_acceleration"], [1.0, 2.0, 3.0])
        self.assertEqual(output["angular_velocity"], [0.1, 0.2, 0.3])
        self.assertTrue(output["sampled_at"].endswith("Z"))
        self.assertEqual(output["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})

    def test_the_world_frame_rotates_the_body_vectors(self) -> None:
        self.serve()
        half = math.sqrt(0.5)
        self.imu._set_measurements(acceleration=(0.0, 0.0, 1.0), angular=(0.0, 0.0, 1.0),
                                   quaternion=(0.0, half, 0.0, half))     # placeholder: a +90 deg pitch
        receipt = self.read_imu("world")
        self.assertEqual(receipt["status"], "completed", receipt)
        acceleration = receipt["output"]["linear_acceleration"]
        self.assertAlmostEqual(acceleration[0], 1.0, places=9)
        self.assertAlmostEqual(acceleration[1], 0.0, places=9)
        self.assertAlmostEqual(acceleration[2], 0.0, places=9)
        angular = receipt["output"]["angular_velocity"]
        self.assertAlmostEqual(angular[0], 1.0, places=9)
        self.assertAlmostEqual(angular[1], 0.0, places=9)
        self.assertAlmostEqual(angular[2], 0.0, places=9)

    def test_a_frame_outside_the_enum_is_refused_before_the_native_call(self) -> None:
        self.serve()
        refused = self.read_imu("sensor")
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", refused)


if __name__ == "__main__":
    unittest.main()
