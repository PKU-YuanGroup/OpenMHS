"""OpenMHS rosbridge driver for the BCR 7-DOF arm ROS 2/Gazebo simulation.

The pinned repository is a Gazebo Fortress/Harmonic simulation of a 7-DOF
arm with ROS 2 Control and MoveIt.  The arm is driven through the
``joint_trajectory_controller`` and observed through the bridged
``/joint_states`` topic.  This is a configuration-only :class:`RosDriver`: it
declares no Python native class and never imports ROS, starts Gazebo or
launches MoveIt.

The primary control path is the controller's acknowledged ROS 2
``control_msgs/action/FollowJointTrajectory`` action at
``/joint_trajectory_controller/follow_joint_trajectory``.  The clone's CLI
uses exactly that client and sends one ``JointTrajectoryPoint`` with seven
positions and a ``time_from_start``.  The action terminal result is the
controller's ``error_code``/``error_string``; it is not a stopped-state
measurement.

No source-backed stop or pause endpoint exists in the pinned clone itself.
The e-stop is a controller switch served by the controller manager of
ros2_control, cited as a reviewed companion source fetched at a pinned commit
(user decision and authorisation of 2026-11-05; ``task.json`` ``companions``
with ``lock``): controller_manager 2.54.4 (Humble)
``/controller_manager/switch_controller`` deactivates
``joint_trajectory_controller`` (STRICT, a 0.4 s switch wait), which aborts its
goal, drops its stored trajectory and leaves each joint's position command at
its last value (joint_trajectory_controller 2.54.1).  It is confirmed by
reading ``/controller_manager/list_controllers`` back with a list-element
predicate (E4): the one element named ``joint_trajectory_controller`` must
report the state ``inactive``.  The world keeps running; it is the
controller's state, not a measured standstill.

The declared re-enable (CORE-086) switches the controller on again, and the
trajectory the stop dropped is not resumed (the orchestrator's SAFE-042
condition: cleared by the stop itself).  On activation the controller holds
the position of the state it starts from (joint_trajectory_controller 2.54.1):
the last command-interface values when
``set_last_command_interface_value_as_state_on_activation`` (true by default at
the pin) holds and every configured state interface has a command interface
with a value, else the measured joint state.  This deployment commands
position only and reads position and velocity (``ros2_controllers.yaml``, the
Gazebo launch's default), so the command read fails on velocity and the
re-enable holds the measured position.  A configuration that also commanded
velocity would hold the last position command instead, which can differ from
the measured position (a joint that had not reached it, was blocked, or whose
command another controller changed while this one was inactive).

Every endpoint, type and fact cites the pinned clone at
9bd3d60b306bb2ed22f5cb1fd588aca99081a711.  The fake transport is ROS-free;
no ROS graph, controller, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: controller_manager 2.54.4 (ros2_control, Humble) at 7f26da88, fetched under work/companions: the switch and the
#: list read-back.
_CM = "companion:ros2_control/controller_manager/src/controller_manager.cpp"
_CM_MSGS = "companion:ros2_control/controller_manager_msgs"
#: joint_trajectory_controller 2.54.1 (ros2_controllers, Humble) at 65db7362: what deactivation and activation do.
_JTC_SRC = "companion:ros2_controllers/joint_trajectory_controller/src/joint_trajectory_controller.cpp"
#: gz_ros2_control 0.7.21 (Humble, Gazebo Fortress) at 3f341cd4: the controller manager inside the simulation.
_GZ_PLUGIN = "companion:gz_ros2_control/gz_ros2_control/src/gz_ros2_control_plugin.cpp"
_GZ_SYSTEM = "companion:gz_ros2_control/gz_ros2_control/src/gz_system.cpp"
_JTC = "joint_trajectory_controller"
#: STRICT (2): the switch fails if anything goes wrong; a 0.4 s wait for the controller manager's update loop.
_SWITCH_WAIT = {"sec": 0, "nanosec": 400000000}

#: The e-stop: deactivate joint_trajectory_controller through the controller manager's switch_controller.
_SWITCH_OFF = {
    "service": "/controller_manager/switch_controller",
    "type": "controller_manager_msgs/srv/SwitchController",
    "source_name": "~/switch_controller",
    "source_ref": _CM + ":557-560",
    "type_ref": _CM + ":557",
    "state_ref": _JTC_SRC + ":1055-1106",
    "description": "Deactivate joint_trajectory_controller (controller_manager switch_controller, STRICT)",
    "request": {"activate_controllers": [], "deactivate_controllers": [_JTC], "strictness": 2,
                "activate_asap": False, "timeout": _SWITCH_WAIT},
    "success": {"path": "ok", "equals": True},
    "timeout_ms": 600,
}
#: The read-back that confirms it: list_controllers reports the controller's lifecycle state (E4 list element).
_LIST = {
    "service": "/controller_manager/list_controllers",
    "type": "controller_manager_msgs/srv/ListControllers",
    "source_name": "~/list_controllers",
    "source_ref": _CM + ":537-539",
    "type_ref": _CM + ":537",
    "state_ref": _CM + ":1752-1755",
    "description": "Read the controllers back; confirmed only when joint_trajectory_controller reports inactive",
    "request": {},
    "success": {"path": "controller", "where": {"name": _JTC}, "field": "state", "equals": "inactive"},
    "timeout_ms": 300,
}
#: The declared re-enable after a reset (CORE-086): activate joint_trajectory_controller again.
_SWITCH_ON = {
    "service": "/controller_manager/switch_controller",
    "type": "controller_manager_msgs/srv/SwitchController",
    "source_name": "~/switch_controller",
    "source_ref": _CM + ":557-560",
    "type_ref": _CM + ":557",
    "description": ("Activate joint_trajectory_controller again (it holds the state it starts from: here the measured "
                    "position, as the position-only command interface defeats the last-command restore)"),
    "request": {"activate_controllers": [_JTC], "deactivate_controllers": [], "strictness": 2,
                "activate_asap": False, "timeout": _SWITCH_WAIT},
    "success": {"path": "ok", "equals": True},
    "result": {"acknowledged": {"value": True}},
    "timeout_ms": 600,
}
_REENABLE_ID = "x-cap.blackcoffeerobotics.activate_controller.v1"

_COMPANION_FACTS = [
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
    Fact("list_controllers fills each ControllerState with the controller's name, type, claimed interfaces and "
         "lifecycle state label.", source="upstream_code", ref=_CM + ":1748-1755"),
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
    Fact("gz_ros2_control names its controller manager node controller_manager unless the SDF names another.",
         source="upstream_code", ref=_GZ_PLUGIN + ":312-317"),
    Fact("gz_ros2_control creates the controller manager in the plugin node's namespace and adds it to its "
         "executor.", source="upstream_code", ref=_GZ_PLUGIN + ":498-506"),
    Fact("gz_ros2_control writes the joint commands on every simulation step and reads and updates the controllers "
         "at the controller period.", source="upstream_code", ref=_GZ_PLUGIN + ":529-581"),
    Fact("For a position-controlled joint the Gazebo system turns the error to the position command into a target "
         "velocity.", source="upstream_code", ref=_GZ_SYSTEM + ":839-846"),
]

#: The CLI creates the FollowJointTrajectory action client on this absolute
#: endpoint; the same literal is repeated in its server-name check.
_ARM_ACTION_REF = "bcr_arm_gazebo/scripts/control_arm_cli.py:21"

#: The CLI imports the action type from control_msgs.action.
_ARM_TYPE_REF = "bcr_arm_gazebo/scripts/control_arm_cli.py:6"

#: The CLI lists the seven controlled joints in this order.
_ARM_NAMES_REF = "bcr_arm_gazebo/scripts/control_arm_cli.py:24-32"

#: The CLI fills one point with positions and a Duration and sends the goal.
_ARM_GOAL_REF = "bcr_arm_gazebo/scripts/control_arm_cli.py:87-99"

#: The bridge launch declares /joint_states as sensor_msgs/msg/JointState.
_JOINT_STATE_REF = "bcr_arm_gazebo/launch/bringup.gazebo.launch.py:209"

#: The bridge launch also names /clock, /tf and the camera topics.
_BRIDGE_REF = "bcr_arm_gazebo/launch/bringup.gazebo.launch.py:203-226"

#: The MoveIt controller map names the joint_trajectory_controller and its
#: FollowJointTrajectory action namespace.
_MOVEIT_CONTROLLERS_REF = "bcr_arm_moveit_config/config/moveit_controllers.yaml:9-20"

#: The controller manager config declares the seven joints and the position
#: command interface with position and velocity state interfaces.
_CONTROLLERS_REF = "bcr_arm_moveit_config/config/ros2_controllers.yaml:1-26"

#: The Gazebo ros2_control system description declares the position command
#: interface and position/velocity/effort state interfaces for all seven joints.
_ROS2_CONTROL_REF = "bcr_arm_description/urdf/control/ros2_control.urdf.xacro:4-50"

#: The xacro loads the Gazebo ros2_control plugin with the controller YAML.
_GAZEBO_PLUGIN_REF = "bcr_arm_description/urdf/control/gazebo_sim_ros2_control.urdf.xacro:5-13"

#: The mechanical xacro states each joint's revolute travel range.
_JOINT_LIMITS_REF = "bcr_arm_description/urdf/mech/bcr_arm_mech.urdf.xacro:141-356"

#: MoveIt's joint_limits.yaml states the configured velocity and acceleration bounds.
_MOVEIT_LIMITS_REF = "bcr_arm_moveit_config/config/joint_limits.yaml:10-45"

#: The launch starts Gazebo and the joint state and trajectory controller spawners.
_LAUNCH_REF = "bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:201-243"

#: The initial positions file is a deployment default, not a limit.
_INITIAL_REF = "bcr_arm_moveit_config/config/initial_positions.yaml:1-10"

_JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7"]

#: The model's revolute travel ranges, in joint1..joint7 order.  These are the
#: installed model's bounds, not a measurement of a delivered arm.
_JOINT_POSITION_LIMIT = Limit(
    min=[-6.28, -2.0, -6.28, -2.0, -6.28, -2.0, -6.28],
    max=[6.28, 2.0, 6.28, 2.0, 6.28, 2.0, 6.28],
    names=_JOINTS,
    unit="rad",
    source="upstream_code",
    ref=_JOINT_LIMITS_REF,
)

#: The clone states no maximum trajectory duration; the operator supplies the
#: site's motion envelope.  A ROS Duration's sec and nanosec fields are both
#: numeric inputs, so each needs an operator-supplied bound.
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
            length=7,
            description="Target joint angles",
            items=Field("number", unit="rad", description="One joint's target angle"),
            limit=_JOINT_POSITION_LIMIT,
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
    "action": "/joint_trajectory_controller/follow_joint_trajectory",
    "profile": "ros2-native",
    "type": "control_msgs/action/FollowJointTrajectory",
    "source_name": "/joint_trajectory_controller/follow_joint_trajectory",
    "source_ref": _ARM_ACTION_REF,
    "type_ref": _ARM_TYPE_REF,
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
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"name": "name", "position": "position", "velocity": "velocity"}},
}

_READ_JOINT_POSITIONS = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "/joint_states",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_REF,
    "path": "position",
}

_READ_JOINT_VELOCITIES = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_name": "/joint_states",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_REF,
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


class BcrArm(RosDriver):
    device_id = "bcr_arm"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md); the simulator's
    # trajectory commands move the arm even though no physical hardware is
    # attached here.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeBcrArm"}
    tags = ["ros", "ros2", "gazebo", "simulation", "robot-arm", "trajectory", "joint-state"]
    display_name = "BCR 7-DOF arm"
    vendor = "Black Coffee Robotics"
    model = "BCR Arm"
    facts = [
        Fact("The repository contains a Gazebo Fortress simulation for a 7-DOF robotic arm with ROS 2 "
             "Control integration and MoveIt motion planning.",
             source="vendor_doc", ref="README.md:7"),
        Fact("The README calls bcr_arm.gazebo.launch.py the primary launch file and says it uses ROS 2 mock "
             "controllers for the arm.",
             source="vendor_doc", ref="README.md:59-65"),
        Fact("ArmControllerCLI creates a FollowJointTrajectory ActionClient on the absolute "
             "/joint_trajectory_controller/follow_joint_trajectory endpoint.",
             source="upstream_code", ref=_ARM_ACTION_REF),
        Fact("control_arm_cli.py imports control_msgs.action.FollowJointTrajectory.",
             source="upstream_code", ref=_ARM_TYPE_REF),
        Fact("ArmControllerCLI lists the seven controlled joints as joint1 through joint7 in that order.",
             source="upstream_code", ref=_ARM_NAMES_REF),
        Fact("ArmControllerCLI builds one JointTrajectoryPoint with positions and a time_from_start Duration, "
             "appends it to trajectory.points and sends the goal asynchronously.",
             source="upstream_code", ref=_ARM_GOAL_REF),
        Fact("The MoveIt simple controller manager names joint_trajectory_controller, type "
             "FollowJointTrajectory, action_ns follow_joint_trajectory and default true.",
             source="upstream_code", ref=_MOVEIT_CONTROLLERS_REF),
        Fact("ros2_controllers.yaml configures joint_trajectory_controller for joint1 through joint7, with "
             "a position command interface and position and velocity state interfaces.",
             source="upstream_code", ref=_CONTROLLERS_REF),
        Fact("ros2_control.urdf.xacro declares gz_ros2_control/GazeboSimSystem and a position command "
             "interface with position, velocity and effort state interfaces for each of the seven joints.",
             source="upstream_code", ref=_ROS2_CONTROL_REF),
        Fact("gazebo_sim_ros2_control.urdf.xacro loads the "
             "gz_ros2_control::GazeboSimROS2ControlPlugin with the controller YAML path.",
             source="upstream_code", ref=_GAZEBO_PLUGIN_REF),
        Fact("The Gazebo bringup bridges /joint_states as sensor_msgs/msg/JointState.",
             source="upstream_code", ref=_JOINT_STATE_REF),
        Fact("The Gazebo bringup bridge also carries /clock and /tf and starts a separate image bridge for the "
             "camera topics.",
             source="upstream_code", ref=_BRIDGE_REF),
        Fact("The arm xacro gives joint1, joint3, joint5 and joint7 the revolute range -6.28..6.28 rad and "
             "joint2, joint4 and joint6 the range -2.0..2.0 rad.",
             source="upstream_code", ref=_JOINT_LIMITS_REF),
        Fact("joint_limits.yaml sets max_velocity 2.0 for joint1 through joint4, 3.0 for joint5 and joint6, "
             "and 4.0 for joint7; max_acceleration is 1.0, 1.5 and 2.0 respectively.",
             source="upstream_code", ref=_MOVEIT_LIMITS_REF),
        Fact("initial_positions.yaml starts all seven joints at 0.0.",
             source="upstream_code", ref=_INITIAL_REF),
        Fact("bcr_arm.gazebo.launch.py starts the Gazebo server and spawns the joint_state_broadcaster and "
             "joint_trajectory_controller controllers.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The launch's spawners name the controller manager /controller_manager.", source="upstream_code",
             ref="bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:223-243"),
        Fact("The Gazebo launch's ros2_controllers_path defaults to bcr_arm_moveit_config's config/ros2_controllers.yaml.",
             source="upstream_code", ref="bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:118-130"),
        Fact("The launch starts gz_sim with the -r argument, so the simulation runs from the start.",
             source="upstream_code", ref="bcr_arm_gazebo/launch/bcr_arm.gazebo.launch.py:201-206"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "joint_trajectory_controller is inactive, as list_controllers read back: its goal was aborted and its "
        "trajectory dropped, and each joint's position command keeps its last value, which the Gazebo system holds; "
        "the world keeps running, it is the controller's state, not a measured standstill, and any client can "
        "re-activate it."
    )

    # The deployed fake is an event-driven recording transport, not Gazebo.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
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
            "the fake is a ROS-free recording transport: it answers the declared FollowJointTrajectory "
            "action and /joint_states subscriptions and runs no Gazebo, gz_ros2_control, MoveIt or ROS graph",
            "the action goal is applied instantly to a placeholder seven-joint vector; there is no "
            "interpolation, timing, feedback, dynamics, gravity, collision or controller error behavior",
            "the joint samples are placeholders; a live run must receive /joint_states from the operator's "
            "Gazebo bridge and the trajectory result from the operator's joint_trajectory_controller",
            "the upstream image bridge, camera topics, /clock, /tf and the MoveIt planning interface are out "
            "of scope",
            "the stop is the companion controller switch: the fake keeps the trajectory controller's lifecycle state, "
            "which switch_controller sets and list_controllers reports in a two-element controller list, and refuses "
            "goals while it is inactive; it runs no controller manager, update loop or lifecycle transition",
            "deactivation keeps each joint's position command at its last value (joint_trajectory_controller.cpp:"
            "1069-1092), so a joint still converges to the last commanded point of the dropped trajectory; the world, "
            "the joint_state_broadcaster and /joint_states keep running",
            "the switch waits up to 0.4 s for the controller manager's update loop (controller_manager.cpp:"
            "1307-1331), which gz_ros2_control drives from the simulation step: with the world paused the switch "
            "times out, answers ok false and the e-stop stays unconfirmed with the latch held (fails closed)",
            "the read-back's list predicate selects the one element named joint_trajectory_controller (E4): none, "
            "two, or a state other than inactive leaves the e-stop unconfirmed",
            "MoveIt, a controller spawner or any other ROS 2 client of /controller_manager/switch_controller can "
            "re-activate the controller after the e-stop; MHS does not watch its state afterwards (safety_status "
            "re-reads it only on request)",
            "the deployment's controller_manager, joint_trajectory_controller and gz_ros2_control must be the pinned "
            "2.54.4, 2.54.1 and 0.7.21 releases (Humble with Gazebo Fortress); the clone also documents Jazzy with "
            "Harmonic, which this package does not serve; rosbridge cannot read their versions",
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
        "x-cap.blackcoffeerobotics.arm_trajectory.v1": _ARM_ACTION,
        "x-cap.blackcoffeerobotics.joint_state.v1": _JOINT_STATE,
        _REENABLE_ID: _SWITCH_ON,
    }
    actions = {
        "x-cap.blackcoffeerobotics.arm_trajectory.v1": Action(
            name="follow_arm_trajectory",
            verb="invoke",
            long_running=True,
            cancellable=True,
            max_duration_ms=120000,
            description=(
                "Send FollowJointTrajectory points; return the controller error_code/error_string"
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
            examples=[{"points": [{"positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                                   "time_from_start": {"sec": 0, "nanosec": 0}}]}],
        ),
        _REENABLE_ID: Action(
            name="activate_trajectory_controller",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: switch joint_trajectory_controller on again through "
                "/controller_manager/switch_controller (STRICT), so the trajectory the e-stop dropped is not resumed. "
                "On activation the controller holds the state it starts from: the last command-interface values when "
                "set_last_command_interface_value_as_state_on_activation (true by default) applies and every state "
                "interface has a command interface, else the measured joints. With this deployment's position-only "
                "command interface (position and velocity states) that is the measured position; a configuration "
                "that also commanded velocity would hold the last position command, which can differ from the "
                "measured position"
            ),
            output={"acknowledged": Field("boolean", description="True once the switch answered ok")},
        ),
        "x-cap.blackcoffeerobotics.joint_state.v1": Action(
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
    # The e-stop deactivates joint_trajectory_controller and reads the controller list back (companion ros2_control,
    # E4 list predicate); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding: mhs.safety.reset releases the latch only; the declared re-enable activates the controller.
    safety_bindings = {"estop": _SWITCH_OFF, "safe_state": _LIST}
