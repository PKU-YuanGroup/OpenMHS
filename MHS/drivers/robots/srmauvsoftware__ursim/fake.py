"""ROS-free canned fake for the pinned URSim Unity ROS 1 observations.

The fake models the subscribe/publish traffic that ``RosDriver`` actually
sends and receives for the declared ``/depth``, ``/imu/HeadingTrue_degree``
and ``/imu/data`` topics.  It is a canned stand-in, not a recording of
captured traffic and not the upstream Unity simulator: no scene, physics or
ROS graph runs here.  Every canned sample and negative switch below is test
data, marked ``# placeholder``; none is a device fact, a Limit or a reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_DEPTH = "/depth"
_HEADING = "/imu/HeadingTrue_degree"
_IMU = "/imu/data"

_ZERO_COVARIANCE = [0.0] * 9  # placeholder


class FakeUrsim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.depth = 12.5              # placeholder
        self.heading_deg = 87.0        # placeholder
        self.imu = {                   # placeholder sample
            "header": {
                "seq": 1,             # placeholder
                "stamp": {"secs": 12, "nsecs": 340000000},  # placeholder
                "frame_id": "imu",    # placeholder
            },
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            "orientation_covariance": list(_ZERO_COVARIANCE),
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            "angular_velocity_covariance": list(_ZERO_COVARIANCE),
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            "linear_acceleration_covariance": list(_ZERO_COVARIANCE),
        }
        self.silent = False            # placeholder negative-path switch
        self.wrong_id = False          # placeholder negative-path switch
        self.malformed = False         # placeholder negative-path switch

    def _sample(self, topic, ident):
        if self.malformed:
            return {"op": "publish", "topic": topic, "id": ident, "msg": {}}  # placeholder
        if topic == _DEPTH:
            return {"op": "publish", "topic": topic, "id": ident, "msg": {"data": self.depth}}
        if topic == _HEADING:
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": {"data": self.heading_deg}}  # placeholder
        if topic == _IMU:
            return {"op": "publish", "topic": topic, "id": ident,
                    "msg": dict(self.imu)}  # placeholder copy
        return None

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            ident = message.get("id")
            if self.silent:
                return None
            if self.wrong_id:
                return self._sample(topic, "not-the-subscription")  # placeholder wrong id
            if topic in (_DEPTH, _HEADING, _IMU) and isinstance(ident, str) and ident:
                return self._sample(topic, ident)
            return None
        if operation in ("unsubscribe", "advertise", "unadvertise"):
            return None
        return None
