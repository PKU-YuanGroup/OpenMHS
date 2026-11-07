"""ROS-free recording fake of the niryo_moveit MoverService (gh.unity-technologies/unity-robotics-hub).

It answers rosbridge ``call_service`` requests for ``/niryo_moveit`` in the shape of the pinned callback
(``tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:72-121``). The request's six start angles
are already radians (``:78``) and become the start of the first plan unchanged. Four plans follow, in the
order pre-grasp, grasp, pick-up, place, each starting at the previous plan's goal. The callback's 0.05 m
grasp drop (``:90-92``) stays inside that callback; this fake does not subtract it and does not solve IK.

A ``plan()`` the callback treats as false becomes a failed service call (``mover.py:48-53``). A successful
service whose ``trajectories`` list is empty models the callback's early ``return response`` (``:84-85``
and the three later empty returns). That empty success is still a failed receipt in the driver, because
the output contract requires four plans.

This is an in-memory stand-in, not captured traffic. No MoveIt, OMPL, collision checking, time
parameterization or Unity scene runs.

Every joint configuration, point count, time spacing, velocity and failure message below is test data,
marked ``# placeholder``. None is a device fact or a Limit.
"""

import copy
import math

from mhs.bridge.ros_transport import RecordingRosTransport

SERVICE = "/niryo_moveit"

#: The arm joints in the planner's order (mover.py:23).
JOINTS = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6")

#: End configurations (radians) of the four plans. Invented joint values, not MoveIt solutions.
GOALS = (
    (0.10, -0.40, 0.20, -0.50, -0.30, 0.10),  # placeholder pre-grasp
    (0.20, -0.20, 0.40, -0.30, -0.20, 0.20),  # placeholder grasp
    (0.10, -0.40, 0.20, -0.50, -0.30, 0.10),  # placeholder pick-up
    (-0.40, -0.10, 0.10, 0.20, 0.30, -0.40),  # placeholder place
)
POINTS_PER_PLAN = 4  # placeholder
STEP_NS = 250_000_000  # placeholder spacing of the points

_POSE_LEAVES = (("position", ("x", "y", "z")), ("orientation", ("x", "y", "z", "w")))


def _finite(value):
    return type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value)


def _header():
    return {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "world"}  # placeholder stamp and frame


def _plan(start, goal):
    """One straight joint-space segment from ``start`` to ``goal`` (placeholder RobotTrajectory)."""
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


class FakeNiryoMoverService(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fail_planning = False  # plan() is false; rosbridge reports result false
        self.empty_response = False  # successful call, trajectories length 0 (mover.py:84-85)
        self.silent = False  # the service never answers
        self.short_response = False  # placeholder malformed answer: three plans instead of four
        self.foreign_joint = False  # placeholder malformed answer: a joint outside the arm group
        self.truncated_point = False  # placeholder malformed answer: a point with five positions
        self.calls = []  # placeholder test record of every call_service message

    def _response(self, message, result, values):
        return {"op": "service_response", "service": message.get("service"), "id": message.get("id"),
                "result": result, "values": values}

    def _start(self, args):
        """The start configuration in radians, or None when the request cannot be read."""
        joints = args.get("joints_input") if isinstance(args, dict) else None
        values = joints.get("joints") if isinstance(joints, dict) else None
        if not isinstance(values, (list, tuple)) or len(values) != len(JOINTS) or not all(
                _finite(value) for value in values):
            return None
        for name in ("pick_pose", "place_pose"):
            pose = args.get(name)
            for part, axes in _POSE_LEAVES:
                block = pose.get(part) if isinstance(pose, dict) else None
                if not isinstance(block, dict) or not all(_finite(block.get(axis)) for axis in axes):
                    return None
        return [float(value) for value in values]  # mover.py:78, already radians

    def _respond(self, message):
        if message.get("op") != "call_service":
            return None
        if message.get("service") != SERVICE:
            return self._response(message, False, "placeholder: service does not exist")
        self.calls.append(copy.deepcopy(message))
        if self.silent:
            return None
        if self.fail_planning:
            # mover.py:48-53 raises when plan() is false. rosbridge reports a failed call.
            return self._response(message, False, "placeholder: error processing request: Trajectory could not be planned")
        if self.empty_response:
            # mover.py:84-85 returns a successful response whose trajectories list is still empty.
            return self._response(message, True, {"trajectories": []})
        start = self._start(message.get("args"))
        if start is None:
            return self._response(message, False, "placeholder: the request could not be read")
        trajectories = []
        for goal in GOALS:
            trajectories.append(_plan(start, goal))
            start = list(goal)  # the next plan starts at this plan's goal (mover.py:87, 97, 105)
        if self.short_response:
            trajectories = trajectories[:3]
        if self.foreign_joint:
            trajectories[2]["joint_trajectory"]["joint_names"][5] = "tool_link"  # placeholder defect
        if self.truncated_point:
            trajectories[1]["joint_trajectory"]["points"][2]["positions"].pop()  # placeholder defect
        return self._response(message, True, {"trajectories": trajectories})
