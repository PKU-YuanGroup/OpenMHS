"""ROS-free recording fake for the SO-101 Gazebo arm trajectory publication.

The fake models the pinned upstream wire contract used by this package: one
``advertise`` and one ``publish`` of a ``trajectory_msgs/msg/JointTrajectory``
on the absolute ``/arm_controller/joint_trajectory`` topic.  It opens no
socket, starts no ROS node, controller, Gazebo world or MoveIt node and runs
no trajectory.

There are no numeric state values in this fake: the only constants are the
upstream topic, the declared message type and the six-joint order, all named
in ``driver.py`` with their clone citations.  A failed transmission is the
only negative path a fire-and-forget publication offers; the fake raises a
transport error for it instead of inventing a controller acknowledgement.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex",
           "wrist_roll", "gripper"]
_TOPIC = "/arm_controller/joint_trajectory"
_TYPE = "trajectory_msgs/msg/JointTrajectory"


class FakeSo101Gazebo(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.advertised = []
        self.published = []
        self.fail_advertise = False
        self.fail_publish = False

    def _valid_point(self, point):
        if not isinstance(point, dict):
            return False
        positions = point.get("positions")
        if not isinstance(positions, list) or len(positions) != 6:
            return False
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in positions):
            return False
        offset = point.get("time_from_start")
        if not isinstance(offset, dict):
            return False
        return (isinstance(offset.get("sec"), int) and not isinstance(offset.get("sec"), bool)
                and isinstance(offset.get("nanosec"), int) and not isinstance(offset.get("nanosec"), bool))

    def _valid_message(self, message):
        if not isinstance(message, dict):
            return False
        if message.get("joint_names") != _JOINTS:
            return False
        points = message.get("points")
        return (isinstance(points, list) and bool(points)
                and all(self._valid_point(point) for point in points))

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            if message.get("topic") != _TOPIC or message.get("type") != _TYPE:
                raise ValueError("the fake only advertises the pinned arm trajectory topic")
            if self.fail_advertise:
                raise ConnectionError("the fake rosbridge rejected the advertisement")
            self.advertised.append({"topic": message.get("topic"), "type": message.get("type")})
            return None
        if operation == "publish":
            if message.get("topic") != _TOPIC:
                raise ValueError("the fake only publishes to the pinned arm trajectory topic")
            if self.fail_publish:
                raise ConnectionError("the fake rosbridge rejected the trajectory publication")
            if not self._valid_message(message.get("msg")):
                raise ValueError("the fake rejected a malformed JointTrajectory message")
            self.published.append(message.get("msg"))
            return None
        return None
