"""ROS-free recording fake for the TrackIMU ROS 2 publisher.

The fake models the pinned wire contract of ``ros2_track_imu``: a
``sensor_msgs/msg/Imu`` publication on the resolved ``/imu`` topic.  It opens
no serial port, starts no ROS node and runs no AHRS or serial loop.  Every
value below is test data, not a device fact or a bound.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRos2TrackImu(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.frame_id = "base_imu_link"                 # placeholder
        self.stamp_sec = 12                             # placeholder
        self.stamp_nanosec = 340000000                  # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.linear_acceleration = {"x": 0.0, "y": 0.0, "z": 0.0}    # placeholder
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}       # placeholder

        # Negative-path switches used by the repository tests.
        self.silent = False          # placeholder: emit no publication
        self.wrong_id = False        # placeholder: emit an unrelated subscription id
        self.fail_subscribe = False  # placeholder: simulate a broken transport link
        self.malformed = None        # placeholder: omit or corrupt one message field

        self.subscriptions = 0       # placeholder counter
        self.last_subscribe = None   # placeholder echo of the received request

    def _message(self):
        message = {
            "header": {
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},  # placeholder
                "frame_id": self.frame_id,
            },
            "orientation": dict(self.orientation),
            # The pinned node sets these covariance diagonals; in this fake
            # they are placeholder wire content only.
            "orientation_covariance": [0.0025, 0.0, 0.0, 0.0, 0.0025, 0.0, 0.0, 0.0, 0.0025],  # placeholder
            "angular_velocity": dict(self.angular_velocity),
            "angular_velocity_covariance": [0.02, 0.0, 0.0, 0.0, 0.02, 0.0, 0.0, 0.0, 0.02],  # placeholder
            "linear_acceleration": dict(self.linear_acceleration),
            "linear_acceleration_covariance": [0.04, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0, 0.0, 0.04],  # placeholder
        }
        if self.malformed == "missing_header":
            message.pop("header")
        elif self.malformed == "missing_orientation":
            message.pop("orientation")
        elif self.malformed == "missing_linear_acceleration":
            message.pop("linear_acceleration")
        elif self.malformed == "missing_angular_velocity":
            message.pop("angular_velocity")
        elif self.malformed == "string_orientation":
            message["orientation"]["x"] = "not-a-number"  # placeholder
        elif self.malformed == "bad_stamp":
            message["header"]["stamp"] = {"sec": "not-an-integer", "nanosec": 0}  # placeholder
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions += 1
        self.last_subscribe = dict(message)
        if message.get("topic") != "/imu":
            return None
        if self.fail_subscribe:
            raise ConnectionError("simulated /imu subscription failure")  # placeholder
        if self.silent:
            return None
        event = {
            "op": "publish",
            "topic": "/imu",
            "id": message.get("id"),
            "msg": self._message(),
        }
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event
