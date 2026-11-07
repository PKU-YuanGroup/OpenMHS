"""OpenMHS rosbridge driver for gh.ifra-cranfield/ros2_robotsimulation.

The pinned repository is the IFRA ROS 2 Foxy robot-simulation package set.  The
robot motion interface is a family of ROS 2 native action servers in
``ros2_actions/scripts``: ``/MoveJ`` and ``/MoveJs`` move a six- or seven-joint
arm to a joint waypoint in degrees, ``/MoveXYZ`` moves the end effector to an
absolute Cartesian position while keeping its current orientation, and
``/MoveG`` moves a parallel gripper.  This package declares those four action
servers only; it is a configuration-only :class:`RosDriver` and declares no
Python native class.  The operator runs the upstream nodes and rosbridge
separately.

The pinned action servers expose no pause, stop, reset or hold service or
action.  Their only stop-shaped path is the action cancel callback, which calls
``move_group_interface.stop()``; ROS action cancellation is not an acknowledged
stop binding under the RosDriver contract (MHS/sdk/docs/ros-driver.md, "Success
and stopping").  This package therefore declares no fabricated safe-state
action and records the missing acknowledged stop as its blocked condition.  A
stock MHS e-stop reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` for this surface.

Every endpoint, type and fact cites the pinned clone at
ee3a4de4cae38de3d83f3c925693bb417e6d047e.  The fake transport is ROS-free and
models the four action wire contracts only; no ROS graph, Gazebo world, MoveIt
planner or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned action-server source.
# ---------------------------------------------------------------------------

_MOVE_J_SERVER_REF = "ros2_actions/scripts/moveJ_action.cpp:81-86"
_MOVE_J_TYPE_REF = "ros2_actions/scripts/moveJ_action.cpp:46"
_MOVE_JS_SERVER_REF = "ros2_actions/scripts/moveJs_action.cpp:81-86"
_MOVE_JS_TYPE_REF = "ros2_actions/scripts/moveJs_action.cpp:46"
_MOVE_XYZ_SERVER_REF = "ros2_actions/scripts/moveXYZ_action.cpp:80-85"
_MOVE_XYZ_TYPE_REF = "ros2_actions/scripts/moveXYZ_action.cpp:46"
_MOVE_G_SERVER_REF = "ros2_actions/scripts/moveG_action.cpp:80-85"
_MOVE_G_TYPE_REF = "ros2_actions/scripts/moveG_action.cpp:46"

#: The upstream README states the accepted velocity-scaling range.
_SPEED_REF = "ros2_actions/README.md:41"

#: A MoveIt velocity scaling factor of 1 is the documented maximum.  The
#: README writes the range as (0, 1], so zero is not a valid motion; the
#: inclusive lower bound keeps the envelope representation honest and the
#: upstream MoveIt call still rejects zero.
_SPEED_LIMIT = Limit(
    min=0,
    max=1,
    unit="1",
    source="vendor_doc",
    ref=_SPEED_REF,
    reason="The README requires a value in (0, 1]; 0 is documented as invalid",
)

#: Joint angles are in degrees on this wire: the server multiplies each goal
#: value by pi/180 before assigning the MoveIt joint target.
_JOINT_UNIT = "deg"


def _joint_fields(count: int) -> dict[str, Field]:
    return {
        f"joint{index}": Field(
            "number",
            unit=_JOINT_UNIT,
            description=(
                f"Target joint{index} angle in degrees"
            ),
        )
        for index in range(1, count + 1)
    }


_SPEED_FIELD = Field(
    "number",
    unit="1",
    description="MoveIt velocity scaling factor in (0, 1].",
    limit=_SPEED_LIMIT,
)

_RESULT_FIELD = Field(
    "string",
    description="Terminal string result: SUCCESS, FAILED or CANCELED.",
)

_XYZ_FIELDS = {
    "positionx": Field("number", unit="m", description="Absolute target x position (m)"),
    "positiony": Field("number", unit="m", description="Absolute target y position (m)"),
    "positionz": Field("number", unit="m", description="Absolute target z position (m)"),
}

# ---------------------------------------------------------------------------
# Action bindings.
# ---------------------------------------------------------------------------

_MOVE_J = {
    "action": "/MoveJ",
    "profile": "ros2-native",
    "type": "ros2_data/action/MoveJ",
    "source_name": "/MoveJ",
    "source_ref": _MOVE_J_SERVER_REF,
    "type_ref": _MOVE_J_TYPE_REF,
    "args": {
        "goal.joint1": {"from": "input.joint1"},
        "goal.joint2": {"from": "input.joint2"},
        "goal.joint3": {"from": "input.joint3"},
        "goal.joint4": {"from": "input.joint4"},
        "goal.joint5": {"from": "input.joint5"},
        "goal.joint6": {"from": "input.joint6"},
        "speed": {"from": "input.speed"},
    },
    "success": {"path": "result", "equals": "MoveJ:SUCCESS"},
    "result": {"map": {"result": "output.result"}},
}

_MOVE_JS = {
    "action": "/MoveJs",
    "profile": "ros2-native",
    "type": "ros2_data/action/MoveJs",
    "source_name": "/MoveJs",
    "source_ref": _MOVE_JS_SERVER_REF,
    "type_ref": _MOVE_JS_TYPE_REF,
    "args": {
        "goal.joint1": {"from": "input.joint1"},
        "goal.joint2": {"from": "input.joint2"},
        "goal.joint3": {"from": "input.joint3"},
        "goal.joint4": {"from": "input.joint4"},
        "goal.joint5": {"from": "input.joint5"},
        "goal.joint6": {"from": "input.joint6"},
        "goal.joint7": {"from": "input.joint7"},
        "speed": {"from": "input.speed"},
    },
    "success": {"path": "result", "equals": "MoveJs:SUCCESS"},
    "result": {"map": {"result": "output.result"}},
}

_MOVE_XYZ = {
    "action": "/MoveXYZ",
    "profile": "ros2-native",
    "type": "ros2_data/action/MoveXYZ",
    "source_name": "/MoveXYZ",
    "source_ref": _MOVE_XYZ_SERVER_REF,
    "type_ref": _MOVE_XYZ_TYPE_REF,
    "args": {
        "positionx": {"from": "input.positionx"},
        "positiony": {"from": "input.positiony"},
        "positionz": {"from": "input.positionz"},
        "speed": {"from": "input.speed"},
    },
    "success": {"path": "result", "equals": "MoveXYZ:SUCCESS"},
    "result": {"map": {"result": "output.result"}},
}

_MOVE_G = {
    "action": "/MoveG",
    "profile": "ros2-native",
    "type": "ros2_data/action/MoveG",
    "source_name": "/MoveG",
    "source_ref": _MOVE_G_SERVER_REF,
    "type_ref": _MOVE_G_TYPE_REF,
    "args": {"goal": {"from": "input.goal"}},
    "success": {"path": "result", "equals": "MoveG:SUCCESS"},
    "result": {"map": {"result": "output.result"}},
}


class IfraRos2Robotsimulation(RosDriver):
    device_id = "ifra-ros2-robotsimulation"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2Robotsimulation"}
    tags = [
        "ros", "ros2", "simulation", "gazebo", "moveit", "robot-arm", "gripper",
        "ifra", "cranfield",
    ]
    display_name = "IFRA ROS 2 robot simulation environment"
    vendor = "IFRA (Cranfield University)"
    model = "ros2_RobotSimulation"
    facts = [
        Fact("MoveJ creates the ROS 2 action server /MoveJ on the MoveJ_ActionServer node.",
             source="upstream_code", ref=_MOVE_J_SERVER_REF),
        Fact("MoveJ.action declares a JointPose goal, a float64 speed, a string result and a string feedback.",
             source="upstream_code", ref="ros2_data/action/MoveJ.action:1-6"),
        Fact("JointPose.msg declares joint1 through joint6 as float64.",
             source="upstream_code", ref="ros2_data/msg/JointPose.msg:1-6"),
        Fact("MoveJ multiplies each of the six goal joint values by k before assigning the MoveIt joint "
             "targets.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:301-306"),
        Fact("MoveJ defines the degree-to-radian constant k = pi/180.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:50-51"),
        Fact("MoveJ applies the goal speed with setMaxVelocityScalingFactor and 1.0 with "
             "setMaxAccelerationScalingFactor.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:142-144"),
        Fact("MoveJ checks each goal joint against per-robot degree limits selected by the ROB_PARAM string "
             "before planning; the irb120, irb1200, irb6640, cr35ia, ur3, ur5 and ur10 branches are present.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:163-289"),
        Fact("MoveJ plans with MoveIt, calls move(), then reports MoveJ:SUCCESS, MoveJ:FAILED or "
             "MoveJ:CANCELED; a planning failure still calls goal_handle->succeed with MoveJ:FAILED.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:310-335"),
        Fact("MoveJ's cancel handler calls move_group_interface.stop() and accepts the cancellation.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:117-128"),
        Fact("The MoveJ execute path checks is_canceling only after move() returns.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:317-329"),
        Fact("MoveJs creates the ROS 2 action server /MoveJs with a JointPoseS goal and a float64 speed.",
             source="upstream_code", ref="ros2_actions/scripts/moveJs_action.cpp:81-86"),
        Fact("MoveJs.action declares a JointPoseS goal, a float64 speed, a string result and a string feedback.",
             source="upstream_code", ref="ros2_data/action/MoveJs.action:1-6"),
        Fact("JointPoseS.msg declares joint1 through joint7 as float64.",
             source="upstream_code", ref="ros2_data/msg/JointPoseS.msg:1-7"),
        Fact("MoveXYZ creates the ROS 2 action server /MoveXYZ and includes the generated MoveXYZ action "
             "header.",
             source="upstream_code", ref="ros2_actions/scripts/moveXYZ_action.cpp:80-85"),
        Fact("MoveXYZ sets an absolute target pose from positionx, positiony and positionz and keeps the "
             "current end-effector orientation.",
             source="upstream_code", ref="ros2_actions/scripts/moveXYZ_action.cpp:163-172"),
        Fact("MoveXYZ reports MoveXYZ:SUCCESS, MoveXYZ:FAILED or MoveXYZ:CANCELED, and a planning failure "
             "still succeeds the goal with MoveXYZ:FAILED.",
             source="upstream_code", ref="ros2_actions/scripts/moveXYZ_action.cpp:174-200"),
        Fact("MoveG creates the ROS 2 action server /MoveG and includes the generated MoveG action header.",
             source="upstream_code", ref="ros2_actions/scripts/moveG_action.cpp:80-85"),
        Fact("MoveG checks the gripper goal against panda_gripper upper 0.04 and egp64 upper 0.025, both "
             "with lower 0.0, then assigns the goal to both gripper joints.",
             source="upstream_code", ref="ros2_actions/scripts/moveG_action.cpp:150-175"),
        Fact("MoveG reports MoveG:SUCCESS, MoveG:FAILED or MoveG:CANCELED, and a planning failure still "
             "succeeds the goal with MoveG:FAILED.",
             source="upstream_code", ref="ros2_actions/scripts/moveG_action.cpp:183-210"),
        Fact("The README states the speed value must be in (0, 1], with 1 the maximum velocity and 0 the "
             "invalid null velocity.",
             source="vendor_doc", ref=_SPEED_REF),
        Fact("The README describes /MoveJ as the 6-DOF joint-waypoint action and /MoveJs as its 7-DOF "
             "variant.",
             source="vendor_doc", ref="ros2_actions/README.md:4-8"),
        Fact("The README describes the ROS 2 actions as executing robot and end-effector motions in Gazebo "
             "simulation.",
             source="vendor_doc", ref="ros2_actions/README.md:2"),
        Fact("The Attacher action loops until a cancel request or a String True on /ros2_Detach, and "
             "returns an empty result; it exposes no stop service or stop action.",
             source="upstream_code", ref="ros2_grasping/scripts/attacher_action.py:181-239"),
        Fact("The MoveJ server registration and cancel callback are its only stop-shaped control path: the "
             "callback calls move_group_interface.stop() and accepts cancellation.",
             source="upstream_code", ref="ros2_actions/scripts/moveJ_action.cpp:81-128"),
    ]

    # No acknowledged stop service or action exists in the pinned clone.  The
    # cancel callback is not an independent stop binding, so the driver records
    # that fact instead of inventing a safe-state action.
    safe_state = (
        "No acknowledged safe state is declared: the pinned action servers expose only a cancel callback "
        "that calls move_group_interface.stop(); action cancellation is not an acknowledged stop binding."
    )

    #: The deployed fake is an event-driven recording of the four action wire
    #: contracts.  It runs no Gazebo physics, MoveIt planner, controller or
    #: timing loop.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo or MoveIt physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": (
                "Event-driven canned action terminals; no physics step, planning, trajectory execution, "
                "pacing or state hash is modelled"
            ),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the four declared ROS 2 action goals "
            "with canned terminals and runs no Gazebo world, MoveIt planner, controller or sensor",
            "joint, Cartesian and gripper goals are not applied to any simulated robot state; the fake "
            "reports the upstream's success/failure result strings only",
            "the upstream README's speed range and the server's per-robot joint and gripper limits are "
            "recorded as source facts, not as a fake motion envelope",
            "the action servers' cancel callbacks are not modelled as an acknowledged stop; the fake has "
            "no hold/queue and completes a default goal immediately",
            "no live ROS graph or rosbridge deployment was contacted; the package remains contract_checked "
            "and model-authored",
        ],
    }

    parameters = {}
    reads = {}
    commands = {
        "x-cap.ifra-cranfield.move-j.v1": _MOVE_J,
        "x-cap.ifra-cranfield.move-js.v1": _MOVE_JS,
        "x-cap.ifra-cranfield.move-xyz.v1": _MOVE_XYZ,
        "x-cap.ifra-cranfield.move-g.v1": _MOVE_G,
    }
    actions = {
        "x-cap.ifra-cranfield.move-j.v1": Action(
            name="move_joint_pose",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description="Move a six-joint arm to a joint waypoint through the ROS 2 /MoveJ action.",
            input={**_joint_fields(6), "speed": _SPEED_FIELD},
            output={"result": _RESULT_FIELD},
        ),
        "x-cap.ifra-cranfield.move-js.v1": Action(
            name="move_joint_pose_seven",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description="Move a seven-joint arm to a joint waypoint through the ROS 2 /MoveJs action.",
            input={**_joint_fields(7), "speed": _SPEED_FIELD},
            output={"result": _RESULT_FIELD},
        ),
        "x-cap.ifra-cranfield.move-xyz.v1": Action(
            name="move_cartesian_position",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description="Move the end effector to an absolute Cartesian position through ROS 2 /MoveXYZ.",
            input={**_XYZ_FIELDS, "speed": _SPEED_FIELD},
            output={"result": _RESULT_FIELD},
        ),
        "x-cap.ifra-cranfield.move-g.v1": Action(
            name="move_gripper",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description="Move the parallel gripper through the ROS 2 /MoveG action.",
            input={
                "goal": Field(
                    "number",
                    unit="m",
                    description="Gripper opening (m); the server checks the selected model's bounds.",
                ),
            },
            output={"result": _RESULT_FIELD},
        ),
    }

    # The pinned action servers expose no acknowledged stop.  No fabricated
    # e-stop or safe-state binding is declared; the package is blocked on that
    # missing native stop.
    safety_bindings = {}
