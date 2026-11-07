"""OpenMHS rosbridge driver for the ROBOTIS OpenMANIPULATOR OMX-F arm.

The pinned repository is the ROS 2 package set for the OpenMANIPULATOR
family.  The card's keyboard teleop entry (``KeyboardController``) is a
console client, not the device interface itself: it publishes a
``trajectory_msgs/JointTrajectory`` to ``/arm_controller/joint_trajectory``,
sends ``control_msgs/action/GripperCommand`` goals to
``/gripper_controller/gripper_cmd`` and subscribes to ``/joint_states``.
The controller configuration in the same clone names the arm controller as
``joint_trajectory_controller/JointTrajectoryController`` and the gripper
controller as ``position_controllers/GripperActionController``; the bringup
helper uses the controller's accepted/terminal
``/arm_controller/follow_joint_trajectory`` action instead of the
fire-and-forget topic.  This package exposes that action-backed arm path,
the gripper action and the joint-state observation.  It does not claim that
a topic publication is a completed motion.

This is a configuration-only :class:`RosDriver`; it declares no Python
native class and never imports ROS.  Every endpoint, type and fact cites the
pinned clone at d31000d90c679af9c982e73de8b12d777c5ff7dd.  The fake transport
is ROS-free and no ROS graph, controller or hardware is contacted.

Safety: the only source-referenced stop-shaped interface in the clone is the
external ``dynamixel_hardware_interface`` ``std_srvs/srv/SetBool`` service
``set_dxl_torque``.  The GUI uses it with ``data=false`` to disable joint
torque.  Torque disable is not a physical emergency stop, does not sense
zero velocity or isolation, and an unsupported gravity-loaded arm can fall.
Torque-off remains an ordinary service request with no safe-state or e-stop
attribution. The external server retirement semantics, gravity support and
controller timing profile must be established before native admission.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The five arm joints declared by the teleop and the omx_f controller config.
_ARM_JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5"]

#: The omx_f arm xacro gives every arm joint the same revolute limit.
_ARM_LIMIT_REF = "open_manipulator_description/urdf/omx_f/omx_f_arm.urdf.xacro:37"

#: Bringup reads the controller's FollowJointTrajectory action name here.
_ARM_ACTION_REF = "open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:44"
_ARM_TYPE_REF = "open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:22"

#: The teleop creates the gripper action client and the joint-state subscriber.
_GRIPPER_ACTION_REF = "open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:46-47"
_GRIPPER_TYPE_REF = "open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:26"
_JOINT_STATE_REF = "open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:51-52"
_JOINT_STATE_TYPE_REF = "open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:30"

#: The GUI creates a std_srvs SetBool client for the relative torque service.
_TORQUE_REF = "open_manipulator_gui/src/omx_f/qnode.cpp:75-76"
_TORQUE_TYPE_REF = "open_manipulator_gui/include/omx_f_gui/qnode.hpp:31"

#: The hardware starts with torque disabled (omx_f.ros2_control.xacro:25).
_INITIAL_TORQUE_REF = "open_manipulator_description/ros2_control/omx_f.ros2_control.xacro:25"

#: Shared joint-position bound.  The xacro writes -pi*2.0 .. pi*2.0; the
#: Limit stores the equivalent radians.  This is the installed model's
#: revolute-joint description, not a measurement of the delivered arm.
_ARM_POSITION_LIMIT = Limit(
    min=-6.283185307179586,
    max=6.283185307179586,
    unit="rad",
    source="upstream_code",
    ref=_ARM_LIMIT_REF,
)

_POSITION_FIELD = Field(
    "number",
    unit="rad",
    description="Target angle of one arm joint in radians",
    limit=_ARM_POSITION_LIMIT,
)

_ARM_POINT = Field(
    "object",
    description="One trajectory point for joint1 through joint5",
    properties={
        "positions": Field(
            "array",
            unit="rad",
            description="Target angles for joint1, joint2, joint3, joint4 and joint5, in that order",
            length=5,
            items=_POSITION_FIELD,
        ),
    },
)

_ARM_ACTION = {
    "action": "/arm_controller/follow_joint_trajectory",
    "profile": "ros2-native",
    "type": "control_msgs/action/FollowJointTrajectory",
    "source_name": "/arm_controller/follow_joint_trajectory",
    "source_ref": _ARM_ACTION_REF,
    "type_ref": _ARM_TYPE_REF,
    "request": {"trajectory": {"joint_names": _ARM_JOINTS, "points": []}},
    "args": {"trajectory.points": {"from": "input.points"}},
    "success": {"path": "error_code", "equals": 0},
    "result": {"map": {"error_code": "error_code", "error_string": "error_string"}},
}

_GRIPPER_ACTION = {
    "action": "/gripper_controller/gripper_cmd",
    "profile": "ros2-native",
    "type": "control_msgs/action/GripperCommand",
    "source_name": "/gripper_controller/gripper_cmd",
    "source_ref": _GRIPPER_ACTION_REF,
    "type_ref": _GRIPPER_TYPE_REF,
    "request": {"command": {"position": 0.0, "max_effort": 0.0}},
    "args": {
        "command.position": {"from": "input.position"},
        "command.max_effort": {"from": "input.max_effort"},
    },
    "success": {"path": "reached_goal", "equals": True},
    "result": {
        "map": {
            "reached_goal": "reached_goal",
            "stalled": "stalled",
            "position": "position",
            "effort": "effort",
        }
    },
}

_JOINT_STATE = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_name": "/joint_states",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_TYPE_REF,
    "path": "$",
    "result": {"map": {"name": "name", "position": "position", "velocity": "velocity"}},
}

#: The relative upstream name is made absolute at the deployment boundary.
_TORQUE_OFF = {
    "service": "/dynamixel_hardware_interface/set_dxl_torque",
    "type": "std_srvs/srv/SetBool",
    "source_name": "dynamixel_hardware_interface/set_dxl_torque",
    "source_ref": _TORQUE_REF,
    "type_ref": _TORQUE_TYPE_REF,
    "request": {"data": False},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"acknowledged": "success"}},
    "timeout_ms": 2000,
}

_ACKNOWLEDGED = Field(
    "boolean",
    description="True when the external torque service returned success; this is not a stopped-state measurement",
)


class OpenManipulatorOmxF(RosDriver):
    device_id = "open-manipulator-omx-f"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeOpenManipulator"}
    tags = ["ros", "ros2", "robotis", "open-manipulator", "omx-f", "arm", "trajectory", "gripper"]
    display_name = "ROBOTIS OpenMANIPULATOR OMX-F arm"
    vendor = "ROBOTIS"
    model = "OMX-F"
    facts = [
        Fact("KeyboardController creates a JointTrajectory publisher on /arm_controller/joint_trajectory.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:41-43"),
        Fact("KeyboardController creates a GripperCommand action client on /gripper_controller/gripper_cmd.",
             source="upstream_code", ref=_GRIPPER_ACTION_REF),
        Fact("KeyboardController subscribes to /joint_states with sensor_msgs/JointState.",
             source="upstream_code", ref=_JOINT_STATE_REF),
        Fact("KeyboardController uses the five arm joint names joint1 through joint5.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:56-62"),
        Fact("The teleop hardcodes demo gripper travel constants gripper_max 1.1 and gripper_min 0.0.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:64-66"),
        Fact("The teleop hardcodes demo max_effort 10.0 for the gripper command.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:121"),
        Fact("send_arm_command publishes a one-point JointTrajectory and does not wait for controller execution.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:108-116"),
        Fact("send_gripper_command sends a GripperCommand goal and waits only for the send future, not the terminal "
             "result.",
             source="upstream_code",
             ref="open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:118-126"),
        Fact("The bringup executor imports control_msgs.action.FollowJointTrajectory.",
             source="upstream_code",
             ref="open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:22"),
        Fact("The bringup executor defaults action_topic to /arm_controller/follow_joint_trajectory.",
             source="upstream_code",
             ref="open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:44"),
        Fact("The bringup executor's goal_response_callback logs a rejected goal and returns without requesting "
             "a result.",
             source="upstream_code",
             ref="open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:126-133"),
        Fact("shutdown_node requests goal cancellation only when a goal handle exists, does not await it, then "
             "destroys the node and exits.",
             source="upstream_code",
             ref="open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:185-190"),
        Fact("The omx_f controller manager configures arm_controller as a JointTrajectoryController and "
             "gripper_controller as a GripperActionController.",
             source="upstream_code",
             ref="open_manipulator_bringup/config/omx_f/hardware_controller_manager.yaml:9-13"),
        Fact("The arm_controller declares joint1 through joint5 and the gripper_controller declares "
             "gripper_joint_1.",
             source="upstream_code",
             ref="open_manipulator_bringup/config/omx_f/hardware_controller_manager.yaml:18-39"),
        Fact("The omx_f arm xacro gives each of joint1 through joint5 the same revolute limit block: velocity "
             "4.8, effort 1000, lower -pi*2.0 and upper pi*2.0.",
             source="upstream_code",
             ref="open_manipulator_description/urdf/omx_f/omx_f_arm.urdf.xacro:37-177"),
        Fact("gripper_joint_1 is revolute and its model limit block gives velocity 4.8, effort 1000, "
             "lower -pi*2.0 and upper pi*2.0.", source="upstream_code",
             ref="open_manipulator_description/urdf/omx_f/omx_f_arm.urdf.xacro:207-212"),
        Fact("The omx_f ros2_control description starts with disable_torque_at_init=true.",
             source="upstream_code", ref=_INITIAL_TORQUE_REF),
        Fact("The omx_f ros2_control description names the relative torque service "
             "dynamixel_hardware_interface/set_dxl_torque.",
             source="upstream_code",
             ref="open_manipulator_description/ros2_control/omx_f.ros2_control.xacro:30"),
        Fact("QNode::init creates a std_srvs::srv::SetBool client named "
             "dynamixel_hardware_interface/set_dxl_torque.",
             source="upstream_code", ref=_TORQUE_REF),
        Fact("QNode::sendTorqueSrv sets request->data from its checked argument and calls async_send_request, but "
             "logs success and returns true without waiting for or checking the service response.",
             source="upstream_code",
             ref="open_manipulator_gui/src/omx_f/qnode.cpp:302-314"),
        Fact("QNode::stopMotion sets a GUI flag and calls MoveGroupInterface::stop locally in the GUI process.",
             source="upstream_code",
             ref="open_manipulator_gui/src/omx_f/qnode.cpp:280-289"),
        Fact("resetStopRequest only clears the GUI's stop_requested_ flag.",
             source="upstream_code",
             ref="open_manipulator_gui/src/omx_f/qnode.cpp:297-300"),
    ]
    # The pinned GUI client does not prove external torque-service ownership
    # retirement or safe support of a gravity-loaded arm. Native safety is blocked.

    parameters = {
        "joint_positions": Field(
            "array",
            unit="rad",
            description="Joint positions reported by one /joint_states sample in the publisher's order",
            items=Field("number", unit="rad", description="One joint position"),
        ),
    }
    reads = {
        "joint_positions": {
            "topic": "/joint_states",
            "type": "sensor_msgs/msg/JointState",
            "source_name": "/joint_states",
            "source_ref": _JOINT_STATE_REF,
            "type_ref": _JOINT_STATE_TYPE_REF,
            "path": "position",
        },
    }
    commands = {
        "x-cap.robotis-git.arm_trajectory.v1": _ARM_ACTION,
        "x-cap.robotis-git.gripper_command.v1": _GRIPPER_ACTION,
        "x-cap.robotis-git.joint_state.v1": _JOINT_STATE,
        "x-cap.robotis-git.torque_off.v1": _TORQUE_OFF,
    }
    actions = {
        "x-cap.robotis-git.arm_trajectory.v1": Action(
            name="follow_arm_trajectory",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=60000,
            description=(
                "Send one JointTrajectory point through the arm controller's acknowledged "
                "FollowJointTrajectory action and report the controller's terminal error_code; this does not "
                "sense joint quiescence or verify that the arm reached the target"
            ),
            input={"points": Field(
                "array",
                description="One trajectory point; it becomes trajectory.points of the FollowJointTrajectory goal",
                length=1,
                items=_ARM_POINT,
            )},
            output={
                "error_code": Field("integer",
                                    description="FollowJointTrajectory result error_code; 0 is SUCCESSFUL"),
                "error_string": Field("string",
                                      description="FollowJointTrajectory result error_string"),
            },
        ),
        "x-cap.robotis-git.gripper_command.v1": Action(
            name="command_gripper",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=30000,
            description=(
                "Send a GripperCommand goal and report the controller's terminal reached_goal, stalled, "
                "position and effort fields; the effort unit is the controller's native effort unit"
            ),
            input={
                "position": Field(
                    "number",
                    unit="rad",
                    description="Target position of gripper_joint_1 in radians",
                    limit=Limit.operator_required(
                        "the xacro models gripper_joint_1 at -2*pi..2*pi radians (omx_f_arm.urdf.xacro:207-212), "
                        "but the operator must supply the narrower installed gripper travel envelope; "
                        "teleop 0.0-1.1 is only a demo constant"
                    ),
                ),
                "max_effort": Field(
                    "number",
                    unit="1",
                    description="Maximum effort in the gripper controller's native effort units",
                    limit=Limit.operator_required(
                        "the model effort limit is 1000 (omx_f_arm.urdf.xacro:212); its mapping to the installed "
                        "GripperCommand controller effort and safe payload needs an operator envelope; "
                        "teleop max_effort=10.0 is only a demo constant"
                    ),
                ),
            },
            output={
                "reached_goal": Field("boolean",
                                      description="GripperCommand result reached_goal flag"),
                "stalled": Field("boolean", description="GripperCommand result stalled flag"),
                "position": Field("number", unit="rad",
                                  description="Gripper joint position reported by the action result"),
                "effort": Field("number", unit="1",
                                description="Effort reported by the action result in the controller's native unit"),
            },
        ),
        "x-cap.robotis-git.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description=(
                "Read one sensor_msgs/JointState sample from /joint_states; the arrays are reported in the "
                "publisher's order and this does not prove that every arm joint is present"
            ),
            output={
                "name": Field("array",
                              description="Joint names reported by the JointState publisher",
                              items=Field("string", description="One joint name")),
                "position": Field("array", unit="rad",
                                  description="Joint positions in the publisher's order",
                                  items=Field("number", unit="rad", description="One joint position")),
                "velocity": Field("array", unit="rad/s",
                                  description="Joint velocities in the publisher's order",
                                  items=Field("number", unit="rad/s", description="One joint velocity")),
            },
        ),
        "x-cap.robotis-git.torque_off.v1": Action(
            name="disable_joint_torque",
            verb="invoke",
            description=(
                "Disable joint torque through the external acknowledged set_dxl_torque SetBool service "
                "(data=false); this is a software service acknowledgement and is not a physical emergency stop, "
                "a zero-velocity measurement or a guarantee that a gravity-loaded arm is held"
            ),
            output={"acknowledged": _ACKNOWLEDGED},
        ),
    }
    # No source-proven settled stop; torque-off is an ordinary request only.
    safety_bindings = {}
