"""OpenMHS rosbridge driver for the pinned Unitree GO1 Gazebo simulation.

The upstream repository is a ROS 2 Humble / Gazebo 11 stack for one Unitree
GO1 quadruped.  It contains no Python device class, no ROS service server and
no ROS action server.  The public interface in the clone is the navigation
topic graph:

* ``/cmd_vel`` carries ``geometry_msgs/msg/Twist`` to the ``move_base``
  state machine;
* ``/odom`` carries ``nav_msgs/msg/Odometry`` from the p3d ground-truth plugin
  (the estimator node creates an odom publisher, but its publish call is
  commented out, ``Estimator.cpp:269``);
* ``/scan`` carries ``sensor_msgs/msg/LaserScan`` from the ray sensor plugin;
* ``/tf`` is published by the navigation helper ``tf_publisher.py`` (the
  estimator's ``sendTransform`` is commented out as well).

The package exposes one velocity publication and two observations.  It keeps
the velocity interface, which is the repository's documented primary control,
rather than replacing it with an observation.  The pinned clone has no ROS
service or action that acknowledges a stop: the internal keyboard ``L2_B``
passive path and the SIGINT handlers are not ROS bindings, and an all-zero
Twist publication is transmission only.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source fetched at a pinned commit (user decision and
authorisation of 2026-11-05; ``task.json`` ``companions`` with ``lock``):
gazebo_ros 3.9.0 (ROS 2 Humble) ``/pause_physics``.  ROS 2 gazebo_ros has no
service that reports the paused flag, so the stop is confirmed by a stall
read-back (E1): two ``/get_model_list`` answers 250 ms apart whose
``header.stamp``, the world's sim time, did not advance.  gazebo_ros2_control
and Gazebo classic 11 are cited for what a paused world does not run.  It is a
frozen sim time, not a measured standstill.

No unpause is offered.  A zero Twist would clear move_base's stored velocity,
but junior_ctrl's 500 Hz loop keeps running on the wall clock through the pause
on the last joint and IMU states it received, and the trotting state steps
whenever its position or velocity error exceeds its thresholds, so what the
legs do when the world resumes is not set by the stored command alone; this
package cannot clear it first (the orchestrator's SAFE-042 condition).  After
``mhs.safety.reset`` the world stays paused and the operator recovers outside
MHS (see ``safe_state``).  The odometry left the device resource: the p3d
plugin publishes it from the world update, so it is silent while paused; it
stays an explicit read capability, and the cmd_vel receipt reports what it sent.

Model review (2026-11-05): the clone also holds the real-robot UDP interface
``IOSDK``, but its CMake logic enables the /cmd_vel move_base state only in
simulation builds and the unitree_legged_sdk library it links is not in the
clone, so this binding has no real-robot path at the pin; Nav2's
controller_server (``navigation.launch.py``) publishes /cmd_vel too, and a
LaserScan with an inf or NaN range fails the read without output.

Every endpoint, type and fact cites the pinned clone at
44659704169515708ec46d0428381dc6c7730350.  The fake transport is ROS-free;
no ROS graph, Gazebo process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 3.9.0 (ROS 2 Humble, Gazebo 11) at ae6e5793, fetched under work/companions: the pause and its stall
#: read-back.  ROS 2 gazebo_ros has no service that reports the paused flag, so the read-back is get_model_list,
#: whose header.stamp is the world's sim time: two answers 250 ms apart with the same stamp (E1, a stall read-back).
_INIT = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp"
_FACTORY = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp"
_GZSERVER = "companion:gazebo_ros_pkgs/gazebo_ros/launch/gzserver.launch.py"
#: Gazebo classic 11.15.1 at b22c6e15 (the corpus clone): the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"
#: gazebo_ros2_control 0.4.12 (Humble) at 42d875b4, fetched under work/companions: the controller update.
_ROS2_CONTROL = "companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp"

#: The e-stop: pause_physics (std_srvs/srv/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/pause_physics",
    "type": "std_srvs/srv/Empty",
    "source_name": "pause_physics",
    "source_ref": _INIT + ":267-271",
    "type_ref": _INIT + ":267",
    "state_ref": _INIT + ":328-333",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 400,
}
#: The stall read-back that confirms it: get_model_list stamps its answer with the world's sim time, which advances
#: only while the world steps; the e-stop is confirmed only when two answers 250 ms apart carry the same stamp.
_READBACK = {
    "service": "/get_model_list",
    "type": "gazebo_msgs/srv/GetModelList",
    "source_name": "get_model_list",
    "source_ref": _FACTORY + ":139-143",
    "type_ref": _FACTORY + ":139",
    "state_ref": _FACTORY + ":168",
    "description": "Read the world's sim time twice, 250 ms apart; the e-stop is confirmed only when it did not advance",
    "request": {},
    "success": {"path": "success", "equals": True},
    "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 250, "unchanged": True},
    "timeout_ms": 300,
}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("gzserver.launch.py adds the init and factory gazebo_ros system plugins to the server command.",
         source="upstream_code", ref=_GZSERVER + ":55-56"),
    Fact("gzserver.launch.py defaults its init and factory arguments to true.", source="upstream_code",
         ref=_GZSERVER + ":186-193"),
    Fact("The init plugin takes the shared gazebo_ros node from gazebo_ros::Node::Get().", source="upstream_code",
         ref=_INIT + ":150-154"),
    Fact("gazebo_ros::Node::Get creates the shared node named gazebo with an empty namespace.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_ros/src/node.cpp:159-171"),
    Fact("The gazebo_ros executor spins its nodes on a thread of its own.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/src/executor.cpp:22-23"),
    Fact("The init plugin creates the pause_physics and unpause_physics services with the std_srvs::srv::Empty "
         "type.", source="upstream_code", ref=_INIT + ":266-277"),
    Fact("OnPause calls world_->SetPaused(true).", source="upstream_code", ref=_INIT + ":328-333"),
    Fact("OnUnpause calls world_->SetPaused(false).", source="upstream_code", ref=_INIT + ":335-340"),
    Fact("The init plugin publishes the simulation clock from a world-update-begin callback.",
         source="upstream_code", ref=_INIT + ":206-207"),
    Fact("The factory plugin creates the get_model_list service with the gazebo_msgs::srv::GetModelList type.",
         source="upstream_code", ref=_FACTORY + ":139-143"),
    Fact("GetModelList sets header.stamp to the world's simulation time, lists the model names and sets success "
         "true.", source="upstream_code", ref=_FACTORY + ":164-174"),
    Fact("The GetModelList response documents header.stamp as the simulation time when the data was collected.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetModelList.srv:2-5"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":835-854"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":824-827"),
    Fact("World::SetPaused stores the paused flag under worldUpdateMutex.", source="upstream_code",
         ref=_WORLD + ":1585-1593"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1579-1582"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":920-929"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":835-863"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1630-1640"),
    Fact("gazebo_ros2_control spins its controller manager's executor on a thread of its own.",
         source="upstream_code", ref=_ROS2_CONTROL + ":400-407"),
    Fact("gazebo_ros2_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS2_CONTROL + ":409-414"),
    Fact("gazebo_ros2_control's Update reads the simulation time, updates the controllers and writes their "
         "commands to the joints.", source="upstream_code", ref=_ROS2_CONTROL + ":419-437"),
]

_CMD_VEL_ID = "x-cap.atharva-05.cmd_vel.v1"


class _SentReceipt:
    """The receipt of a cmd_vel publication also reports the three values it handed to rosbridge.

    The device resource reads no topic (a paused world publishes none), so the receipt is where a caller sees what
    a publication sent; it is the transmitted request, not a measurement. Every other call, the e-stop and the
    reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _CMD_VEL_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        for key in ("linear_x", "linear_y", "angular_z"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: The ROS 2 ``State_move_base`` node subscribes to the absolute /cmd_vel
#: topic with geometry_msgs::msg::Twist.
_CMD_VEL_REF = "unitree_guide2/src/FSM/State_move_base.cpp:87-90"

#: The README declares the public odometry and scan topics and their types.
_ODOM_REF = "README.md:50-53"
_SCAN_REF = "README.md:56-59"

#: Go1Robot sets the robot model velocity limits; the move_base callback does
#: not apply them itself, so the MHS envelope enforces the model bound.
_LINEAR_X = Limit(
    min=-0.4,
    max=0.4,
    unit="m/s",
    source="upstream_code",
    ref="unitree_guide2/src/common/unitreeRobot.cpp:149",
    reason="Go1Robot sets the X robot velocity limit to -0.4..0.4 m/s; "
           "State_move_base passes the Twist to setHighCmd without clamping, so the driver envelope "
           "enforces the model limit",
)
_LINEAR_Y = Limit(
    min=-0.3,
    max=0.3,
    unit="m/s",
    source="upstream_code",
    ref="unitree_guide2/src/common/unitreeRobot.cpp:150",
    reason="Go1Robot sets the Y robot velocity limit to -0.3..0.3 m/s; "
           "State_move_base passes the Twist to setHighCmd without clamping, so the driver envelope "
           "enforces the model limit",
)
_ANGULAR_Z = Limit(
    min=-0.5,
    max=0.5,
    unit="rad/s",
    source="upstream_code",
    ref="unitree_guide2/src/common/unitreeRobot.cpp:151",
    reason="Go1Robot sets the yaw robot velocity limit to -0.5..0.5 rad/s; "
           "State_move_base passes the Twist to setHighCmd without clamping, so the driver envelope "
           "enforces the model limit",
)

_POSITION = Field(
    "object",
    description="Position selected from nav_msgs/Odometry pose.pose.position",
    properties={
        "x": Field("number", unit="m", description="Position x in the odometry frame"),
        "y": Field("number", unit="m", description="Position y in the odometry frame"),
        "z": Field("number", unit="m", description="Position z in the odometry frame"),
    },
)
_ORIENTATION = Field(
    "object",
    description="Orientation selected from nav_msgs/Odometry pose.pose.orientation",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose selected from message field pose.pose",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)
_LINEAR = Field(
    "object",
    description="Linear velocity selected from nav_msgs/Odometry twist.twist.linear",
    properties={
        "x": Field("number", unit="m/s", description="Linear velocity x"),
        "y": Field("number", unit="m/s", description="Linear velocity y"),
        "z": Field("number", unit="m/s", description="Linear velocity z"),
    },
)
_ANGULAR = Field(
    "object",
    description="Angular velocity selected from nav_msgs/Odometry twist.twist.angular",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)
_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist selected from message field twist.twist",
    properties={"linear": _LINEAR, "angular": _ANGULAR},
)
_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution, arrival or stop confirmation",
    ),
}
_SCAN_OUTPUT = {
    "frame_id": Field("string", description="Frame id from the LaserScan header"),
    "angle_min": Field("number", unit="rad", description="First scan angle"),
    "angle_max": Field("number", unit="rad", description="Last scan angle"),
    "angle_increment": Field("number", unit="rad", description="Angular distance between consecutive samples"),
    "time_increment": Field("number", unit="s", description="Time between consecutive samples"),
    "scan_time": Field("number", unit="s", description="Time between scans"),
    "range_min": Field("number", unit="m", description="Minimum range value"),
    "range_max": Field("number", unit="m", description="Maximum range value"),
    "ranges": Field(
        "array",
        unit="m",
        description="Measured ranges in metres; the pinned ray plugin is configured for 450 samples",
        items=Field("number", unit="m", description="One measured range"),
    ),
    "intensities": Field(
        "array",
        description="Per-sample intensities from the LaserScan message",
        items=Field("number", description="One intensity sample"),
    ),
}

#: One explicit geometry_msgs/Twist publication on the absolute /cmd_vel
#: topic.  The callback copies only linear.x, linear.y and angular.z into the
#: move_base high command; no motion, arrival or stop acknowledgement is sent
#: back on the topic.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_name": "/cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "angular.z": {"from": "input.angular_z"},
    },
}

#: The odometry resource fields subscribe to the public /odom topic.
_ODOM = {
    "topic": "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_name": "/odom",
    "source_ref": _ODOM_REF,
}

#: One LaserScan observation from the public /scan topic.
_SCAN = {
    "topic": "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "operation": "subscribe",
    "source_name": "/scan",
    "source_ref": _SCAN_REF,
    "path": "$",
    "result": {
        "map": {
            "frame_id": "header.frame_id",
            "angle_min": "angle_min",
            "angle_max": "angle_max",
            "angle_increment": "angle_increment",
            "time_increment": "time_increment",
            "scan_time": "scan_time",
            "range_min": "range_min",
            "range_max": "range_max",
            "ranges": "ranges",
            "intensities": "intensities",
        }
    },
}


class UnitreeRos2Sim(RosDriver):
    device_id = "unitree-go1-sim"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    # A mobile base is at least R2 in the catalogue; the card floor is R0.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeUnitreeRos2Sim"}
    tags = ["ros", "ros2", "gazebo", "simulation", "mobile-base", "cmd-vel",
            "odometry", "laser-scan", "unitree", "go1"]
    display_name = "Unitree GO1 Gazebo simulation"
    vendor = "atharva-05"
    model = "Unitree GO1 in the go1_sim Gazebo world"
    facts = [
        Fact("The README describes the repository as a simulation environment for the Unitree GO1 "
             "robot in Gazebo 11 and ROS 2, tested with ROS Humble on Ubuntu 22.04.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The README starts go1_gazebo, then unitree_guide2 junior_ctrl; the operator presses 2 for "
             "fixed_stand and 5 for move_base mode, in which the robot accepts velocity commands.",
             source="vendor_doc", ref="README.md:32-36"),
        Fact("The README declares the velocity control interface on the absolute /cmd_vel topic with "
             "geometry_msgs/Twist.", source="vendor_doc", ref="README.md:42-45"),
        Fact("The README declares odometry on the absolute /odom topic with nav_msgs/Odometry from the "
             "ground-truth plugin.", source="vendor_doc", ref="README.md:50-53"),
        Fact("The README declares 2D LiDAR data on the absolute /scan topic with sensor_msgs/LaserScan "
             "from the Gazebo sensor plugin.", source="vendor_doc", ref="README.md:56-59"),
        Fact("The README declares transforms on the absolute /tf topic with tf2_msgs/TFMessage.",
             source="vendor_doc", ref="README.md:62-65"),
        Fact("The ROS 2 State_move_base constructor creates the state_mb node and calls initRecv().",
             source="upstream_code", ref="unitree_guide2/src/FSM/State_move_base.cpp:49-63"),
        Fact("State_move_base::getUserCmd calls setHighCmd with the _vx, _vy and _wz values received from "
             "the Twist callback.", source="upstream_code",
             ref="unitree_guide2/src/FSM/State_move_base.cpp:77-79"),
        Fact("State_move_base::twistCallback copies msg->linear.x, msg->linear.y and msg->angular.z into "
             "_vx, _vy and _wz.", source="upstream_code",
             ref="unitree_guide2/src/FSM/State_move_base.cpp:81-85"),
        Fact("State_move_base::initRecv creates a subscription for geometry_msgs::msg::Twist on the "
             "absolute /cmd_vel topic with queue depth 1.", source="upstream_code",
             ref="unitree_guide2/src/FSM/State_move_base.cpp:87-90"),
        Fact("State_Trotting::setHighCmd writes vx and vy into _vCmdBody and wz into _dYawCmd directly; "
             "it does not clamp them.", source="upstream_code",
             ref="unitree_guide2/src/FSM/State_Trotting.cpp:129-134"),
        Fact("The Go1Robot constructor sets _robVelLimitX to -0.4..0.4, _robVelLimitY to -0.3..0.3 and "
             "_robVelLimitYaw to -0.5..0.5.", source="upstream_code",
             ref="unitree_guide2/src/common/unitreeRobot.cpp:139-151"),
        Fact("The Gazebo ray sensor is configured for 450 samples over 0.0..6.28319 rad, range "
             "0.4..35.0 m and update_rate 30; its plugin remaps ~/out to scan, outputs "
             "sensor_msgs/LaserScan and uses frame_name laser_link.",
             source="upstream_code", ref="go1_sim/go1_description/xacro/robot.xacro:185-217"),
        Fact("The p3d ground-truth plugin tracks body_name base_link, publishes topic_name odom in "
             "frame_name odom and updates at 100 Hz.", source="upstream_code",
             ref="go1_sim/go1_description/xacro/robot.xacro:220-227"),
        Fact("The ROS 2 Estimator creates a node named estimator, a publisher for nav_msgs::msg::Odometry "
             "on odom and a tf2_ros TransformBroadcaster.", source="upstream_code",
             ref="unitree_guide2/src/control/Estimator.cpp:123-127"),
        Fact("Estimator::run fills the odometry message and the odom transform in its ROS 2 block, but the "
             "sendTransform and publish calls are commented out.", source="upstream_code",
             ref="unitree_guide2/src/control/Estimator.cpp:226-273"),
        Fact("KeyBoard::checkCmd maps key 1 to UserCommand::L2_B (passive) and key 5 to "
             "UserCommand::L2_Y (move_base).", source="upstream_code",
             ref="unitree_guide2/src/interface/KeyBoard.cpp:25-42"),
        Fact("State_Passive::enter sets mode 10, zero q, dq and tau, Kp 0 and Kd 8 for the Gazebo "
             "platform, and its checkChange returns PASSIVE unless the user command is L2_A.",
             source="upstream_code", ref="unitree_guide2/src/FSM/State_Passive.cpp:9-48"),
        Fact("FSM::run calls ioInter->setPassive() when checkSafty() returns false.", source="upstream_code",
             ref="unitree_guide2/src/FSM/FSM.cpp:38-45"),
        Fact("IOROS::RosShutDown(int sig) prints a shutdown message and calls rclcpp::shutdown().",
             source="upstream_code", ref="unitree_guide2/src/interface/IOROS.cpp:236-242"),
        Fact("main.cpp's ShutDown(int sig) prints 'stop the controller' and sets the running flag to false.",
             source="upstream_code", ref="unitree_guide2/src/main.cpp:30-35"),
        Fact("IOROS::initSend creates twelve MotorCmd publishers on the per-leg controller command "
             "topics, and initRecv subscribes twelve MotorState topics and /imu_plugin/out.",
             source="upstream_code", ref="unitree_guide2/src/interface/IOROS.cpp:352-383"),
        Fact("unitree_guide2's CMakeLists sets CATKIN_MAKE ON, SIMULATION ON, REAL_ROBOT OFF and MOVE_BASE ON, "
             "and sets ROS_2 only when CATKIN_MAKE, SIMULATION and MOVE_BASE are all on.",
             source="upstream_code", ref="unitree_guide2/CMakeLists.txt:11-19"),
        Fact("CMake stops with an error when SIMULATION and REAL_ROBOT are both on or both off.",
             source="upstream_code", ref="unitree_guide2/CMakeLists.txt:40-42"),
        Fact("ROS_2 adds the COMPILE_WITH_ROS2_MB definition.", source="upstream_code",
             ref="unitree_guide2/CMakeLists.txt:71-73"),
        Fact("main constructs IOROS for the Gazebo platform under COMPILE_WITH_SIMULATION and IOSDK for the "
             "real robot under COMPILE_WITH_REAL_ROBOT.", source="upstream_code",
             ref="unitree_guide2/src/main.cpp:68-76"),
        Fact("For ROBOT_TYPE_Go1 the IOSDK constructor builds its unitree_legged_sdk safety object as "
             "LeggedType::Aliengo and its UDP object with LOWLEVEL, 8090, 192.168.123.10 and 8007.",
             source="upstream_code",
             ref="unitree_guide2/src/interface/IOSDK.cpp:10-14"),
        Fact("navigation.launch.py starts Nav2's controller_server with cmd_vel remapped to cmd_vel.",
             source="upstream_code", ref="go1_sim/go1_navigation/launch/navigation.launch.py:118-127"),
        Fact("start_world.launch.py includes gazebo_ros's gazebo.launch.py.", source="upstream_code",
             ref="go1_sim/go1_gazebo/launch/start_world.launch.py:44-50"),
        Fact("junior_ctrl's main loop calls ControlFrame::run until SIGINT clears the running flag.",
             source="upstream_code", ref="unitree_guide2/src/main.cpp:106-110"),
        Fact("FSM::run exchanges commands and states, runs the estimator and the current state, and waits for the "
             "rest of its period on the system clock.", source="upstream_code",
             ref="unitree_guide2/src/FSM/FSM.cpp:38-66"),
        Fact("State_move_base is a State_Trotting whose checkChange goes to PASSIVE on L2_B and to FIXEDSTAND on "
             "L2_A.", source="upstream_code", ref="unitree_guide2/src/FSM/State_move_base.cpp:49-75"),
        Fact("The trotting state starts the gait wave when checkStepOrNot is true and sets all four legs to stance "
             "otherwise.", source="upstream_code", ref="unitree_guide2/src/FSM/State_Trotting.cpp:95-99"),
        Fact("checkStepOrNot is true when the commanded x or y velocity exceeds 0.03, a position error exceeds "
             "0.08, a velocity error exceeds 0.05 or the yaw-rate command exceeds 0.20.", source="upstream_code",
             ref="unitree_guide2/src/FSM/State_Trotting.cpp:115-127"),
        Fact("KeyBoard::checkCmd maps key 2 to UserCommand::L2_A (fixed stand).", source="upstream_code",
             ref="unitree_guide2/src/interface/KeyBoard.cpp:25-30"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused: two get_model_list answers 250 ms apart carried the same sim time, so no "
        "world update runs and gazebo_ros2_control writes no leg command; it is a frozen sim time, not a measured "
        "standstill. No unpause is offered: an operator puts junior_ctrl in fixed_stand (key 2) or stops it, then "
        "unpauses outside MHS."
    )
    #: The deployed fake is an event-driven rosbridge contract stand-in, not a
    #: recording of captured traffic and not a physics simulator.
    fidelity = {
        "engine": "analytic:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge fake with no physics step, ray sensor, state integration "
                     "or wall-clock pacing; placeholder observations do not establish trajectory or "
                     "state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in, not a recording of captured traffic: "
            "it runs no Gazebo physics, ray sensor, p3d ground-truth plugin, estimator node or ROS graph",
            "the /odom pose and orientation are placeholders; the /odom twist echoes the last published "
            "Twist only as a contract effect and is not an integrated motion state",
            "the fake returns three placeholder LaserScan ranges; the pinned ray plugin is configured "
            "for 450 samples over 0.0..6.28319 rad at 30 Hz (go1_sim/go1_description/xacro/robot.xacro:185-217)",
            "the /scan range values, scan_time and time_increment are placeholders, not ray-cast "
            "measurements or sensor timing",
            "the clone exposes no acknowledged ROS stop, pause or reset service or action, and a zero-Twist "
            "publication remains transmission-only; the stop is the companion gazebo_ros world pause, confirmed by "
            "the E1 stall read-back: the fake keeps a paused flag that /pause_physics sets and a sim-time stamp that "
            "/get_model_list reports and that advances on every answer unless paused; it runs no Gazebo World::Step",
            "a frozen get_model_list stamp is also what a hung but unpaused gzserver shows (nothing advances then "
            "either); a GUI step or a WorldControl multi_step between the two samples fails the check (fails "
            "closed); the e-stop declares estop_latency_ms 1500 because the pause (400 ms), two read-backs (300 ms "
            "each) and the 250 ms interval exceed the default 1000 ms budget",
            "no unpause is offered: a zero Twist clears move_base's stored velocity (State_move_base.cpp:81-85), "
            "but junior_ctrl's loop keeps running on the wall clock through the pause (main.cpp:106-110, "
            "FSM.cpp:38-66) on stale joint and IMU states, and the trotting state steps whenever an error exceeds "
            "its thresholds (State_Trotting.cpp:95-99, 115-127), so the stored command does not alone decide what "
            "the legs do on an unpause; the operator recovers outside MHS (junior_ctrl key 2 for fixed_stand or "
            "stopping junior_ctrl, then the Gazebo GUI play button or ros2 service call /unpause_physics)",
            "while paused, /odom (p3d plugin), /scan (ray sensor) and /clock come only from world updates, so they "
            "are silent and the odometry and scan reads fail NOT_READY after their timeouts (the fake silences them "
            "while its flag is set); the device resource reads no topic, so commands and resets do not wait for "
            "them, and the cmd_vel receipt reports the values it sent",
            "a live world can be unpaused or stepped by the Gazebo GUI, a WorldControl message or any ROS 2 client "
            "of /unpause_physics; MHS does not watch the sim time after the e-stop (safety_status re-reads it only "
            "on request)",
            "the deployment's gazebo_ros, gazebo_ros2_control and Gazebo must be the pinned 3.9.0, 0.4.12 and "
            "11.15.1 releases the companion citations name; rosbridge cannot read their versions",
            "the /cmd_vel interface acts only in move_base mode; the fake does not model the state "
            "machine and the driver has no ROS observation of the active FSM mode",
            "/tf, /imu_plugin/out, the twelve MotorCmd/MotorState controller topics and the internal "
            "state machine are not exposed by this package",
            "a live run requires the operator's ROS 2 Humble, Gazebo 11, go1_sim launch, junior_ctrl in "
            "move_base mode and rosbridge; none of them is started or validated here",
            "the bridge refuses non-finite numbers, so a scan whose ranges contain inf or NaN (for example a "
            "beam without a return) fails the read without output instead of being served as data",
            "/odom comes only from the p3d ground-truth plugin at 100 Hz: the estimator's publish call is "
            "commented out (Estimator.cpp:269)",
            "go1_navigation's navigation.launch.py starts Nav2's servers with cmd_vel remapped to cmd_vel "
            "(default robot_namespace empty, so /cmd_vel); Nav2's controller publishes velocity setpoints there "
            "while navigating and overrides this package's setpoints",
            "the clone also holds the real-robot UDP interface IOSDK (main.cpp:73-76, IOSDK.cpp:10-14), but "
            "the move_base /cmd_vel state is compiled only in simulation builds (CMakeLists.txt:17-19, 40-42, "
            "71-73) and the unitree_legged_sdk library it links is not in the clone",
        ],
    }

    # The device resource reads no topic: /odom is published from the world update, so it is silent while the e-stop
    # holds the world paused, and a resource that waited for it would fail NOT_READY after every reset and delay
    # every command by its timeout.  It stays an explicit read capability below.
    estop_latency_ms = 1500
    commands = {
        "x-cap.atharva-05.cmd_vel.v1": _CMD_VEL,
        "x-cap.atharva-05.scan.v1": _SCAN,
        "x-cap.atharva-05.odometry.v1": dict(_ODOM, path="$", timeout_ms=2000,
                                              result={"map": {"pose": "pose.pose", "twist": "twist.twist"}}),
    }
    actions = {
        "x-cap.atharva-05.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint to /cmd_vel for the move_base state "
                "machine. The receipt confirms only that rosbridge accepted the publication, not motion, "
                "arrival or stopping."
            ),
            input={
                "linear_x": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame forward velocity written to twist.linear.x",
                    limit=_LINEAR_X,
                ),
                "linear_y": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame lateral velocity written to twist.linear.y",
                    limit=_LINEAR_Y,
                ),
                "angular_z": Field(
                    "number",
                    unit="rad/s",
                    description="Body-frame yaw rate written to twist.angular.z",
                    limit=_ANGULAR_Z,
                ),
            },
            output={**_PUBLISHED,
                    "sent_linear_x": Field("number", unit="m/s", description="The linear.x handed to rosbridge (the "
                                                                              "transmitted request)"),
                    "sent_linear_y": Field("number", unit="m/s", description="The linear.y handed to rosbridge (the "
                                                                              "transmitted request)"),
                    "sent_angular_z": Field("number", unit="rad/s", description="The angular.z handed to rosbridge "
                                                                                 "(the transmitted request)")},
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0}],
        ),
        "x-cap.atharva-05.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one fresh nav_msgs/Odometry sample from /odom (silent, and NOT_READY, while the world "
                        "is paused)",
            output={"pose": _POSE, "twist": _TWIST},
        ),
        "x-cap.atharva-05.scan.v1": Action(
            name="read_scan",
            verb="read",
            description="Read one sensor_msgs/LaserScan sample from the absolute /scan topic",
            output=_SCAN_OUTPUT,
        ),
    }
    # The e-stop pauses the Gazebo world and confirms it by a sim time that no longer advances (companion gazebo_ros,
    # E1 stall read-back); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
