"""OpenMHS rosbridge driver for the UR10e arm on the fake-hardware path.

The pinned repository is a UR10e plus Robotiq 2F140 stack. This package
serves only the fake-hardware path of ``ur_robotiq_control.launch.py``
(``use_fake_hardware`` true): the README's mock-components strategy, the
``controller_manager`` ``ros2_control_node``, and the six-joint
``scaled_joint_trajectory_controller`` FollowJointTrajectory action. It does
not serve the Isaac topic-based launch, and it does not serve the real
``ur_ros2_control_node`` that the same launch starts unless
``use_fake_hardware`` is set. Those two nodes publish the same endpoint
names, so a rosbridge pointed at the real node can command a real arm. The
mode stays ``simulated``; the risk is R2.

This is a configuration-only :class:`RosDriver`. It declares no Python
native class and never imports ROS, starts a controller manager or launches
a robot.

The primary control path is ``control_msgs/action/FollowJointTrajectory`` at
``/scaled_joint_trajectory_controller/follow_joint_trajectory``. The vendored
driver example creates that client and sends joint positions with a
``time_from_start``. The action terminal result is the controller's
``error_code`` and ``error_string``; it is not a stopped-state measurement.

The e-stop is a controller switch served by the controller manager of
ros2_control, cited as a reviewed companion source fetched at a pinned
commit (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): controller_manager 2.54.4 (Humble)
``/controller_manager/switch_controller`` deactivates
``scaled_joint_trajectory_controller`` (STRICT, a 0.4 s switch wait). The
scaled controller does not override ``on_deactivate``, so
joint_trajectory_controller 2.54.1 applies: the goal is aborted and the
stored trajectory is dropped. The stop is confirmed by reading
``/controller_manager/list_controllers`` back with a list-element predicate
(E4): the one element named ``scaled_joint_trajectory_controller`` must
report the state ``inactive``. The world keeps running; it is the
controller's state, not a measured standstill, and it does not prove that
``joint_trajectory_controller``, the forward controllers or the gripper are
inactive.

The declared re-enable (CORE-086) switches that same controller on again.
The trajectory the stop dropped is not resumed (the orchestrator's SAFE-042
condition: cleared by the stop itself). On activation the controller holds
the position of the state it starts from. This deployment commands position
only and reads position and velocity, so the command-interface read fails
on velocity and the re-enable holds the measured position. Reset releases
the latch only and does not activate the controller.

The lock profile name ``ros2-humble-gzsim6`` is the existing shared label
of these two pins. It is not a claim that this package runs Gazebo.

Every package endpoint, type and fact cites the pinned clone at
7db5397edae2795c8366d1ac1581f277124bde98. Companion facts cite the pins in
``task.json``. The fake transport is ROS-free; no ROS graph, controller,
simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) --
#: controller_manager 2.54.4 (ros2_control, Humble) at 7f26da88: the switch and the list read-back.
_CM = "companion:ros2_control/controller_manager/src/controller_manager.cpp"
_CM_NODE = "companion:ros2_control/controller_manager/src/ros2_control_node.cpp"
_CM_MSGS = "companion:ros2_control/controller_manager_msgs"
#: joint_trajectory_controller 2.54.1 (ros2_controllers, Humble) at 65db7362: deactivation and activation.
_JTC_SRC = "companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp"
_CONTROLLER = "scaled_joint_trajectory_controller"
#: STRICT (2): the switch fails if anything goes wrong; a 0.4 s wait for the controller manager's update loop.
_SWITCH_WAIT = {"sec": 0, "nanosec": 400000000}

_EXAMPLES = "src/Universal_Robots_ROS2_Driver/ur_robot_driver/examples/examples.py"
_XBOX = "src/ur_robotiq_servo/ur_robotiq_servo/xbox_control.py"
_LAUNCH = "src/ur_robotiq_description/launch/ur_robotiq_control.launch.py"
_ISAAC = "src/ur_robotiq_description/launch/ur_robotiq_isaac_control.launch.py"
_MOVEIT = "src/ur_robotiq_moveit_config/launch/ur_robotiq_moveit.launch.py"
_YAML = "src/ur_robotiq_description/config/ur_robotiq_controllers.yaml"
_LIMITS = "src/Universal_Robots_ROS2_Description/config/ur10e/joint_limits.yaml"
_HEADER = ("src/Universal_Robots_ROS2_Driver/ur_controllers/include/ur_controllers/"
           "scaled_joint_trajectory_controller.hpp")
_SCALED = "src/Universal_Robots_ROS2_Driver/ur_controllers/src/scaled_joint_trajectory_controller.cpp"
_MACRO = "src/Universal_Robots_ROS2_Description/urdf/ur_macro.xacro"
_ROS2C = "src/Universal_Robots_ROS2_Description/urdf/ur.ros2_control.xacro"
_GENERIC = "companion:ros2_control/hardware_interface/src/mock_components/generic_system.cpp"
_RM = "companion:ros2_control/hardware_interface/src/resource_manager.cpp"

#: The e-stop: deactivate scaled_joint_trajectory_controller through the controller manager's switch_controller.
_SWITCH_OFF = {
    "service": "/controller_manager/switch_controller",
    "type": "controller_manager_msgs/srv/SwitchController",
    "source_name": "~/switch_controller",
    "source_ref": _CM + ":557-560",
    "type_ref": _CM + ":557",
    "state_ref": _JTC_SRC + ":1055-1106",
    "description": "Deactivate scaled_joint_trajectory_controller (controller_manager switch_controller, STRICT)",
    "request": {"activate_controllers": [], "deactivate_controllers": [_CONTROLLER], "strictness": 2,
                "activate_asap": False, "timeout": _SWITCH_WAIT},
    "success": {"path": "ok", "equals": True},
    "timeout_ms": 600,
}
#: The read-back that confirms it: list_controllers reports that one controller's lifecycle state (E4).
_LIST = {
    "service": "/controller_manager/list_controllers",
    "type": "controller_manager_msgs/srv/ListControllers",
    "source_name": "~/list_controllers",
    "source_ref": _CM + ":537-539",
    "type_ref": _CM + ":537",
    "state_ref": _CM + ":1752-1755",
    "description": "Read the controllers back; confirmed only when scaled_joint_trajectory_controller reports inactive",
    "request": {},
    "success": {"path": "controller", "where": {"name": _CONTROLLER}, "field": "state", "equals": "inactive"},
    "timeout_ms": 300,
}
#: The declared re-enable after a reset (CORE-086): activate scaled_joint_trajectory_controller again.
_SWITCH_ON = {
    "service": "/controller_manager/switch_controller",
    "type": "controller_manager_msgs/srv/SwitchController",
    "source_name": "~/switch_controller",
    "source_ref": _CM + ":557-560",
    "type_ref": _CM + ":557",
    "description": ("Activate scaled_joint_trajectory_controller again (it holds the state it starts from: here the "
                    "measured position, as the position-only command interface defeats the last-command restore)"),
    "request": {"activate_controllers": [_CONTROLLER], "deactivate_controllers": [], "strictness": 2,
                "activate_asap": False, "timeout": _SWITCH_WAIT},
    "success": {"path": "ok", "equals": True},
    "result": {"acknowledged": {"value": True}},
    "timeout_ms": 600,
}
_REENABLE_ID = "x-cap.qdeyna.activate_controller.v1"

_COMPANION_FACTS = [
    Fact("ros2_control_node names its controller manager node controller_manager.",
         source="upstream_code", ref=_CM_NODE + ":43"),
    Fact("The controller manager creates the list_controllers service with the "
         "controller_manager_msgs::srv::ListControllers type under its private name.", source="upstream_code",
         ref=_CM + ":537-539"),
    Fact("The controller manager creates the switch_controller service with the "
         "controller_manager_msgs::srv::SwitchController type under its private name.", source="upstream_code",
         ref=_CM + ":557-560"),
    Fact("switch_controller_service_cb passes the request's controllers to activate and deactivate, its strictness, "
         "activate_asap and timeout to switch_controller and answers ok only when that returns OK.",
         source="upstream_code", ref=_CM + ":1980-2031"),
    Fact("switch_controller asks the realtime update loop for the switch and waits for it up to the request's timeout "
         "(1 s when it is zero); when the wait times out it clears the request and returns ERROR.",
         source="upstream_code", ref=_CM + ":1307-1331"),
    Fact("The controller manager's update loop performs a requested switch.", source="upstream_code",
         ref=_CM + ":2224-2228"),
    Fact("list_controllers fills each ControllerState name from the controller info and its state from the "
         "lifecycle label.", source="upstream_code", ref=_CM + ":1752-1755"),
    Fact("SwitchController defines strictness STRICT as 2, under which the switch fails if anything goes wrong, and "
         "returns ok when the controllers were switched.", source="upstream_code",
         ref=_CM_MSGS + "/srv/SwitchController.srv:5-33"),
    Fact("ControllerState's state field is unconfigured, inactive, active or finalized.", source="upstream_code",
         ref=_CM_MSGS + "/msg/ControllerState.msg:1-2"),
    Fact("On deactivation the trajectory controller aborts an active goal, keeps each position command at its last "
         "value, releases its interfaces and drops its stored trajectory.", source="upstream_code",
         ref=_JTC_SRC + ":1055-1106"),
    Fact("On activation the trajectory controller takes its current and last commanded state from the command "
         "interfaces when set_last_command_interface_value_as_state_on_activation is set and the command read "
         "succeeds, and otherwise reads both from the state interfaces.", source="upstream_code",
         ref=_JTC_SRC + ":1004-1020"),
    Fact("set_last_command_interface_value_as_state_on_activation defaults to true: the last command interface value "
         "is then used as both the current state and the last commanded state on activation.",
         source="upstream_code",
         ref="companion:ros2_controllers/joint_trajectory_controller/src/"
             "joint_trajectory_controller_parameters.yaml:75-79"),
    Fact("Reading the state from the command interfaces fails when the controller has a velocity state interface but "
         "no velocity command interface with values.", source="upstream_code", ref=_JTC_SRC + ":498-510"),
    Fact("On activation the trajectory controller starts by holding the position of the state it starts from.",
         source="upstream_code", ref=_JTC_SRC + ":1027-1029"),
    Fact("set_hold_position commands the positions of the controller's current state (state_current_).",
         source="upstream_code", ref=_JTC_SRC + ":1617-1626"),
    Fact("The trajectory controller rejects a new action goal while it is inactive.", source="upstream_code",
         ref=_JTC_SRC + ":1251-1262"),
    Fact("Before activation the controller manager claims every individual state interface the controller "
         "requested and skips that controller when the claim throws.",
         source="upstream_code", ref=_CM + ":1653-1681"),
    Fact("claim_state_interface throws when the state interface key does not exist.",
         source="upstream_code", ref=_RM + ":743-747"),
    Fact("GenericSystem records each gpio state interface from the hardware info.",
         source="upstream_code", ref=_GENERIC + ":244-251"),
    Fact("GenericSystem exports each gpio state interface.",
         source="upstream_code", ref=_GENERIC + ":301-305"),
    Fact("GenericSystem initializes a gpio state from the component parameter initial_<interface name> when the "
         "interface has no initial_value.",
         source="upstream_code", ref=_GENERIC + ":714-726"),
]

_JOINTS = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]

#: The ur10e joint_limits.yaml writes these bounds with a !degrees tag. Copying the literals as radians would
#: invent a number the line does not state, so the operator supplies the radian envelope.
_POSITION_LIMIT = Limit.operator_required(
    "ur10e joint_limits.yaml writes min_position and max_position with the !degrees tag, so those literals are "
    "degrees and are not a radian envelope; the operator supplies the radian joint-position envelope"
)
_TIME_SEC_LIMIT = Limit.operator_required(
    "the pinned clone states no maximum trajectory duration; the operator supplies the trajectory "
    "time envelope for the deployed controller"
)
_TIME_NSEC_LIMIT = Limit.operator_required(
    "the pinned clone states no nanosecond range for a trajectory Duration; the operator supplies the "
    "trajectory time envelope for the deployed controller"
)

_POINT = Field(
    "object",
    description="One FollowJointTrajectory point",
    properties={
        "positions": Field(
            "array",
            unit="rad",
            length=6,
            description="Target joint angles",
            items=Field("number", unit="rad", description="One joint's target angle"),
            limit=_POSITION_LIMIT,
        ),
        "time_from_start": Field(
            "object",
            description="Start offset",
            properties={
                "sec": Field("integer", unit="s", description="Whole seconds", limit=_TIME_SEC_LIMIT),
                "nanosec": Field("integer", unit="ns", description="Nanoseconds within the second",
                                 limit=_TIME_NSEC_LIMIT),
            },
        ),
    },
)

_ARM_ACTION = {
    "action": "/scaled_joint_trajectory_controller/follow_joint_trajectory",
    "profile": "ros2-native",
    "type": "control_msgs/action/FollowJointTrajectory",
    "source_name": "/scaled_joint_trajectory_controller/follow_joint_trajectory",
    "source_ref": _EXAMPLES + ":94",
    "type_ref": _EXAMPLES + ":32",
    "request": {"trajectory": {"joint_names": _JOINTS, "points": []}},
    "args": {"trajectory.points": {"from": "input.points"}},
    "success": {"path": "error_code", "equals": 0},
    "result": {"map": {"error_code": "error_code", "error_string": "error_string"}},
    "timeout_ms": 2000,
}

_JOINT_STATE = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "/joint_states",
    "source_ref": _XBOX + ":44",
    "type_ref": _XBOX + ":3",
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"name": "name", "position": "position", "velocity": "velocity"}},
}

_READ_JOINT_POSITIONS = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "/joint_states",
    "source_ref": _XBOX + ":44",
    "type_ref": _XBOX + ":3",
    "path": "position",
}

_READ_JOINT_VELOCITIES = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "/joint_states",
    "source_ref": _XBOX + ":44",
    "type_ref": _XBOX + ":3",
    "path": "velocity",
}

_POSITIONS_FIELD = Field(
    "array",
    unit="rad",
    description="Joint positions from one JointState sample, in publisher order",
    items=Field("number", unit="rad", description="One joint position"),
)

_VELOCITIES_FIELD = Field(
    "array",
    unit="rad/s",
    description="Joint velocities from one JointState sample, in publisher order",
    items=Field("number", unit="rad/s", description="One joint velocity"),
)

_NAMES_FIELD = Field(
    "array",
    description="Joint names from the JointState publisher",
    items=Field("string", description="One joint name"),
)


class Ur10eArm(RosDriver):
    device_id = "ur10e_arm"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md). The fake-hardware
    # trajectory commands move the arm joints even though this package does
    # not attach physical hardware. The same endpoint names exist on the real
    # driver node, which this package does not serve.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeUr10eArm"}
    tags = ["ros", "ros2", "fake-hardware", "robot-arm", "trajectory", "joint-state", "ur10e"]
    display_name = "UR10e arm (fake hardware)"
    vendor = "qdeyna"
    model = "UR10e"
    facts = [
        Fact("The README is a setup guide for a UR10e robotic arm with a Robotiq 2F140 gripper, integrated with "
             "Isaac Sim.",
             source="vendor_doc", ref="README.md:1-3"),
        Fact("The README lists two control strategies: Mock Components, and topic-based ROS 2 control with Isaac Sim.",
             source="vendor_doc", ref="README.md:12-14"),
        Fact("The ROS 2 devcontainer feature line names ROS 2 Humble with all dependencies.",
             source="vendor_doc", ref="README.md:105"),
        Fact("examples.py imports control_msgs.action.FollowJointTrajectory.",
             source="upstream_code", ref=_EXAMPLES + ":32"),
        Fact("examples.py lists the six controlled joints as shoulder_pan_joint, shoulder_lift_joint, elbow_joint, "
             "wrist_1_joint, wrist_2_joint and wrist_3_joint, in that order.",
             source="upstream_code", ref=_EXAMPLES + ":45-52"),
        Fact("examples.py creates a FollowJointTrajectory action client on the absolute "
             "/scaled_joint_trajectory_controller/follow_joint_trajectory endpoint.",
             source="upstream_code", ref=_EXAMPLES + ":92-96"),
        Fact("examples.py also names the absolute /controller_manager/switch_controller service.",
             source="upstream_code", ref=_EXAMPLES + ":82"),
        Fact("examples.py treats a trajectory as successful when the result error_code equals "
             "FollowJointTrajectory.Result.SUCCESSFUL.",
             source="upstream_code", ref=_EXAMPLES + ":135"),
        Fact("xbox_control.py imports sensor_msgs.msg.JointState.",
             source="upstream_code", ref=_XBOX + ":3"),
        Fact("xbox_control.py subscribes to the absolute /joint_states topic with a JointState callback.",
             source="upstream_code", ref=_XBOX + ":44"),
        Fact("ur_robotiq_control.launch.py starts controller_manager's ros2_control_node only when "
             "use_fake_hardware is true.",
             source="upstream_code", ref=_LAUNCH + ":193-202"),
        Fact("The same launch starts ur_robot_driver's ur_ros2_control_node unless use_fake_hardware is true.",
             source="upstream_code", ref=_LAUNCH + ":204-213"),
        Fact("The launch spawns robotiq_gripper_controller unless use_fake_hardware is true, and "
             "robotiq_gripper_joint_trajectory_controller when it is true, both against /controller_manager.",
             source="upstream_code", ref=_LAUNCH + ":215-225"),
        Fact("The launch's controller spawners pass --controller-manager /controller_manager.",
             source="upstream_code", ref=_LAUNCH + ":333-338"),
        Fact("The launch spawns forward_position_controller and forward_gripper_position_controller inactive.",
             source="upstream_code", ref=_LAUNCH + ":350-354"),
        Fact("The launch's initial joint-controller spawner addresses the controller manager as /controller_manager.",
             source="upstream_code", ref=_LAUNCH + ":358-364"),
        Fact("The controllers_file launch argument defaults to ur_robotiq_controllers.yaml.",
             source="upstream_code", ref=_LAUNCH + ":453-455"),
        Fact("The tf_prefix launch argument defaults to an empty string.",
             source="upstream_code", ref=_LAUNCH + ":483-487"),
        Fact("The use_fake_hardware launch argument defaults to false and is described as starting the robot with "
             "fake hardware that mirrors commands to its states.",
             source="upstream_code", ref=_LAUNCH + ":492-495"),
        Fact("The initial_joint_controller launch argument defaults to scaled_joint_trajectory_controller.",
             source="upstream_code", ref=_LAUNCH + ":521-523"),
        Fact("The activate_joint_controller launch argument defaults to true.",
             source="upstream_code", ref=_LAUNCH + ":528-530"),
        Fact("ur_robotiq_controllers.yaml declares joint_trajectory_controller, "
             "scaled_joint_trajectory_controller, the forward position and velocity controllers and the Robotiq "
             "gripper controllers.",
             source="upstream_code", ref=_YAML + ":15-37"),
        Fact("scaled_joint_trajectory_controller is configured for the six arm joints with a position command "
             "interface, position and velocity state interfaces, and a speed_scaling state interface name.",
             source="upstream_code", ref=_YAML + ":90-116"),
        Fact("forward_position_controller is configured for the same six arm joints.",
             source="upstream_code", ref=_YAML + ":129-137"),
        Fact("The ur10e joint_limits.yaml writes min_position and max_position with the !degrees tag "
             "(shoulder joints and wrists 360, elbow 180).",
             source="upstream_code", ref=_LIMITS + ":18-80"),
        Fact("ScaledJointTrajectoryController includes joint_trajectory_controller/joint_trajectory_controller.hpp.",
             source="upstream_code", ref=_HEADER + ":43"),
        Fact("ScaledJointTrajectoryController extends JointTrajectoryController and overrides "
             "state_interface_configuration, on_activate, update and on_init; on_deactivate is not among them.",
             source="upstream_code", ref=_HEADER + ":52-64"),
        Fact("The scaled controller's scaling_factor_ member defaults to 1.0.",
             source="upstream_code", ref=_HEADER + ":78"),
        Fact("state_interface_configuration appends speed_scaling_interface_name when that name is non-empty.",
             source="upstream_code", ref=_SCALED + ":63-70"),
        Fact("on_activate searches the state interfaces already assigned to the controller for the speed-scaling "
             "name, logs an error when that search misses, and then calls JointTrajectoryController::on_activate.",
             source="upstream_code", ref=_SCALED + ":75-95"),
        Fact("When use_fake_hardware is true, ur_macro.xacro includes ur.ros2_control.xacro.",
             source="upstream_code", ref=_MACRO + ":113-114"),
        Fact("The fake-hardware ros2_control plugin in that description is mock_components/GenericSystem.",
             source="upstream_code", ref=_ROS2C + ":44-48"),
        Fact("Inside the block omitted for sim_gazebo and sim_ignition, the description declares gpio "
             "speed_scaling with state interface speed_scaling_factor and parameter initial_speed_scaling_factor 1. "
             "The comment says the following are joints used only for testing with fake hardware.",
             source="upstream_code", ref=_ROS2C + ":140-166"),
        Fact("The scaled controller's update reads the scaling factor only when the interface is present, and "
             "returns OK immediately while the lifecycle state is inactive.",
             source="upstream_code", ref=_SCALED + ":101-107"),
        Fact("ur_robotiq_isaac_control.launch.py defaults initial_joint_controller to joint_trajectory_controller.",
             source="upstream_code", ref=_ISAAC + ":183"),
        Fact("ur_robotiq_moveit.launch.py says the scaled_joint_trajectory_controller does not work on fake "
             "hardware and, when use_fake_hardware is true, sets joint_trajectory_controller as the MoveIt default.",
             source="upstream_code", ref=_MOVEIT + ":148-156"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "scaled_joint_trajectory_controller is inactive, as list_controllers read back: its goal was aborted and its "
        "trajectory dropped, and each joint's position command keeps its last value; the world keeps running, it is "
        "the controller's state and not a measured standstill, other arm controllers and the gripper are not shown "
        "inactive, and any client can re-activate it."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake (no controller manager and no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven recording stand-in with no physics step, trajectory interpolation, "
                      "controller timing or wall-clock pacing; the placeholder joint samples do not "
                      "establish trajectory or state-hash replay"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared FollowJointTrajectory action, "
            "/joint_states and the two controller-manager services, and it runs no ROS graph, controller manager, "
            "Isaac Sim or robot",
            "the action goal is applied instantly to a placeholder six-joint vector; there is no interpolation, "
            "timing, feedback, dynamics or controller error behavior",
            "the joint samples are placeholders; a live run must receive /joint_states from the operator's graph "
            "and the trajectory result from the operator's scaled_joint_trajectory_controller",
            "this package serves only the fake-hardware path of ur_robotiq_control.launch.py (use_fake_hardware "
            "true). The Isaac launch defaults initial_joint_controller to joint_trajectory_controller and is not "
            "served. The real ur_ros2_control_node starts unless use_fake_hardware is set and uses the same "
            "endpoint names",
            "the MoveIt launch sets joint_trajectory_controller as its default when use_fake_hardware is true; "
            "this package does not serve MoveIt, and the e-stop does not show that controller inactive",
            "the stop is the companion controller switch: the fake keeps the scaled controller's lifecycle state, "
            "which switch_controller sets and list_controllers reports beside joint_state_broadcaster, and it "
            "refuses goals while that controller is inactive; it runs no controller manager or update loop",
            "deactivation keeps each joint's position command at its last value (joint_trajectory_controller.cpp:"
            "1069-1075) and drops the stored trajectory; the gripper and the other arm controllers are not stopped",
            "forward_position_controller is loaded inactive and claims the same six arm joints, so another client "
            "can activate it after this controller releases its interfaces",
            "the switch waits up to 0.4 s for the controller manager's update loop (controller_manager.cpp:"
            "1307-1331; a zero duration becomes 1 s). A timeout answers ok false and the e-stop stays unconfirmed "
            "with the latch held (fails closed). The action timeout_ms is 2000, shorter than the example overlay's "
            "10 s trajectory time",
            "the read-back's list predicate selects the one element named scaled_joint_trajectory_controller (E4): "
            "none, two, or a state other than inactive leaves the e-stop unconfirmed. It does not prove "
            "joint_trajectory_controller, the forward controllers or the gripper are inactive",
            "any other ROS 2 client of /controller_manager/switch_controller can re-activate the controller after "
            "the e-stop; MHS does not watch its state afterwards",
            "the scaled controller requests speed_scaling_interface_name (scaled_joint_trajectory_controller.cpp:"
            "63-70). The controller manager claims that state interface before activation and skips the controller "
            "when the claim throws (controller_manager.cpp:1653-1681; resource_manager.cpp:743-747). The on_activate "
            "log at scaled_joint_trajectory_controller.cpp:91-92 runs only after the interfaces were assigned; it "
            "is not a path the manager takes when the interface is missing. On this fake-hardware path, "
            "ur_macro.xacro:113-114 includes ur.ros2_control.xacro, which selects mock_components/GenericSystem "
            "(:44-48) and declares gpio speed_scaling/speed_scaling_factor with initial_speed_scaling_factor 1 "
            "(:160-166). GenericSystem exports that gpio state and initializes it from the initial_ parameter "
            "(generic_system.cpp:301-305, :714-726). A description that omits the gpio does not reach on_activate",
            "the deployment's controller_manager and joint_trajectory_controller must be the pinned 2.54.4 and "
            "2.54.1 Humble releases. The lock profile name ros2-humble-gzsim6 is a shared label, not a claim that "
            "this package runs Gazebo. rosbridge cannot read those versions. A non-empty tf_prefix is out of scope: "
            "this package binds the unprefixed names only",
        ],
    }
    parameters = {
        "joint_positions": _POSITIONS_FIELD,
        "joint_velocities": _VELOCITIES_FIELD,
    }
    reads = {
        "joint_positions": _READ_JOINT_POSITIONS,
        "joint_velocities": _READ_JOINT_VELOCITIES,
    }
    commands = {
        "x-cap.qdeyna.arm_trajectory.v1": _ARM_ACTION,
        "x-cap.qdeyna.joint_state.v1": _JOINT_STATE,
        _REENABLE_ID: _SWITCH_ON,
    }
    actions = {
        "x-cap.qdeyna.arm_trajectory.v1": Action(
            name="follow_arm_trajectory",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description=(
                "Send FollowJointTrajectory points on the fake-hardware scaled controller; return the controller "
                "error_code and error_string"
            ),
            input={
                "points": Field(
                    "array",
                    min_items=1,
                    description="Trajectory points",
                    items=_POINT,
                ),
            },
            output={
                "error_code": Field("integer", description="Controller result error_code; 0 is SUCCESSFUL"),
                "error_string": Field("string", description="Controller result error_string"),
            },
            examples=[{"points": [{"positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                                   "time_from_start": {"sec": 1, "nanosec": 0}}]}],
        ),
        _REENABLE_ID: Action(
            name="activate_trajectory_controller",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: switch scaled_joint_trajectory_controller on again "
                "through /controller_manager/switch_controller (STRICT), so the trajectory the e-stop dropped is not "
                "resumed. On activation the controller holds the state it starts from. With this deployment's "
                "position-only command interface and position and velocity state interfaces, that is the measured "
                "position. Reset itself does not activate the controller"
            ),
            output={"acknowledged": Field("boolean", description="True once the switch answered ok")},
        ),
        "x-cap.qdeyna.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description=(
                "Read one JointState sample; arrays use publisher order; freshness is not proven"
            ),
            output={
                "name": _NAMES_FIELD,
                "position": _POSITIONS_FIELD,
                "velocity": _VELOCITIES_FIELD,
            },
        ),
    }
    # The e-stop deactivates scaled_joint_trajectory_controller and reads that one list element back (E4).
    # Anything else leaves the e-stop unconfirmed with the latch held. No reset binding: mhs.safety.reset
    # releases the latch only; the declared re-enable activates the controller. No unpause: there is no world pause.
    safety_bindings = {"estop": _SWITCH_OFF, "safe_state": _LIST}
