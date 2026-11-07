"""ROS-free recording fake of the ur3_moveit MoverService (gh.unity-technologies/robotics-object-pose-estimation).

It answers rosbridge ``call_service`` requests for ``/ur3_moveit`` the way the pinned callback shapes them
(``ROS/src/ur3_moveit/scripts/mover.py:61-110``): the request's six start angles arrive in degrees and become the
radian start of the first plan (``:66-73``); five plans follow in the order pre grasp, grasp, pick up, place, post
place, each starting at the last point of the previous one (``:75-107``); a plan MoveIt cannot find makes the
callback raise, which rosbridge reports as a failed service call. It is an in-memory stand-in, not a recording of
captured traffic: no MoveIt, OMPL, collision checking, time parameterization or Unity scene runs.

Every joint configuration, point count, time spacing, velocity and failure message below is test data, marked
``# placeholder``; none is a device fact or a Limit.
"""

import copy
import math

from mhs.bridge.ros_transport import RecordingRosTransport

SERVICE = "/ur3_moveit"

#: The arm joints in the planner's order (mover.py:21).
JOINTS = ("shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint",
          "wrist_3_joint")

#: End configurations (radians) of the five plans. Invented joint values, not MoveIt solutions of any pose.
GOALS = (
    (0.10, -0.40, 0.90, -0.50, -1.57, 0.10),  # placeholder pre grasp
    (0.10, -0.30, 0.95, -0.65, -1.57, 0.10),  # placeholder grasp
    (0.10, -0.40, 0.90, -0.50, -1.57, 0.10),  # placeholder pick up
    (-0.60, -0.40, 0.90, -0.50, -1.57, -0.60),  # placeholder place
    (-0.60, -0.50, 0.85, -0.35, -1.57, -0.60),  # placeholder post place
)
POINTS_PER_PLAN = 4  # placeholder
STEP_NS = 250_000_000  # placeholder spacing of the points

_POSE_LEAVES = (("position", ("x", "y", "z")), ("orientation", ("x", "y", "z", "w")))


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _header():
    return {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "world"}  # placeholder stamp and frame


def _plan(start, goal):
    """One straight joint-space segment from ``start`` to ``goal`` (placeholder shape of a RobotTrajectory)."""
    points = []
    duration = (POINTS_PER_PLAN - 1) * STEP_NS / 1e9
    for index in range(POINTS_PER_PLAN):
        share = index / (POINTS_PER_PLAN - 1)
        elapsed = index * STEP_NS
        points.append({
            "positions": [a + (b - a) * share for a, b in zip(start, goal)],
            "velocities": [(b - a) / duration for a, b in zip(start, goal)],  # placeholder constant rate
            "accelerations": [0.0] * len(JOINTS),  # placeholder
            "effort": [],
            "time_from_start": {"secs": elapsed // 1_000_000_000, "nsecs": elapsed % 1_000_000_000},
        })
    return {
        "joint_trajectory": {"header": _header(), "joint_names": list(JOINTS), "points": points},
        "multi_dof_joint_trajectory": {"header": _header(), "joint_names": [], "points": []},
    }


class FakeUr3MoverService(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fail_planning = False  # the callback raised (no plan found); rosbridge reports result false
        self.silent = False  # the service never answers
        self.short_response = False  # placeholder malformed answer: four plans instead of five
        self.foreign_joint = False  # placeholder malformed answer: a joint outside the arm group
        self.truncated_point = False  # placeholder malformed answer: a point with five positions
        self.calls = []  # placeholder test record of every call_service message

    def _response(self, message, result, values):
        return {"op": "service_response", "service": message.get("service"), "id": message.get("id"),
                "result": result, "values": values}

    def _start(self, args):
        """The start configuration in radians, or None for a request the callback could not read."""
        joints = args.get("joints_input") if isinstance(args, dict) else None
        if not isinstance(joints, dict):
            return None
        values = [joints.get(f"joint_0{index}") for index in range(len(JOINTS))]
        if not all(_finite(value) for value in values):
            return None
        for name in ("pick_pose", "place_pose"):
            pose = args.get(name)
            for part, axes in _POSE_LEAVES:
                block = pose.get(part) if isinstance(pose, dict) else None
                if not isinstance(block, dict) or not all(_finite(block.get(axis)) for axis in axes):
                    return None
        return [math.radians(value) for value in values]  # mover.py:66-73

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        if message.get("service") != SERVICE:
            return self._response(message, False, "placeholder: service does not exist")
        self.calls.append(copy.deepcopy(message))
        if self.silent:
            return None
        if self.fail_planning:
            # mover.py:78 indexes the last point of an empty plan when MoveIt finds none; the rospy handler error
            # reaches rosbridge as a failed call.
            return self._response(message, False, "placeholder: error processing request: list index out of range")
        start = self._start(message.get("args"))
        if start is None:
            return self._response(message, False, "placeholder: the request could not be read")
        trajectories = []
        for goal in GOALS:
            trajectories.append(_plan(start, goal))
            start = list(goal)  # the next plan starts at this plan's last point (mover.py:78, 86, 92, 98)
        if self.short_response:
            trajectories = trajectories[:4]
        if self.foreign_joint:
            trajectories[2]["joint_trajectory"]["joint_names"][5] = "finger_joint"  # placeholder defect
        if self.truncated_point:
            trajectories[1]["joint_trajectory"]["points"][2]["positions"].pop()  # placeholder defect
        return self._response(message, True, {"trajectories": trajectories})
