"""Acceptance run of the Duro Inertial GPS package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent

FIX = "x-cap.szenergy.fix.v1"
IMU = "x-cap.szenergy.imu.v1"
MAG = "x-cap.szenergy.mag.v1"
TIME_REF = "x-cap.szenergy.time_reference.v1"
STATUS_FLAG = "x-cap.szenergy.fix_status.v1"
STATUS_TEXT = "x-cap.szenergy.fix_status_text.v1"
POSE = "x-cap.szenergy.pose.v1"
ODOM = "x-cap.szenergy.odometry.v1"
ATTITUDE = "x-cap.szenergy.attitude.v1"

OUTPUT_INVALID = {"MHS.CAPABILITY.OUTPUT_INVALID"}
NOT_READY = {"MHS.DEVICE.NOT_READY"}
NON_FINITE_OR_OUTPUT = {"MHS.OUTCOME.UNKNOWN", "MHS.CAPABILITY.OUTPUT_INVALID"}

EXPECTED_SUBSCRIPTIONS = [
    ("/fix", "sensor_msgs/NavSatFix"),
    ("/imu", "sensor_msgs/Imu"),
    ("/mag", "sensor_msgs/MagneticField"),
    ("/time_ref", "sensor_msgs/TimeReference"),
    ("/status_flag", "std_msgs/UInt8"),
    ("/status_string", "std_msgs/String"),
    ("/current_pose", "geometry_msgs/PoseStamped"),
    ("/odom", "nav_msgs/Odometry"),
    ("/rollpitchyaw", "geometry_msgs/Vector3"),
]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DuroGpsCases(unittest.TestCase):
    def setUp(self) -> None:
        self.server = load(HERE, backend="fake")
        self.addCleanup(close_server, self.server)
        self.client = client_for(self.server)
        self.device_id = self.client.hello()["devices"][0]["device_id"]
        self.session_id = self.client.open_session(device_ids=[self.device_id])["session_id"]
        self.native = next(iter(self.server.devices.values())).bridge.native

    def invoke(self, capability_id: str) -> dict:
        return self.client.invoke(
            capability_id, {}, device_id=self.device_id, session_id=self.session_id
        )

    def completed(self, capability_id: str) -> dict:
        receipt = self.invoke(capability_id)
        self.assertEqual(receipt.get("status"), "completed", receipt)
        return receipt["output"]["sample"]

    def refused(self, capability_id: str, codes: set[str]) -> dict:
        receipt = self.invoke(capability_id)
        self.assertIn(receipt.get("status"), {"failed", "unknown"}, receipt)
        self.assertIn((receipt.get("error") or {}).get("mhs_code"), codes, receipt)
        return receipt

    # -- complete native samples -------------------------------------------------

    def test_fix_returns_the_complete_navsatfix_sample(self) -> None:
        sample = self.completed(FIX)
        self.assertEqual(
            set(sample),
            {"header", "status", "latitude", "longitude", "altitude",
             "position_covariance", "position_covariance_type"},
        )
        self.assertEqual(set(sample["header"]), {"seq", "stamp", "frame_id"})
        self.assertEqual(set(sample["header"]["stamp"]), {"secs", "nsecs"})
        self.assertEqual(set(sample["status"]), {"status", "service"})
        self.assertEqual(len(sample["position_covariance"]), 9)
        self.assertEqual(sample["position_covariance_type"], 2)  # placeholder test value
        self.assertEqual(sample["header"]["frame_id"], "test_duro_link")  # placeholder test value

    def test_imu_returns_complete_three_axis_measurements(self) -> None:
        sample = self.completed(IMU)
        self.assertEqual(
            set(sample),
            {"header", "orientation", "orientation_covariance", "angular_velocity",
             "angular_velocity_covariance", "linear_acceleration",
             "linear_acceleration_covariance"},
        )
        for name in ("angular_velocity", "linear_acceleration"):
            self.assertEqual(set(sample[name]), {"x", "y", "z"})
        self.assertEqual(set(sample["orientation"]), {"x", "y", "z", "w"})
        for name in ("orientation_covariance", "angular_velocity_covariance",
                     "linear_acceleration_covariance"):
            self.assertEqual(len(sample[name]), 9)

    def test_mag_returns_the_vector_and_its_covariance(self) -> None:
        sample = self.completed(MAG)
        self.assertEqual(set(sample), {"header", "magnetic_field", "magnetic_field_covariance"})
        self.assertEqual(set(sample["magnetic_field"]), {"x", "y", "z"})
        self.assertEqual(len(sample["magnetic_field_covariance"]), 9)

    def test_time_reference_preserves_source_and_ros1_stamp(self) -> None:
        sample = self.completed(TIME_REF)
        self.assertEqual(set(sample), {"header", "time_ref", "source"})
        self.assertEqual(sample["source"], "gps_duro")
        self.assertEqual(sample["header"]["frame_id"], "test_ros_time")  # placeholder test value
        self.assertEqual(set(sample["time_ref"]), {"secs", "nsecs"})

    def test_pose_returns_utm_position_and_quaternion(self) -> None:
        sample = self.completed(POSE)
        self.assertEqual(set(sample), {"header", "pose"})
        self.assertEqual(set(sample["pose"]["position"]), {"x", "y", "z"})
        self.assertEqual(set(sample["pose"]["orientation"]), {"x", "y", "z", "w"})

    def test_odometry_returns_child_frame_and_full_pose(self) -> None:
        sample = self.completed(ODOM)
        self.assertEqual(set(sample), {"header", "child_frame_id", "pose", "twist"})
        self.assertEqual(sample["child_frame_id"], "test_duro_link")  # placeholder test value
        # nav_msgs/Odometry: pose is PoseWithCovariance, twist is TwistWithCovariance.
        self.assertEqual(set(sample["pose"]), {"pose", "covariance"})
        self.assertEqual(set(sample["pose"]["pose"]), {"position", "orientation"})
        self.assertEqual(sample["pose"]["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0})
        self.assertEqual(len(sample["pose"]["covariance"]), 36)
        self.assertEqual(set(sample["twist"]), {"twist", "covariance"})
        self.assertEqual(set(sample["twist"]["twist"]), {"linear", "angular"})
        self.assertEqual(len(sample["twist"]["covariance"]), 36)

    def test_a_flattened_odometry_pose_is_an_output_error(self) -> None:
        # The pre-review shape (position directly under pose) is not nav_msgs/Odometry.
        odom = self.native.samples["/odom"]
        odom["pose"] = {"position": odom["pose"]["pose"]["position"],
                        "orientation": odom["pose"]["pose"]["orientation"],
                        "covariance": odom["pose"]["covariance"]}
        self.refused(ODOM, OUTPUT_INVALID)

    def test_attitude_returns_three_euler_axes(self) -> None:
        sample = self.completed(ATTITUDE)
        self.assertEqual(set(sample), {"x", "y", "z"})

    def test_status_capabilities_report_the_same_fix_mode(self) -> None:
        flag = self.completed(STATUS_FLAG)
        text = self.completed(STATUS_TEXT)
        self.assertEqual(flag["data"], 4)  # placeholder test value
        self.assertEqual(text["data"], "Fixed RTK")  # placeholder test value

    # -- upstream gating and invalid quality ------------------------------------

    def test_invalid_fix_publishes_status_but_no_navsatfix(self) -> None:
        self.native.fix_mode = 0  # placeholder: invalid mode
        self.refused(FIX, NOT_READY)
        self.refused(POSE, NOT_READY)
        self.refused(ODOM, NOT_READY)
        self.assertEqual(self.completed(STATUS_FLAG)["data"], 0)
        self.assertEqual(self.completed(STATUS_TEXT)["data"], "Invalid")

    def test_dead_reckoning_keeps_the_navsatfix_no_fix_status(self) -> None:
        self.native.fix_mode = 5  # placeholder: dead-reckoning mode
        sample = self.completed(FIX)
        self.assertEqual(sample["status"]["status"], -1)  # STATUS_NO_FIX is a placeholder code
        self.assertEqual(self.completed(STATUS_FLAG)["data"], 5)
        self.assertEqual(self.completed(STATUS_TEXT)["data"], "Dead Reckoning (DR)")

    def test_unsupported_positive_mode_keeps_status_no_fix(self) -> None:
        self.native.fix_mode = 7  # placeholder: unsupported positive mode
        sample = self.completed(FIX)
        self.assertEqual(sample["status"]["status"], -1)  # STATUS_NO_FIX is a placeholder code
        self.assertEqual(self.completed(STATUS_FLAG)["data"], 7)
        self.assertEqual(self.completed(STATUS_TEXT)["data"], "Not implemented")

    def test_imu_is_silent_until_configuration_is_received(self) -> None:
        self.native.imu_ready = False
        self.refused(IMU, NOT_READY)

    # -- endpoint and wire shape -------------------------------------------------

    def test_subscriptions_name_the_declared_ros1_endpoints_and_types(self) -> None:
        for capability_id in (FIX, IMU, MAG, TIME_REF, STATUS_FLAG, STATUS_TEXT, POSE, ODOM, ATTITUDE):
            self.completed(capability_id)
        sent = self.native.sent
        subscriptions = [(message["topic"], message["type"])
                         for message in sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions, EXPECTED_SUBSCRIPTIONS)
        self.assertTrue(all(message.get("queue_length") == 1 for message in sent
                            if message.get("op") == "subscribe"), sent)
        for topic in (topic for topic, _type in EXPECTED_SUBSCRIPTIONS):
            self.assertTrue(any(message.get("op") == "unsubscribe"
                                and message.get("topic") == topic for message in sent), sent)

    def test_no_service_or_command_operation_is_sent(self) -> None:
        for capability_id in (FIX, IMU, MAG, TIME_REF, STATUS_FLAG, STATUS_TEXT, POSE, ODOM, ATTITUDE):
            self.completed(capability_id)
        self.assertTrue({message.get("op") for message in self.native.sent}
                        <= {"subscribe", "unsubscribe"}, self.native.sent)

    def test_the_read_only_resource_state_is_empty_and_needs_no_topic(self) -> None:
        before = len(self.native.sent)
        state = self.client.read("receiver", device_id=self.device_id, session_id=self.session_id)
        self.assertEqual(state["state"], {})
        self.assertEqual(state["revision"], 0)
        self.assertEqual(len(self.native.sent), before)

    # -- malformed, silent and failed observations -------------------------------

    def test_a_missing_covariance_is_an_output_error(self) -> None:
        self.native.samples["/fix"].pop("position_covariance")
        self.refused(FIX, OUTPUT_INVALID)

    def test_a_wrong_covariance_length_is_an_output_error(self) -> None:
        self.native.samples["/fix"]["position_covariance"] = [0.0] * 8  # placeholder bad length
        self.refused(FIX, OUTPUT_INVALID)

    def test_a_boolean_measurement_is_an_output_error(self) -> None:
        self.native.samples["/fix"]["latitude"] = True
        self.refused(FIX, OUTPUT_INVALID)

    def test_a_malformed_stamp_is_an_output_error(self) -> None:
        self.native.samples["/fix"]["header"]["stamp"] = {"secs": "100", "nsecs": 1}
        self.refused(FIX, OUTPUT_INVALID)

    def test_a_non_finite_measurement_is_refused(self) -> None:
        self.native.samples["/fix"]["latitude"] = float("nan")
        self.refused(FIX, NON_FINITE_OR_OUTPUT)

    def test_an_extra_message_field_is_an_output_error(self) -> None:
        self.native.samples["/fix"]["bogus_field"] = 1  # placeholder schema-version mismatch
        self.refused(FIX, OUTPUT_INVALID)

    def test_a_silent_topic_times_out_as_not_ready(self) -> None:
        self.native.silent_topics.add("/mag")
        self.refused(MAG, NOT_READY)

    def test_an_unrelated_subscription_id_is_not_accepted(self) -> None:
        self.native.wrong_id_topics.add("/time_ref")
        self.refused(TIME_REF, NOT_READY)

    def test_a_transport_failure_is_not_reported_as_completed(self) -> None:
        self.native.fail_topics.add("/imu")
        receipt = self.invoke(IMU)
        self.assertIn(receipt.get("status"), {"failed", "unknown"}, receipt)
        self.assertNotEqual(receipt.get("status"), "completed")
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()
