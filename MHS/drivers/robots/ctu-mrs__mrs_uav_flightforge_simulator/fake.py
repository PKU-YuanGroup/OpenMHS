"""ROS-free recording fake for the MRS FlightForge simulator observation topics.

The fake models the two fixed subscriptions declared by the package:
``/clock`` (``rosgraph_msgs/msg/Clock``) and
``/flightforge_simulator/uav_poses`` (``geometry_msgs/msg/PoseArray``).  All
numbers and state strings below are test data, not device facts.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeFlightforge(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.silent_clock = False        # placeholder negative-path switch
        self.malformed_clock = False     # placeholder negative-path switch
        self.clock_sec = 12              # placeholder
        self.clock_nanosec = 340000000   # placeholder
        self.pose_frame = "simulator_origin"  # placeholder
        self.pose_x = 1.0                # placeholder
        self.pose_y = 2.0                # placeholder
        self.pose_z = 3.0                # placeholder

    def _respond(self, message):
        operation = message.get("op")
        if operation != "subscribe":
            return None
        topic = message.get("topic")
        if topic == "/clock":
            if self.silent_clock:
                return None
            if self.malformed_clock:
                # Wrong ROS 2 Time field names: the output schema must refuse it.
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": message.get("id"),
                    "msg": {"clock": {"secs": self.clock_sec}},  # placeholder, intentionally malformed
                }
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}},  # placeholder
            }
        if topic == "/flightforge_simulator/uav_poses":
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": {
                        "stamp": {"sec": self.clock_sec, "nanosec": self.clock_nanosec},  # placeholder
                        "frame_id": self.pose_frame,  # placeholder
                    },
                    "poses": [
                        {
                            "position": {
                                "x": self.pose_x,  # placeholder
                                "y": self.pose_y,  # placeholder
                                "z": self.pose_z,  # placeholder
                            },
                            "orientation": {
                                "x": 0.0,  # placeholder
                                "y": 0.0,  # placeholder
                                "z": 0.0,  # placeholder
                                "w": 1.0,  # placeholder
                            },
                        }
                    ],
                },
            }
        return None
