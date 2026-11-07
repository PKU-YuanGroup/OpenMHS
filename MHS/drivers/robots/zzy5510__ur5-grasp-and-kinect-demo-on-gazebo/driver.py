"""OpenMHS rosbridge driver for the pinned UR5 grasp Gazebo simulation.

The upstream repository is a ROS 1 / Gazebo 7 simulation demo.  The vendored
``gazebo_ros`` server plugin is loaded by the shipped ``gzserver`` wrapper and
advertises the private ``pause_physics`` and ``unpause_physics`` services.
Those two acknowledged ``std_srvs/Empty`` calls are the simulation's stop and
resume controls.  The package also exposes two explicit observations: the
Gazebo ``/clock`` publication and the joint-state controller's
``/joint_states`` publication.

The pause holds only until something unpauses the world: the resume command,
the Gazebo GUI that the shipped launch opens by default, or another client.  The
clone also vendors real-hardware drivers (ur_modern_driver with ur_bringup, and
robotiq_85_driver) that this package does not bind (model review, 2026-11-05).

This is a configuration-only :class:`RosDriver`.  It declares no Python native
class, does not launch Gazebo, MoveIt or the controllers, and does not import
or run upstream code.  The MoveIt planning/execution interface and the Kinect
image stream are out of scope: they are clients or sensors of this world, not
the simulation's pause/resume control surface.

Every endpoint, type and fact cites the pinned clone at
a5b25d72fe7637ebfad26a60c4bc57c1a8b418c4.  The fake transport is ROS-free and
all of its state values are placeholders.
"""

from mhs.driver import Action, Fact, Field, RosDriver

_CPP = "src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_GZSERVER = "src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/scripts/gzserver"
_LAUNCH = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/launch_simulation.launch"
_MAIN = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/main.launch"
_EMPTY = "src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
_JSC_CPP = "src/UR_with_Robotiq_grasp_gazebo/depends/ros_controllers/joint_state_controller/src/joint_state_controller.cpp"
_JSC_YAML = "src/universal_robot/ur_gazebo/controller/joint_state_controller.yaml"
_CONTROLLER_UTILS = "src/universal_robot/ur_gazebo/launch/controller_utils.launch"
_ARM_YAML = "src/universal_robot/ur_gazebo/controller/arm_controller_ur10.yaml"
_MODEL = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/model2.urdf"
_XACRO = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/ur_with_kinect.xacro"
_KINECT = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/kinect.xacro"
_MOVE_MODEL = ("src/UR_with_Robotiq_grasp_gazebo/depends/spawn_robot_tools/spawn_robot_tools_pkg/src/"
               "spawn_robot_tools_pkg/move_generic_model.py")
_UR5_BRINGUP = "src/universal_robot/ur_bringup/launch/ur5_bringup.launch"
_ROBOTIQ = "src/UR_with_Robotiq_grasp_gazebo/ur_tc/robotiq_85_gripper/robotiq_85_driver/src/robotiq_85/robotiq_85_gripper.py"

#: GazeboRosApiPlugin advertises the relative service \"pause_physics\" on the
#: private node handle; the node is named \"gazebo\", so the resolved endpoint is
#: /gazebo/pause_physics.  The advertised type is std_srvs::Empty.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _CPP + ":430-436",
    "type_ref": _CPP + ":432",
    "timeout_ms": 5000,
    "success": {"path": "$", "equals": {}},
}

#: GazeboRosApiPlugin advertises the relative service \"unpause_physics\".
_RESUME = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_name": "unpause_physics",
    "source_ref": _CPP + ":439-445",
    "type_ref": _CPP + ":441",
    "timeout_ms": 5000,
    "success": {"path": "$", "equals": {}},
}

#: The world-update hook publishes rosgraph_msgs/Clock on the absolute /clock.
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/Clock",
    "source_name": "/clock",
    "source_ref": _CPP + ":221",
    "type_ref": _CPP + ":221",
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

#: JointStateController advertises sensor_msgs/JointState on the relative
#: \"joint_states\" name through the root node handle.
_JOINT_STATE = {
    "topic": "/joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "joint_states",
    "source_ref": _JSC_CPP + ":57",
    "type_ref": _JSC_CPP + ":57",
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {
        "map": {
            "joint_names": "name",
            "joint_positions": "position",
            "joint_velocities": "velocity",
            "joint_efforts": "effort",
        }
    },
}

_CLOCK_TIME = Field(
    "object",
    description="One simulated ROS clock sample; both components come from the Gazebo sim time",
    properties={
        "secs": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nsecs": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)

_JOINT_NAMES = Field(
    "array",
    items=Field("string", description="Joint name in the published message order"),
    description="Joint names in the order published by the joint-state controller",
)

_JOINT_POSITIONS = Field(
    "array",
    unit="1",
    items=Field("number", unit="1", description="One joint position; see the array description for its unit"),
    description="Joint positions in the published order; the controller publishes every registered joint: "
                "rad for the six revolute arm joints, m for the prismatic arm_to_finger1 and arm_to_finger2",
)

_JOINT_VELOCITIES = Field(
    "array",
    unit="1",
    items=Field("number", unit="1", description="One joint velocity; see the array description for its unit"),
    description="Joint velocities in the published order: rad/s for the revolute arm joints, m/s for the "
                "prismatic finger joints",
)

_JOINT_EFFORTS = Field(
    "array",
    unit="1",
    items=Field("number", unit="1", description="One joint effort; see the array description for its unit"),
    description="Joint efforts in the published order: N.m for the revolute arm joints, N for the prismatic "
                "finger joints",
)


class Ur5GraspKinectGazebo(RosDriver):
    device_id = "ur5-grasp-kinect"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUr5GraspKinectGazebo"}
    tags = ["ros", "ros1", "gazebo", "simulation", "ur5", "robot-arm", "kinect", "pause"]
    display_name = "UR5 grasp and Kinect Gazebo simulation"
    vendor = "zzy5510"
    facts = [
        Fact("The shipped main.launch starts the simulation launch and the MoveIt move_group launch.",
             source="upstream_code", ref=_MAIN + ":7-12"),
        Fact("launch_simulation.launch includes gazebo_ros empty_world.launch with use_sim_time true and the "
             "world file from smart_grasping_sandbox_sample.",
             source="upstream_code", ref=_LAUNCH + ":12-20"),
        Fact("The gazebo_ros gzserver wrapper appends -s libgazebo_ros_api_plugin.so unless that plugin is "
             "already present in the arguments.",
             source="upstream_code", ref=_GZSERVER + ":20-24"),
        Fact("GazeboRosApiPlugin initializes the ROS node with the name gazebo.",
             source="upstream_code", ref=_CPP + ":122"),
        Fact("GazeboRosApiPlugin advertises its services on a private node handle named '~'.",
             source="upstream_code", ref=_CPP + ":140"),
        Fact("advertiseServices creates the relative pause_physics and unpause_physics services with the "
             "std_srvs/Empty type.",
             source="upstream_code", ref=_CPP + ":430-445"),
        Fact("pausePhysics calls world_->SetPaused(true) and returns true.",
             source="upstream_code", ref=_CPP + ":1626-1630"),
        Fact("unpausePhysics calls world_->SetPaused(false) and returns true.",
             source="upstream_code", ref=_CPP + ":1632-1636"),
        Fact("GazeboRosApiPlugin advertises rosgraph_msgs/Clock on the absolute /clock topic.",
             source="upstream_code", ref=_CPP + ":221"),
        Fact("GazeboRosApiPlugin connects publishSimTime to the world update-begin event.",
             source="upstream_code", ref=_CPP + ":201"),
        Fact("publishSimTime reads world_->SimTime() and publishes it as rosgraph_msgs/Clock.",
             source="upstream_code", ref=_CPP + ":2091-2110"),
        Fact("JointStateController advertises sensor_msgs/JointState on the relative joint_states name through "
             "the root node handle.",
             source="upstream_code", ref=_JSC_CPP + ":57"),
        Fact("The shipped joint-state controller configuration sets the controller type and publish_rate 50.",
             source="upstream_code", ref=_JSC_YAML + ":1-3"),
        Fact("The shipped controller_utils.launch loads the joint-state controller configuration and spawns "
             "the joint_state_controller.",
             source="upstream_code", ref=_CONTROLLER_UTILS + ":14-16"),
        Fact("launch_simulation.launch loads arm_controller_ur10.yaml and spawns arm_controller, then loads "
             "gripper_gazebo_trajectory.yaml and spawns hand_controller.",
             source="upstream_code", ref=_LAUNCH + ":43-48"),
        Fact("arm_controller_ur10.yaml, which launch_simulation.launch loads, names six joints in the order "
             "shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint and "
             "wrist_3_joint.",
             source="upstream_code", ref=_ARM_YAML + ":3-9"),
        Fact("launch_simulation.launch sets robot_description from ur_with_kinect.xacro.",
             source="upstream_code", ref=_LAUNCH + ":23"),
        Fact("ur_with_kinect.xacro includes model2.urdf and kinect.xacro.",
             source="upstream_code", ref=_XACRO + ":5-6"),
        Fact("model2.urdf declares arm_to_finger1 and arm_to_finger2 as prismatic joints.",
             source="upstream_code", ref=_MODEL + ":366-396"),
        Fact("model2.urdf loads the gazebo_ros_control plugin with DefaultRobotHWSim.",
             source="upstream_code", ref=_MODEL + ":5-6"),
        Fact("launch_simulation.launch declares gui with default true and paused with default false.",
             source="upstream_code", ref=_LAUNCH + ":2-5"),
        Fact("move_generic_model.py's move_model pauses physics, sets the model state and then unpauses "
             "physics through g_unpause when pause_physics is true.",
             source="upstream_code", ref=_MOVE_MODEL + ":103-164"),
        Fact("ur5_bringup.launch takes a robot_ip argument for the IP of the robot controller.",
             source="upstream_code", ref=_UR5_BRINGUP + ":11-12"),
        Fact("Robotiq85Gripper opens a serial port, by default /dev/ttyUSB0 at 115200 baud.",
             source="upstream_code", ref=_ROBOTIQ + ":6-10"),
        Fact("The shipped model2.urdf declares the six arm joints as revolute joints with a position limit "
             "from -3.14159265359 to 3.14159265359 rad.",
             source="upstream_code", ref=_MODEL + ":43-203"),
        Fact("The Kinect's gazebo_ros_openni_kinect plugin publishes rgb/image_raw, depth/image_raw, "
             "depth/points and the two camera-info topics under its camera name.",
             source="upstream_code", ref=_KINECT + ":46-54"),
    ]
    safe_state = (
        "The acknowledged /gazebo/pause_physics service pauses the Gazebo world: it stops stepping, so the "
        "clock and joint-state publications stop and the controllers cannot move the arm until something "
        "unpauses it (the resume command, the Gazebo GUI that the shipped launch opens, or another client). "
        "This is not a stopped-state measurement; a pending trajectory goal continues after an unpause."
    )
    fidelity = {
        "engine": "analytic:ROS contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven contract fake with no Gazebo physics, controller, MoveIt planner or "
                     "wall-clock pacing; placeholder clock and joint samples do not establish trajectory or "
                     "state replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract transport: it answers the declared /clock, /joint_states, "
            "/gazebo/pause_physics and /gazebo/unpause_physics endpoints and runs no Gazebo, ODE physics, "
            "gazebo_ros_control, MoveIt, contacts, sensors or wall-clock loop",
            "the clock, joint names, joint positions, velocities and efforts are placeholders; they do not "
            "prove motion, arrival, grasp or stopped state",
            "the fake's pause handler flips a local flag; it does not pause a simulator, does not cancel a "
            "pending controller goal and provides no stopped-state measurement",
            "the /clock and /joint_states fake publications go silent while paused, matching the upstream "
            "world-update and controller update paths, but the fake does not model publish rates or latencies",
            "anything with access to Gazebo can undo the pause: the GUI that launch_simulation.launch starts "
            "by default, and the vendored spawn_robot_tools move_model, which unpauses physics after moving a "
            "model when called with pause_physics (its own launch files, not the shipped main.launch)",
            "the spawned arm (model2.urdf through ur_with_kinect.xacro) uses the ur10 meshes and UR10 link "
            "offsets (model2.urdf:55, 108, 139) and the launch loads arm_controller_ur10.yaml, although the "
            "repository and its paths name a UR5; /joint_states also carries the two prismatic finger joints",
            "the clone vendors real-hardware drivers that this package does not bind: ur_modern_driver with "
            "ur_bringup launch files for a UR arm at a robot_ip, and robotiq_85_driver, which opens a serial "
            "port for a Robotiq 2F-85; on such a graph /joint_states reads the real arm while "
            "/gazebo/pause_physics does not exist, so the e-stop fails with the latch held",
            "the package exposes only the simulation pause/resume services and the two explicit observations; "
            "the arm trajectory controllers, MoveIt planning, the Kinect image and point-cloud streams, the "
            "gripper command topics and the remaining Gazebo services are NOT COVERED",
            "no real ROS graph, Gazebo, MoveIt, simulator or hardware was contacted; evidence is F0 "
            "contract_checked only",
        ],
    }

    commands = {
        "x-cap.zzy5510.pause.v1": dict(_PAUSE, result={"acknowledged": {"value": True}}),
        "x-cap.zzy5510.resume.v1": dict(_RESUME, result={"acknowledged": {"value": True}}),
        "x-cap.zzy5510.clock.v1": _CLOCK,
        "x-cap.zzy5510.joint_state.v1": _JOINT_STATE,
    }
    actions = {
        "x-cap.zzy5510.pause.v1": Action(
            name="pause",
            safe_state=True,
            description="Pause the Gazebo world with the acknowledged /gazebo/pause_physics service; the "
                        "receipt is the service acknowledgement, not a stopped-state measurement",
            output={"acknowledged": Field(
                "boolean",
                description="True once the pause service acknowledged; not a measured stopped state")},
        ),
        "x-cap.zzy5510.resume.v1": Action(
            name="resume",
            description="Resume the Gazebo world with the acknowledged /gazebo/unpause_physics service; an "
                        "interrupted controller goal may continue after the unpause",
            output={"acknowledged": Field(
                "boolean", description="True once the resume service acknowledged")},
        ),
        "x-cap.zzy5510.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one /clock sample from the Gazebo world-update publication; the topic is "
                        "silent while paused and this is an explicit observation, not the resource snapshot",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.zzy5510.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description="Read one /joint_states sample from the joint-state controller; the topic is silent "
                        "while paused and this is an explicit observation, not the resource snapshot",
            output={
                "joint_positions": _JOINT_POSITIONS,
                "joint_velocities": _JOINT_VELOCITIES,
                "joint_efforts": _JOINT_EFFORTS,
                "joint_names": _JOINT_NAMES,
            },
        ),
    }
    # The runtime latches before calling the Gazebo pause service, and the same
    # input-free pause action is the declared safe-state achievement.  There is
    # no reset binding: unpausing would let a pending controller goal continue,
    # so mhs.safety.reset clears only the software latch.
    safety_bindings = {"estop": _PAUSE}
