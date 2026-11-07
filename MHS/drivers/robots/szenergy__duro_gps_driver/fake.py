"""ROS-free recording fake for the Duro Inertial GPS ROS 1 topic surface.

The fake models only the pinned wire contract: the nine README topic
publishers and the upstream validity gating.  It opens no socket, starts no
ROS node and runs no SBP decoder or navigation filter.  Every stored value,
frame id and canned reply below is test data, not a device fact, a physical
limit or a valid-position claim.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport


_FIX_MODE_TEXT = {
    0: "Invalid",
    1: "Single Point Position (SPP)",
    2: "Differential GNSS (DGNSS)",
    3: "Float RTK",
    4: "Fixed RTK",
    5: "Dead Reckoning (DR)",
    6: "SBAS Position",
}  # placeholder: canned status text for the fake's mode switch


class FakeDuroGpsDriver(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fix_mode = 4                      # placeholder test mode
        self.imu_ready = True                  # placeholder: IMU_AUX received
        self.silent_topics = set()             # placeholder negative-path switch
        self.wrong_id_topics = set()           # placeholder negative-path switch
        self.fail_topics = set()               # placeholder negative-path switch
        self.samples = self._make_samples()    # placeholder canned messages

    @staticmethod
    def _header(frame_id: str) -> dict:
        return {
            "seq": 7,                          # placeholder
            "stamp": {"secs": 100, "nsecs": 123456789},  # placeholder
            "frame_id": frame_id,
        }

    def _make_samples(self) -> dict:
        orientation = {"x": 0.1, "y": 0.2, "z": 0.3, "w": 0.92736185}  # placeholder
        position = {"x": 697214.762607, "y": 5285721.97968, "z": 0.0}  # placeholder
        return {
            "/fix": {
                "header": self._header("test_duro_link"),
                "status": {"status": 2, "service": 0},  # placeholder
                "latitude": 47.123456,     # placeholder
                "longitude": 19.987654,    # placeholder
                "altitude": 123.45,        # placeholder
                "position_covariance": [
                    0.0004, 0.0, 0.0,
                    0.0, 0.0004, 0.0,
                    0.0, 0.0, 0.0016,
                ],                         # placeholder
                "position_covariance_type": 2,  # placeholder
            },
            "/imu": {
                "header": self._header("test_duro_link"),
                "orientation": orientation,
                "orientation_covariance": [0.0] * 9,  # placeholder default
                "angular_velocity": {"x": 0.01745, "y": -0.0349, "z": 0.05235},  # placeholder
                "angular_velocity_covariance": [0.0] * 9,  # placeholder default
                "linear_acceleration": {"x": 9.80665, "y": -4.903325, "z": 2.4516625},  # placeholder
                "linear_acceleration_covariance": [0.0] * 9,  # placeholder default
            },
            "/mag": {
                "header": self._header("test_duro_link"),
                "magnetic_field": {"x": 0.000012, "y": -0.000023, "z": 0.000034},  # placeholder
                "magnetic_field_covariance": [0.0] * 9,  # placeholder default
            },
            "/time_ref": {
                "header": self._header("test_ros_time"),
                "time_ref": {"secs": 101, "nsecs": 987654321},  # placeholder
                "source": "gps_duro",      # placeholder canned source label
            },
            "/status_flag": {"data": 4},  # placeholder, refreshed from fix_mode
            "/status_string": {"data": "Fixed RTK"},  # placeholder, refreshed from fix_mode
            "/current_pose": {
                "header": self._header("test_utm"),
                "pose": {"position": dict(position), "orientation": dict(orientation)},
            },
            "/odom": {
                "header": self._header("test_utm"),
                "child_frame_id": "test_duro_link",
                # nav_msgs/Odometry nests PoseWithCovariance and TwistWithCovariance
                # (the node writes odom.pose.pose.position, src/duro.cpp:173-175).
                "pose": {
                    "pose": {
                        "position": dict(position),
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},  # placeholder publisher default
                    },
                    "covariance": [0.0] * 36,  # placeholder default
                },
                "twist": {
                    "twist": {
                        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder default
                        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder default
                    },
                    "covariance": [0.0] * 36,  # placeholder default
                },
            },
            "/rollpitchyaw": {"x": 0.01, "y": -0.02, "z": 0.03},  # placeholder
        }

    def _navsat_status(self) -> int:
        if self.fix_mode == 1:
            return 0                           # placeholder: STATUS_FIX
        if self.fix_mode in (2, 3, 4):
            return 2                           # placeholder: STATUS_GBAS_FIX
        if self.fix_mode == 6:
            return 1                           # placeholder: STATUS_SBAS_FIX
        return -1                              # placeholder: STATUS_NO_FIX

    def _mode_text(self) -> str:
        return _FIX_MODE_TEXT.get(self.fix_mode, "Not implemented")

    def _message(self, topic: str) -> dict | None:
        if topic == "/imu" and not self.imu_ready:
            return None
        if topic in ("/fix", "/current_pose", "/odom") and self.fix_mode <= 0:
            return None
        sample = copy.deepcopy(self.samples.get(topic))
        if sample is None:
            return None
        if topic == "/fix":
            sample["status"]["status"] = self._navsat_status()
        if topic == "/status_flag":
            sample["data"] = self.fix_mode
        if topic == "/status_string":
            sample["data"] = self._mode_text()
        return sample

    def _respond(self, message):
        if message.get("op") != "subscribe":
            # advertise, unadvertise and unsubscribe need no fake reply.
            return None
        topic = message.get("topic")
        if topic in self.silent_topics:
            return None
        if topic in self.fail_topics:
            raise ConnectionError("simulated ROS transport failure")  # placeholder
        payload = self._message(topic)
        if payload is None:
            return None
        event = {"op": "publish", "topic": topic, "id": message.get("id"), "msg": payload}
        if topic in self.wrong_id_topics:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event
