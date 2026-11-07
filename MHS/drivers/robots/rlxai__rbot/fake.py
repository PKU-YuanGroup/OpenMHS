"""ROS-free recording fake for the rbot simulated 2-D LiDAR contract.

The fake answers one fixed ``sensor_msgs/msg/LaserScan`` subscription on the
absolute ``/scan`` topic.  The 8-range array, timestamps and frame name below
are placeholders, not the pinned sensor's values or the 720-sample size.  It
runs no Gazebo, ROS graph, raycast, noise model or wall-clock loop.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRbotScan(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.no_scan = False       # placeholder negative-path switch
        self.malformed_scan = False  # placeholder negative-path switch
        self.nonfinite_scan = False  # placeholder negative-path switch: an infinite first range
        self.scan = {
            "header": {
                "stamp": {"sec": 12, "nanosec": 340000000},  # placeholder
                "frame_id": "lidar_2d_link",                 # placeholder
            },
            "angle_min": -1.0,        # placeholder
            "angle_max": 1.0,         # placeholder
            "angle_increment": 0.25,  # placeholder
            "time_increment": 0.0,    # placeholder
            "scan_time": 0.1,         # placeholder
            "range_min": 0.1,         # placeholder
            "range_max": 10.0,        # placeholder
            "ranges": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7],  # placeholder
            "intensities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # placeholder
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe" and message.get("topic") == "/scan":
            if self.no_scan:
                return None
            if self.malformed_scan:
                # A transport-valid message missing the required scan fields.
                return {
                    "op": "publish",
                    "topic": "/scan",
                    "id": message.get("id"),
                    "msg": {"header": {"frame_id": "lidar_2d_link"}},  # placeholder
                }
            scan = dict(self.scan)
            if self.nonfinite_scan:
                scan["ranges"] = [float("inf")] + list(scan["ranges"][1:])  # placeholder
            return {
                "op": "publish",
                "topic": "/scan",
                "id": message.get("id"),
                "msg": scan,
            }
        return None
