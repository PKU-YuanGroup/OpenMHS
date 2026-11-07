"""ROS-free transport fake for the ENPS-DWA simulator observation topics.

The fake models the pinned wire contract of ``enps_dwa_node``: a
``nav_msgs/Odometry`` publication on the resolved ``/odom`` topic and a
``sensor_msgs/LaserScan`` publication on the resolved ``/scan360`` topic.  It
opens no socket, starts no ROS node and runs no social-force, ENPS, DWA or
physics code.  Every value below is test data, not a device fact or a bound.
"""

from math import pi

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeEnpsDwa(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.stamp_secs = 12                         # placeholder
        self.stamp_nsecs = 340000000                 # placeholder
        self.odom_frame_id = "odom"                  # placeholder
        self.odom_child_frame_id = "base_link"       # placeholder
        self.position = {"x": 10.0, "y": 10.0, "z": 0.0}          # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.linear_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}     # placeholder
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}    # placeholder
        self.scan_frame_id = "base_link"             # placeholder
        self.scan_range_min = 0.3                    # placeholder
        self.scan_range_max = 2.5                    # placeholder
        self.scan_ranges = [2.5, 2.5, 1.2, 0.8, 2.5, 2.5, 1.7, 2.5]  # placeholder

        # Negative-path switches used by the repository tests.
        self.silent = False            # placeholder: emit no publication
        self.wrong_id = False          # placeholder: emit an unrelated subscription id
        self.fail_subscribe = False    # placeholder: simulate a broken transport link
        self.malformed = None          # placeholder: omit or corrupt one message field

        self.subscriptions = 0         # placeholder counter
        self.last_subscribe = None     # placeholder echo of the received request

    def _odometry(self):
        message = {
            "header": {
                "seq": 0,  # placeholder
                "frame_id": self.odom_frame_id,
                "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},  # placeholder
            },
            "child_frame_id": self.odom_child_frame_id,
            "pose": {
                "pose": {
                    "position": dict(self.position),
                    "orientation": dict(self.orientation),
                },
                "covariance": [0.0] * 36,  # placeholder
            },
            "twist": {
                "twist": {
                    "linear": dict(self.linear_velocity),
                    "angular": dict(self.angular_velocity),
                },
                "covariance": [0.0] * 36,  # placeholder
            },
        }
        if self.malformed == "missing_pose":
            message.pop("pose")
        elif self.malformed == "missing_twist":
            message.pop("twist")
        elif self.malformed == "string_position":
            message["pose"]["pose"]["position"]["x"] = "not-a-number"  # placeholder
        elif self.malformed == "missing_stamp":
            message["header"].pop("stamp")
        return message

    def _scan(self):
        message = {
            "header": {
                "seq": 0,  # placeholder
                "frame_id": self.scan_frame_id,
                "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},  # placeholder
            },
            "angle_min": -pi,                     # placeholder
            "angle_max": pi,                      # placeholder
            "angle_increment": 2.0 * pi / len(self.scan_ranges),  # placeholder
            "time_increment": 0.0,                # placeholder
            "scan_time": 1.0 / 30.0,              # placeholder
            "range_min": self.scan_range_min,
            "range_max": self.scan_range_max,
            "ranges": list(self.scan_ranges),
            "intensities": [],  # placeholder: the upstream node never sets intensities
        }
        if self.malformed == "missing_ranges":
            message.pop("ranges")
        elif self.malformed == "string_range":
            message["ranges"][0] = "not-a-number"  # placeholder
        elif self.malformed == "missing_header":
            message.pop("header")
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        self.subscriptions += 1
        self.last_subscribe = dict(message)
        topic = message.get("topic")
        if topic not in ("/odom", "/scan360"):
            return None
        if self.fail_subscribe:
            raise ConnectionError("simulated ENPS-DWA subscription failure")  # placeholder
        if self.silent:
            return None
        event = {
            "op": "publish",
            "topic": topic,
            "id": message.get("id"),
            "msg": self._odometry() if topic == "/odom" else self._scan(),
        }
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event
