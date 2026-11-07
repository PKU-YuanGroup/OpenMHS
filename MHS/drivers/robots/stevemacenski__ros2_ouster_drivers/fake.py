"""ROS-free recording fake for the pinned Ouster PointCloud2 publication.

The fake answers the same rosbridge subscribe operation the bridge sends for
the declared ``sensor_msgs/msg/PointCloud2`` topic and returns a native-shaped
message with exactly the standard PointCloud2 members.  Every value below is
test data, not a device fact or a lidar measurement.
"""

import base64
import struct

from mhs.bridge.ros_transport import RecordingRosTransport

# Test data only: the values describe the fake's one-point sample, never a
# real lidar's dimensions, geometry, frame or measurement.
_TOPIC = "/points"                     # the launch-default resolution of the relative points topic
_FRAME_ID = "laser_data_frame"         # placeholder
_STAMP_SEC = 1234                      # placeholder
_STAMP_NANOSEC = 567000000             # placeholder
_POINT_X = 1.0                         # placeholder
_POINT_Y = 2.0                         # placeholder
_POINT_Z = 3.0                         # placeholder
_POINT_STEP = 12                       # placeholder: three float32 values
_ROW_STEP = 12                         # placeholder: one point per row
_FIELDS = [                            # placeholder layout of one XYZ point
    {"name": "x", "offset": 0, "datatype": 7, "count": 1},
    {"name": "y", "offset": 4, "datatype": 7, "count": 1},
    {"name": "z", "offset": 8, "datatype": 7, "count": 1},
]


class FakeOusterLidar(RecordingRosTransport):
    """In-memory rosbridge peer for the declared PointCloud2 subscription."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.sample_count = 0                          # placeholder counter
        self.silent = bool(_options.get("silent", False))        # placeholder negative-path switch
        self.malformed = bool(_options.get("malformed", False))  # placeholder negative-path switch

    def _pointcloud(self):
        self.sample_count += 1
        nanosec = (_STAMP_NANOSEC + self.sample_count * 1000000) % 1000000000  # placeholder
        data = base64.b64encode(
            struct.pack("<fff", _POINT_X, _POINT_Y, _POINT_Z)  # placeholder point coordinates
        ).decode("ascii")
        return {
            "header": {
                "stamp": {"sec": _STAMP_SEC, "nanosec": nanosec},  # placeholder
                "frame_id": _FRAME_ID,                              # placeholder
            },
            "height": 1,                # placeholder
            "width": 1,                 # placeholder
            "fields": list(_FIELDS),    # placeholder
            "is_bigendian": False,
            "point_step": _POINT_STEP,  # placeholder
            "row_step": _ROW_STEP,      # placeholder
            "data": data,               # placeholder sample bytes
            "is_dense": True,
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        if message.get("topic") != _TOPIC:
            return None
        if self.silent:
            return None
        if self.malformed:
            # A mapping without the exact standard PointCloud2 members must be
            # refused by the bridge's point-cloud conversion, not repaired.
            return {
                "op": "publish",
                "topic": _TOPIC,
                "id": message.get("id"),
                "msg": {"header": {"frame_id": _FRAME_ID}},  # placeholder malformed sample
            }
        return {
            "op": "publish",
            "topic": _TOPIC,
            "id": message.get("id"),
            "msg": self._pointcloud(),
        }
