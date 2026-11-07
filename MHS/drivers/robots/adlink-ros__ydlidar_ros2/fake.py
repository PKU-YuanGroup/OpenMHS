"""ROS-free contract fake for the YDLIDAR ROS 2 LaserScan publisher.

The fake models the pinned wire contract of ``ydlidar_node``: one
``sensor_msgs/msg/LaserScan`` publication on the resolved ``/scan`` topic.  It
subclasses the SDK's ``RecordingRosTransport`` base class but answers with a
canned handler; it does not replay captured traffic.  It opens no serial port,
starts no ROS node and runs no lidar scan loop.  Every value below is test
data, not a device fact or a bound; the real scan length is computed at run time
from the configured angles and the device's angular increment.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeYdlidarRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.frame_id = "laser_frame"            # placeholder
        self.stamp_sec = 12                      # placeholder
        self.stamp_nanosec = 340000000           # placeholder
        self.angle_min = -1.5707963267948966     # placeholder
        self.angle_max = 1.5707963267948966      # placeholder
        self.angle_increment = 0.7853981633974483  # placeholder
        self.scan_time = 0.1                     # placeholder
        self.time_increment = 0.0125             # placeholder
        self.range_min = 0.01                    # placeholder
        self.range_max = 16.0                    # placeholder
        self.ranges = [1.0, 2.0, 3.0, 4.0, 5.0]  # placeholder
        self.intensities = [0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder

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
            "angle_min": self.angle_min,             # placeholder
            "angle_max": self.angle_max,             # placeholder
            "angle_increment": self.angle_increment, # placeholder
            "scan_time": self.scan_time,             # placeholder
            "time_increment": self.time_increment,   # placeholder
            "range_min": self.range_min,             # placeholder
            "range_max": self.range_max,             # placeholder
            "ranges": list(self.ranges),             # placeholder
            "intensities": list(self.intensities),   # placeholder
        }
        if self.malformed == "missing_header":
            message.pop("header")
        elif self.malformed == "missing_ranges":
            message.pop("ranges")
        elif self.malformed == "missing_intensities":
            message.pop("intensities")
        elif self.malformed == "string_range":
            message["ranges"][0] = "not-a-number"    # placeholder
        elif self.malformed == "bad_stamp":
            message["header"]["stamp"]["sec"] = "not-an-integer"  # placeholder
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions += 1
        self.last_subscribe = dict(message)
        if message.get("topic") != "/scan":
            return None
        if self.fail_subscribe:
            raise ConnectionError("simulated /scan subscription failure")  # placeholder
        if self.silent:
            return None
        event = {
            "op": "publish",
            "topic": "/scan",
            "id": message.get("id"),
            "msg": self._message(),
        }
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event
