"""OpenMHS rosbridge driver for the RRBot two-joint arm in gh.ros-simulation/gazebo_ros_demos.

The pinned repository is the Gazebo/ROS 1 RRBot demonstration.  ``rrbot.xacro``
declares a revolute-revolute arm with the continuous joints ``joint1`` and
``joint2``; ``rrbot_control.yaml`` loads an effort-based
``JointPositionController`` for each joint; and the README shows the operator
sending one position command with ``rostopic pub``.  This is a
configuration-only :class:`~mhs.driver.RosDriver` over rosbridge: it declares no
Python native class, imports no ROS and starts neither Gazebo nor ros_control.

Scope: the two joint-position command topics.  The pinned clone names the joint
state, laser-scan and camera topics, but it does not declare their message
types, and this helper requires an explicit type binding for every endpoint;
those observations are therefore NOT COVERED rather than guessed.

No acknowledged stop exists in the pinned clone.  Both control endpoints are
fire-and-forget ``std_msgs/Float64`` publications.  The clone declares no pause,
stop, controller-switch, reset or safe-state service or action, and a
zero-position publication is transmission only.  The package therefore declares
no e-stop or safe-state binding; the runtime's software latch refuses new
commands, but it cannot interrupt the external controllers or Gazebo, so a stock
e-stop reports ``MHS.SAFETY.SAFE_STATE_UNREACHED``.  This package is blocked
rather than claiming a stopped state.

Every endpoint, type and fact cites the pinned clone at
``bc1f5a5bc6c2355bb4f175cab86d3c9eabeb09f1``.  The fake transport is ROS-free;
all of its values are placeholders, not device facts or limits.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

#: README: the repository is a Gazebo/ROS example set and is GPL-3.0.
_README_REF = "README.md:1-6"
#: README: the ROS Control quick start and the one documented position command.
_COMMAND_EXAMPLE_REF = "README.md:22-28"

#: rrbot_control.yaml: the joint-state controller and its publish rate.
_JOINT_STATE_CONFIG_REF = "rrbot_control/config/rrbot_control.yaml:3-5"
#: rrbot_control.yaml: the two effort-based joint position controllers.
_POSITION_CONFIG_REF = "rrbot_control/config/rrbot_control.yaml:7-15"
#: rrbot_control.launch: the YAML is loaded and the three controllers are spawned in /rrbot.
_SPAWNER_REF = "rrbot_control/launch/rrbot_control.launch:3-10"
#: rrbot_control.launch: /joint_states is remapped to /rrbot/joint_states.
_JOINT_STATE_REMAP_REF = "rrbot_control/launch/rrbot_control.launch:13-16"
#: rqt publisher: the joint1 command topic and its std_msgs/Float64 type.
_JOINT1_COMMAND_REF = "rrbot_control/launch/rrbot_rqt.perspective:63"
#: rqt plot: the joint1 command/data and controller state/error field paths.
_JOINT1_PLOT_REF = "rrbot_control/launch/rrbot_rqt.perspective:36"
#: package.xml: the runtime dependencies of the control package.
_CONTROL_DEPS_REF = "rrbot_control/package.xml:19-24"

#: rrbot.xacro: joint1 and joint2 are continuous joints with no travel limit.
_JOINT1_REF = "rrbot_description/urdf/rrbot.xacro:55-61"
_JOINT2_REF = "rrbot_description/urdf/rrbot.xacro:90-96"
#: rrbot.xacro: both joints use the EffortJointInterface transmission.
_TRANSMISSION_REF = "rrbot_description/urdf/rrbot.xacro:199-219"
#: rrbot.gazebo: the gazebo_ros_control plugin and its /rrbot namespace.
_ROS_CONTROL_REF = "rrbot_description/urdf/rrbot.gazebo:5-9"

#: rrbot_world.launch: the launch-time paused argument and the empty_world include.
_WORLD_LAUNCH_REF = "rrbot_gazebo/launch/rrbot_world.launch:3-18"
#: rrbot_world.launch: the URDF is spawned with gazebo_ros spawn_model.
_SPAWN_REF = "rrbot_gazebo/launch/rrbot_world.launch:24-26"
#: The tutorial world plugin requires the gazebo_ros API plugin to be loaded.
_GAZEBO_API_REF = "gazebo_tutorials/src/simple_world_plugin.cpp:12-16"

#: The laser and camera plugins declare these topics, but not their ROS types.
_LASER_TOPIC_REF = "rrbot_description/urdf/rrbot.gazebo:68-71"
_CAMERA_TOPIC_REF = "rrbot_description/urdf/rrbot.gazebo:99-105"
#: RViz displays the same laser and camera topics.
_RVIZ_LASER_REF = "rrbot_description/launch/rrbot.rviz:102-119"
_RVIZ_CAMERA_REF = "rrbot_description/launch/rrbot.rviz:124-127"

#: Reviewer additions: the manifests' licence declarations (the README states GPL-3.0),
#: the rqt launch that opens the saved publisher, and the commented-out control include.
_CONTROL_LICENSE_REF = "rrbot_control/package.xml:9"
_DESCRIPTION_LICENSE_REF = "rrbot_description/package.xml:9"
_GAZEBO_LICENSE_REF = "rrbot_gazebo/package.xml:7"
_TUTORIALS_LICENSE_REF = "gazebo_tutorials/package.xml:16"
_RQT_LAUNCH_REF = "rrbot_control/launch/rrbot_rqt.launch:4-5"
_CONTROL_INCLUDE_REF = "rrbot_gazebo/launch/rrbot_world.launch:28-29"

# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------

#: The URDF declares both joints continuous, so the clone states no travel
#: bound.  The site supplies the deployed joint envelope.
_JOINT1_LIMIT = Limit.operator_required(
    "rrbot.xacro declares joint1 as a continuous joint with no travel bound, and rrbot_control.yaml "
    "declares PID gains but no position limit; the site supplies the joint1 envelope"
)
_JOINT2_LIMIT = Limit.operator_required(
    "rrbot.xacro declares joint2 as a continuous joint with no travel bound, and rrbot_control.yaml "
    "declares PID gains but no position limit; the site supplies the joint2 envelope"
)

_POSITION_FIELD = Field(
    "number",
    unit="rad",
    description="Target joint angle sent as the data field of one std_msgs/Float64 message",
)
_PUBLISHED = {
    "published": Field("boolean",
                       description="True when the driver handed the message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a topic publication carries no execution, arrival or stop "
                                   "confirmation"),
}

#: The two controller command topics.  The README shows joint2 explicitly with
#: std_msgs/Float64; the rqt publisher shows joint1 with the same type.
_JOINT1_COMMAND = {
    "topic": "/rrbot/joint1_position_controller/command",
    "type": "std_msgs/Float64",
    "source_name": "/rrbot/joint1_position_controller/command",
    "source_ref": _JOINT1_COMMAND_REF,
    "type_ref": _JOINT1_COMMAND_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.position"}},
}
_JOINT2_COMMAND = {
    "topic": "/rrbot/joint2_position_controller/command",
    "type": "std_msgs/Float64",
    "source_name": "/rrbot/joint2_position_controller/command",
    "source_ref": _COMMAND_EXAMPLE_REF,
    "type_ref": _COMMAND_EXAMPLE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.position"}},
}


class GazeboRosDemosRrbot(RosDriver):
    device_id = "rrbot"
    device_kind = "robot.arm"
    mode = "simulated"
    #: A robot arm is at least R2 (MHS/spec/04-safety.md); the controllers move
    #: the arm even though this package contacts only the simulated ROS graph.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeGazeboRosDemosRrbot"}
    tags = ["ros", "ros1", "gazebo", "simulation", "rrbot", "robot-arm", "joint-position", "demo"]
    display_name = "RRBot two-joint arm (Gazebo/ROS demos)"
    vendor = "ros-simulation"
    model = "RRBot revolute-revolute manipulator"

    facts = [
        Fact("The README identifies the repository as example robots and code for interfacing Gazebo with ROS "
             "and states GPL-3.0 licensing.",
             source="vendor_doc", ref=_README_REF),
        Fact("The README's ROS Control quick start runs rrbot_control.launch and shows the position command "
             "rostopic pub /rrbot/joint2_position_controller/command std_msgs/Float64 with data -0.9; the value "
             "is an example, not a declared joint limit.",
             source="vendor_doc", ref=_COMMAND_EXAMPLE_REF),
        Fact("rrbot_control.yaml configures joint_state_controller as "
             "joint_state_controller/JointStateController with publish_rate 50.",
             source="upstream_code", ref=_JOINT_STATE_CONFIG_REF),
        Fact("rrbot_control.yaml configures joint1_position_controller for joint1 and joint2_position_controller "
             "for joint2 as effort_controllers/JointPositionController with PID gains 100.0, 0.01 and 10.0.",
             source="upstream_code", ref=_POSITION_CONFIG_REF),
        Fact("rrbot_control.launch loads rrbot_control.yaml and spawns joint_state_controller, "
             "joint1_position_controller and joint2_position_controller through the controller_manager spawner "
             "under the /rrbot namespace.",
             source="upstream_code", ref=_SPAWNER_REF),
        Fact("rrbot_control.launch remaps /joint_states to /rrbot/joint_states for robot_state_publisher.",
             source="upstream_code", ref=_JOINT_STATE_REMAP_REF),
        Fact("The rqt publisher records /rrbot/joint1_position_controller/command with type_name "
             "std_msgs/Float64, enabled False, rate 100.0 and the data expression sin(i/100).",
             source="upstream_code", ref=_JOINT1_COMMAND_REF),
        Fact("The rqt plot records /rrbot/joint1_position_controller/command/data and "
             "/rrbot/joint1_position_controller/state/error as field expressions.",
             source="upstream_code", ref=_JOINT1_PLOT_REF),
        Fact("rrbot_control/package.xml declares controller_manager, joint_state_controller, "
             "robot_state_publisher, rqt_gui and effort_controllers as runtime dependencies.",
             source="upstream_code", ref=_CONTROL_DEPS_REF),
        Fact("rrbot.xacro declares joint1 as a continuous joint with axis 0 1 0 and damping 0.7.",
             source="upstream_code", ref=_JOINT1_REF),
        Fact("rrbot.xacro declares joint2 as a continuous joint with axis 0 1 0 and damping 0.7.",
             source="upstream_code", ref=_JOINT2_REF),
        Fact("rrbot.xacro declares SimpleTransmission blocks for joint1 and joint2 that use "
             "hardware_interface/EffortJointInterface.",
             source="upstream_code", ref=_TRANSMISSION_REF),
        Fact("rrbot.gazebo loads libgazebo_ros_control.so with robotNamespace /rrbot and "
             "gazebo_ros_control/DefaultRobotHWSim.",
             source="upstream_code", ref=_ROS_CONTROL_REF),
        Fact("rrbot_world.launch exposes a paused launch argument defaulting to false and forwards it to "
             "gazebo_ros empty_world.launch with the rrbot world.",
             source="upstream_code", ref=_WORLD_LAUNCH_REF),
        Fact("rrbot_world.launch starts gazebo_ros spawn_model to spawn the robot_description URDF as model "
             "rrbot.",
             source="upstream_code", ref=_SPAWN_REF),
        Fact("The gazebo_tutorials world plugin requires libgazebo_ros_api_plugin.so from the gazebo_ros "
             "package to be loaded.",
             source="upstream_code", ref=_GAZEBO_API_REF),
        Fact("The Hokuyo sensor plugin declares the topic /rrbot/laser/scan; this fact records the topic, not "
             "a message type.",
             source="upstream_code", ref=_LASER_TOPIC_REF),
        Fact("The camera plugin declares cameraName rrbot/camera1 and imageTopicName image_raw, giving the "
             "topic /rrbot/camera1/image_raw; this fact records the topic, not a message type.",
             source="upstream_code", ref=_CAMERA_TOPIC_REF),
        Fact("The RViz configuration displays /rrbot/laser/scan as a rviz/LaserScan display.",
             source="upstream_code", ref=_RVIZ_LASER_REF),
        Fact("The RViz configuration displays /rrbot/camera1/image_raw as a rviz/Camera display.",
             source="upstream_code", ref=_RVIZ_CAMERA_REF),
        Fact("rrbot_control/package.xml declares the licence BSD.",
             source="upstream_code", ref=_CONTROL_LICENSE_REF),
        Fact("rrbot_description/package.xml declares the licence BSD.",
             source="upstream_code", ref=_DESCRIPTION_LICENSE_REF),
        Fact("rrbot_gazebo/package.xml declares the licence BSD.",
             source="upstream_code", ref=_GAZEBO_LICENSE_REF),
        Fact("gazebo_tutorials/package.xml declares the licence TODO.",
             source="upstream_code", ref=_TUTORIALS_LICENSE_REF),
        Fact("rrbot_rqt.launch starts rqt_gui with the rrbot_rqt.perspective file.",
             source="upstream_code", ref=_RQT_LAUNCH_REF),
        Fact("rrbot_world.launch leaves its include of rrbot_control.launch commented out.",
             source="upstream_code", ref=_CONTROL_INCLUDE_REF),
    ]

    safe_state = (
        "No acknowledged stop exists in the pinned clone: both control endpoints are fire-and-forget "
        "std_msgs/Float64 publications, and the clone declares no pause, stop, controller-switch, reset or "
        "safe-state service or action. A zero-position publication is transmission only. The runtime software "
        "latch refuses new commands but cannot interrupt the external controllers or Gazebo, so a stock e-stop "
        "reports MHS.SAFETY.SAFE_STATE_UNREACHED and this package does not claim a stopped state."
    )

    #: The deployed fake is an event-driven recording transport, not Gazebo.
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract stand-in (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": ("Event-driven advertisement/publication recording with no PID control, physics step, "
                      "controller timing or wall-clock pacing; placeholder command records do not establish "
                      "trajectory or state-hash replay"),
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it records advertise and publish messages for the two "
            "declared command topics and runs no Gazebo, gazebo_ros_control, controller_manager, PID, physics, "
            "ROS graph or wall-clock loop",
            "the command records are placeholders and do not move a simulated joint; a live run needs the "
            "operator's Gazebo, gazebo_ros_control and rosbridge deployment",
            "the pinned clone names /rrbot/joint_states, /rrbot/laser/scan and /rrbot/camera1/image_raw but "
            "does not declare their message types; the SDK requires an explicit type binding, so the joint-state, "
            "laser and camera observations are NOT COVERED rather than guessed",
            "no source-backed stop, pause, controller switch or safe-state action is declared; the runtime "
            "software latch is not an independent stop and does not interrupt the controllers or the world",
            "the URDF declares both joints continuous, so the clone states no joint travel bound; the operator "
            "overlay must supply every joint envelope before a command is admitted",
            "the Gazebo product launch, physics parameters, controller gains, joint state, laser, camera, TF, "
            "clock, RViz and controller_manager services are out of scope",
            "no ROS graph, Gazebo process or hardware is contacted; a live run needs the operator's ROS 1 graph "
            "and rosbridge endpoint",
            "rrbot_rqt.launch opens rqt_gui with a saved publisher for /rrbot/joint1_position_controller/command "
            "(disabled, rate 100, data sin(i/100)); enabled in the GUI it competes with this package and keeps "
            "moving joint1 while MHS is latched",
            "rrbot_world.launch does not start the controllers (its rrbot_control.launch include is commented "
            "out); until rrbot_control.launch runs, the command topics have no subscriber and a publication is "
            "lost",
            "licence: the README states GPL-3.0, the rrbot_control, rrbot_description and rrbot_gazebo manifests "
            "declare BSD and gazebo_tutorials declares TODO; the card says NOASSERTION and publish_review required",
        ],
    }

    #: The resource has no declared state fields: the clone declares no message
    #: type for an observation topic that the SDK can bind.
    commands = {
        "x-cap.ros-simulation.rrbot_joint1_position.v1": _JOINT1_COMMAND,
        "x-cap.ros-simulation.rrbot_joint2_position.v1": _JOINT2_COMMAND,
    }
    actions = {
        "x-cap.ros-simulation.rrbot_joint1_position.v1": Action(
            name="set_joint1_position",
            verb="invoke",
            description=(
                "Publish one std_msgs/Float64 position command for joint1 to the effort-based "
                "joint1_position_controller. The receipt confirms only that rosbridge accepted the publication, "
                "not that the controller applied it, that the joint reached the target or that it stopped."
            ),
            input={"position": Field(
                "number", unit="rad",
                description="Target joint1 angle sent as the message data field",
                limit=_JOINT1_LIMIT,
            )},
            output=_PUBLISHED,
            examples=[{"position": 0.0}],
        ),
        "x-cap.ros-simulation.rrbot_joint2_position.v1": Action(
            name="set_joint2_position",
            verb="invoke",
            description=(
                "Publish one std_msgs/Float64 position command for joint2 to the effort-based "
                "joint2_position_controller. The receipt confirms only that rosbridge accepted the publication, "
                "not that the controller applied it, that the joint reached the target or that it stopped."
            ),
            input={"position": Field(
                "number", unit="rad",
                description="Target joint2 angle sent as the message data field",
                limit=_JOINT2_LIMIT,
            )},
            output=_PUBLISHED,
            examples=[{"position": 0.0}],
        ),
    }
    #: No e-stop or safe-state binding exists: the clone exposes only topic
    #: publications and declares no acknowledged stop.  A software latch is
    #: not an e-stop and no safe-state action is claimed.
    safety_bindings = {}
