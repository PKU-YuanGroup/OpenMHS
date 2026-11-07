"""OpenMHS rosbridge driver for the multi-robot TurtleBot3 Gazebo/Nav stack.

The pinned repository is a ROS 1 Noetic / Gazebo 11 simulation collection.  It
ships a two-robot close-world launch (``tb3_0`` and ``tb3_1``), TurtleBot3
Burger robot descriptions, the TurtleBot3 navigation launch and a C++ drive
node.  This package is a configuration-only :class:`RosDriver` over rosbridge;
it declares no Python native class and does not launch Gazebo, move_base or
rosbridge.

The scope is the two simulated mobile bases' primary low-level motion input and
their laser/odometry observations:

* one ``geometry_msgs/Twist`` publication on ``/tb3_0/cmd_vel`` and one on
  ``/tb3_1/cmd_vel`` (the Gazebo differential-drive plugin command topics and
  the move_base remap targets);
* one ``sensor_msgs/LaserScan`` read on each ``/tb3_<n>/scan``;
* one ``nav_msgs/Odometry`` pose read on each ``/tb3_<n>/odom``.

A rosbridge publication only confirms that the client sent a message.  The
upstream differential-drive plugin and move_base publish no motion or
stopping acknowledgement on these topics, and the pinned clone does not
declare the move_base goal action type.  The velocity bounds are
operator-required because the clone's 0.3 m/s and 1.5 rad/s drive-node
constants are demo-loop constants, not a signed cmd_vel envelope.  The
declared risk is R2 (mobile-base transit): the command topics are the
relative ``cmd_vel`` topics of two mobile bases, which a real TurtleBot3
behind the same rosbridge would also consume, and a simulated label never
lowers the risk of such a binding (MHS-004 section 2.1).

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic) ``/gazebo/pause_physics``,
confirmed by reading ``/gazebo/get_physics_properties`` back until ``pause`` is
true, and ``/gazebo/unpause_physics`` as the declared re-enable after a reset
(CORE-086).  One pause stops both robots: the gazebo_ros differential-drive
plugin sets wheel velocities and publishes odometry only from the world
update.  It is the paused flag, not a measured standstill; any client or the
Gazebo GUI can unpause or step the world, and odometry and laser scans are
silent while it is paused, so they are explicit reads, not the device
resource.  The plugin keeps a stored command while paused: the resume first
publishes a zero ``Twist`` on both command topics (unacknowledged
publications) and then unpauses.

Every endpoint, type, bound and fact of the package's own surface cites the
pinned clone at afcc20c73158370f32cf123a0d73a698f9d02579; the stop, its
read-back, the re-enable and the facts about them cite the companions at
their pins.  The fake is a ROS-free contract transport; no ROS graph,
simulator or robot is contacted by this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The launch default names the resolved absolute command topic for tb3_0.
_TB3_0_CMD_VEL_REF = "turtlebot3/turtlebot3_navigation/launch/move_base1.launch:10"
#: The launch default names the resolved absolute command topic for tb3_1.
_TB3_1_CMD_VEL_REF = "turtlebot3/turtlebot3_navigation/launch/move_base2.launch:10"
#: The launch default names the resolved absolute laser topic for tb3_0.
_TB3_0_SCAN_REF = "turtlebot3/turtlebot3_navigation/launch/move_base1.launch:8"
#: The launch default names the resolved absolute laser topic for tb3_1.
_TB3_1_SCAN_REF = "turtlebot3/turtlebot3_navigation/launch/move_base2.launch:8"
#: The launch default names the resolved absolute odometry topic for tb3_0.
_TB3_0_ODOM_REF = "turtlebot3/turtlebot3_navigation/launch/move_base1.launch:11"
#: The launch default names the resolved absolute odometry topic for tb3_1.
_TB3_1_ODOM_REF = "turtlebot3/turtlebot3_navigation/launch/move_base2.launch:11"

#: The shipped C++ node includes geometry_msgs/Twist and advertises that type.
_TWIST_TYPE_REF = "turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:25"
#: The shipped C++ node includes sensor_msgs/LaserScan for its scan callback.
_LASERSCAN_TYPE_REF = "turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:24"
#: The shipped C++ node includes nav_msgs/Odometry for its odometry callback.
_ODOM_TYPE_REF = "turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:26"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.9.3 (ROS 1 Noetic) at cd9cc952: the API plugin serves the pause, its read-back and the unpause.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 11.15.1 at b22c6e15: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":492-498",
    "type_ref": _API + ":494",
    "state_ref": _API + ":1725-1729",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
}
#: The read-back that confirms it: get_physics_properties reports the paused flag (res.pause = IsPaused()).
_READBACK = {
    "service": "/gazebo/get_physics_properties",
    "type": "gazebo_msgs/GetPhysicsProperties",
    "source_name": "get_physics_properties",
    "source_ref": _API + ":383-389",
    "type_ref": _API + ":385",
    "state_ref": _API + ":1489",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}
#: The declared re-enable after a reset (CORE-086): unpause_physics clears the paused flag.
_RESUME = {
    "service": "/gazebo/unpause_physics",
    "type": "std_srvs/Empty",
    "source_name": "unpause_physics",
    "source_ref": _API + ":501-507",
    "type_ref": _API + ":503",
    "description": "Unpause the Gazebo world (gazebo_ros unpause_physics: World::SetPaused(false))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
    "result": {"acknowledged": {"value": True}},
}
#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the "
         "arguments already name it.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24"),
    Fact("empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the "
         "physics engine argument -e $(arg physics).", source="upstream_code", ref=_LAUNCH + ":46-48"),
    Fact("empty_world.launch defaults its physics argument to ode.", source="upstream_code", ref=_LAUNCH + ":15"),
    Fact("empty_world.launch defaults its gui argument to true.", source="upstream_code", ref=_LAUNCH + ":8"),
    Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
         source="upstream_code", ref=_LAUNCH + ":51-54"),
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":125-126"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":145"),
    Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
         "queue gazebo_queue_.", source="upstream_code", ref=_API + ":492-498"),
    Fact("The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_.",
         source="upstream_code", ref=_API + ":501-507"),
    Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
         "type on gazebo_queue_.", source="upstream_code", ref=_API + ":383-389"),
    Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is "
         "ok.", source="upstream_code", ref=_API + ":257-264"),
    Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
         ref=_API + ":1725-1729"),
    Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
         ref=_API + ":1731-1735"),
    Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1489"),
    Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
         "sets success false and returns false.", source="upstream_code", ref=_API + ":1496-1528"),
    Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the "
         "API plugin connects publishSimTime.", source="upstream_code", ref=_API + ":219-222"),
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
]
#: The gazebo_ros differential-drive plugin (companion gazebo_ros_pkgs) that the burger xacros load.
_DIFF_DRIVE = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp"
_DIFF_DRIVE_FACTS = [
    Fact("GazeboRosDiffDrive subscribes to its command topic with cmdVelCallback on the plugin's own callback "
         "queue.", source="upstream_code", ref=_DIFF_DRIVE + ":159-164"),
    Fact("GazeboRosDiffDrive connects UpdateChild to the world-update begin event.", source="upstream_code",
         ref=_DIFF_DRIVE + ":177-179"),
    Fact("When more than the update period of simulation time has passed, UpdateChild publishes odometry, reads the "
         "requested wheel speeds and sets the wheel joint velocities.", source="upstream_code",
         ref=_DIFF_DRIVE + ":269-289"),
    Fact("getWheelVelocities derives both wheel speeds from the stored x_ and rot_.", source="upstream_code",
         ref=_DIFF_DRIVE + ":324-333"),
    Fact("cmdVelCallback stores linear.x in x_ and angular.z in rot_.", source="upstream_code",
         ref=_DIFF_DRIVE + ":335-340"),
    Fact("QueueThread serves the plugin's callback queue with a 0.01 s wall-clock wait while the plugin is alive.",
         source="upstream_code", ref=_DIFF_DRIVE + ":342-349"),
]

#: The re-enable capability and the zero commands it publishes before the unpause (CORE-086).
_RESUME_ID = "x-cap.mortezaaliyari.resume.v1"
_CMD_VEL_IDS = ("x-cap.mortezaaliyari.tb3-0-cmd-vel.v1", "x-cap.mortezaaliyari.tb3-1-cmd-vel.v1")
_ZERO_TWIST = {"linear_velocity": 0.0, "angular_velocity": 0.0}

#: No source states a signed command envelope.  The drive node's compile-time
#: 0.3 m/s and 1.5 rad/s constants drive its own obstacle-avoidance loop; they
#: are not a bound on an arbitrary cmd_vel publication.
_LINEAR_LIMIT = Limit.operator_required(
    "the pinned clone gives only the drive node's compile-time 0.3 m/s demo forward speed, not a signed "
    "cmd_vel envelope; the operator supplies the site linear speed bound"
)
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned clone gives only the drive node's compile-time 1.5 rad/s demo turn rate, not a signed "
    "cmd_vel envelope; the operator supplies the site yaw-rate bound"
)

_CMD_VEL_OUTPUT = {
    "published": Field("boolean",
                       description="True when the driver handed the Twist message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
    "sent_linear_velocity": Field("number", unit="m/s", description="The linear.x handed to rosbridge (the "
                                                                     "transmitted request, not a measured speed)"),
    "sent_angular_velocity": Field("number", unit="rad/s", description="The angular.z handed to rosbridge (the "
                                                                        "transmitted request, not a measured rate)"),
}


def _odom_pose(robot: str) -> Field:
    return Field(
        "object",
        description=f"{robot} nav_msgs/Odometry pose.pose sample in the robot's odometry frame",
        properties={
            "position": Field(
                "object",
                description="Position in the odometry frame",
                properties={
                    "x": Field("number", unit="m", description="Position x"),
                    "y": Field("number", unit="m", description="Position y"),
                    "z": Field("number", unit="m", description="Position z"),
                },
            ),
            "orientation": Field(
                "object",
                description="Orientation as a unit quaternion",
                properties={
                    "x": Field("number", unit="1", description="Quaternion x"),
                    "y": Field("number", unit="1", description="Quaternion y"),
                    "z": Field("number", unit="1", description="Quaternion z"),
                    "w": Field("number", unit="1", description="Quaternion w"),
                },
            ),
        },
    )


def _scan_ranges(robot: str) -> Field:
    return Field(
        "array",
        unit="m",
        description=f"{robot} sensor_msgs/LaserScan ranges, one range per angular sample",
        items=Field("number", unit="m", description="Range in metres at one angular sample"),
        length=360,
    )


def _cmd_vel(robot: str, endpoint: str, source_ref: str) -> dict:
    return {
        "topic": endpoint,
        "type": "geometry_msgs/Twist",
        "operation": "publish",
        "source_name": endpoint,
        "source_ref": source_ref,
        "type_ref": _TWIST_TYPE_REF,
        "message": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        "args": {
            "linear.x": {"from": "input.linear_velocity"},
            "angular.z": {"from": "input.angular_velocity"},
        },
        "description": f"Publish one geometry_msgs/Twist setpoint to the {robot} command topic",
    }


def _cmd_vel_action(robot: str) -> Action:
    return Action(
        name=f"publish_{robot.replace('_', '')}_cmd_vel",
        verb="invoke",
        risk="R2",
        description=(
            f"Publish one geometry_msgs/Twist velocity setpoint to the {robot} Gazebo cmd_vel topic; the "
            "receipt confirms only that rosbridge accepted the publication, not motion, arrival or stopping"
        ),
        input={
            "linear_velocity": Field(
                "number",
                unit="m/s",
                description=f"Body-frame forward velocity for {robot}; the differential-drive plugin consumes linear.x",
                limit=_LINEAR_LIMIT,
            ),
            "angular_velocity": Field(
                "number",
                unit="rad/s",
                description=f"Body-frame yaw rate for {robot}; the differential-drive plugin consumes angular.z",
                limit=_ANGULAR_LIMIT,
            ),
        },
        output=_CMD_VEL_OUTPUT,
    )


#: The four explicit odometry and laser reads (silent while the world is paused, so not the device resource).
_TB3_0_ODOM_READ = {
    "topic": "/tb3_0/odom",
    "type": "nav_msgs/Odometry",
    "operation": "subscribe",
    "source_name": "/tb3_0/odom",
    "source_ref": _TB3_0_ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose"}},
    "timeout_ms": 2000,
}
_TB3_1_ODOM_READ = {
    "topic": "/tb3_1/odom",
    "type": "nav_msgs/Odometry",
    "operation": "subscribe",
    "source_name": "/tb3_1/odom",
    "source_ref": _TB3_1_ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose"}},
    "timeout_ms": 2000,
}
_TB3_0_SCAN_READ = {
    "topic": "/tb3_0/scan",
    "type": "sensor_msgs/LaserScan",
    "operation": "subscribe",
    "source_name": "/tb3_0/scan",
    "source_ref": _TB3_0_SCAN_REF,
    "type_ref": _LASERSCAN_TYPE_REF,
    "result": {"map": {"ranges": "output.ranges"}},
    "timeout_ms": 2000,
}
_TB3_1_SCAN_READ = {
    "topic": "/tb3_1/scan",
    "type": "sensor_msgs/LaserScan",
    "operation": "subscribe",
    "source_name": "/tb3_1/scan",
    "source_ref": _TB3_1_SCAN_REF,
    "type_ref": _LASERSCAN_TYPE_REF,
    "result": {"map": {"ranges": "output.ranges"}},
    "timeout_ms": 2000,
}


class _ZeroBeforeResume:
    """The declared re-enable (CORE-086) publishes a zero Twist on both command topics before it unpauses.

    The gazebo_ros differential-drive plugin stores the last cmd_vel and turns it into wheel velocities at every
    world update with no command timeout (companion gazebo_ros_diff_drive.cpp:269-289, 324-340), and its callbacks
    still run while the world is paused (342-349), so an unpause alone would resume a command stored before or
    during the pause (SAFE-042). The zeros replace them. They are topic publications: unacknowledged and handled on
    each plugin's own queue thread, so they are not confirmed before the world runs again. A failed zero
    publication fails the resume before the unpause is sent. A cmd_vel receipt also reports the two values it sent
    (the device resource reads no topic). Every other call goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        if capability_id in _CMD_VEL_IDS:
            output = dict(self._inner.call(capability_id, args, ctx))
            values = dict(args or {})
            output["sent_linear_velocity"] = float(values["linear_velocity"])
            output["sent_angular_velocity"] = float(values["angular_velocity"])
            return output
        if capability_id != _RESUME_ID:
            return self._inner.call(capability_id, args, ctx)
        zeroed = [bool(dict(self._inner.call(command, dict(_ZERO_TWIST), ctx) or {}).get("published"))
                  for command in _CMD_VEL_IDS]
        output = dict(self._inner.call(capability_id, args, ctx))
        output["zero_commands_published"] = all(zeroed)
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class MultiRobotGazeboNavistack(RosDriver):
    device_id = "turtlebot3-multi"
    device_kind = "world.sim"
    mode = "simulated"
    # The two commands drive mobile bases on relative cmd_vel topics that a real TurtleBot3 behind the same rosbridge
    # would also consume, so they are R2 (mobile-base transit) even though their effect here is confined to the
    # simulated world, as in the WPR and HECTOR packages.  The stop is the Gazebo world pause of the companion
    # gazebo_ros (task.json companions), read back.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeMultiTurtlebot3"}
    tags = ["ros", "ros1", "simulation", "gazebo", "turtlebot3", "multi-robot", "navigation", "cmd-vel"]
    display_name = "Multi-robot TurtleBot3 Gazebo/Nav stack"
    vendor = "mortezaaliyari"
    model = "TurtleBot3 Burger tb3_0 and tb3_1 in Gazebo 11"
    facts = [
        Fact("README.md states the project targets Ubuntu Focal, ROS Noetic and Gazebo 11.",
             source="vendor_doc", ref="README.md:11-14"),
        Fact("The closeworld2 launch includes gazebo_ros empty_world.launch with the closeworld2 world, "
             "paused=false and use_sim_time=true.",
             source="upstream_code",
             ref="turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:16-23"),
        Fact("The closeworld2 launch defaults first_tb3 to tb3_0 and second_tb3 to tb3_1.",
             source="upstream_code",
             ref="turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:3-4"),
        Fact("The closeworld2 launch opens a tb3_0 group and selects turtlebot3_burger1.urdf.xacro for it.",
             source="upstream_code",
             ref="turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:25-26"),
        Fact("The closeworld2 launch opens a tb3_1 group and selects turtlebot3_burger2.urdf.xacro for it.",
             source="upstream_code",
             ref="turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:41-42"),
        Fact("The burger1 Gazebo differential-drive plugin subscribes to the relative cmd_vel topic and "
             "publishes odometry on the relative odom topic.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_description/urdf/turtlebot3_burger1.gazebo.xacro:51-55"),
        Fact("The burger2 Gazebo differential-drive plugin subscribes to the relative cmd_vel topic and "
             "publishes odometry on the relative odom topic.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_description/urdf/turtlebot3_burger2.gazebo.xacro:51-55"),
        Fact("The burger1 laser sensor publishes scan at 5 Hz with 360 samples over 0 to 6.28319 rad and a "
             "range of 0.120 to 3.5 m.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_description/urdf/turtlebot3_burger1.gazebo.xacro:104-121"),
        Fact("The burger2 laser sensor publishes scan at 5 Hz with 360 samples over 0 to 6.28319 rad and a "
             "range of 0.120 to 3.5 m.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_description/urdf/turtlebot3_burger2.gazebo.xacro:104-121"),
        Fact("The shipped C++ drive-node header includes sensor_msgs/LaserScan, geometry_msgs/Twist and "
             "nav_msgs/Odometry.",
             source="upstream_code",
             ref="turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:22-26"),
        Fact("The drive node reads cmd_vel_topic_name, advertises geometry_msgs::Twist on it and subscribes "
             "to the relative scan and odom topics.",
             source="upstream_code",
             ref="turtlebot3_gazebo/src/turtlebot3_drive.cpp:42-57"),
        Fact("The drive node uses compile-time LINEAR_VELOCITY 0.3 and ANGULAR_VELOCITY 1.5 constants for its "
             "own obstacle-avoidance loop; the clone states no signed cmd_vel envelope for these topics.",
             source="upstream_code",
             ref="turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:35-36"),
        Fact("The navigation launch sets use_sim_time true and includes amcl1, amcl2, move_base1 and "
             "move_base2.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_navigation/launch/turtlebot3_navigation.launch:1-27"),
        Fact("move_base1 defaults cmd_vel_topic to /tb3_0/cmd_vel, odom_topic to /tb3_0/odom and laser_topic "
             "to /tb3_0/scan.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_navigation/launch/move_base1.launch:8-11"),
        Fact("move_base1 remaps its cmd_vel, odom and scan topics to those absolute tb3_0 topics.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_navigation/launch/move_base1.launch:33-35"),
        Fact("move_base2 defaults cmd_vel_topic to /tb3_1/cmd_vel, odom_topic to /tb3_1/odom and laser_topic "
             "to /tb3_1/scan.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_navigation/launch/move_base2.launch:8-11"),
        Fact("move_base2 remaps its cmd_vel, odom and scan topics to those absolute tb3_1 topics.",
             source="upstream_code",
             ref="turtlebot3/turtlebot3_navigation/launch/move_base2.launch:33-35"),
        Fact("The README tells the operator to set the RViz 2D Nav Goal topic to /tb3_1 or /tb3_2.",
             source="vendor_doc", ref="README.md:39-40"),
        *_COMPANION_FACTS,
        *_DIFF_DRIVE_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so "
        "neither robot's drive plugin sets wheel velocities and odom and scan are silent; it is the paused flag, "
        "not a measured standstill, it holds until the resume command, the Gazebo GUI or another client unpauses "
        "the world (a GUI step advances it), and each plugin keeps its stored cmd_vel, which the resume zeroes "
        "first without an acknowledgement."
    )
    #: The package only publishes cmd_vel and observes scan/odom.  The fake is a
    #: ROS-free contract transport: no physics, no simulator and no pacing.
    fidelity = {
        "engine": "analytic:ROS-free contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven handler fake with canned observations; no physics step, pacing or state-hash "
                     "replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free handler transport: it answers the declared cmd_vel, scan and odom endpoints "
            "and runs no Gazebo, physics, navigation stack or wall-clock loop",
            "the scan arrays are placeholder ranges; a deployed Gazebo laser publishes 360 samples at 5 Hz from "
            "0.120 to 3.5 m",
            "the odometry pose is updated by a placeholder increment per publication so the command has a "
            "visible state effect; it is not physics, integration time or a measured trajectory",
            "a publication receipt confirms rosbridge transmission only, not motion, arrival or stopping",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets, /gazebo/get_physics_properties reports and /gazebo/unpause_physics "
            "clears; it runs no Gazebo World::Step, and its GetPhysicsProperties numbers are placeholders",
            "while paused, a live Gazebo runs no world update or sensor update, so both odom topics, both scan "
            "topics and /clock are silent and a read fails NOT_READY after its 2 s timeout; the fake silences "
            "them while its flag is set; the four observations are explicit reads, not the device resource, so "
            "a reset device stays readable and a command never waits for a silent topic",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, "
            "by a WorldControl message or by any ROS client; MHS does not watch the flag after the e-stop",
            "the read-back needs the ODE engine (empty_world.launch's default): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held; a graph "
            "without gazebo_ros has neither service",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name; rosbridge cannot read their versions",
            "the resume publishes a zero Twist on both command topics before the unpause; they are unacknowledged "
            "and each plugin handles them on its own queue thread, so a stored command may act for a few world "
            "steps before it is replaced, and move_base1/2 or the drive node, when they run, publish new commands "
            "on the same topics at any time",
            "the move_base goal action, /clock, TF and the map server are outside scope because the pinned clone "
            "does not declare their message types",
        ],
    }

    #: The device resource reads no topic: odometry and laser scans are published only while the world runs, and
    #: a resource that waited for them would fail NOT_READY after every reset and delay every command by its
    #: timeout.  They are the four explicit read capabilities below.
    commands = {
        "x-cap.mortezaaliyari.tb3-0-cmd-vel.v1": _cmd_vel(
            "tb3_0", "/tb3_0/cmd_vel", _TB3_0_CMD_VEL_REF),
        "x-cap.mortezaaliyari.tb3-1-cmd-vel.v1": _cmd_vel(
            "tb3_1", "/tb3_1/cmd_vel", _TB3_1_CMD_VEL_REF),
        "x-cap.mortezaaliyari.tb3-0-odom.v1": _TB3_0_ODOM_READ,
        "x-cap.mortezaaliyari.tb3-0-scan.v1": _TB3_0_SCAN_READ,
        "x-cap.mortezaaliyari.tb3-1-odom.v1": _TB3_1_ODOM_READ,
        "x-cap.mortezaaliyari.tb3-1-scan.v1": _TB3_1_SCAN_READ,
        _RESUME_ID: _RESUME,
    }
    actions = {
        "x-cap.mortezaaliyari.tb3-0-cmd-vel.v1": _cmd_vel_action("tb3_0"),
        "x-cap.mortezaaliyari.tb3-1-cmd-vel.v1": _cmd_vel_action("tb3_1"),
        "x-cap.mortezaaliyari.tb3-0-odom.v1": Action(
            name="read_tb3_0_odom", verb="read",
            description="Read one fresh /tb3_0/odom sample; silent while the world is paused (NOT_READY)",
            output={"pose": _odom_pose("tb3_0")}),
        "x-cap.mortezaaliyari.tb3-0-scan.v1": Action(
            name="read_tb3_0_scan", verb="read",
            description="Read one fresh /tb3_0/scan sample; silent while the world is paused (NOT_READY)",
            output={"ranges": _scan_ranges("tb3_0")}),
        "x-cap.mortezaaliyari.tb3-1-odom.v1": Action(
            name="read_tb3_1_odom", verb="read",
            description="Read one fresh /tb3_1/odom sample; silent while the world is paused (NOT_READY)",
            output={"pose": _odom_pose("tb3_1")}),
        "x-cap.mortezaaliyari.tb3-1-scan.v1": Action(
            name="read_tb3_1_scan", verb="read",
            description="Read one fresh /tb3_1/scan sample; silent while the world is paused (NOT_READY)",
            output={"ranges": _scan_ranges("tb3_1")}),
        _RESUME_ID: Action(
            name="resume_simulation",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: publish a zero Twist on /tb3_0/cmd_vel and "
                "/tb3_1/cmd_vel, then unpause the Gazebo world with /gazebo/unpause_physics. Each differential-drive "
                "plugin keeps the last cmd_vel it stored and applies it as soon as the world runs; the zeros "
                "replace them, but they are unacknowledged publications, so a stored command can still act for a "
                "few world steps, and a running move_base publishes new ones."
            ),
            output={
                "acknowledged": Field("boolean", description="True once /gazebo/unpause_physics answered"),
                "zero_commands_published": Field(
                    "boolean", description="True when both zero Twists were handed to rosbridge before the "
                                           "unpause; transmissions, not confirmations"),
            },
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding: mhs.safety.reset releases the latch only; the declared resume is the new start (CORE-086).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _ZeroBeforeResume(super().make_bridge(native))
