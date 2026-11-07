"""OpenMHS rosbridge driver for the Coppolam ROS MAV swarm simulator (uav1).

The pinned repository is a ROS 1 catkin workspace: a C++ ``mav_controller``
swarm node plus a vendored hector_quadrotor Gazebo stack.  This package is a
configuration-only :class:`~mhs.driver.RosDriver` over rosbridge.  It declares
no Python native class, does not launch Gazebo or the upstream nodes, and
neither imports nor runs the clone.

Scope, for the first UAV (``uav1``):

* an explicit ``nav_msgs/Odometry`` read on ``/uav1/ground_truth/state`` (not a
  resource read: the p3d plugin publishes it from the world update, so it is
  silent while the world is paused);
* one bounded ``geometry_msgs/Twist`` publication on ``/uav1/cmd_vel``, the
  velocity channel that the repo's ``behaviour`` node also uses; the receipt
  reports the values sent;
* the acknowledged ``hector_uav_msgs/EnableMotors`` service on
  ``/uav1/enable_motors`` as an ordinary command;
* the ``hector_uav_msgs/LandingAction`` action on ``/uav1/action/landing`` as
  an ordinary command.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source fetched at a pinned commit (user decision and
authorisation of 2026-11-05; ``task.json`` ``companions`` with ``lock``):
gazebo_ros 2.8.7 (ROS Melodic) ``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true.  Gazebo 9.19.0
is cited for what a paused world does not run.  The pause is the paused flag,
not a measured standstill.  No unpause is offered: the velocity controller
keeps the last ``cmd_vel`` and the behaviour node publishes again when
simulation time resumes, and this package cannot clear that command first
(SAFE-042).  The landing action is not a stop.  No physical e-stop, no
hardware run and no live ROS graph is claimed here.

Every endpoint, type and Fact cites the pinned clone at
``eca05eaaecc05242493b176f2f2656f21b14c250``.  The fake transport is ROS-free;
all of its state values are placeholders, not device facts.  The workspace is
a single-UAV scope; the clone's three-UAV and ten-UAV launches, the autonomous
``behaviour`` node and the swarm coordination are not covered.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_BEHAVIOUR = "src/mav_controller/src/behaviour.cpp"
_VELOCITY = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/src/"
             "velocity_controller.cpp")
_CONTROLLER_YAML = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/params/"
                    "controller.yaml")
_CONTROLLER_PARAMS = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/params/"
                      "params.yaml")
_LIMITERS = ("src/hector/hector_quadrotor/hector_quadrotor_interface/include/"
             "hector_quadrotor_interface/limiters.h")
_SPAWN = ("src/hector/hector_quadrotor/hector_quadrotor_gazebo/launch/"
          "spawn_quadrotor.launch")
_SENSORS = ("src/hector/hector_quadrotor/hector_quadrotor_gazebo/urdf/"
            "quadrotor_sensors.gazebo.xacro")
_STATETRACKER = "src/mav_controller/src/trackers/statetracker.h"
_ACTIONS_LAUNCH = ("src/hector/hector_quadrotor/hector_quadrotor_actions/launch/"
                   "actions.launch")
_LANDING = ("src/hector/hector_quadrotor/hector_quadrotor_actions/src/"
            "landing_action.cpp")
_LANDING_ACTION = ("src/hector/hector_quadrotor/hector_uav_msgs/action/"
                   "Landing.action")
_BASE_ACTION = ("src/hector/hector_quadrotor/hector_quadrotor_actions/include/"
                "hector_quadrotor_actions/base_action.h")
_HARDWARE = ("src/hector/hector_quadrotor/hector_quadrotor_controller_gazebo/src/"
             "quadrotor_hardware_gazebo.cpp")
_HARDWARE_H = ("src/hector/hector_quadrotor/hector_quadrotor_controller_gazebo/include/"
               "hector_quadrotor_controller_gazebo/quadrotor_hardware_gazebo.h")
_CONTROLLER_LAUNCH = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/launch/"
                      "controller.launch")
_ATTITUDE = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/src/"
             "attitude_controller.cpp")
_THREE_MAVS = "src/mav_controller/launch/3mavs.launch"
_POSITION = ("src/hector/hector_quadrotor/hector_quadrotor_controllers/src/"
             "position_controller.cpp")
_POSE_ACTION = ("src/hector/hector_quadrotor/hector_quadrotor_actions/src/"
                "pose_action.cpp")
_TAKEOFF = ("src/hector/hector_quadrotor/hector_quadrotor_actions/src/"
            "takeoff_action.cpp")
_NORMAL_LAUNCH = "src/mav_controller/worlds/normal.launch"
_NORMAL_WORLD = "src/mav_controller/worlds/normal.world"
_XACRO = ("src/hector/hector_quadrotor/hector_quadrotor_gazebo/urdf/"
          "quadrotor_controller.gazebo.xacro")

# -- Companion sources (task.json companions; user decision 2026-11-05) ------
#: gazebo_ros 2.8.7 (ROS Melodic) at 0667c5e5, fetched under work/companions.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
_P3D = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_p3d.cpp"
#: Gazebo classic 9.19.0 at e4400ae7, fetched under work/companions.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":462-468",
    "type_ref": _API + ":464",
    "state_ref": _API + ":1662-1666",
    "description": "Pause the Gazebo world (gazebo_ros pause_physics: World::SetPaused(true))",
    "request": {},
    "success": {"path": "$", "equals": {}},
    "timeout_ms": 500,
}
#: The read-back that confirms it: get_physics_properties reports the paused flag.
_READBACK = {
    "service": "/gazebo/get_physics_properties",
    "type": "gazebo_msgs/GetPhysicsProperties",
    "source_name": "get_physics_properties",
    "source_ref": _API + ":364-370",
    "type_ref": _API + ":366",
    "state_ref": _API + ":1426",
    "description": "Read the world's paused flag back; the e-stop is confirmed only when pause is true",
    "request": {},
    "success": {"path": "pause", "equals": True},
    "timeout_ms": 500,
}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the "
         "arguments already name it.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24"),
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":127-128"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":147"),
    Fact("The API plugin starts a ros::AsyncSpinner.", source="upstream_code", ref=_API + ":149-151"),
    Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
         "queue gazebo_queue_.", source="upstream_code", ref=_API + ":462-468"),
    Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
         "type on gazebo_queue_.", source="upstream_code", ref=_API + ":364-370"),
    Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is "
         "ok.", source="upstream_code", ref=_API + ":235-242"),
    Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
         ref=_API + ":1662-1666"),
    Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
         ref=_API + ":1668-1672"),
    Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1426"),
    Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
         "sets success false and returns false.", source="upstream_code", ref=_API + ":1433-1465"),
    Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the "
         "API plugin connects publishSimTime.", source="upstream_code", ref=_API + ":224-227"),
    Fact("gazebo_ros_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS_CONTROL + ":196-199"),
    Fact("gazebo_ros_control's Update reads the simulation time, updates the controllers and calls writeSim.",
         source="upstream_code", ref=_ROS_CONTROL + ":211-257"),
    Fact("GazeboRosP3D connects UpdateChild to the world-update begin event.", source="upstream_code",
         ref=_P3D + ":207-208"),
    Fact("GazeboRosP3D::UpdateChild pushes pose_msg_ onto its publish queue.", source="upstream_code",
         ref=_P3D + ":350-351"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":691-710"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":683"),
    Fact("World::SetPaused stores the paused flag under worldUpdateMutex.", source="upstream_code",
         ref=_WORLD + ":1428-1436"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1422-1425"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":776-782"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":691-718"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1462-1477"),
]

_CMD_VEL_ID = "x-cap.coppolam.cmd_vel.v1"


class _SentReceipt:
    """The cmd_vel receipt also reports the twist components handed to rosbridge.

    The device resource reads no topic (a paused world publishes none), so the receipt is where a caller sees what
    a publication sent. The four numbers are the transmitted request, not a measurement. Every other call, the
    e-stop and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _CMD_VEL_ID:
            return output
        payload = dict(args or {})
        output = dict(output)
        output["sent_linear_x"] = float(payload["linear_x"])
        output["sent_linear_y"] = float(payload["linear_y"])
        output["sent_linear_z"] = float(payload["linear_z"])
        output["sent_angular_z"] = float(payload["angular_z"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)

# ---------------------------------------------------------------------------
# Units, limits and fixed payloads
# ---------------------------------------------------------------------------

#: No source states a command envelope.  controller.yaml:18 is a combined xy
#: magnitude (Vector3Limiter scales x, y and z when it is exceeded), 27-28 and
#: 44-45 are clamps whose negative side FieldLimiter derives in code, and the
#: 3.14 yawrate clamp belongs to the attitude controller, not to cmd_vel.
_LINEAR_X = Limit.operator_required(
    "no per-axis x envelope is stated; controller.yaml max_xy 10.0 limits the xy magnitude")
_LINEAR_Y = Limit.operator_required(
    "no per-axis y envelope is stated; controller.yaml max_xy 10.0 limits the xy magnitude")
_LINEAR_Z = Limit.operator_required(
    "no z envelope is stated; the velocity controller clamps z at max 5.0 and derives -max")
_ANGULAR_Z = Limit.operator_required(
    "no yaw-rate envelope is stated; the attitude controller clamps the yawrate at 3.14")

_VEC_M = Field(
    "object",
    description="A Cartesian vector in metres",
    properties={
        "x": Field("number", unit="m", description="x component"),
        "y": Field("number", unit="m", description="y component"),
        "z": Field("number", unit="m", description="z component"),
    },
)
_VEC_MPS = Field(
    "object",
    description="A Cartesian velocity vector in metres per second",
    properties={
        "x": Field("number", unit="m/s", description="x component"),
        "y": Field("number", unit="m/s", description="y component"),
        "z": Field("number", unit="m/s", description="z component"),
    },
)
_VEC_RPS = Field(
    "object",
    description="A Cartesian angular-velocity vector in radians per second",
    properties={
        "x": Field("number", unit="rad/s", description="x component"),
        "y": Field("number", unit="rad/s", description="y component"),
        "z": Field("number", unit="rad/s", description="z component"),
    },
)
_QUATERNION = Field(
    "object",
    description="A unit quaternion (dimensionless)",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
        "w": Field("number", unit="1", description="w component"),
    },
)
_POSE = Field(
    "object",
    description="A position and orientation",
    properties={
        "position": _VEC_M,
        "orientation": _QUATERNION,
    },
)
_TWIST = Field(
    "object",
    description="A linear and angular velocity",
    properties={
        "linear": _VEC_MPS,
        "angular": _VEC_RPS,
    },
)
_ODOMETRY_OUTPUT = {
    "frame_id": Field("string", description="The Odometry header frame_id"),
    "pose": _POSE,
    "twist": _TWIST,
}
_PUBLISHED_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication has no execution acknowledgement"),
    "sent_linear_x": Field("number", unit="m/s",
                           description="The linear.x value handed to rosbridge (the transmitted request, not a "
                                       "measured velocity)"),
    "sent_linear_y": Field("number", unit="m/s",
                           description="The linear.y value handed to rosbridge (the transmitted request, not a "
                                       "measured velocity)"),
    "sent_linear_z": Field("number", unit="m/s",
                           description="The linear.z value handed to rosbridge (the transmitted request, not a "
                                       "measured velocity)"),
    "sent_angular_z": Field("number", unit="rad/s",
                            description="The angular.z value handed to rosbridge (the transmitted request, not a "
                                        "measured yaw rate)"),
}
_ARM_OUTPUT = {
    "success": Field("boolean", description="The EnableMotors response success flag"),
}
_LAND_OUTPUT = {
    "landed": Field("boolean",
                    description="True when the landing action reached its succeeded terminal state"),
}

#: An ordinary landing command, not a stop: an empty landing_zone means "land
#: below the current pose", and the pose action it calls re-enables the motors
#: first (pose_action.cpp:56-58).
_LANDING_BINDING = {
    "action": "/uav1/action/landing",
    "type": "hector_uav_msgs/LandingAction",
    "profile": "ros1-actionlib",
    "source_name": "action/landing",
    "source_ref": f"{_LANDING}:42-43",
    "type_ref": f"{_LANDING}:83-84",
    "request": {"landing_zone": {"header": {"frame_id": ""}}},
    "success": {"path": "$", "equals": {}},
    "result": {"landed": {"value": True}},
    "timeout_ms": 34000,
    "description": "Land below the current pose and disable motors through the landing action (not a stop)",
}

#: The velocity controller subscribes the relative cmd_vel topic with
#: geometry_msgs/Twist and interprets it in the base_stabilized frame.
_CMD_VEL = {
    "topic": "/uav1/cmd_vel",
    "type": "geometry_msgs/Twist",
    "source_name": "cmd_vel",
    "source_ref": f"{_VELOCITY}:101-105",
    "operation": "publish",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},   # placeholder
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "linear.z": {"from": "input.linear_z"},
        "angular.z": {"from": "input.angular_z"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
    "description": "Publish one geometry_msgs/Twist velocity command; transmission only",
}

#: The hardware sim advertises the relative enable_motors service.
_ARM = {
    "service": "/uav1/enable_motors",
    "type": "hector_uav_msgs/EnableMotors",
    "source_name": "enable_motors",
    "source_ref": f"{_HARDWARE}:108",
    "type_ref": f"{_HARDWARE_H}:40-42",
    "request": {"enable": True},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success"}},
    "description": "Send the fixed EnableMotors enable=true request; success is the response flag",
}

#: The p3d plugin publishes nav_msgs/Odometry on the relative ground_truth/state
#: topic; the launch also gives message_to_tf that relative name.
_ODOMETRY = {
    "topic": "/uav1/ground_truth/state",
    "type": "nav_msgs/Odometry",
    "source_name": "ground_truth/state",
    "source_ref": f"{_SPAWN}:39-40",
    "type_ref": f"{_STATETRACKER}:15-17",
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "frame_id": "header.frame_id",
        "pose": "pose.pose",
        "twist": "twist.twist",
    }},
    "description": "Read one nav_msgs/Odometry sample from the uav1 ground-truth publisher",
}

class MavSwarm(RosDriver):
    device_id = "mav-swarm"
    device_kind = "world.sim"
    mode = "simulated"
    #: A velocity channel that flies a simulated multirotor is a mobile-base
    #: motion source even without attached hardware; the card floor is R0.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeMavSwarm"}
    tags = ["ros", "ros1", "simulation", "gazebo", "hector-quadrotor", "uav", "swarm", "cmd-vel", "stop"]
    display_name = "Coppolam ROS MAV swarm simulator (uav1)"
    vendor = "coppolam"
    model = "mav_controller behavior node and hector_quadrotor Gazebo stack"
    facts = [
        Fact("The behaviour node derives name as the literal uav concatenated with the id parameter, "
             "builds cmdtopic as '/' + name + '/cmd_vel' and advertises geometry_msgs/Twist on it.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:400-413"),
        Fact("The behaviour node builds its own state topic as '/' + name + '/ground_truth/state' and "
             "subscribes to it with the statetracker callback.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:416-420"),
        Fact("The velocity controller subscribes the relative command/twist topic with "
             "geometry_msgs/TwistStamped and the relative cmd_vel topic with geometry_msgs/Twist.",
             source="upstream_code", ref=f"{_VELOCITY}:101-105"),
        Fact("The cmd_vel callback stores the received Twist, stamps it with the current ROS time and "
             "sets its header frame_id to base_stabilized_frame_.",
             source="upstream_code", ref=f"{_VELOCITY}:161-171"),
        Fact("The velocity controller transforms base_stabilized linear x and y into the world frame "
             "using the current yaw, while linear z passes through unchanged.",
             source="upstream_code", ref=f"{_VELOCITY}:216-224"),
        Fact("The velocity controller uses command.angular.z as the yaw-rate command and ignores "
             "angular.x and angular.y in its control update.",
             source="upstream_code", ref=f"{_VELOCITY}:256-262"),
        Fact("The velocity controller initializes its linear limiter with the controller node handle "
             "and its angular limiter with the yawrate field.",
             source="upstream_code", ref=f"{_VELOCITY}:92-93"),
        Fact("FieldLimiter starts unbounded; when its max or min parameter exists it reads max "
             "(default infinity) and min (default -max).",
             source="upstream_code", ref=f"{_LIMITERS}:52-62"),
        Fact("Vector3Limiter::limit clamps each axis, then scales x, y and z together when the xy "
             "magnitude exceeds max_xy and again when the full magnitude exceeds max.",
             source="upstream_code", ref=f"{_LIMITERS}:121-143"),
        Fact("Vector3Limiter initializes x, y and z FieldLimiters and reads max and max_xy from its "
             "node handle.",
             source="upstream_code", ref=f"{_LIMITERS}:108-119"),
        Fact("The shipped controller YAML sets velocity max_xy 10.0 and velocity z max 5.0 (both "
             "commented m/s) and, in the attitude section, yawrate max 3.14.",
             source="upstream_code", ref=f"{_CONTROLLER_YAML}:16-45"),
        Fact("The 3mavs launch runs the uav1 spawn and behaviour node inside the uav1 group namespace "
             "with id 1.",
             source="upstream_code", ref=f"{_THREE_MAVS}:13-24"),
        Fact("The p3d ground-truth plugin is named quadrotor_groundtruth_sim, uses "
             "libgazebo_ros_p3d.so, publishes topicName ground_truth/state at updateRate 100.0 and "
             "sets gaussianNoise 0.0.",
             source="upstream_code", ref=f"{_SENSORS}:56-61"),
        Fact("The statetracker header includes nav_msgs/Odometry.h and declares its callback with a "
             "nav_msgs::Odometry ConstPtr.",
             source="upstream_code", ref=f"{_STATETRACKER}:17-53"),
        Fact("The spawn launch passes the relative ground_truth/state name to the message_to_tf "
             "odometry_topic parameter.",
             source="upstream_code", ref=f"{_SPAWN}:38-40"),
        Fact("The actions launch starts the pose_action, landing_action and takeoff_action nodes.",
             source="upstream_code", ref=f"{_ACTIONS_LAUNCH}:1-5"),
        Fact("The landing action server is constructed on the relative action/landing name and its "
             "pose client on the relative action/pose name.",
             source="upstream_code", ref=f"{_LANDING}:42-44"),
        Fact("The landing action reads action_frequency 10.0, landing_height 0.3, connection_timeout "
             "10.0 and the misspelled action_timout 30.0 as defaults.",
             source="upstream_code", ref=f"{_LANDING}:45-53"),
        Fact("The landing callback uses the current pose when landing_zone.header.frame_id is empty, "
             "sets the target z to min(landing_height, current z), sends the PoseGoal and waits for "
             "its result for action_timeout.",
             source="upstream_code", ref=f"{_LANDING}:56-67"),
        Fact("The landing callback sets the action succeeded only when the pose client state is "
             "SUCCEEDED and enableMotors(false) returns true; otherwise it sets aborted.",
             source="upstream_code", ref=f"{_LANDING}:69-78"),
        Fact("The Landing action goal carries a geometry_msgs/PoseStamped landing_zone, its result "
             "is empty, and the comment says an empty landing zone lands directly below.",
             source="upstream_code", ref=f"{_LANDING_ACTION}:1-6"),
        Fact("The shipped controller params set action_timeout 30.0, command_timeout 0.5, "
             "dist_tolerance 0.1, yaw_tolerance 0.35, time_in_tolerance 1.0, landing_height 0.1, "
             "takeoff_height 0.1 and estop_deceleration 1.0.",
             source="upstream_code", ref=f"{_CONTROLLER_PARAMS}:1-13"),
        Fact("The controller launch loads controller.yaml under the controller namespace and "
             "params.yaml into the launching namespace.",
             source="upstream_code", ref=f"{_CONTROLLER_LAUNCH}:10-11"),
        Fact("The hardware sim advertises the relative enable_motors service with the "
             "hector_uav_msgs/EnableMotors type.",
             source="upstream_code", ref=f"{_HARDWARE}:108"),
        Fact("The EnableMotors callback stores the request enable flag in motor_status_.running, "
             "returns true and sets the response success flag.",
             source="upstream_code", ref=f"{_HARDWARE}:274-283"),
        Fact("BaseActionServer::enableMotors sends an EnableMotors request and returns the result of "
             "the service call, not the response success field.",
             source="upstream_code", ref=f"{_BASE_ACTION}:74-79"),
        Fact("The controller launch relays the absolute /estop topic to the relative estop topic.",
             source="upstream_code", ref=f"{_CONTROLLER_LAUNCH}:16"),
        Fact("The attitude controller subscribes the relative estop topic with its estopCb callback.",
             source="upstream_code", ref=f"{_ATTITUDE}:107"),
        Fact("While the motors run and command_timeout is non-zero, an attitude, yawrate or thrust "
             "command stamp older than command_timeout sets command_estop_.",
             source="upstream_code", ref=f"{_ATTITUDE}:153-168"),
        Fact("When estop_ or command_estop_ is set, the attitude controller zeroes the roll, pitch and "
             "yawrate commands and lowers the thrust by estop_deceleration times mass times the "
             "period, not below zero.",
             source="upstream_code", ref=f"{_ATTITUDE}:181-186"),
        Fact("The attitude controller's estop callback only stores the Bool and, on a false-to-true "
             "transition, caches the current thrust command; it sends no acknowledgement.",
             source="upstream_code", ref=f"{_ATTITUDE}:221-231"),
        Fact("The behaviour node creates an EnableMotors client on the relative enable_motors name "
             "and waits until enableMotors(true) succeeds before its control loop.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:468-469"),
        Fact("The behaviour node's collisionchecker calls system(\"pkill -f ros\") when the planar "
             "distance is at most 0.3; this is not a ROS stop service.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:110-117"),
        Fact("The behaviour loop also calls system(\"pkill -f ros\") once t_elps reaches 5000.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:586-588"),
        Fact("The behaviour node defines H_DES 1.0 as the desired level height, STARTTIME 30.0 "
             "simulation seconds and ros_rate 10.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:64-77"),
        Fact("Each behaviour loop iteration publishes a cmd_vel whose linear.z is a PID output on "
             "H_DES minus the current height.",
             source="upstream_code", ref=f"{_BEHAVIOUR}:573-577"),
        Fact("A cmd_vel with any non-zero component makes the velocity controller preempt the "
             "position controller's twist input.",
             source="upstream_code", ref=f"{_VELOCITY}:173-181"),
        Fact("The velocity controller stamps its attitude, yawrate and thrust outputs with the stamp "
             "of the twist command it used.",
             source="upstream_code", ref=f"{_VELOCITY}:264-267"),
        Fact("When its twist output was preempted or the motors are not running, the position "
             "controller drops its pose command, resets and stops its twist output.",
             source="upstream_code", ref=f"{_POSITION}:178-198"),
        Fact("The position controller ignores a PoseStamped command whose frame_id is not its "
             "world_frame_.",
             source="upstream_code", ref=f"{_POSITION}:273-283"),
        Fact("The pose action callback begins by calling enableMotors(true).",
             source="upstream_code", ref=f"{_POSE_ACTION}:56-58"),
        Fact("Each pose action iteration publishes the target pose; the goal succeeds after the "
             "current pose has stayed within dist_tolerance and yaw_tolerance for time_in_tolerance "
             "and aborts after action_timeout.",
             source="upstream_code", ref=f"{_POSE_ACTION}:80-101"),
        Fact("writeSim applies the limited controller wrench only while motor_status_.on and "
             "running are true; otherwise it publishes a zero wrench.",
             source="upstream_code", ref=f"{_HARDWARE}:242-270"),
        Fact("normal.launch defaults paused to false, use_sim_time to true, gui to true and physics to ode.",
             source="upstream_code", ref=f"{_NORMAL_LAUNCH}:6-12"),
        Fact("When use_sim_time is true, normal.launch sets the parameter /use_sim_time to true.",
             source="upstream_code", ref=f"{_NORMAL_LAUNCH}:17-18"),
        Fact("normal.launch starts the node named gazebo of package gazebo_ros, and its type is gzserver unless "
             "debug is true.",
             source="upstream_code", ref=f"{_NORMAL_LAUNCH}:28-32"),
        Fact("When gui is true, normal.launch starts the node gazebo_gui of package gazebo_ros and type gzclient.",
             source="upstream_code", ref=f"{_NORMAL_LAUNCH}:35-36"),
        Fact("The 3mavs launch includes $(find mav_controller)/worlds/normal.launch.",
             source="upstream_code", ref=f"{_THREE_MAVS}:11"),
        Fact("normal.world sets the world physics type to ode.",
             source="upstream_code", ref=f"{_NORMAL_WORLD}:6"),
        Fact("The README says other versions should also work.",
             source="upstream_code", ref="README.md:6"),
        Fact("The quadrotor_controller macro loads libgazebo_ros_control.so with controlPeriod 0.01 and robotSimType "
             "hector_quadrotor_controller_gazebo/QuadrotorHardwareSim.",
             source="upstream_code", ref=f"{_XACRO}:5-7"),
        Fact("The behaviour node's main constructs ros::Rate loop_rate(ros_rate).",
             source="upstream_code", ref=f"{_BEHAVIOUR}:387"),
        Fact("The behaviour loop calls ros::spinOnce() and then loop_rate.sleep().",
             source="upstream_code", ref=f"{_BEHAVIOUR}:591-592"),
        Fact("The takeoff action callback calls enableMotors(true).",
             source="upstream_code", ref=f"{_TAKEOFF}:59"),
        Fact("The velocity controller's reset assigns an empty TwistStamped to twist_command_.",
             source="upstream_code", ref=f"{_VELOCITY}:110-118"),
        Fact("When the motors are not running, the velocity controller's update calls reset().",
             source="upstream_code", ref=f"{_VELOCITY}:196-199"),
        Fact("The velocity controller's update passes twist_command_.twist through twist_limiter_ and uses that "
             "result as its command.",
             source="upstream_code", ref=f"{_VELOCITY}:206-207"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true: the paused flag, not a measured "
        "standstill. No unpause is offered: twist_command_ keeps the last cmd_vel (velocity_controller.cpp:169) and "
        "the behaviour node publishes again when simulation time resumes (behaviour.cpp:577, :592); an operator "
        "stops those nodes and clears the stored twist outside MHS, then unpauses."
    )
    fidelity = {
        "engine": "analytic:ROS-free protocol fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned ROS replies with no Gazebo step, hector controller, "
                     "swarm behaviour or wall-clock pacing; placeholder odometry and action/service "
                     "results do not establish flight, landing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free ros_transport handler: it answers the declared odometry, cmd_vel, "
            "enable_motors and landing endpoints and the two companion Gazebo services, and it records "
            "outbound messages; it runs no ROS graph, Gazebo, hector_quadrotor, mav_controller behaviour "
            "or physics",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo "
            "World::Step",
            "no unpause is offered: twist_command_ keeps the last cmd_vel (velocity_controller.cpp:169) and "
            "update() applies it on the next controller step (velocity_controller.cpp:207) with the stamp "
            "stored at receipt (velocity_controller.cpp:265-267); reset() clears it only when the motors "
            "are not running (velocity_controller.cpp:117, :197-198), and that update does not run while "
            "the world is paused; the behaviour node publishes cmd_vel again when simulation time resumes "
            "(behaviour.cpp:573-577, :591-592; normal.launch sets /use_sim_time). The operator stops the "
            "behaviour nodes and clears the stored twist outside MHS, then unpauses with the Gazebo GUI "
            "or rosservice call gazebo/unpause_physics",
            "while paused, /uav1/ground_truth/state is silent: GazeboRosP3D::UpdateChild is connected to "
            "the world-update begin event (gazebo_ros_p3d.cpp:207-208) and pushes the odometry there "
            "(gazebo_ros_p3d.cpp:351), and World::Step calls Update only when the world is not paused, a "
            "step is pending or a reset is due (World.cc:691-697). The topic left the device resource and "
            "stays an explicit read, which fails after its timeout while the fake's flag is set. The "
            "cmd_vel receipt reports the values it sent. A paused world's step or multi_step WorldControl, "
            "or the GUI, can still run updates",
            "a live world can be unpaused or stepped by the Gazebo GUI that normal.launch opens by default "
            "(gui true, node gazebo_gui), by a WorldControl message (World.cc:1462-1477) or by any other "
            "ROS client. safety_status returns the cached e-stop confirmation and does not call "
            "get_physics_properties again (RosBridge.safety_status, mhs/bridge/ros.py:2227-2232), so it "
            "cannot detect an external unpause or a WorldControl step. ProcessMessages still runs while "
            "paused (World.cc:718)",
            "the read-back needs the ODE engine: normal.launch defaults physics to ode and normal.world "
            "sets physics type ode; with another engine get_physics_properties returns false "
            "(gazebo_ros_api_plugin.cpp:1458-1465) and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and 9.19.0 releases "
            "the companion citations name; the README says other versions should also work (README.md:6), "
            "and rosbridge cannot read their versions",
            "enable_motors stays an ordinary command. Its callback sets motor_status_.running and returns "
            "true (quadrotor_hardware_gazebo.cpp:274-283) and is advertised on the model node handle "
            "without a custom queue (quadrotor_hardware_gazebo.cpp:108). The API plugin starts a "
            "ros::AsyncSpinner (gazebo_ros_api_plugin.cpp:149-151), so the service can be answered while "
            "the world is paused. writeSim, which applies the wrench only while the motors are on and "
            "running (quadrotor_hardware_gazebo.cpp:242-270), is called from gazebo_ros_control's Update "
            "on the world-update begin event and does not run until the world steps. The fake answers the "
            "service while its flag is set and does not move its placeholder pose",
            "the fake returns immediate landing success while its flag is clear, and an aborted landing "
            "while the flag is set; the real landing action waits for the pose action for up to the 30 s "
            "action_timout, that pose goal first calls enableMotors(true), and the pose controller does "
            "not update while the world is paused. The landing action is an ordinary command, not a stop. "
            "The takeoff callback also calls enableMotors(true) (takeoff_action.cpp:59)",
            "while the fake's flag is clear, a cmd_vel publication adds its components to a placeholder "
            "odometry pose so the explicit read can change; while the flag is set the publication is "
            "stored and the placeholder pose does not move. The receipt's sent_* fields are the "
            "transmitted request. Live, the velocity controller stores the twist and the attitude "
            "controller's 0.5 s command_timeout (attitude_controller.cpp:153-168) treats an output stamp "
            "older than that as command_estop_; the stored twist itself is not cleared by that timeout",
            "the package covers uav1 only; the 3mavs, 4mavs, 9mavs and 10mavs launches, the autonomous "
            "behaviour node, the swarm state-action matrix and inter-UAV collision avoidance are NOT "
            "COVERED. The absolute /uav1 names are this driver's deployment choice: 3mavs.launch puts the "
            "spawn and the behaviour node in group ns uav1 (3mavs.launch:13-24); the upstream names are "
            "relative",
            "the behaviour node also publishes /uav1/cmd_vel and enables motors; running it beside this "
            "driver gives the vehicle competing commanders, and on an unpause it publishes again",
            "the ground_truth/state publisher is the external libgazebo_ros_p3d.so plugin named by the "
            "xacro; the clone does not contain that plugin's source",
            "the four cmd_vel inputs are operator_required: the clone states only a combined xy magnitude "
            "(velocity max_xy 10.0), a velocity z clamp (max 5.0, negative side derived in code) and an "
            "attitude yawrate clamp (3.14), none of them a per-axis command envelope; "
            "site-limits.example.json holds example values only",
            "the landing action's enableMotors(false) checks only the service call result, not the "
            "response success field; the driver repeats that contract and does not add a motor status "
            "read-back",
            "the behaviour node calls system(\"pkill -f ros\") on a near collision and once t_elps "
            "reaches 5000; it kills every host process whose command line contains ros, including "
            "rosbridge and an mhs serve process whose package path contains ros",
            "mhs.safety.reset releases the latch only; the world stays paused and no re-enable binding "
            "is declared. The operator recovers outside MHS",
            "the package declares no hardware backend and no live ROS or Gazebo validation; all evidence "
            "is fake-backend contract evidence only",
        ],
    }

    # The device resource reads no topic. /uav1/ground_truth/state is published from the world update, so it
    # is silent while the e-stop holds the world paused. It stays an explicit read capability below.
    commands = {
        "x-cap.coppolam.odometry.v1": _ODOMETRY,
        "x-cap.coppolam.cmd_vel.v1": _CMD_VEL,
        "x-cap.coppolam.arm.v1": _ARM,
        "x-cap.coppolam.land.v1": _LANDING_BINDING,
    }
    actions = {
        "x-cap.coppolam.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one nav_msgs/Odometry sample from /uav1/ground_truth/state (silent, and not "
                        "completed, while the world is paused)",
            output=_ODOMETRY_OUTPUT,
        ),
        "x-cap.coppolam.cmd_vel.v1": Action(
            name="set_velocity",
            verb="invoke",
            risk="R2",
            description="Publish one geometry_msgs/Twist velocity command on /uav1/cmd_vel; the "
                        "receipt reports the values sent and confirms transmission only, not arrival, "
                        "motion or a continuous stream",
            input={
                "linear_x": Field("number", unit="m/s",
                                  description="base_stabilized linear x velocity", limit=_LINEAR_X),
                "linear_y": Field("number", unit="m/s",
                                  description="base_stabilized linear y velocity", limit=_LINEAR_Y),
                "linear_z": Field("number", unit="m/s",
                                  description="world-frame vertical velocity", limit=_LINEAR_Z),
                "angular_z": Field("number", unit="rad/s",
                                   description="yaw-rate command", limit=_ANGULAR_Z),
            },
            output=_PUBLISHED_OUTPUT,
        ),
        "x-cap.coppolam.arm.v1": Action(
            name="enable_motors",
            verb="invoke",
            risk="R2",
            description="Send the fixed EnableMotors enable=true request on /uav1/enable_motors; "
                        "success is the service response flag, not a sensed motor state",
            output=_ARM_OUTPUT,
        ),
        "x-cap.coppolam.land.v1": Action(
            name="land",
            verb="invoke",
            risk="R2",
            cancellable=False,
            max_duration_ms=34000,
            description="Land below the current pose and disable motors through "
                        "hector_uav_msgs/LandingAction; an ordinary command, not a stop: its pose "
                        "goal re-enables the motors first",
            output=_LAND_OUTPUT,
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros). A failed pause
    # or a read-back other than pause true leaves the e-stop unconfirmed with the latch held. No reset binding
    # and no re-enable: mhs.safety.reset releases the latch only and the world stays paused. The landing action
    # and enable_motors stay ordinary commands.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
