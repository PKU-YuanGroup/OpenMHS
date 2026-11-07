"""OpenMHS rosbridge driver for the EPFL-LASA KUKA LWR RViz simulation.

The pinned repository is a ROS 1 simulation and visualisation environment for
a seven-joint KUKA LWR arm.  ``lwr_simulation.launch`` starts the loopback
controller manager, the IAI velocity/position controllers and the
``lasa_to_iai`` parser; the arm is commanded by publishing a
``iai_control_msgs/MultiJointVelocityImpedanceCommand`` on
``/r_arm_vel/command`` and the simulated state is published as a
``sensor_msgs/JointState`` on ``/joint_states``.  The README states that no
dynamics or physics simulation is included.

This package is a configuration-only :class:`RosDriver` over rosbridge; it
declares no Python native class, imports no ROS, starts no controller and
runs no simulation.  The single velocity publication is an extension
capability: a rosbridge publication is transmission evidence only and is not
a bounded-duration motion or an arrival receipt.  The joint-state observation
is a second extension capability because no catalogue class carries a
``sensor_msgs/JointState`` sample.

The pinned clone advertises no stop, pause, cancel, controller-switch or reset
service or action.  A zero-velocity publication is transmission-only, and the
velocity controller's command watchdog zeroes the desired velocity after
``watchdog_period`` without a new message, which is a timeout on the command
stream, not an acknowledged stop.  The e-stop is a sensed-confirmation stop
(SAFE-049, simulated only): the zero publication is the request, and the safe
state is achieved only when ``/r_arm_vel/state`` shows the applied desired
velocities and the measured joint velocities inside the operator bounds across
consecutive fresh samples.  The shipped simulation launch also starts two
other publishers on ``/r_arm_vel/command`` (the ``lasa_to_iai`` parser and the
position P-controller).  While either keeps publishing, the sensed state does
not hold and the stop stays unconfirmed and latched.  There is no unpause.
The realtime launch files put the real arm's joint state on ``/joint_states``.

Every endpoint, type and fact cites the pinned clone at
66448f9e8995b557335b6b51c9ab6ed6c5afd99d.  The fake is a ROS-free event-driven
contract stand-in; no ROS graph, controller, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references
# ---------------------------------------------------------------------------

#: The README states the simulation's joint velocity/position interface and
#: that no dynamics or physics simulation is included.
_README_INTERFACE_REF = "README.md:39"

#: The README names /r_arm_vel/command as the command topic and
#: /joint_states (sensor_msgs/JointState) as the state topic.
_README_TOPICS_REF = "README.md:56"

#: The launch loads the configuration (3-4) and the spawner starts the r_arm_vel controller (6-7).
_VEL_LAUNCH_REF = "kuka_lwr_bringup/launch/controllers/lwr_sim_vel_controllers.launch:3-7"

#: The loopback launch sets /use_sim_time (7), the publish rate (10) and starts the
#: loopback manager with the simulation parameters dt, damping and mass (17-22).
_LOOPBACK_LAUNCH_REF = "kuka_lwr_bringup/launch/controllers/lwr_loopback_sim_controllers.launch:7-22"

#: The controller configuration names r_arm_vel, its C++ class and its seven
#: right-arm joints.
_VEL_CONFIG_REF = "kuka_lwr_bringup/config/lwr_sim_vel_controllers.yaml:1-10"

#: MultiJointVelocityImpedanceController subscribes the relative "command"
#: topic; the controller state is published on "state".
_COMMAND_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                "multi_joint_velocity_impedance_controller.cpp:124")

#: The controller header includes the generated command message header, which
#: proves the fully qualified type used by the command callback.
_COMMAND_TYPE_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/include/"
                     "iai_robot_mechanism_controllers/multi_joint_velocity_impedance_controller.h:52")

#: The same header includes the controller-state message used by the state publisher.
_STATE_TYPE_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/include/"
                   "iai_robot_mechanism_controllers/multi_joint_velocity_impedance_controller.h:53")

#: The RealtimePublisher is constructed on the relative "state" topic.
_STATE_PUBLISHER_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                        "multi_joint_velocity_impedance_controller.cpp:128-130")

#: The update assigns the stamped controller-state fields every tenth cycle.
_STATE_FILL_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                   "multi_joint_velocity_impedance_controller.cpp:192-203")

#: desired.velocities[j] is assigned from the applied command.
_STATE_DESIRED_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                      "multi_joint_velocity_impedance_controller.cpp:199")

#: actual.velocities[j] is assigned from the joint's velocity_.
_STATE_ACTUAL_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                     "multi_joint_velocity_impedance_controller.cpp:201")

#: The controller subscribes "command" (124) and creates the "state" publisher (128-130).
_COMMAND_STATE_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                      "multi_joint_velocity_impedance_controller.cpp:124-130")

#: The command callback: the length check, the copy and the watchdog time stamp.
_COMMAND_CB_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                   "multi_joint_velocity_impedance_controller.cpp:211-227")

#: The command message definition states the velocity field in rad/s (5) and add_torque (10).
_COMMAND_MSG_REF = ("iai_stuff/iai_common_msgs/iai_control_msgs/msg/"
                    "MultiJointVelocityImpedanceCommand.msg:4-10")

#: The controller constructor initializes the command watchdog period.
_WATCHDOG_INIT_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                      "multi_joint_velocity_impedance_controller.cpp:44-46")

#: The controller header declares the watchdog members' types.
_WATCHDOG_TYPES_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/include/"
                       "iai_robot_mechanism_controllers/multi_joint_velocity_impedance_controller.h:95-96")

#: The controller update zeroes the desired velocity when the watchdog is
#: active (no command within the watchdog period).
_WATCHDOG_REF = ("iai_stuff/iai_control_pkgs/iai_robot_mechanism_controllers/src/"
                 "multi_joint_velocity_impedance_controller.cpp:169-177")

#: The desired_joints callback (103-120) and the loopback manager's init, which creates the
#: pr2 ControllerManager, reads the three simulation parameters and subscribes desired_joints.
_LOOPBACK_INIT_REF = ("iai_stuff/iai_control_pkgs/loopback_controller_manager/"
                      "loopback_controller_manager.cpp:103-138")

#: The loopback manager advances velocity and position from the commanded
#: effort, dt, damping and mass.
_LOOPBACK_STEP_REF = ("iai_stuff/iai_control_pkgs/loopback_controller_manager/"
                      "loopback_controller_manager.cpp:210-226")

#: kdl_arm_kinematics advertises five kinematics query services.  The clone also
#: registers a Lisp alter_urdf service (urdf_management, which carries a
#: CATKIN_IGNORE marker); neither stops, pauses, cancels or resets anything.
_KDL_SERVICES_REF = "iai_stuff/iai_control_pkgs/kdl_arm_kinematics/src/arm_kinematics.cpp:142-147"
_ALTER_URDF_REF = "iai_stuff/iai_control_pkgs/urdf_management/src/service.lisp:56"

#: The single-arm parser subscribes the external KUKA impedance command and
#: publishes the IAI position and velocity commands.
_PARSER_REF = "lasa_to_iai_parser/scripts/lasa_to_iai.py:25-27"
#: The parser republishes every received velocity array of num_dof entries.
_PARSER_VEL_REF = "lasa_to_iai_parser/scripts/lasa_to_iai.py:59-70"

#: lwr_simulation.launch: the realtime include (realtime false), the three
#: controller launches and the lasa_to_iai_parser node.
_SIM_LAUNCH_REF = "kuka_lwr_bringup/launch/lwr_simulation.launch:8-29"
#: lwr_sim_pos_controllers.launch: the state separator and the position
#: P-controller whose velocity output is remapped to /r_arm_vel/command.
_POS_LAUNCH_REF = "kuka_lwr_bringup/launch/controllers/lwr_sim_pos_controllers.launch:6-14"
#: JController.control_tick: publish only within 0.1 s of a position goal.
_POS_TICK_REF = "iai_stuff/iai_control_pkgs/iai_control_utils/src/iai_control_utils/jcontroller.py:118-145"
#: The velocity controller gains and the 'perfect sim' comment.
_VEL_GAINS_REF = "kuka_lwr_bringup/config/lwr_sim_vel_controllers.yaml:11-22"
#: lwr_realtime.launch: realtime defaults to true and gates joint_state_publisher.
_REALTIME_LAUNCH_REF = "kuka_lwr_bringup/launch/lwr_realtime.launch:8-26"
#: lwr2_realtime.launch starts joint_state_publisher with no realtime condition.
_LWR2_REALTIME_REF = "kuka_lwr_bringup/launch/lwr2_realtime.launch:16-21"
#: lwr2_simulation.launch includes lwr2_realtime.launch next to the simulation.
_LWR2_SIM_REF = "kuka_lwr_bringup/launch/lwr2_simulation.launch:9-27"
#: README: the simulation quick start and the realtime visualization.
_README_QUICKSTART_REF = "README.md:24-28"
_README_REALTIME_REF = "README.md:61-67"

#: The arm xacro states the seven revolute joint limits; joint 0 is shown as
#: an example (lower/upper, effort, velocity).
_URDF_LIMIT_REF = "kuka_lwr_description/urdf/kuka_lwr_arm_lasa.urdf.xacro:55-59"

#: The shipped starting configuration names the seven right-arm joints and
#: their initial positions.
_START_CONFIG_REF = "kuka_lwr_bringup/config/lwr_start_config.yaml:1-17"

#: The clone states an unsigned arm-velocity magnitude in the URDF, not a
#: signed command envelope for /r_arm_vel/command.  The operator must supply
#: the reviewed per-joint envelope before any velocity is accepted.
_VELOCITY_LIMIT = Limit.operator_required(
    "the clone states an unsigned arm-velocity magnitude for each URDF joint and no signed command "
    "envelope for /r_arm_vel/command; the operator supplies the reviewed per-joint velocity bound"
)

#: ROS 1 std_msgs/Header as rosbridge delivers it (seq, stamp secs/nsecs, frame_id).
_HEADER_FIELD = Field(
    "object",
    description="ROS 1 std_msgs/Header of the joint-state sample",
    properties={
        "seq": Field("integer", unit="1", description="Publisher sequence number"),
        "stamp": Field(
            "object",
            description="ROS 1 time of the sample",
            properties={
                "secs": Field("integer", unit="s", description="Whole seconds"),
                "nsecs": Field("integer", unit="ns", description="Nanoseconds within the second"),
            },
        ),
        "frame_id": Field("string", description="Frame id set by the publisher"),
    },
)

#: One sensor_msgs/JointState sample.  The simulated arm has seven joints.
_JOINT_STATE_FIELD = Field(
    "object",
    description="One sensor_msgs/JointState sample from /joint_states",
    properties={
        "header": _HEADER_FIELD,
        "name": Field("array", description="Joint names in publisher order",
                      items=Field("string", description="One joint name")),
        "position": Field("array", unit="rad", description="Joint positions in publisher order",
                          items=Field("number", unit="rad", description="One joint position")),
        "velocity": Field("array", unit="rad/s", description="Joint velocities in publisher order",
                          items=Field("number", unit="rad/s", description="One joint velocity")),
        "effort": Field("array", unit="N.m", description="Joint efforts in publisher order",
                        items=Field("number", unit="N.m", description="One joint effort")),
    },
)

_JOINT_POSITIONS_FIELD = Field(
    "array",
    unit="rad",
    description="Joint positions in the controller's joint order",
    items=Field("number", unit="rad", description="One joint position"),
)

_JOINT_VELOCITIES_FIELD = Field(
    "array",
    unit="rad/s",
    description="Joint velocities in the controller's joint order",
    items=Field("number", unit="rad/s", description="One joint velocity"),
)

#: The resource snapshot reads two leaves of the same /joint_states sample so
#: that a stale header or sequence number cannot make every read a mutation.
_JOINT_STATE_READ = {
    "topic": "/joint_states",
    "type": "sensor_msgs/JointState",
    "source_ref": _README_TOPICS_REF,
    "operation": "subscribe",
}

_PUBLISHED = Field("boolean", description="True when the rosbridge publication was handed to the transport")
_CONFIRMED = Field("boolean",
                   description="Always false for a topic publication: rosbridge carries no execution confirmation")

#: The velocity command binding: one publication on the controller's resolved
#: /r_arm_vel/command topic.  The controller subscribes the relative "command"
#: name (source_ref) and its callback takes the iai_control_msgs type
#: (type_ref); the configured controller name is r_arm_vel.
_VELOCITY_COMMAND = {
    "topic": "/r_arm_vel/command",
    "type": "iai_control_msgs/MultiJointVelocityImpedanceCommand",
    "source_name": "command",
    "source_ref": _COMMAND_REF,
    "type_ref": _COMMAND_TYPE_REF,
    "operation": "publish",
    "args": {"velocity": {"from": "input.joint_velocities"}},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: The joint-state observation: a fresh subscription on the README's
#: /joint_states topic, which it states is a sensor_msgs/JointState.
_JOINT_STATE_COMMAND = {
    "topic": "/joint_states",
    "type": "sensor_msgs/JointState",
    "source_ref": _README_TOPICS_REF,
    "operation": "subscribe",
    "result": {"map": {"joint_state": "output.$"}},
}

#: Sensed-confirmation stop (SAFE-049).  The zero-velocity publication is the request and proves nothing by
#: itself.  desired.velocities[j] is the applied command (command[j] after the watchdog), not a plant
#: measurement.  actual.velocities[j] is joints_[j]->velocity_.  The clone states no numeric tolerance and no
#: at-rest bound, so both thresholds are operator_required.  This is ROS 1: the source declares no history, and
#: the bridge discards the first sample.  The client bounds are fake-scale; a live deployment sets them in
#: simulation_deployment['estop_confirmation'].
_NO_DESIRED_TOLERANCE = (
    "the clone assigns desired.velocities from the applied command and states no numeric tolerance; "
    "the operator supplies the largest absolute desired velocity that still counts as a zero command"
)
_NO_ACTUAL_BOUND = (
    "the clone assigns actual.velocities from joint velocity_ and states no at-rest bound; "
    "the operator supplies the largest norm of the seven joint velocities that counts as stopped"
)
_ZERO_VELOCITIES = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

_SENSED_STOP = {
    "request": [
        {
            "topic": "/r_arm_vel/command",
            "type": "iai_control_msgs/MultiJointVelocityImpedanceCommand",
            "source_name": "command",
            "source_ref": _COMMAND_REF,
            "type_ref": _COMMAND_TYPE_REF,
            "message": {"velocity": list(_ZERO_VELOCITIES)},
            "timeout_ms": 500,
            "description": "seven zero joint velocities on /r_arm_vel/command (the request, not a stop by itself)",
        },
    ],
    "sources": {
        "arm_state": {
            "topic": "/r_arm_vel/state",
            "type": "pr2_controllers_msgs/JointTrajectoryControllerState",
            "source_name": "state",
            "source_ref": _STATE_PUBLISHER_REF,
            "type_ref": _STATE_TYPE_REF,
            "fill_refs": {
                "desired.velocities": _STATE_DESIRED_REF,
                "actual.velocities": _STATE_ACTUAL_REF,
            },
        },
    },
    "predicate": [
        {"source": "arm_state", "path": f"desired.velocities.{index}", "name": f"desired_v{index}",
         "unit": "rad/s", "abs_max": Limit.operator_required(_NO_DESIRED_TOLERANCE)}
        for index in range(7)
    ] + [
        {"source": "arm_state",
         "paths": [f"actual.velocities.{index}" for index in range(7)],
         "name": "actual_norm", "unit": "rad/s",
         "norm_max": Limit.operator_required(_NO_ACTUAL_BOUND)},
    ],
    "consecutive": 2,
    "min_span_ms": 40,
    "max_gap_ms": 500,
    "confirm_within_ms": 800,
    "description": (
        "Seven zero joint velocities are published on /r_arm_vel/command; the stop is achieved only when "
        "/r_arm_vel/state shows every applied desired velocity within the operator bound and the norm of the "
        "seven measured joint velocities within the operator bound, in two consecutive fresh stamped samples "
        "inside the confirmation window"
    ),
}


class KukaRvizSimulation(RosDriver):
    """Configuration-only ROS 1 rosbridge driver for the KUKA LWR simulation."""

    device_id = "kuka-rviz-simulation"
    device_kind = "robot.arm"
    mode = "simulated"
    #: A moving robot arm is at least R2 even when the only backend exercised
    #: here is the F0 contract fake.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeKukaRvizSimulation"}
    tags = ["ros", "ros1", "simulation", "kuka", "lwr", "joint-state", "velocity", "rviz"]
    display_name = "KUKA LWR RViz simulation"
    vendor = "EPFL-LASA"
    model = "KUKA LWR 7-DOF (loopback simulation)"

    facts = [
        Fact("The README states that the simulation offers a joint velocity/position-resolved interface, "
             "that commands are sent to it, and that no dynamics or physics simulation is included.",
             source="vendor_doc", ref=_README_INTERFACE_REF),
        Fact("The README names /r_arm_vel/command as the topic to publish and says the current robot state "
             "is published on /joint_states with type sensor_msgs/JointState.",
             source="vendor_doc", ref=_README_TOPICS_REF),
        Fact("lwr_sim_vel_controllers.launch loads the controller configuration and starts the "
             "pr2_controller_manager spawner with the r_arm_vel controller.",
             source="upstream_code", ref=_VEL_LAUNCH_REF),
        Fact("The velocity-controller configuration names r_arm_vel, its "
             "iai_robot_mechanism_controllers/MultiJointVelocityImpedanceController type and the seven "
             "right_arm_0_joint through right_arm_6_joint joints.",
             source="upstream_code", ref=_VEL_CONFIG_REF),
        Fact("MultiJointVelocityImpedanceController subscribes the relative command topic with queue size 1 "
             "and creates a state publisher on the relative state topic.",
             source="upstream_code", ref=_COMMAND_STATE_REF),
        Fact("The controller header includes pr2_controllers_msgs/JointTrajectoryControllerState.h.",
             source="upstream_code", ref=_STATE_TYPE_REF),
        Fact("When loop_count_ % 10 == 0 and the state publisher trylocks, the update assigns header.stamp from "
             "the update time, desired.velocities[j] from command[j], actual.positions[j] from position_, "
             "actual.velocities[j] from velocity_ and error.velocities[j] from error[j].",
             source="upstream_code", ref=_STATE_FILL_REF),
        Fact("The command callback takes an iai_control_msgs::MultiJointVelocityImpedanceCommand; only when its "
             "velocity array length equals the configured joint count does it copy the velocities and set "
             "watchdog_time_, otherwise it logs an error.",
             source="upstream_code", ref=_COMMAND_CB_REF),
        Fact("The iai_control_msgs/MultiJointVelocityImpedanceCommand definition declares velocity as a "
             "float32 array in rad/s; stiffness, damping and add_torque are also declared.",
             source="upstream_code", ref=_COMMAND_MSG_REF),
        Fact("The controller constructor initializes watchdog_period to 0.1.",
             source="upstream_code", ref=_WATCHDOG_INIT_REF),
        Fact("The controller header declares watchdog_time_ as ros::Time and watchdog_period as ros::Duration.",
             source="upstream_code", ref=_WATCHDOG_TYPES_REF),
        Fact("The controller update replaces every desired velocity with zero when the time since "
             "watchdog_time_ exceeds watchdog_period.",
             source="upstream_code", ref=_WATCHDOG_REF),
        Fact("lwr_loopback_sim_controllers.launch sets /use_sim_time false, requests a 250 Hz joint-state "
             "publish rate, starts the loopback_controller_manager node and sets dt 0.004 s, damping 0.0 "
             "and mass 0.01.",
             source="upstream_code", ref=_LOOPBACK_LAUNCH_REF),
        Fact("LoopbackControllerManager's init creates a pr2_controller_manager::ControllerManager, reads dt, "
             "damping and mass parameters (defaults 0.01, 0.1 and 0.1) and subscribes the private "
             "desired_joints topic, whose callback writes the received joint positions into the joint states.",
             source="upstream_code", ref=_LOOPBACK_INIT_REF),
        Fact("LoopbackControllerManager::simulateJoints integrates commanded effort, damping, mass and dt "
             "into joint velocity and then joint position; a comment says KDL should be used for correct "
             "dynamics.",
             source="upstream_code", ref=_LOOPBACK_STEP_REF),
        Fact("kdl_arm_kinematics advertises the private services get_fk, get_ik, get_ik_solver_info, "
             "get_fk_solver_info and get_weighted_ik.",
             source="upstream_code", ref=_KDL_SERVICES_REF),
        Fact("urdf_management's service.lisp registers an alter_urdf service.",
             source="upstream_code", ref=_ALTER_URDF_REF),
        Fact("lasa_to_iai.py subscribes /KUKA/joint_imp_cmd as a JointStateImpedance and publishes "
             "/r_arm_pos_controller/command and /r_arm_vel/command.",
             source="upstream_code", ref=_PARSER_REF),
        Fact("lasa_to_iai.py republishes the velocity of every /KUKA/joint_imp_cmd message that carries num_dof "
             "velocities as a MultiJointVelocityImpedanceCommand on /r_arm_vel/command.",
             source="upstream_code", ref=_PARSER_VEL_REF),
        Fact("The arm xacro declares joint 0 as revolute with limit lower -170 * M_PI / 180, upper "
             "170 * M_PI / 180, effort 204 and velocity arm_velocity_scale_factor * 110 * M_PI / 180 (an "
             "unsigned magnitude).",
             source="upstream_code", ref=_URDF_LIMIT_REF),
        Fact("lwr_start_config.yaml lists the seven right-arm joint names and their positions under "
             "joints/name and joints/position.",
             source="upstream_code", ref=_START_CONFIG_REF),
        Fact("lwr_simulation.launch includes lwr_realtime.launch with realtime false, the loopback, velocity "
             "and position controller launch files, and starts the lasa_to_iai_parser node.",
             source="upstream_code", ref=_SIM_LAUNCH_REF),
        Fact("lwr_sim_pos_controllers.launch starts r_arm_state_separator with ~in_joint_states remapped to "
             "/joint_states and ~out_joint_states to /r_arm_pos_controller/joint_states, and r_arm_pos_controller "
             "(joint_p_ctrl.py) with ~vel_command_out remapped to /r_arm_vel/command.",
             source="upstream_code", ref=_POS_LAUNCH_REF),
        Fact("JController.control_tick returns without publishing when more than rospy.Duration(0.1) has passed "
             "since last_command_time, and otherwise publishes the P-controller velocity clipped to max_speed on "
             "~vel_command_out while that publisher has connections.",
             source="upstream_code", ref=_POS_TICK_REF),
        Fact("lwr_sim_vel_controllers.yaml gives every r_arm_vel joint the gains p 2.5, i 0.0 and d 0.0 under "
             "the comment 'for perfect sim: chose p=m/dt with damping=0'.",
             source="upstream_code", ref=_VEL_GAINS_REF),
        Fact("lwr_realtime.launch defaults realtime to true and then starts joint_state_publisher with source_list "
             "/KUKA/joint_states and rate 500.",
             source="upstream_code", ref=_REALTIME_LAUNCH_REF),
        Fact("lwr2_realtime.launch starts joint_state_publisher with source_list /KUKA/joint_states and rate 500 "
             "without a realtime condition.",
             source="upstream_code", ref=_LWR2_REALTIME_REF),
        Fact("lwr2_simulation.launch includes lwr2_realtime.launch, the loopback, velocity and position "
             "controller launch files, and starts the lasa_to_iai_parser node.",
             source="upstream_code", ref=_LWR2_SIM_REF),
        Fact("The README's simulation quick start runs roslaunch kuka_lwr_bringup lwr2_alone_simulation.launch.",
             source="vendor_doc", ref=_README_QUICKSTART_REF),
        Fact("The README's realtime visualization starts lwr2_alone_realtime.launch with the kuka_fri_bridge and "
             "says the kuka_fri_bridge will be publishing the /joint_states topic.",
             source="vendor_doc", ref=_README_REALTIME_REF),
    ]

    safe_state = (
        "Simulated only: seven zero joint velocities on /r_arm_vel/command are the request, not a stop by "
        "itself; the stop is achieved only when /r_arm_vel/state shows every applied desired velocity and the "
        "norm of the measured joint velocities inside the operator bounds, in two consecutive fresh stamped "
        "samples within the confirmation window. Nothing is claimed after it. A competing publisher leaves "
        "the stop unconfirmed and latched, and there is no unpause."
    )
    #: The request step's timeout (500 ms) plus confirm_within_ms (800 ms).
    estop_latency_ms = 1300

    #: The deployed fake is an event-driven contract stand-in, not the
    #: upstream loopback simulation.
    fidelity = {
        "engine": "analytic:ROS-free event-driven contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven contract fake with no physics step or pacing; placeholder joint "
                     "samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic contract stand-in, not a recording of captured traffic: it answers "
            "the declared /joint_states subscription and /r_arm_vel/state confirmation samples and records "
            "/r_arm_vel/command publications; it runs no ROS graph, loopback_controller_manager, PR2 or IAI "
            "controller, URDF model or physics step",
            "the fake does not reproduce the loopback integration (dt 0.004 s, damping 0.0, mass 0.01 in "
            "lwr_loopback_sim_controllers.launch:19-21) or the requested 250 Hz joint-state publish rate "
            "(lwr_loopback_sim_controllers.launch:10); its joint samples are placeholders",
            "the launch starts external pr2_controller_manager, IAI velocity/position controllers and the "
            "lasa_to_iai parser; none is started or validated here",
            "the controller's 0.1 s watchdog zeroes the desired velocity after a silent period, but the fake "
            "does not model the controller or its watchdog; the watchdog is a timeout on silence, not the "
            "acknowledged stop",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): one publication of seven zero "
            "velocities on /r_arm_vel/command, achieved only when /r_arm_vel/state shows desired.velocities "
            "(the applied command, desired.velocities[j] = command[j]) within the operator bound and the norm of "
            "actual.velocities (actual.velocities[j] = velocity_) within the operator bound, in two consecutive "
            "fresh stamped samples inside the confirmation window; ROS 1 discards the first sample of the new "
            "subscription; thresholds are operator_required (fake placeholders in fixtures/estop-confirmation.json) "
            "and the client bounds are fake-scale, so a live deployment sets both in "
            "simulation_deployment['estop_confirmation']",
            "the fake sets measured joint velocity to the commanded velocity at once (a placeholder, not the "
            "loopback); it does not integrate simulateJoints and does not model commanded_effort_ or the "
            "watchdog; confirmation on the fake is a contract stand-in",
            "the velocity envelope is operator_required; site-limits.example.json is an example overlay "
            "only, not a device fact",
            "a live run needs the operator's ROS 1 graph and rosbridge; no ROS process, node or hardware "
            "is contacted",
            "lwr_simulation.launch also starts lasa_to_iai_parser, which republishes every /KUKA/joint_imp_cmd "
            "velocity array (the README's own test publishes one at 20 Hz) on /r_arm_vel/command, and "
            "r_arm_pos_controller, which publishes velocities there while position goals arrive on "
            "/r_arm_pos_controller/command; either keeps desired.velocities off zero, so the stop stays "
            "unconfirmed and latched; this package has no unpause and cannot clear a command those nodes store",
            "lwr_realtime.launch (realtime defaults to true) and lwr2_realtime.launch start joint_state_publisher, "
            "which republishes the real arm's /KUKA/joint_states as /joint_states at 500 Hz: in the README's "
            "realtime visualization /joint_states is the real KUKA arm, and lwr2_simulation.launch starts it next "
            "to the simulation as a second /joint_states publisher; the sensed source is /r_arm_vel/state, not "
            "/joint_states; the SDK cannot prove a ROS graph is simulated; a real controller of this class behind "
            "/r_arm_vel/command would act on the same publication (R2, out of scope)",
            "the README's quick start names lwr2_alone_simulation.launch, which is not in the pinned clone; "
            "lwr_simulation.launch is the single-arm simulation with the loopback manager as the only "
            "/joint_states publisher",
            "the fake echoes a commanded velocity into its joint-state sample until the next command, while the "
            "controller zeroes the desired velocity after watchdog_period (0.1) without a new command",
            "no ROS graph, rosbridge connection, simulator execution, hardware run or human review has occurred",
        ],
    }

    # Resource state: the two numeric leaves of the /joint_states sample.  The
    # full sample remains an explicit observation below; the resource snapshot
    # does not depend on the header's sequence number or timestamp.
    parameters = {
        "joint_positions": _JOINT_POSITIONS_FIELD,
        "joint_velocities": _JOINT_VELOCITIES_FIELD,
    }
    reads = {
        "joint_positions": dict(_JOINT_STATE_READ, path="position"),
        "joint_velocities": dict(_JOINT_STATE_READ, path="velocity"),
    }

    # The observation is explicit so the resource snapshot never waits for a
    # sample that the external controller may stop publishing.
    commands = {
        "x-cap.epfl-lasa.joint_velocity.v1": _VELOCITY_COMMAND,
        "x-cap.epfl-lasa.joint_states.v1": _JOINT_STATE_COMMAND,
    }

    actions = {
        "x-cap.epfl-lasa.joint_velocity.v1": Action(
            name="publish_joint_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one iai_control_msgs/MultiJointVelocityImpedanceCommand with the seven desired "
                "joint velocities on /r_arm_vel/command. The receipt confirms only that rosbridge accepted "
                "the publication, not motion, arrival or stopping."
            ),
            input={
                "joint_velocities": Field(
                    "array",
                    unit="rad/s",
                    length=7,
                    description="Seven desired joint velocities in the controller's joint order",
                    items=Field("number", unit="rad/s", description="One desired joint velocity"),
                    limit=_VELOCITY_LIMIT,
                ),
            },
            output={"published": _PUBLISHED, "confirmed": _CONFIRMED},
        ),
        "x-cap.epfl-lasa.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one sensor_msgs/JointState sample published on /joint_states",
            output={"joint_state": _JOINT_STATE_FIELD},
        ),
    }

    safety_bindings = {"sensed_stop": _SENSED_STOP}
