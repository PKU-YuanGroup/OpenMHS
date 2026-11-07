"""ROS-free recording fake for the Panda Servo outgoing trajectory topic.

The fake models the pinned wire contract of the one command endpoint this
package exposes: an ``advertise`` and a ``publish`` of a
``trajectory_msgs/msg/JointTrajectory`` on
``/joint_trajectory_controller/joint_trajectory``.  It opens no socket, starts
no ROS node and runs no Gazebo, MoveIt Servo or controller.

A ROS topic publication has no application reply.  The fake therefore records
the message and returns nothing; the bridge's ``{"published": true,
"confirmed": false}`` result is the whole receipt.  Every value the fake keeps
is test data, not a device fact, and is marked ``# placeholder``.
"""

import copy
import math

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINTS = ["panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
           "panda_joint5", "panda_joint6", "panda_joint7"]

_TOPIC = "/joint_trajectory_controller/joint_trajectory"


class FakePandaGzMoveit2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.last_trajectory = None          # placeholder: the last recorded JointTrajectory
        self.publish_count = 0               # placeholder counter
        self.fail_publish = False            # placeholder negative-path switch
        self.drop_publish = False            # placeholder negative-path switch

    def _record(self, message):
        if message.get("joint_names") != _JOINTS:
            raise ValueError("the fake only records the seven panda_joint names")
        points = message.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("a JointTrajectory needs at least one point")
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("a JointTrajectoryPoint must be an object")
            positions = point.get("positions")
            if not isinstance(positions, list) or len(positions) != len(_JOINTS):
                raise ValueError("a JointTrajectoryPoint needs seven positions")
            for value in positions:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("joint positions must be finite numbers")
            start = point.get("time_from_start")
            if not isinstance(start, dict):
                raise ValueError("a JointTrajectoryPoint needs time_from_start")
            for key in ("sec", "nanosec"):
                value = start.get(key)
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError("time_from_start fields must be integers")
        self.last_trajectory = copy.deepcopy(message)   # placeholder recording
        self.publish_count += 1                          # placeholder counter

    def _respond(self, message):
        operation = message.get("op")
        if operation == "advertise":
            if message.get("topic") != _TOPIC:
                return None
            return None
        if operation == "publish":
            if message.get("topic") != _TOPIC:
                return None
            if self.fail_publish:
                raise ConnectionError("fake publication failure")   # placeholder negative path
            if self.drop_publish:
                return None                                          # placeholder negative path
            body = message.get("msg")
            if not isinstance(body, dict):
                raise ValueError("a JointTrajectory publication needs an object message")
            self._record(body)
            return None
        if operation == "unadvertise":
            return None
        return None
