"""OpenMHS rosbridge driver for the pinned linorobot2 ROS 2 Gazebo environment.

The upstream repository is a launch/description stack for 2WD, 4WD and mecanum
mobile robots.  It does not contain a Python device class and it does not start
the robot firmware; the executable interface in the clone is the ROS 2 topic
graph created by the Gazebo launch and its bridge:

* the gz-sim drive plugins consume ``/cmd_vel`` (``geometry_msgs/msg/Twist``)
  and publish raw wheel odometry on ``/odom/unfiltered``;
* ``linorobot2_gazebo`` bridges ``/clock``, ``/imu/data``, ``/joint_states`` and
  ``/scan`` from Gazebo into ROS 2;
* the only in-repo ROS node, ``command_timeout``, republishes a zero Twist on
  ``/cmd_vel`` after 0.2 s without a nonzero command and creates no service or
  action server.

The clone has no stop of its own.  The e-stop is the Gazebo world pause of the
simulator's own repository, cited as reviewed companion sources fetched at
pinned commits (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): gz-sim 8.15.0 (Harmonic) serves the WorldControl
service ``/world/turtlebot3_world/control``, and ros_gz 1.0.25 (Jazzy) bridges
it as ``ros_gz_interfaces/srv/ControlWorld``.  The reply of that request is
true for any request gz-sim queued, so it confirms nothing; the stop is
confirmed by a fresh-sample topic read-back (E2): after the request returned,
``WorldStatistics.paused`` on ``/world/turtlebot3_world/stats`` must be true in
two samples that arrived at least 40 ms apart, after a discarded first one,
within 600 ms.  Neither endpoint exists unless the operator runs ros_gz's
``parameter_bridge`` with the two arguments in ``operator_bridges`` (E3): the
clone's own bridge carries topics only.  Without them the e-stop fails closed.

The declared re-enable (CORE-086) publishes a zero Twist on ``/cmd_vel`` and then
unpauses the world: DiffDrive keeps the last Twist it received and applies it as
soon as the world runs, so the zero replaces it (unacknowledged), and the
clone's command_timeout node also publishes a zero Twist 0.2 s after the last
nonzero command, on the wall clock, paused or not.  The odometry, IMU and scan
left the device resource: a paused world does not publish them, and a reset
device must stay readable; they are explicit read capabilities, and the cmd_vel
receipt reports the values it sent.

Every endpoint of the package's own surface cites the pinned clone at
f6b0bd0350c4a9d6b815ef4bb5c701a1e5129711.  The fake transport is ROS-free; no
ROS graph, Gazebo process, sensor or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The ros_gz_bridge argument list names the absolute ROS endpoints and their
#: ROS 2 message types.  These cited lines are the wire declarations.
_CLOCK_REF = "linorobot2_gazebo/launch/gazebo.launch.py:140"
_CMD_VEL_REF = "linorobot2_gazebo/launch/gazebo.launch.py:141"
_ODOM_REF = "linorobot2_gazebo/launch/gazebo.launch.py:142"
_IMU_REF = "linorobot2_gazebo/launch/gazebo.launch.py:143"
_JOINT_STATES_REF = "linorobot2_gazebo/launch/gazebo.launch.py:144"
_SCAN_REF = "linorobot2_gazebo/launch/gazebo.launch.py:145"

#: The gz-sim DiffDrive system's own command/odometry topic names.
_DIFF_DRIVE_TOPIC_REF = "linorobot2_description/urdf/controllers/diff_drive.urdf.xacro:4-10"
_DIFF_DRIVE_RATE_REF = "linorobot2_description/urdf/controllers/diff_drive.urdf.xacro:16"

#: The command_timeout node: relative cmd_vel publisher/subscription and timer.
_COMMAND_TIMEOUT_REF = "linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:21-35"
_COMMAND_TIMEOUT_TIMER_REF = "linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:37-48"
_COMMAND_TIMEOUT_CALLBACK_REF = "linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:50-55"

#: The launch starts command_timeout unconditionally and remaps the EKF output.
_COMMAND_TIMEOUT_NODE_REF = "linorobot2_gazebo/launch/gazebo.launch.py:159-163"
_EKF_REMAP_REF = "linorobot2_gazebo/launch/gazebo.launch.py:174"
_ODOM_ARGUMENT_REF = "linorobot2_gazebo/launch/gazebo.launch.py:60-64"

#: The EKF consumes both raw odometry and IMU data.
_EKF_REF = "linorobot2_base/config/ekf.yaml:3-24"

#: Sensor declarations in the shared robot description.
_LASER_REF = "linorobot2_description/urdf/sensors/generic_laser.urdf.xacro:6-14"
_LASER_TOPIC_REF = "linorobot2_description/urdf/sensors/laser.urdf.xacro:47-53"
_IMU_SENSOR_REF = "linorobot2_description/urdf/sensors/imu.urdf.xacro:16-22"
_DEPTH_REF = "linorobot2_description/urdf/sensors/depth_sensor.urdf.xacro:56-69"
_CAMERA_BRIDGE_REF = "linorobot2_gazebo/launch/gazebo.launch.py:146-156"

#: The clone states that the microcontroller firmware lives in another repository.
_FIRMWARE_REF = "docs/base_controller.md:35"

#: The launch's default world and its SDF name: the world control endpoints name it.
_WORLD_ARGUMENT_REF = "linorobot2_gazebo/launch/gazebo.launch.py:66-69"
_WORLD_SDF_REF = "linorobot2_gazebo/worlds/turtlebot3_world.sdf:11"

# -- Companion sources (task.json companions with lock; user decision and authorisation of 2026-11-05) -----------
#: gz-sim 8.15.0 (Harmonic) at 446a4433, fetched under work/companions: the world runner, its control service and
#: its statistics, and the systems a paused world does not run.
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_DIFF = "companion:gz_sim/src/systems/diff_drive/DiffDrive.cc"
_MECANUM = "companion:gz_sim/src/systems/mecanum_drive/MecanumDrive.cc"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
_IMU_SYSTEM = "companion:gz_sim/src/systems/imu/Imu.cc"
#: ros_gz 1.0.25 (Jazzy) at b87d7523, fetched under work/companions: the bridge's service and message mappings.
_SRV = "companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp"
_SERVICE_FACTORY = "companion:ros_gz/ros_gz_bridge/src/service_factory.hpp"
_CONVERT = "companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp"
_BRIDGE_README = "companion:ros_gz/ros_gz_bridge/README.md"
_BRIDGE_CONFIG = "companion:ros_gz/ros_gz_bridge/src/bridge_config.cpp"
_FACTORY = "companion:ros_gz/ros_gz_bridge/src/factory.hpp"
_INTERFACES = "companion:ros_gz/ros_gz_interfaces"
#: gz-transport 13.6.0 at 35fef7ea, fetched under work/companions: the bridge's gz request (facts only).
_NODE_HH = "companion:gz_transport/include/gz/transport/Node.hh"

_WORLD = "/world/turtlebot3_world"
#: The e-stop: a WorldControl request with pause true; gz-sim queues it and applies it in the step loop.
_PAUSE = {
    "service": _WORLD + "/control",
    "type": "ros_gz_interfaces/srv/ControlWorld",
    "source_name": "control",
    "source_ref": _RUN + ":325",
    "type_ref": _SRV + ":43-52",
    "state_ref": _RUN + ":1443",
    "description": "Pause the Gazebo world (gz-sim WorldControl through ros_gz: SetPaused(true) in the step loop)",
    "request": {"world_control": {"pause": True}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 400,
}
#: The read-back that confirms it (E2): WorldStatistics.paused on the world's stats topic, in fresh samples.
_READBACK = {
    "topic": _WORLD + "/stats",
    "type": "ros_gz_interfaces/msg/WorldStatistics",
    "operation": "subscribe",
    "source_name": "stats",
    "source_ref": _RUN + ":807-808",
    "type_ref": _BRIDGE_README + ":52",
    "state_ref": _RUN + ":534",
    "description": "Read the world's paused flag from fresh statistics samples; the e-stop is confirmed only when two "
                   "samples that arrived after the request report paused true",
    "success": {"path": "paused", "equals": True},
    "fresh": {"after_request": True, "discard_first": True, "consecutive": 2, "within_ms": 600,
              "min_interval_ms": 40},
}
#: The declared re-enable after a reset (CORE-086): a WorldControl request with pause false.
_RESUME = {
    "service": _WORLD + "/control",
    "type": "ros_gz_interfaces/srv/ControlWorld",
    "source_name": "control",
    "source_ref": _RUN + ":325",
    "type_ref": _SRV + ":43-52",
    "description": "Unpause the Gazebo world (gz-sim WorldControl through ros_gz: SetPaused(false))",
    "request": {"world_control": {"pause": False}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 400,
    "result": {"acknowledged": {"value": True}},
}
_RESUME_ID = "x-cap.linorobot.resume.v1"
_CMD_VEL_ID = "x-cap.linorobot.cmd_vel.v1"
_ZERO_TWIST = {"linear_velocity": 0.0, "angular_velocity": 0.0}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("SimulationRunner composes its transport namespace as /world/ followed by the world name.",
         source="upstream_code", ref=_RUN + ":249"),
    Fact("SimulationRunner advertises the control service with OnWorldControl as its callback.",
         source="upstream_code", ref=_RUN + ":325"),
    Fact("OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState.",
         source="upstream_code", ref=_RUN + ":1321-1328"),
    Fact("OnWorldControlState appends the control to worldControls and sets the Boolean reply to true.",
         source="upstream_code", ref=_RUN + ":1375-1377"),
    Fact("ProcessWorldControl calls SetPaused with the pause flag of each queued control.",
         source="upstream_code", ref=_RUN + ":1440-1443"),
    Fact("A queued control with multi_step on a paused world adds the steps and unpauses the world so that stepping "
         "can occur.", source="upstream_code", ref=_RUN + ":1445-1452"),
    Fact("SetPaused stores the pause state in currentInfo.paused.", source="upstream_code", ref=_RUN + ":1290-1291"),
    Fact("Step publishes the world statistics.", source="upstream_code", ref=_RUN + ":1023-1024"),
    Fact("Step processes the world control messages.", source="upstream_code", ref=_RUN + ":1063-1064"),
    Fact("The Run loop calls Step on every iteration and counts a processed iteration only while not paused.",
         source="upstream_code", ref=_RUN + ":896-911"),
    Fact("The statistics publisher on the stats topic is limited to 10 messages per second.",
         source="upstream_code", ref=_RUN + ":806-808"),
    Fact("PublishStats copies currentInfo.paused into the WorldStatistics message.", source="upstream_code",
         ref=_RUN + ":534"),
    Fact("UpdateCurrentInfo advances the simulation time and the iteration count only while not paused.",
         source="upstream_code", ref=_RUN + ":423-429"),
    Fact("The Physics system steps the physics only when not paused.", source="upstream_code",
         ref=_PHYSICS + ":1047-1051"),
    Fact("DiffDrive's PreUpdate returns early while paused.", source="upstream_code", ref=_DIFF + ":451-453"),
    Fact("DiffDrive's PostUpdate returns early while paused.", source="upstream_code", ref=_DIFF + ":501-503"),
    Fact("DiffDrive's cmd_vel callback stores the received Twist as its target velocity while enabled.",
         source="upstream_code", ref=_DIFF + ":637-644"),
    Fact("MecanumDrive's cmd_vel callback stores the received Twist as its target velocity.",
         source="upstream_code", ref=_MECANUM + ":672-676"),
    Fact("The IMU system updates and publishes only when not paused.", source="upstream_code",
         ref=_IMU_SYSTEM + ":145-146"),
    Fact("The bridge maps ros_gz_interfaces/srv/ControlWorld to a gz.msgs.WorldControl request with a gz.msgs.Boolean "
         "reply.", source="upstream_code", ref=_SRV + ":42-52"),
    Fact("The ControlWorld response's success is the gz Boolean reply's data.", source="upstream_code",
         ref=_SRV + ":134-141"),
    Fact("For a failed gz request the ControlWorld response's success is false.", source="upstream_code",
         ref=_SRV + ":170-178"),
    Fact("The service bridge converts each ROS request and sends it with gz Request and a callback that sends the ROS "
         "response.", source="upstream_code", ref=_SERVICE_FACTORY + ":56-86"),
    Fact("Node::Request with a callback requests a service using a non-blocking call.", source="upstream_code",
         ref=_NODE_HH + ":662-677"),
    Fact("The WorldStatistics conversion copies the gz header into the ROS header and copies paused.",
         source="upstream_code", ref=_CONVERT + ":840-844"),
    Fact("ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag.",
         source="upstream_code", ref=_INTERFACES + "/msg/WorldStatistics.msg:1-14"),
    Fact("ControlWorld takes a WorldControl request and answers bool success.", source="upstream_code",
         ref=_INTERFACES + "/srv/ControlWorld.srv:1-3"),
    Fact("WorldControl's fields include pause, step and multi_step.", source="upstream_code",
         ref=_INTERFACES + "/msg/WorldControl.msg:1-3"),
    Fact("The bridge README maps ros_gz_interfaces/msg/WorldStatistics to gz.msgs.WorldStatistics.",
         source="vendor_doc", ref=_BRIDGE_README + ":52"),
    Fact("The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to gz.msgs.WorldControl and "
         "gz.msgs.Boolean.", source="vendor_doc", ref=_BRIDGE_README + ":86"),
    Fact("The bridge README's service example starts parameter_bridge with a /world/<name>/control ControlWorld "
         "argument.", source="vendor_doc", ref=_BRIDGE_README + ":261-265"),
    Fact("Without a configured QoS profile the bridge's publisher QoS is KeepLast with the publisher queue size.",
         source="upstream_code", ref=_BRIDGE_CONFIG + ":274-279"),
    Fact("The bridge's publisher allows its deadline, depth, durability, history, liveliness and reliability QoS to be "
         "overridden.", source="upstream_code", ref=_FACTORY + ":61-82"),
]


class _ZeroBeforeResume:
    """The declared re-enable (CORE-086) publishes a zero Twist on /cmd_vel before it unpauses the world.

    The receipt of a cmd_vel publication also reports the two components it handed to rosbridge (the transmitted
    request): the device resource reads no topic (a paused world publishes no odometry), so the receipt is where a
    caller sees what a publication sent.

    DiffDrive stores the last Twist it received (companion DiffDrive.cc:637-644; MecanumDrive.cc:672-676 for the
    mecanum base) and applies it as soon as the world runs, and the bridge forwards /cmd_vel while the world is
    paused, so an unpause alone would resume a command stored before or during the pause (SAFE-042). The zero replaces
    it. It is a topic publication: unacknowledged and handled by the bridge and the gz-transport callback, so it is not
    confirmed before the world runs again. A failed zero publication fails the resume before the unpause is sent.
    Every other call, the e-stop and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        if capability_id == _CMD_VEL_ID:
            return self._sent(self._inner.call(capability_id, args, ctx), args)
        if capability_id != _RESUME_ID:
            return self._inner.call(capability_id, args, ctx)
        published = self._inner.call(_CMD_VEL_ID, dict(_ZERO_TWIST), ctx)
        output = dict(self._inner.call(capability_id, args, ctx))
        output["zero_command_published"] = bool(dict(published or {}).get("published"))
        return output

    @staticmethod
    def _sent(output, args):
        output = dict(output)
        values = dict(args or {})
        for key in ("linear_velocity", "angular_velocity"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: No source states a site bound for a Twist component.  The joystick scales
#: and the Nav2 velocity smoother are client-side/navigation settings, not the
#: range the Gazebo drive plugins enforce; both bounds stay operator-owned.
_SPEED_LIMIT = Limit.operator_required(
    "the clone states no numeric bound for geometry_msgs/Twist.linear.x on /cmd_vel; the joystick "
    "scale and the Nav2 velocity smoother are client/navigation settings, not the drive plugins' "
    "accepted range, and the operator supplies the signed forward/reverse envelope"
)
_TURN_LIMIT = Limit.operator_required(
    "the clone states no numeric bound for geometry_msgs/Twist.angular.z on /cmd_vel; the joystick "
    "scale and the Nav2 velocity smoother are client/navigation settings, not the drive plugins' "
    "accepted range, and the operator supplies the signed yaw-rate envelope"
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
_CLOCK_TIME = Field(
    "object",
    description="rosgraph_msgs/Clock simulation time sample",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)
_IMU_ORIENTATION = Field(
    "object",
    description="sensor_msgs/Imu orientation quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)
_IMU_VECTOR = Field(
    "object",
    description="Three-component sensor_msgs/Imu vector",
    properties={
        "x": Field("number", description="Vector x"),
        "y": Field("number", description="Vector y"),
        "z": Field("number", description="Vector z"),
    },
)
_LASER_SCAN = {
    "angle_min": Field("number", unit="rad", description="Start angle of the scan"),
    "angle_max": Field("number", unit="rad", description="End angle of the scan"),
    "angle_increment": Field("number", unit="rad", description="Angular distance between measurements"),
    "range_min": Field("number", unit="m", description="Minimum measurable range"),
    "range_max": Field("number", unit="m", description="Maximum measurable range"),
    "frame_id": Field("string", description="Frame id from the message header"),
    "ranges": Field("array", unit="m", description="Range measurements; the fake returns a reduced placeholder "
                                                    "array", items=Field("number", unit="m")),
}
_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the ROS message to rosbridge"),
    "confirmed": Field("boolean", description="Always false: a rosbridge publication carries no execution "
                                               "confirmation"),
}

#: One explicit geometry_msgs/Twist publication.  The gz-sim drive plugins
#: consume cmd_vel; no motion, arrival or stopping acknowledgement is sent.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_ref": _CMD_VEL_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
}

#: The simulation clock is a non-latched topic observation.
_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "operation": "subscribe",
    "source_ref": _CLOCK_REF,
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

#: The raw wheel odometry published by the drive plugins (silent while the world is paused).
_ODOM = {
    "topic": "/odom/unfiltered",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_ref": _ODOM_REF,
    "path": "$",
    "timeout_ms": 2000,
    "result": {"map": {"pose": "pose.pose", "twist": "twist.twist"}},
}

#: The simulated IMU stream from the gz IMU system.
_IMU = {
    "topic": "/imu/data",
    "type": "sensor_msgs/msg/Imu",
    "operation": "subscribe",
    "source_ref": _IMU_REF,
    "path": "$",
    "result": {"map": {
        "orientation": "orientation",
        "angular_velocity": "angular_velocity",
        "linear_acceleration": "linear_acceleration",
    }},
}

#: The default 2D lidar stream.
_SCAN = {
    "topic": "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "operation": "subscribe",
    "source_ref": _SCAN_REF,
    "path": "$",
    "result": {"map": {
        "angle_min": "angle_min",
        "angle_max": "angle_max",
        "angle_increment": "angle_increment",
        "range_min": "range_min",
        "range_max": "range_max",
        "frame_id": "header.frame_id",
        "ranges": "ranges",
    }},
}


class Linorobot2(RosDriver):
    device_id = "linorobot2"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeLinorobot2"}
    tags = ["ros", "ros2", "gazebo", "simulation", "mobile-base", "cmd-vel", "odometry"]
    display_name = "linorobot2 Gazebo mobile-base environment"
    vendor = "linorobot"
    facts = [
        Fact("The Gazebo launch bridges /clock (rosgraph_msgs/Clock), /cmd_vel (geometry_msgs/Twist), "
             "/odom/unfiltered (nav_msgs/Odometry), /imu/data (sensor_msgs/Imu), /joint_states "
             "(sensor_msgs/JointState) and /scan (sensor_msgs/LaserScan) between ROS 2 and Gazebo.",
             source="upstream_code", ref="linorobot2_gazebo/launch/gazebo.launch.py:140-145"),
        Fact("diff_drive.urdf.xacro uses the gz-sim DiffDrive system with command topic cmd_vel and odometry "
             "topic odom/unfiltered.",
             source="upstream_code", ref=_DIFF_DRIVE_TOPIC_REF),
        Fact("skid_steer.urdf.xacro also uses the gz-sim DiffDrive system with command topic cmd_vel and "
             "odometry topic odom/unfiltered.",
             source="upstream_code",
             ref="linorobot2_description/urdf/controllers/skid_steer.urdf.xacro:4-10"),
        Fact("omni_drive.urdf.xacro uses the gz-sim MecanumDrive system with command topic cmd_vel and "
             "odometry topic odom/unfiltered.",
             source="upstream_code",
             ref="linorobot2_description/urdf/controllers/omni_drive.urdf.xacro:4-10"),
        Fact("The DiffDrive plugin is configured with an odom_publish_frequency of 50 Hz.",
             source="upstream_code", ref=_DIFF_DRIVE_RATE_REF),
        Fact("The command_timeout node creates a geometry_msgs/Twist publisher and subscription on the "
             "relative cmd_vel topic and a 0.2 s timer.",
             source="upstream_code", ref=_COMMAND_TIMEOUT_REF),
        Fact("When at least 2e8 ns have passed since prev_cmd_time_ and zero_cmd_sent_ is false, "
             "the command_timeout brake timer sets zero_cmd_sent_ and publishes one Twist with linear.x, "
             "linear.y and angular.z set to 0.0.",
             source="upstream_code", ref=_COMMAND_TIMEOUT_TIMER_REF),
        Fact("The command_timeout twist callback ignores an all-zero command and otherwise refreshes "
             "prev_cmd_time_ and clears zero_cmd_sent_.",
             source="upstream_code", ref=_COMMAND_TIMEOUT_CALLBACK_REF),
        Fact("The command_timeout node creates a publisher, a subscription and a timer only; it creates "
             "no ROS service or action server.",
             source="upstream_code", ref=_COMMAND_TIMEOUT_REF),
        Fact("The ros_gz_bridge parameter_bridge argument list contains topic bridges only; it declares no "
             "service or action bridge.",
             source="upstream_code", ref="linorobot2_gazebo/launch/gazebo.launch.py:136-157"),
        Fact("The Gazebo launch starts the command_timeout node unconditionally and passes it no parameters.",
             source="upstream_code", ref=_COMMAND_TIMEOUT_NODE_REF),
        Fact("The EKF consumes odom/unfiltered and imu/data and runs at 50 Hz.",
             source="upstream_code", ref=_EKF_REF),
        Fact("The generic laser publishes 360 rays at 10 Hz with a 0.08 m to 12.0 m range on the scan "
             "topic.",
             source="upstream_code", ref=_LASER_REF),
        Fact("The laser sensor writes the configured topic_name and update_rate into the Gazebo sensor "
             "topic and update_rate.",
             source="upstream_code", ref=_LASER_TOPIC_REF),
        Fact("The simulated IMU publishes on imu/data at 50 Hz.",
             source="upstream_code", ref=_IMU_SENSOR_REF),
        Fact("The RGBD camera sensor is a 640x480 R8G8B8 rgbd_camera publishing on the camera topic at 30 Hz.",
             source="upstream_code", ref=_DEPTH_REF),
        Fact("The camera bridge entries declare sensor_msgs/Image for the color and depth topics and remap "
             "them to /camera/color/image_raw and /camera/depth/image_rect_raw.",
             source="upstream_code", ref=_CAMERA_BRIDGE_REF),
        Fact("The documentation states that all firmware for the base microcontroller is maintained in the "
             "linorobot2_hardware repository.",
             source="vendor_doc", ref=_FIRMWARE_REF),
        Fact("The documentation states that the Gazebo plugins replace the microcontroller so the rest of "
             "the stack sees the same interface.",
             source="vendor_doc", ref="docs/base_controller.md:85-87"),
        Fact("The Gazebo launch declares the world_name argument with the default turtlebot3_world.",
             source="upstream_code", ref=_WORLD_ARGUMENT_REF),
        Fact("turtlebot3_world.sdf names its world turtlebot3_world.", source="upstream_code", ref=_WORLD_SDF_REF),
        Fact("playground.sdf names its world playground.", source="upstream_code",
             ref="linorobot2_gazebo/worlds/playground.sdf:11"),
        Fact("The docker gazebo service launches the world named by WORLD, playground by default.",
             source="vendor_doc", ref="docs/docker.md:322"),
        Fact("The Gazebo launch starts the gz-sim server with -r and -s, and a separate GUI client when gui is true.",
             source="upstream_code", ref="linorobot2_gazebo/launch/gazebo.launch.py:107-120"),
        Fact("The Nav2 collision monitor publishes its output on cmd_vel.", source="upstream_code",
             ref="linorobot2_navigation/config/navigation.yaml:302-303"),
        Fact("The README lists a Jazzy and a Lyrical branch.", source="vendor_doc", ref="README.md:8-9"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The world turtlebot3_world is paused: after the WorldControl pause two fresh stats samples, 40 ms or more "
        "apart within 600 ms, reported paused true, so the world does not step and the drive plugins apply no "
        "velocity; it is the paused flag in that window, not a measured standstill, it needs the operator-run ros_gz "
        "bridges, and the GUI, a WorldControl client or a step request can unpause or step the world."
    )
    fidelity = {
        "engine": "analytic:ROS-free contract fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned observations; the fake echoes the last commanded twist in raw "
                     "odometry as a placeholder and runs no physics; its world statistics follow the wall clock",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract stand-in, not a recording: it answers the declared subscribe, "
            "advertise, publish and service operations with canned placeholder values and runs no Gazebo, DiffDrive "
            "plugin, EKF, sensor, contact or physics",
            "the pose, twist, clock, IMU and LaserScan values are placeholders; the fake echoes the last "
            "commanded twist in /odom/unfiltered only so a publication has an observable contract effect, and "
            "does not integrate motion or claim a trajectory",
            "the real LaserScan has 360 rays (generic_laser.urdf.xacro:6-14); the fake returns a reduced "
            "placeholder array without a fixed length",
            "the camera image and point-cloud topics are declared by the bridge but not exposed; image capture "
            "is NOT COVERED by this package",
            "a live run requires the operator's Gazebo simulation, ros_gz_bridge, robot_localization EKF and "
            "the upstream launch; none of them is started or validated here",
            "the stop is the companion gz-sim world pause (WorldControl through ros_gz ControlWorld), whose reply is "
            "true for any request gz-sim queued (SimulationRunner.cc:1375-1377); it is confirmed by the E2 read-back: "
            "the fake keeps a paused flag that the control request sets after its next statistics sample and "
            "publishes /world/turtlebot3_world/stats every 100 ms (placeholder) while subscribed; it runs no "
            "SimulationRunner",
            "the e-stop endpoints exist only while the operator runs ros_gz's parameter_bridge with the two "
            "arguments of operator_bridges (the clone's bridge carries topics only, gazebo.launch.py:136-157); "
            "without them the control call is not answered and the read-back sees no sample, so the e-stop fails "
            "closed; the declared estop_latency_ms 1500 covers the control call (400 ms) and the read-back bound "
            "(600 ms)",
            "the read-back's freshness is the arrival time only: the bridged WorldStatistics header is the gz header, "
            "which PublishStats does not stamp (ros_gz convert copies it, ros_gz_interfaces.cpp:840); the bridge's "
            "default publisher QoS sets only KeepLast with the queue size (bridge_config.cpp:274-279), so its "
            "durability stays rclcpp's default, volatile, which replays no history to a late subscriber; the first "
            "sample is discarded and a burst of samples restarts the count; "
            "an operator QoS override of the stats publisher (factory.hpp:61-82) to a deeper transient-local "
            "history is not covered beyond that burst rule",
            "the endpoints name the launch's default world turtlebot3_world (gazebo.launch.py:66-69, "
            "turtlebot3_world.sdf:11); the docker gazebo service defaults to the playground world "
            "(docs/docker.md:322), and with any other world the declared endpoints do not exist and the e-stop "
            "fails closed",
            "a live world can be unpaused or stepped by the Gazebo GUI that the launch starts with gui true "
            "(gazebo.launch.py:114-120), a WorldControl multi_step (SimulationRunner.cc:1445-1452) or any client of "
            "the control service; MHS does not watch the flag after the e-stop (safety_status re-reads it only on "
            "request)",
            "while paused, DiffDrive does not publish /odom/unfiltered (DiffDrive.cc:501-503) and the IMU system does "
            "not publish /imu/data (Imu.cc:145-146), and sensors update on simulation time, which a paused world does "
            "not advance (SimulationRunner.cc:423-429); the fake silences the three while paused, their reads fail "
            "NOT_READY after their timeouts, and the device resource reads no topic; /clock keeps the frozen time",
            "the resume publishes a zero Twist before the unpause: DiffDrive keeps the last Twist (DiffDrive.cc:"
            "637-644) and the bridge forwards /cmd_vel while paused; the zero is unacknowledged, and command_timeout "
            "also publishes one zero Twist 0.2 s after the last nonzero command on the wall clock "
            "(command_timeout.py:37-48; launched without use_sim_time, gazebo.launch.py:159-163); Nav2's collision "
            "monitor and the joystick teleop may publish new commands; the world resumes from the state it paused "
            "in, body velocities included",
            "the deployment's gz-sim, ros_gz and gz-transport must be the pinned 8.15.0, 1.0.25 and 13.6.0 releases "
            "(ROS 2 Jazzy with Gazebo Harmonic); the README also lists a Lyrical branch (README.md:9), which this "
            "package does not serve; rosbridge cannot read the versions",
            "the clone also ships the physical robot's bringup: linorobot2_bringup starts micro_ros_agent on "
            "the base serial port /dev/ttyACM0 by default (default_robot.launch.py:35-64) and can start a "
            "joystick teleop (bringup.launch.py:29-30, 101-105), and the documentation says Gazebo preserves "
            "the microcontroller's interface (docs/base_controller.md:85-87); the same /cmd_vel publication "
            "would move a real base if the endpoint is a hardware graph, where no world exists and the e-stop "
            "fails closed",
        ],
    }

    # The device resource reads no topic: /odom/unfiltered, /imu/data and /scan are published from world updates, so
    # they are silent while the e-stop holds the world paused; a resource that waited for them would fail NOT_READY
    # after every reset and delay every command by its timeout.  They stay explicit read capabilities below.
    estop_latency_ms = 1500
    commands = {
        _CMD_VEL_ID: _CMD_VEL,
        "x-cap.linorobot.odometry.v1": _ODOM,
        "x-cap.linorobot.clock.v1": _CLOCK,
        "x-cap.linorobot.imu.v1": _IMU,
        "x-cap.linorobot.scan.v1": _SCAN,
        _RESUME_ID: _RESUME,
    }
    actions = {
        _CMD_VEL_ID: Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint to /cmd_vel for the gz-sim DiffDrive "
                "plugin. The receipt confirms only that rosbridge accepted the publication, not motion, "
                "arrival or stopping."
            ),
            input={
                "linear_velocity": Field(
                    "number", unit="m/s",
                    description="Body-frame forward velocity written to twist.linear.x",
                    limit=_SPEED_LIMIT,
                ),
                "angular_velocity": Field(
                    "number", unit="rad/s",
                    description="Body-frame yaw rate written to twist.angular.z",
                    limit=_TURN_LIMIT,
                ),
            },
            output={**_PUBLISHED,
                    "sent_linear_velocity": Field("number", unit="m/s", description="The linear.x handed to rosbridge "
                                                                                    "(the transmitted request)"),
                    "sent_angular_velocity": Field("number", unit="rad/s", description="The angular.z handed to "
                                                                                       "rosbridge (the transmitted "
                                                                                       "request)")},
            examples=[{"linear_velocity": 0.0, "angular_velocity": 0.0}],
        ),
        "x-cap.linorobot.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one fresh nav_msgs/Odometry sample from /odom/unfiltered (silent, and NOT_READY, while "
                        "the world is paused)",
            output={"pose": _POSE, "twist": _TWIST},
        ),
        "x-cap.linorobot.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one rosgraph_msgs/Clock sample from the bridged /clock topic",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.linorobot.imu.v1": Action(
            name="read_imu",
            verb="read",
            description="Read one sensor_msgs/Imu sample from the bridged /imu/data topic (silent while paused)",
            output={
                "orientation": _IMU_ORIENTATION,
                "angular_velocity": _IMU_VECTOR,
                "linear_acceleration": _IMU_VECTOR,
            },
        ),
        "x-cap.linorobot.scan.v1": Action(
            name="read_laser_scan",
            verb="read",
            description="Read one sensor_msgs/LaserScan sample from the bridged /scan topic (silent while paused)",
            output=_LASER_SCAN,
        ),
        _RESUME_ID: Action(
            name="resume_simulation",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: publish a zero Twist on /cmd_vel, then unpause the "
                "world with a WorldControl request (pause false) on /world/turtlebot3_world/control. DiffDrive keeps "
                "the last Twist it received and applies it as soon as the world runs; the zero replaces it, but it is "
                "an unacknowledged publication, so a stored command can still act for a few world steps."
            ),
            output={
                "acknowledged": Field("boolean", description="True once the world control request answered success"),
                "zero_command_published": Field(
                    "boolean", description="True when the zero Twist was handed to rosbridge before the unpause; "
                                           "a transmission, not a confirmation"),
            },
        ),
    }
    #: E3: the bridges the operator runs (ros_gz parameter_bridge, one argument each); the package never starts them.
    operator_bridges = [
        {"args": "/world/turtlebot3_world/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE_README + ":86",
         "description": "The world control service: the e-stop pause and the resume."},
        {"args": "/world/turtlebot3_world/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":52",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    # The e-stop pauses the world and confirms it by the paused flag in fresh statistics samples (companion gz-sim
    # and ros_gz, E2); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding: mhs.safety.reset releases the latch only; the declared resume is the new start (CORE-086).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _ZeroBeforeResume(super().make_bridge(native))
