"""ROS-free canned fake for the ros_autonomous_slam observation topics.

The fake models the pinned wire contract only: a nav_msgs/OccupancyGrid
publication on /map, a ros_autonomous_slam/PointArray publication on
/filtered_points, a geometry_msgs/PointStamped publication on /clicked_point,
a nav_msgs/Odometry publication on /odom and a sensor_msgs/LaserScan
publication on /scan.  It opens no ROS connection, starts no Gazebo, GMAPPING
or move_base process and runs no physics, navigation, SLAM or wall-clock loop.
Every value below is test data, not a device fact or a bound.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRosAutonomousSlam(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.stamp_secs = 12                  # placeholder
        self.stamp_nsecs = 340000000          # placeholder
        self.frame_id = "map"                 # placeholder
        self.base_frame = "base_footprint"    # placeholder
        self.map_width = 4                    # placeholder
        self.map_height = 3                   # placeholder
        self.map_resolution = 0.05            # placeholder
        self.map_data = [0, 0, 100, -1, 0, 0, 100, -1, 0, 0, 100, -1]  # placeholder
        self.frontier_points = [               # placeholder points
            {"x": 1.0, "y": 2.0, "z": 0.0},    # placeholder
            {"x": 3.0, "y": 4.0, "z": 0.0},    # placeholder
            {"x": 5.0, "y": 6.0, "z": 0.0},    # placeholder
        ]
        self.region_point = {"x": -2.0, "y": 0.5, "z": 0.0}  # placeholder
        self.scan_ranges = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]  # placeholder
        self.scan_intensities = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]  # placeholder

        # Negative-path switches used by the repository tests.
        self.silent_topic = None      # placeholder: emit no publication
        self.malformed_topic = None   # placeholder: emit an empty message
        self.wrong_id = False         # placeholder: emit an unrelated subscription id
        self.nonfinite_scan = False   # placeholder: emit an infinite first range
        self.subscriptions = []       # placeholder request log

    def _stamp(self):
        return {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs}  # placeholder

    def _position(self):
        return {"x": 0.5, "y": -0.25, "z": 0.0}  # placeholder

    def _orientation(self):
        return {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder

    def _message(self, topic):
        if topic == "/map":
            return {
                "header": {"seq": 1, "stamp": self._stamp(), "frame_id": self.frame_id},
                "info": {
                    "map_load_time": {"secs": 0, "nsecs": 0},  # placeholder
                    "resolution": self.map_resolution,
                    "width": self.map_width,
                    "height": self.map_height,
                    "origin": {
                        "position": {"x": -2.0, "y": 0.5, "z": 0.0},  # placeholder
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    },
                },
                "data": list(self.map_data),
            }
        if topic == "/filtered_points":
            return {"points": [dict(point) for point in self.frontier_points]}
        if topic == "/clicked_point":
            return {
                "header": {"seq": 1, "stamp": self._stamp(), "frame_id": self.frame_id},
                "point": dict(self.region_point),
            }
        if topic == "/odom":
            return {
                "header": {"seq": 1, "stamp": self._stamp(), "frame_id": self.frame_id},
                "child_frame_id": self.base_frame,
                "pose": {"pose": {"position": self._position(),
                                  "orientation": self._orientation()},
                         "covariance": [0.0] * 36},  # placeholder
                "twist": {"twist": {"linear": {"x": 0.2, "y": 0.0, "z": 0.0},  # placeholder
                                    "angular": {"x": 0.0, "y": 0.0, "z": 0.1}},  # placeholder
                          "covariance": [0.0] * 36},  # placeholder
            }
        if topic == "/scan":
            return {
                "header": {"seq": 1, "stamp": self._stamp(), "frame_id": "base_scan"},  # placeholder frame
                "angle_min": -0.35,          # placeholder
                "angle_max": 0.35,           # placeholder
                "angle_increment": 0.1,      # placeholder
                "time_increment": 0.0,       # placeholder
                "scan_time": 0.1,            # placeholder
                "range_min": 0.12,           # placeholder
                "range_max": 3.5,            # placeholder
                "ranges": ([float("inf")] + list(self.scan_ranges[1:]) if self.nonfinite_scan
                           else list(self.scan_ranges)),
                "intensities": list(self.scan_intensities),
            }
        return None

    def _publish(self, topic, request, message):
        event = {"op": "publish", "topic": topic, "id": request.get("id"), "msg": message}
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions.append(dict(message))
        topic = message.get("topic")
        if topic not in ("/map", "/filtered_points", "/clicked_point", "/odom", "/scan"):
            return None
        if topic == self.silent_topic:
            return None
        if topic == self.malformed_topic:
            return self._publish(topic, message, {})
        return self._publish(topic, message, self._message(topic))
