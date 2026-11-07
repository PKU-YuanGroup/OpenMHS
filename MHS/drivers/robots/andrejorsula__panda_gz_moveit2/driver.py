"""OpenMHS rosbridge driver for the Franka Emika Panda Gazebo/MoveIt 2 simulation.

The pinned repository is a configuration-only ROS 2 Galactic / Gazebo Fortress
workspace: MoveIt 2 planning, ``gz_ros2_control`` (through the pinned
``ign_ros2_control`` fork) and a MoveIt Servo node whose outgoing commands are
published on ``/joint_trajectory_controller/joint_trajectory`` as
``trajectory_msgs/JointTrajectory``.  This package is a configuration-only
:class:`RosDriver`; it declares no Python native class and never imports ROS,
starts Gazebo or launches MoveIt.

The exposed control is that Servo output publication.  A publication carries
no controller acknowledgement: the receipt reports ``published`` and a
``confirmed`` value that is always false.  The repository's acknowledged
``FollowJointTrajectory`` action is used by MoveIt, but its exact wire type is
not declared anywhere in the pinned clone (``control_msgs`` is only an
``exec_depend``), so this package does not invent that citation.

No source-backed stop, pause, controller-switch or safe-state endpoint is
declared in the pinned clone.  The runtime therefore latches in software and
refuses further publications, but it cannot interrupt a trajectory the
external controller has already accepted; this package is blocked and claims
no stopped state.

Every endpoint, type and fact cites the pinned clone at
8e5c6fd5d0d39ce2ad1d14968f86104f4ae0b9cb.  The fake transport is ROS-free;
no ROS graph, controller, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The arm joints, in the order MoveIt and the controllers publish them.
_JOINTS = ["panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
           "panda_joint5", "panda_joint6", "panda_joint7"]

#: The generated URDF carries the mechanical travel range of every arm joint.
_URDF_LIMITS_REF = "panda_description/urdf/panda.urdf:43-307"

#: Servo publishes its outgoing commands on this absolute topic as a
#: trajectory_msgs/JointTrajectory message.
_COMMAND_TOPIC_REF = "panda_moveit_config/config/servo.yaml:50"
_COMMAND_TYPE_REF = "panda_moveit_config/config/servo.yaml:15"

#: The generated URDF is the installed model's joint specification.
_JOINT_POSITION_LIMIT = Limit(
    min=[-2.897246558310587, -1.7627825445142729, -2.897246558310587, -3.07177948351002,
         -2.897246558310587, -0.017453292519943295, -2.897246558310587],
    max=[2.897246558310587, 1.7627825445142729, 2.897246558310587, -0.06981317007977318,
         2.897246558310587, 3.752457891787808, 2.897246558310587],
    names=_JOINTS,
    unit="rad",
    source="upstream_code",
    ref=_URDF_LIMITS_REF,
)

#: The clone declares no trajectory-duration envelope for this topic.  A
#: deployed controller's timing is a site decision, not a repo constant.
_TIME_SEC_LIMIT = Limit.operator_required(
    "the pinned clone declares no trajectory time_from_start envelope for the Servo output topic; "
    "the operator supplies the deployed controller's timing bound"
)
_TIME_NSEC_LIMIT = Limit.operator_required(
    "the pinned clone declares no nanosecond range for time_from_start; the operator supplies the "
    "deployed controller's timing bound"
)

_POINT = Field(
    "object",
    description="One trajectory point",
    properties={
        "positions": Field(
            "array",
            unit="rad",
            length=7,
            description="Joint angles, panda_joint1..7",
            items=Field("number", unit="rad", description="One joint angle"),
            limit=_JOINT_POSITION_LIMIT,
        ),
        "time_from_start": Field(
            "object",
            description="Start offset",
            properties={
                "sec": Field("integer", unit="s", description="Whole seconds", limit=_TIME_SEC_LIMIT),
                "nanosec": Field("integer", unit="ns", description="Nanoseconds",
                                 limit=_TIME_NSEC_LIMIT),
            },
        ),
    },
)

_COMMAND = {
    "topic": "/joint_trajectory_controller/joint_trajectory",
    "type": "trajectory_msgs/msg/JointTrajectory",
    "source_ref": _COMMAND_TOPIC_REF,
    "type_ref": _COMMAND_TYPE_REF,
    "operation": "publish",
    "message": {"joint_names": list(_JOINTS)},
    "args": {"points": {"from": "input.points"}},
}

_ACTION = Action(
    name="publish_joint_trajectory",
    verb="invoke",
    description=(
        "Publish a JointTrajectory on the Servo output topic; the receipt reports publication only, "
        "never execution or stopping"
    ),
    risk="R2",
    input={
        "points": Field(
            "array",
            min_items=1,
            description="Trajectory points",
            items=_POINT,
        ),
    },
    output={
        "published": Field("boolean", description="True when rosbridge sent it"),
        "confirmed": Field("boolean",
                           description="False: publication is unacknowledged"),
    },
    examples=[{"points": [{"positions": [0.0, -0.7853981633974483, 0.0, -2.356194490192345,
                                            0.0, 1.5707963267948966, 0.7853981633974483],
                          "time_from_start": {"sec": 1, "nanosec": 0}}]}],
)


class PandaGzMoveit2(RosDriver):
    device_id = "panda-gz-moveit2"
    device_kind = "robot.arm"
    mode = "simulated"
    # A robot arm is at least R2 (MHS/spec/04-safety.md).  The simulation's
    # publication moves the arm even when no physical hardware is attached.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakePandaGzMoveit2"}
    tags = ["ros", "ros2", "gazebo", "fortress", "moveit2", "servo", "panda", "robot-arm", "trajectory",
            "simulation", "ros2-control"]
    display_name = "Franka Emika Panda Gazebo/MoveIt 2 simulation"
    vendor = "Andrej Orsula"
    model = "Franka Emika Panda (Gazebo Fortress, MoveIt 2)"
    facts = [
        Fact("The repository provides Franka Emika Panda software packages that enable manipulation "
             "with MoveIt 2 inside Gazebo and use gz_ros2_control for control.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The branch targets ROS 2 Galactic and Gazebo Fortress.",
             source="vendor_doc", ref="README.md:11"),
        Fact("panda_moveit_config's README says move_group.launch.py configures MoveIt 2 to plan motions "
             "inside a simulation and that the real robot is not yet supported.",
             source="vendor_doc", ref="panda_moveit_config/README.md:9"),
        Fact("The README's ign_control example executes motions with simulated controllers.",
             source="vendor_doc", ref="panda_moveit_config/README.md:33"),
        Fact("servo.yaml sets command_out_type to trajectory_msgs/JointTrajectory.",
             source="upstream_code", ref=_COMMAND_TYPE_REF),
        Fact("servo.yaml sets command_out_topic to /joint_trajectory_controller/joint_trajectory.",
             source="upstream_code", ref=_COMMAND_TOPIC_REF),
        Fact("servo.yaml sets move_group_name to arm.",
             source="upstream_code", ref="panda_moveit_config/config/servo.yaml:27"),
        Fact("servo.yaml sets incoming_command_timeout to 0.25, commented 'Stop servoing if X seconds elapse "
             "without a new command', and num_outgoing_halt_msgs_to_publish to 1.",
             source="upstream_code", ref="panda_moveit_config/config/servo.yaml:35-38"),
        Fact("moveit_controller_manager.yaml lists joint_trajectory_controller and "
             "gripper_trajectory_controller as the controller names.",
             source="upstream_code", ref="panda_moveit_config/config/moveit_controller_manager.yaml:1-3"),
        Fact("The joint_trajectory_controller entry uses action_ns follow_joint_trajectory, type "
             "FollowJointTrajectory and is the default controller.",
             source="upstream_code", ref="panda_moveit_config/config/moveit_controller_manager.yaml:6-9"),
        Fact("controllers_effort.yaml configures the controller manager at 250 Hz with a "
             "joint_state_broadcaster and two joint_trajectory_controller instances.",
             source="upstream_code", ref="panda_moveit_config/config/controllers_effort.yaml:1-12"),
        Fact("controllers_effort.yaml gives the arm joint_trajectory_controller the seven panda_joint "
             "names, the effort command interface and position and velocity state interfaces.",
             source="upstream_code", ref="panda_moveit_config/config/controllers_effort.yaml:14-28"),
        Fact("panda.ros2_control declares a ros2_control system whose hardware plugin is "
             "fake_components/GenericSystem for the fake plugin and ign_ros2_control/IgnitionSystem "
             "for the ign plugin.",
             source="upstream_code", ref="panda_description/urdf/panda.ros2_control:23-30"),
        Fact("panda.gazebo loads the ign_ros2_control-system plugin with the controller parameter file.",
             source="upstream_code", ref="panda_description/urdf/panda.gazebo:11-14"),
        Fact("The generated URDF declares lower and upper position limits for the seven revolute "
             "panda_joint joints.",
             source="upstream_code", ref=_URDF_LIMITS_REF),
        Fact("initial_joint_positions.yaml starts the arm at joint1 0, joint2 -0.7853981633974483, "
             "joint3 0, joint4 -2.356194490192345, joint5 0, joint6 1.5707963267948966 and "
             "joint7 0.7853981633974483.",
             source="upstream_code", ref="panda_description/config/initial_joint_positions.yaml:2-9"),
        Fact("The SRDF defines the arm chain from panda_link0 to panda_hand_tcp.",
             source="upstream_code", ref="panda_moveit_config/srdf/panda.srdf:8-9"),
        Fact("move_group.launch.py starts moveit_servo's servo_node_main with the servo parameters when "
             "enable_servo is true.",
             source="upstream_code", ref="panda_moveit_config/launch/move_group.launch.py:265-282"),
        Fact("move_group.launch.py declares ros2_control_command_interface with default effort and "
             "enable_servo with default true.",
             source="upstream_code", ref="panda_moveit_config/launch/move_group.launch.py:426-439"),
        Fact("move_group.launch.py spawns every controller named in moveit_controller_manager.yaml plus "
             "joint_state_broadcaster.",
             source="upstream_code", ref="panda_moveit_config/launch/move_group.launch.py:309-321"),
        Fact("ex_ign_control.launch.py launches Ignition Gazebo with the -r flag and includes "
             "move_group.launch.py with the ign ros2_control plugin and the effort command interface.",
             source="upstream_code", ref="panda_moveit_config/launch/ex_ign_control.launch.py:30-56"),
        Fact("ex_ign_control.launch.py bridges /clock from Ignition to rosgraph_msgs/msg/Clock.",
             source="upstream_code", ref="panda_moveit_config/launch/ex_ign_control.launch.py:76-82"),
        Fact("panda_ign_moveit2.repos pulls ros_ign galactic, ign_ros2_control devel and "
             "ros2_controllers jtc_effort from external repositories.",
             source="upstream_code", ref="panda_ign_moveit2.repos:1-13"),
        Fact("panda_moveit_config/package.xml depends on control_msgs, controller_manager, "
             "joint_trajectory_controller, moveit_servo and moveit.",
             source="upstream_code", ref="panda_moveit_config/package.xml:16-24"),
    ]
    safe_state = (
        "No source-backed stop, pause, controller-switch or safe-state endpoint is declared in the "
        "pinned clone: the only verifiable command endpoint is the Servo outgoing JointTrajectory "
        "publication, so the runtime's software latch refuses further publications but cannot "
        "interrupt a trajectory the external controller has already accepted, does not fence Servo or "
        "move_group, and this package claims no stopped state."
    )

    #: The deployed fake is a ROS-free recording transport, not Gazebo.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo or MoveIt physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven recording stand-in with no physics step, trajectory interpolation, "
                      "controller timing, feedback or wall-clock pacing; the placeholder trajectory "
                      "recording does not establish trajectory or state-hash replay"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it records the advertised and published "
            "JointTrajectory messages and runs no Gazebo, gz_ros2_control, MoveIt Servo, "
            "joint_trajectory_controller or ROS graph",
            "the publication is not an acknowledged command: the fake cannot show controller "
            "acceptance, interpolation, execution, timing, feedback, collision behaviour or a "
            "stopped state, and the receipt always reports confirmed=false",
            "the last trajectory the fake stores is placeholder test data; a live run must publish "
            "through the operator's rosbridge and observe the controller separately",
            "the acknowledged FollowJointTrajectory action used by MoveIt is not exposed: the clone "
            "only names the short type FollowJointTrajectory and an exec_depend on control_msgs, so "
            "the exact control_msgs wire type cannot be cited at this pin",
            "the /joint_states observation, /move_action planning interface, gripper controller, "
            "/clock and Gazebo model/physics are out of scope",
            "no source-backed stop, pause, controller-switch or safe-state action is declared; the "
            "runtime software latch is not an independent stop and does not interrupt an accepted "
            "trajectory",
            "move_group.launch.py starts MoveIt Servo by default (enable_servo true), and Servo publishes its "
            "outgoing commands on the same /joint_trajectory_controller/joint_trajectory topic this package "
            "publishes to; move_group also executes plans through the same controller's "
            "follow_joint_trajectory action; neither is fenced by the MHS latch",
            "ex_ign_control.launch.py starts Gazebo running (-r), so an accepted trajectory keeps executing in "
            "the free-running simulation after an e-stop",
        ],
    }

    commands = {
        "x-cap.andrejorsula.joint_trajectory.v1": _COMMAND,
    }
    actions = {
        "x-cap.andrejorsula.joint_trajectory.v1": _ACTION,
    }
    # No source-proven stop exists: the clone exposes only the Servo output
    # publication.  A software latch is not an e-stop and no safe-state action
    # is claimed.
    safety_bindings = {}
