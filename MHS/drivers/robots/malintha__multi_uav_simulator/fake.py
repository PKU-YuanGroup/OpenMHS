"""ROS-free contract fake for the pinned Mavswarm2 per-vehicle endpoints.

The fake models only the wire contract used by ``driver.py``: a
``visualization_msgs/msg/Marker`` publication on
``/mavswarm2/robot_3/trajectory`` and a ``geometry_msgs/msg/Point``
publication on ``/mavswarm2/robot_3/desired_state``.  It runs no Mavswarm2
node, SCP planner, geometric controller, GSL integration, TF broadcaster or
RViz, and it does not apply a goal.

Every number below is test data, not a device fact, and is marked
``# placeholder``.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

TRAJECTORY_TOPIC = "/mavswarm2/robot_3/trajectory"
DESIRED_TOPIC = "/mavswarm2/robot_3/desired_state"


class FakeMultiUavSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.trajectory_points = [
            {"x": 2.0, "y": -1.5, "z": 2.0},  # placeholder
        ]
        self.frame_id = "map"                 # source fact: the marker frame
        self.trajectory_sec = 12              # placeholder
        self.trajectory_nanosec = 0           # placeholder
        self.last_goal = None                 # placeholder observation for tests
        self.initial_goal = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.silent_trajectory = False        # placeholder negative-path switch
        self.malformed_trajectory = False     # placeholder negative-path switch

    def _marker_message(self, ident):
        points = [] if self.malformed_trajectory else [dict(point) for point in self.trajectory_points]
        return {
            "op": "publish",
            "topic": TRAJECTORY_TOPIC,
            "id": ident,
            "msg": {
                "header": {
                    "frame_id": self.frame_id,
                    "stamp": {"sec": self.trajectory_sec, "nanosec": self.trajectory_nanosec},  # placeholder
                },
                "ns": "trajectory",
                "id": 3,             # placeholder
                "type": 4,           # placeholder
                "action": 0,         # placeholder
                "points": points,
            },
        }

    def _goal_message(self, ident):
        goal = self.last_goal if self.last_goal is not None else self.initial_goal
        return {
            "op": "publish",
            "topic": DESIRED_TOPIC,
            "id": ident,
            "msg": {
                "x": goal.get("x"),  # placeholder until a publication is recorded
                "y": goal.get("y"),  # placeholder until a publication is recorded
                "z": goal.get("z"),  # placeholder until a publication is recorded
            },
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == TRAJECTORY_TOPIC:
                if self.silent_trajectory:
                    return None
                return self._marker_message(message.get("id"))
            if topic == DESIRED_TOPIC:
                return self._goal_message(message.get("id"))
            return None
        if operation == "publish":
            if message.get("topic") == DESIRED_TOPIC:
                self.last_goal = dict(message.get("msg") or {})
            return None
        return None
