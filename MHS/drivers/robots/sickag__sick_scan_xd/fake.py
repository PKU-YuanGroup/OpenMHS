"""ROS-free recording fake for the sick_scan_xd LaserScan subscription.

The fake models one rosbridge ``subscribe`` to the launch-default
``/scan`` topic and answers with one ``publish`` event carrying
a ``sensor_msgs/msg/LaserScan``-shaped object.  Every number below is test
data, not a device fact or a limit.  No ROS graph, rosbridge connection or
scanner is contacted.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

SCAN_TOPIC = "/scan"
SCAN_TYPE = "sensor_msgs/msg/LaserScan"


class FakeSickScanXd(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.frame_id = "fake_scan_frame"       # placeholder frame name
        self.stamp_sec = 12                     # placeholder
        self.stamp_nanosec = 340000000          # placeholder
        self.angle_min = -1.658062789           # placeholder
        self.angle_max = 1.658062789            # placeholder
        self.angle_increment = 0.8290313945      # placeholder
        self.time_increment = 0.000033           # placeholder
        self.scan_time = 0.04                   # placeholder
        self.range_min = 0.05                   # placeholder
        self.range_max = 100.0                  # placeholder
        self.ranges = [0.5, 1.0, 1.5, 2.0, 2.5]  # placeholder scan samples
        self.intensities = [10.0, 20.0, 30.0, 40.0, 50.0]  # placeholder scan samples
        self.silent = False                     # placeholder negative-path switch
        self.omit_ranges = False                # placeholder negative-path switch

    def _respond(self, message):
        if message.get("op") == "unsubscribe":
            return None
        if message.get("op") != "subscribe" or message.get("topic") != SCAN_TOPIC:
            return None
        if self.silent:
            return None
        scan = {
            "header": {
                "frame_id": self.frame_id,
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},
            },
            "angle_min": self.angle_min,
            "angle_max": self.angle_max,
            "angle_increment": self.angle_increment,
            "time_increment": self.time_increment,
            "scan_time": self.scan_time,
            "range_min": self.range_min,
            "range_max": self.range_max,
            "ranges": list(self.ranges),
            "intensities": list(self.intensities),
        }
        if self.omit_ranges:
            del scan["ranges"]
        return {"op": "publish", "topic": SCAN_TOPIC, "id": message.get("id"), "msg": scan}
