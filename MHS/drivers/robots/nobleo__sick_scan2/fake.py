"""ROS-free recording fake for the pinned SICK scan2 LaserScan publication.

The fake answers the same rosbridge subscribe operation the bridge sends for
the declared ``sensor_msgs/msg/LaserScan`` topic and returns a native-shaped
message with the fields a ``sensor_msgs/msg/LaserScan`` carries.  Every number
below is test data, not a device fact or a scanner limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

# Test data only: the values below describe the fake's one-sample observation,
# never a real scanner's geometry, range or sample budget.
_FRAME_ID = "world"                    # placeholder
_STAMP_SEC = 1234                     # placeholder
_STAMP_NANOSEC = 567000000            # placeholder
_ANGLE_MIN = -0.5                     # placeholder
_ANGLE_MAX = 0.5                      # placeholder
_ANGLE_INCREMENT = 0.25               # placeholder
_TIME_INCREMENT = 0.0001             # placeholder
_SCAN_TIME = 0.05                    # placeholder
_RANGE_MIN = 0.05                    # placeholder
_RANGE_MAX = 100.0                   # placeholder
_RANGES = [
    0.5,                              # placeholder
    0.75,                             # placeholder
    1.0,                              # placeholder
    1.25,                             # placeholder
    1.5,                              # placeholder
]                                     # placeholder
_INTENSITIES = [
    10.0,                             # placeholder
    20.0,                             # placeholder
    30.0,                             # placeholder
    40.0,                             # placeholder
    50.0,                             # placeholder
]                                     # placeholder


class FakeSickScan2(RecordingRosTransport):
    """In-memory rosbridge peer for the declared LaserScan subscription."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.nonfinite = bool(_options.get("nonfinite", False))  # placeholder negative-path switch
        self.scan_count = 0              # placeholder
        self.silent = bool(_options.get("silent", False))        # placeholder negative-path switch
        self.malformed = bool(_options.get("malformed", False))  # placeholder negative-path switch

    def _scan_message(self):
        self.scan_count += 1
        nanosec = (_STAMP_NANOSEC + self.scan_count * 1000000) % 1000000000  # placeholder
        return {
            "header": {
                "stamp": {"sec": _STAMP_SEC, "nanosec": nanosec},  # placeholder
                "frame_id": _FRAME_ID,                              # placeholder
            },
            "angle_min": _ANGLE_MIN,                                # placeholder
            "angle_max": _ANGLE_MAX,                                # placeholder
            "angle_increment": _ANGLE_INCREMENT,                    # placeholder
            "time_increment": _TIME_INCREMENT,                      # placeholder
            "scan_time": _SCAN_TIME,                                # placeholder
            "range_min": _RANGE_MIN,                                # placeholder
            "range_max": _RANGE_MAX,                                # placeholder
            "ranges": [float("inf"), *_RANGES[1:]] if self.nonfinite else list(_RANGES),                                # placeholder
            "intensities": list(_INTENSITIES),                      # placeholder
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        if message.get("topic") != "/scan":
            return None
        if self.silent:
            return None
        if self.malformed:
            # The wire message is a mapping but lacks the declared fields; the
            # bridge's output mapping must refuse it rather than invent a scan.
            return {
                "op": "publish",
                "topic": "/scan",
                "id": message.get("id"),
                "msg": {"header": {"frame_id": _FRAME_ID}},  # placeholder
            }
        return {
            "op": "publish",
            "topic": "/scan",
            "id": message.get("id"),
            "msg": self._scan_message(),
        }
