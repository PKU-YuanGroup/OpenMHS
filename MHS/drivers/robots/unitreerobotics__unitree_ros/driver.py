"""OpenMHS rosbridge declaration for the Unitree A1 Gazebo joint-controller package.

The pinned upstream is a ROS 1 Catkin workspace.  The concrete control surface
is ``unitree_legged_control``: twelve ``UnitreeJointController`` instances
subscribe to the relative ``command`` topic (``MotorCmd``) and publish the
relative ``state`` topic (``MotorState``).  ``unitree_controller`` starts the
twelve publishers on ``/<robot>_gazebo/<joint>_controller/command`` and also
publishes the aggregate ``/<robot>_gazebo/lowState/state`` (``LowState``).
This package declares the twelve command publications and the aggregate
``LowState`` observation as a configuration-only :class:`RosDriver`; it
declares no Python native class and no ROS graph is contacted.

The package is **blocked**, not completed: the upstream has no acknowledged
stop service or action.  ``UnitreeJointController::stopping()`` is empty, the
controller's ``update()`` keeps applying the last ``MotorCmd`` held in its
``RealtimeBuffer``, and the only native stop-like command is a ``BRAKE``
``MotorCmd`` published on the same twelve command topics.  A rosbridge topic
publication is transmission-only, and RosDriver's safe-state binding accepts
only a fixed acknowledged service or action call, so no genuine stop can be
declared.  This is the concrete HELPER_MISSING blocker recorded in RESULT.json;
the declaration is not served as a completed integration.

Every endpoint, type and fact cites the pinned clone at
``5994d4faef0a9cadd3287f8de0199a67eeb2a259``.  The fake transport is ROS-free;
no ROS graph, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The A1 URDF is the selected, explicit model.  Its twelve revolute joint
#: limit lines state the position, velocity and effort envelope used below.
_A1_URDF = "robots/a1_description/urdf/a1.urdf"

#: The joint-controller header includes the two message types.
_MOTOR_TYPE_REF = "unitree_legged_control/include/joint_controller.h:21-22"

#: servo.cpp creates the twelve publishers; the command topic suffixes are
#: the quoted literals on these lines.
_COMMAND_LINES = {
    "FR_hip": 224,
    "FR_thigh": 225,
    "FR_calf": 226,
    "FL_hip": 227,
    "FL_thigh": 228,
    "FL_calf": 229,
    "RR_hip": 230,
    "RR_thigh": 231,
    "RR_calf": 232,
    "RL_hip": 233,
    "RL_thigh": 234,
    "RL_calf": 235,
}

#: The A1 URDF <limit> line for each joint (position, velocity and effort).
_LIMIT_LINES = {
    "FR_hip": 369,
    "FR_thigh": 411,
    "FR_calf": 439,
    "FL_hip": 521,
    "FL_thigh": 563,
    "FL_calf": 591,
    "RR_hip": 673,
    "RR_thigh": 715,
    "RR_calf": 743,
    "RL_hip": 825,
    "RL_thigh": 867,
    "RL_calf": 895,
}

#: The four hip joints share one limit line shape, the four thighs another and
#: the four calves another.  Values are read from the cited line by G4.
_HIP = dict(min=-0.802851455917, max=0.802851455917)
_THIGH = dict(min=-1.0471975512, max=4.18879020479)
_CALF = dict(min=-2.69653369433, max=-0.916297857297)

#: The aggregate LowState publisher in servo.cpp.
_LOW_STATE_REF = "unitree_controller/src/servo.cpp:223"

#: The MotorState array in LowState has 20 entries; the A1 uses the first 12.
_MOTOR_STATE = Field(
    "object",
    description="One unitree_legged_msgs/MotorState entry from LowState.motorState",
    properties={
        "mode": Field("integer", description="Motor mode reported by the controller"),
        "q": Field("number", unit="rad", description="Joint position reported by the controller"),
        "dq": Field("number", unit="rad/s", description="Joint velocity reported by the controller"),
        "ddq": Field("number", unit="rad/s2", description="Joint acceleration reported by the controller"),
        "tauEst": Field("number", unit="N.m", description="Estimated output torque"),
        "q_raw": Field("number", unit="rad", description="Raw joint position"),
        "dq_raw": Field("number", unit="rad/s", description="Raw joint velocity"),
        "ddq_raw": Field("number", unit="rad/s2", description="Raw joint acceleration"),
        "temperature": Field("integer", unit="Cel", description="Motor temperature"),
    },
)

_MOTOR_STATES = Field(
    "array",
    items=_MOTOR_STATE,
    length=20,
    description="LowState.motorState, twenty MotorState entries in the message order",
)


def _limits(joint: str) -> tuple[Limit, Limit, Limit]:
    """Return the sourced A1 position, velocity and effort limits for one joint."""
    line = f"{_A1_URDF}:{_LIMIT_LINES[joint]}"
    if joint.endswith("hip"):
        position = _HIP
    elif joint.endswith("thigh"):
        position = _THIGH
    else:
        position = _CALF
    return (
        Limit(min=position["min"], max=position["max"], unit="rad",
              source="upstream_code", ref=line),
        Limit(min=-21.0, max=21.0, unit="rad/s",
              source="upstream_code", ref=line),
        Limit(min=-33.5, max=33.5, unit="N.m",
              source="upstream_code", ref=line),
    )


def _inputs(joint: str) -> dict[str, Field]:
    position, velocity, effort = _limits(joint)
    gain_reason = (
        "No pinned text states a position or damping gain bound for this joint. "
        "body.cpp:18-37 calls its gains reference values that need debugging, and "
        "robot_control.yaml's PID block is controller configuration, not a device limit."
    )
    return {
        "mode": Field("integer", enum=[0, 10],
                      description="Motor command mode: 10 = PMSM control, 0 = BRAKE damping"),
        "q": Field("number", unit="rad", description="Target joint position", limit=position),
        "dq": Field("number", unit="rad/s", description="Target joint velocity", limit=velocity),
        "tau": Field("number", unit="N.m", description="Target joint torque", limit=effort),
        "kp": Field("number", description="Position gain supplied by the operator",
                    limit=Limit.operator_required(gain_reason)),
        "kd": Field("number", description="Damping gain supplied by the operator",
                    limit=Limit.operator_required(gain_reason)),
    }


def _command(joint: str) -> dict:
    return {
        "topic": f"/a1_gazebo/{joint}_controller/command",
        "type": "unitree_legged_msgs/MotorCmd",
        "operation": "publish",
        "source_name": "command",
        "source_ref": "unitree_legged_control/src/joint_controller.cpp:90",
        "type_ref": _MOTOR_TYPE_REF,
        "message": {
            "mode": 0,
            "q": 0.0,
            "dq": 0.0,
            "tau": 0.0,
            "Kp": 0.0,
            "Kd": 0.0,
            "reserve": [0, 0, 0],
        },
        "args": {
            "mode": {"from": "input.mode"},
            "q": {"from": "input.q"},
            "dq": {"from": "input.dq"},
            "tau": {"from": "input.tau"},
            "Kp": {"from": "input.kp"},
            "Kd": {"from": "input.kd"},
        },
    }


def _action(joint: str) -> Action:
    return Action(
        name=f"command_{joint.lower()}",
        risk="R2",
        description=f"Publish a unitree_legged_msgs/MotorCmd for the A1 {joint} joint controller",
        input=_inputs(joint),
        output={
            "published": Field("boolean", description="True when rosbridge accepted the publication"),
            "confirmed": Field("boolean",
                               description="Always false: a rosbridge publication carries no execution confirmation"),
        },
    )


_COMMANDS = {
    f"x-cap.unitreerobotics.{joint.lower()}_command.v1": _command(joint)
    for joint in _COMMAND_LINES
}
_ACTIONS = {
    f"x-cap.unitreerobotics.{joint.lower()}_command.v1": _action(joint)
    for joint in _COMMAND_LINES
}

_LOW_STATE = {
    "topic": "/a1_gazebo/lowState/state",
    "type": "unitree_legged_msgs/LowState",
    "operation": "subscribe",
    "source_name": "lowState/state",
    "source_ref": _LOW_STATE_REF,
    "type_ref": "unitree_controller/src/servo.cpp:10",
    "path": "motorState",
    "result": {"map": {"motor_state": "output.$"}},
}

_COMMANDS["x-cap.unitreerobotics.low_state.v1"] = _LOW_STATE
_ACTIONS["x-cap.unitreerobotics.low_state.v1"] = Action(
    name="read_low_state",
    verb="read",
    risk="R0",
    description="Read the aggregate LowState.motorState array published by the Unitree servo node",
    output={"motor_state": _MOTOR_STATES},
)

#: The upstream's only native stop-like command is a BRAKE MotorCmd published
#: on the same per-joint command topics.  This is declared as an input-free
#: safe-state action to exercise the stop path, but RosDriver accepts a
#: safe-state binding only as a fixed acknowledged service or action call; a
#: topic publication is transmission-only.  The declaration is therefore
#: refused while the driver is compiled, which is the concrete blocker.
_BRAKE = {
    "topic": "/a1_gazebo/FR_hip_controller/command",
    "type": "unitree_legged_msgs/MotorCmd",
    "operation": "publish",
    "safe_state": True,
    "source_name": "command",
    "source_ref": "unitree_legged_control/src/joint_controller.cpp:90",
    "type_ref": _MOTOR_TYPE_REF,
    "message": {
        "mode": 0,
        "q": 0.0,
        "dq": 0.0,
        "tau": 0.0,
        "Kp": 0.0,
        "Kd": 0.0,
        "reserve": [0, 0, 0],
    },
}

_COMMANDS["x-cap.unitreerobotics.brake.v1"] = _BRAKE
_ACTIONS["x-cap.unitreerobotics.brake.v1"] = Action(
    name="brake",
    safe_state=True,
    risk="R2",
    description="Publish BRAKE mode to the FR hip command topic (intended stop path; not acknowledged)",
    output={
        "published": Field("boolean", description="True when rosbridge accepted the publication"),
        "confirmed": Field("boolean",
                           description="Always false: a rosbridge publication carries no execution confirmation"),
    },
)


class UnitreeA1Gazebo(RosDriver):
    device_id = "unitree_a1_gazebo"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUnitreeRos"}
    tags = ["ros", "ros1", "gazebo", "unitree", "a1", "joint-control", "low-state"]
    display_name = "Unitree A1 Gazebo joint-controller interface"
    vendor = "Unitree Robotics"
    model = "A1"
    facts = [
        Fact("The README limits this package to Gazebo simulation of low-level torque, position and angular "
             "velocity control and says Gazebo cannot do high-level walking; physical robots use the separate "
             "unitree_ros_to_real project.", source="vendor_doc", ref="README.md:2-3"),
        Fact("normal.launch spawns the twelve A1 joint controllers under the /a1_gazebo namespace.",
             source="upstream_code", ref="unitree_gazebo/launch/normal.launch:36-45"),
        Fact("servo.cpp subscribes to the twelve /<robot>_gazebo/<joint>_controller/state MotorState topics and "
             "to /trunk_imu and the four /visual/*_foot_contact/the_force topics.",
             source="upstream_code", ref="unitree_controller/src/servo.cpp:32-48"),
        Fact("servo.cpp creates the twelve /<robot>_gazebo/<joint>_controller/command MotorCmd "
             "publishers with queue size 1.", source="upstream_code",
             ref="unitree_controller/src/servo.cpp:224-235"),
        Fact("UnitreeJointController subscribes to the relative command topic and publishes the relative state "
             "topic with a realtime publisher.", source="upstream_code",
             ref="unitree_legged_control/src/joint_controller.cpp:88-95"),
        Fact("The controller's update loop reads command.readFromRT() on every cycle, so the last MotorCmd "
             "continues to be applied until another command replaces it.", source="upstream_code",
             ref="unitree_legged_control/src/joint_controller.cpp:136-161"),
        Fact("BRAKE mode sets zero position stiffness, zero velocity, damping 20 and zero torque; it is a "
             "damping command, not an acknowledged stop of the controller or the Gazebo world.",
             source="upstream_code", ref="unitree_legged_control/src/joint_controller.cpp:156-162"),
        Fact("UnitreeJointController::stopping() has an empty body; the controller lifecycle reports no stop "
             "action.", source="upstream_code", ref="unitree_legged_control/src/joint_controller.cpp:205-206"),
        Fact("The MotorCmd and MotorState message types are included from the unitree_legged_msgs package by the "
             "joint-controller header.", source="upstream_code",
             ref="unitree_legged_control/include/joint_controller.h:21-22"),
        Fact("The A1 URDF states revolute position, velocity and effort limits for the twelve leg joints.",
             source="upstream_code", ref=f"{_A1_URDF}:369-895"),
        Fact("The aggregate /<robot>_gazebo/lowState/state LowState publisher is created in the servo main "
             "loop.", source="upstream_code", ref=_LOW_STATE_REF),
    ]
    safe_state = (
        "No native stop is bound. The runtime latch refuses further commands, but each "
        "UnitreeJointController keeps applying the last MotorCmd from its RealtimeBuffer and the Gazebo world "
        "continues to step; a BRAKE MotorCmd is a damping command on one command topic and is not an "
        "acknowledged stop."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step, no controller update loop and no pacing; "
                     "canned LowState values do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the twelve command topics and the aggregate "
            "LowState subscription declared here and runs no ROS graph, controller, Gazebo physics or contact",
            "the LowState values are placeholders; a live deployment must receive them from the operator's "
            "unitree_servo and Gazebo graph",
            "the twelve command publications are independent topics, not one atomic twelve-joint action; a "
            "publish receipt proves only that rosbridge accepted the message",
            "no native stop is bound and the last MotorCmd persists in the controller's realtime buffer, so the "
            "runtime latch cannot stop the simulated physics",
            "the upstream package has no acknowledged stop service or action and no hardware interface at this "
            "pin; physical control is a separate unitree_ros_to_real deployment",
            "position and damping gains are operator-required because no pinned text states a device gain bound",
        ],
    }

    commands = _COMMANDS
    actions = _ACTIONS
    safety_bindings = {"safe_state": _BRAKE}
