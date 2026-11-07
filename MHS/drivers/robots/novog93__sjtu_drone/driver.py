"""OpenMHS rosbridge driver for the gh.novog93/sjtu_drone Gazebo quadrotor simulation.

The pinned upstream is a ROS 2 + Gazebo 11 simulation.  The flight controller
is the C++ Gazebo model plugin ``libplugin_drone.so``; the Python
``sjtu_drone_control`` nodes are in-process helpers that publish the same
topics.  This package is therefore a configuration-only :class:`RosDriver`
over the pinned topic contract.  It declares no Python native class and does
not import, launch or install the upstream code.

The plugin takes all flight commands as ROS 2 publications, not services or
actions: ``takeoff``, ``land``, ``reset``, ``posctrl``, ``dronevel_mode`` and
``cmd_vel`` under the ``/simple_drone`` namespace configured by the shipped
SDF.  It publishes ``state`` (Int8), ``gt_pose`` (Pose), ``gt_vel`` and
``gt_acc`` (Twist) and ``cmd_mode`` (String).  A rosbridge publication is a
transmission only: the receipt reports ``published: true`` and
``confirmed: false``, never that the simulated drone took off, landed, moved
or stopped.

The clone contains no service or action server for flight control.  The
shipped ``reset_sim.sh`` script calls the ``/reset_world`` service, which
``gazebo_ros`` provides, not this repository.  It is not a stop: the plugin's
only reset path, ``Reset()`` (reached from the model plugin's reset hook and
from the ``reset`` topic), clears the attitude and velocity PID controllers and
the current force and torque but leaves the flight state ``navi_state`` and the
stored ``cmd_vel`` unchanged, and ``UpdateDynamics`` keeps applying thrust from
that command while the state is flying; ``/reset_world`` stays an ordinary
command (model review 2026-11-04).

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source fetched at a pinned commit (user decision and
authorisation of 2026-11-05; ``task.json`` ``companions`` with ``lock``):
gazebo_ros 3.9.0 (ROS 2 Humble) ``/pause_physics``, confirmed by a stall
read-back (E1): two ``/get_model_list`` answers 250 ms apart whose
``header.stamp``, the world's sim time, did not advance.  The plugin's update
runs only on the world-update event, so a paused world applies no force; it is
a frozen sim time, not a measured standstill.

No unpause is offered.  The plugin keeps its flight state and stored command:
in position-control mode the cmd_vel linear fields are position targets (a
zero Twist is a flight to the world origin), a take-off in progress continues
with 1.5 times the force, and every stored command carries drift noise, so this
package cannot clear the stored motion before an unpause (the orchestrator's
SAFE-042 condition).  After ``mhs.safety.reset`` the world stays paused and the
operator recovers outside MHS (see ``safe_state``).  The last cmd_vel left the
device resource (it only carries what clients publish); it stays an explicit
read capability, and the cmd_vel receipt reports what it sent.  Every endpoint,
type and fact of the package's own surface cites the pinned clone at
3f8627ebddf390fd35ffb84b8654b62e0b66fca2; the stop, its read-back and the facts
about them cite the companions at their pins.  The fake is a ROS-free scripted
transport, not captured traffic and not the Gazebo simulator.
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
]

_CMD_VEL_ID = "x-cap.novog93.cmd_vel.v1"
_AXES = ("linear_x", "linear_y", "linear_z", "angular_x", "angular_y", "angular_z")


class _SentReceipt:
    """The receipt of a cmd_vel publication also reports the six values it handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees what a publication sent; it is the
    transmitted request (before the plugin adds its drift noise), not a measurement. Every other call, the e-stop
    and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _CMD_VEL_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        for key in _AXES:
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: The shipped SDF gives the plugin's ROS node the /simple_drone namespace.
_NAMESPACE_REF = "sjtu_drone_description/models/sjtu_drone/sjtu_drone.sdf:194"

#: The plugin header declares the relative topic names, the message types and
#: the state enum values.
_TOPIC_DEFAULTS_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:60-68"
_TYPE_INCLUDES_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:27-35"
_STATE_ENUM_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:45-48"

#: The header lines that show the exact relative topic literals.
_CMD_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:61"
_POSCTRL_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:61"
_TAKEOFF_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:62"
_LAND_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:63"
_RESET_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:63"
_VEL_MODE_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:64"
_POSE_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:66"
_VEL_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:66"
_ACC_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:66"
_MODE_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:67"
_STATE_BIND_REF = "sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:68"

#: The subscription and publication sites in the plugin implementation.
_CMD_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:68-73"
_POSCTRL_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:77-80"
_TAKEOFF_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:95-99"
_LAND_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:104-108"
_RESET_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:113-117"
_VEL_MODE_SUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:122-126"
_POSE_PUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:139-140"
_VEL_PUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:145-146"
_ACC_PUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:151-152"
_CMD_MODE_PUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:157-158"
_STATE_PUB_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:163-164"

#: The callbacks that consume the commands and publish the observations.
_CMD_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:227-254"
_POSCTRL_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:262-265"
_TAKEOFF_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:288-295"
_LAND_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:301-308"
_RESET_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:315-319"
_VEL_MODE_CALLBACK_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:328-339"
_STATE_UPDATE_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:395-416"
_POSE_PUBLISH_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:434-450"
_VEL_PUBLISH_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:453-461"
_ACC_PUBLISH_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:454-467"

#: The reset path and the force application that a world reset leaves running
#: (model review 2026-11-04).
_PRIVATE_RESET_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:36-56"
_PLUGIN_RESET_HOOK_REF = "sjtu_drone_description/src/plugin_drone.cpp:156-159"
_FORCE_FROM_CMD_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:488-568"
_FORCE_BY_STATE_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:573-585"

#: The Python helper documents the intended units and overloaded meanings.
_PY_MOVE_REF = "sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:200-213"
_PY_MOVE_TO_REF = "sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:215-233"
_PY_TOPIC_REF = "sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:42-48"

#: The README lists the control and ground-truth topic contracts.
_README_CONTROL_REF = "README.md:35-44"
_README_GROUND_TRUTH_REF = "README.md:46-50"

#: The shipped helper script calls Gazebo's acknowledged world-reset service.
_RESET_WORLD_REF = "sjtu_drone_bringup/scripts/reset_sim.sh:3"

#: The clone exposes only topic publication and subscription for flight control.
_ROS_SETUP_REF = "sjtu_drone_description/src/plugin_drone_private.cpp:59-174"

_CMD_REASON = (
    "the clone states no numeric command bound: the PID gains and limits in the shipped YAML/SDF are "
    "controller parameters, not a cmd_vel input envelope, and the same Twist fields are overloaded "
    "(position targets in position-control mode, velocity/tilt/rate otherwise); the operator supplies "
    "the deployment envelope"
)
_POSITION_REASON = (
    "the Python moveTo helper documents x, y and z as metres, but the clone states no numeric position "
    "bound and the same cmd_vel fields carry velocity instead when position control is off; the operator "
    "supplies the deployment envelope"
)

_PUBLISHED = {
    "published": Field(
        "boolean",
        description="True when the driver handed the message to rosbridge",
    ),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution acknowledgement",
    ),
}

_STATE = Field(
    "integer",
    description=(
        "Last Int8 value on the state topic: the plugin header defines LANDED_MODEL 0, FLYING_MODEL 1, "
        "TAKINGOFF_MODEL 2 and LANDING_MODEL 3; the README's 0 landed, 1 flying, 2 hovering labels do "
        "not match the C++ enum names"
    ),
)

_POSE = Field(
    "object",
    description="Ground-truth pose published by the plugin",
    properties={
        "x": Field("number", unit="m", description="position.x from geometry_msgs/Pose"),
        "y": Field("number", unit="m", description="position.y from geometry_msgs/Pose"),
        "z": Field("number", unit="m", description="position.z from geometry_msgs/Pose"),
        "orientation_w": Field("number", unit="1", description="orientation.w quaternion component"),
        "orientation_x": Field("number", unit="1", description="orientation.x quaternion component"),
        "orientation_y": Field("number", unit="1", description="orientation.y quaternion component"),
        "orientation_z": Field("number", unit="1", description="orientation.z quaternion component"),
    },
)

_MODE = Field(
    "string",
    description=(
        "Last value on cmd_mode. The plugin publishes the String 'velocity' or 'position' only from the "
        "dronevel_mode callback; it does not publish a mode on posctrl changes."
    ),
)

_TWIST = Field(
    "object",
    description="Last geometry_msgs/Twist observed on the cmd_vel topic",
    properties={
        "linear": Field(
            "object",
            description="Twist linear components",
            properties={
                "x": Field("number", unit="1", description="linear.x as most recently published"),
                "y": Field("number", unit="1", description="linear.y as most recently published"),
                "z": Field("number", unit="1", description="linear.z as most recently published"),
            },
        ),
        "angular": Field(
            "object",
            description="Twist angular components",
            properties={
                "x": Field("number", unit="1", description="angular.x as most recently published"),
                "y": Field("number", unit="1", description="angular.y as most recently published"),
                "z": Field("number", unit="1", description="angular.z as most recently published"),
            },
        ),
    },
)

_TAKEOFF = {
    "topic": "/simple_drone/takeoff",
    "type": "std_msgs/msg/Empty",
    "operation": "publish",
    "source_name": "takeoff",
    "source_ref": _TAKEOFF_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {},
}

_LAND = {
    "topic": "/simple_drone/land",
    "type": "std_msgs/msg/Empty",
    "operation": "publish",
    "source_name": "land",
    "source_ref": _LAND_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {},
}

_RESET = {
    "topic": "/simple_drone/reset",
    "type": "std_msgs/msg/Empty",
    "operation": "publish",
    "source_name": "reset",
    "source_ref": _RESET_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {},
}

_POSCTRL = {
    "topic": "/simple_drone/posctrl",
    "type": "std_msgs/msg/Bool",
    "operation": "publish",
    "source_name": "posctrl",
    "source_ref": _POSCTRL_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {"data": False},
    "args": {"data": {"from": "input.enabled"}},
}

_VEL_MODE = {
    "topic": "/simple_drone/dronevel_mode",
    "type": "std_msgs/msg/Bool",
    "operation": "publish",
    "source_name": "dronevel_mode",
    "source_ref": _VEL_MODE_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {"data": False},
    "args": {"data": {"from": "input.enabled"}},
}

_CMD_VEL = {
    "topic": "/simple_drone/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "linear.z": {"from": "input.linear_z"},
        "angular.x": {"from": "input.angular_x"},
        "angular.y": {"from": "input.angular_y"},
        "angular.z": {"from": "input.angular_z"},
    },
}

_RESET_WORLD = {
    "service": "/reset_world",
    "type": "std_srvs/srv/Empty",
    "source_name": "/reset_world",
    "source_ref": _RESET_WORLD_REF,
    "success": {"path": "$", "equals": {}},
    "result": {"reset": {"value": True}},
}

_STATE_READ = {
    "topic": "/simple_drone/state",
    "type": "std_msgs/msg/Int8",
    "operation": "subscribe",
    "source_name": "state",
    "source_ref": _STATE_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "result": {"map": {"state": "output.data"}},
}

_POSE_READ = {
    "topic": "/simple_drone/gt_pose",
    "type": "geometry_msgs/msg/Pose",
    "operation": "subscribe",
    "source_name": "gt_pose",
    "source_ref": _POSE_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "result": {"map": {
        "x": "output.position.x",
        "y": "output.position.y",
        "z": "output.position.z",
        "orientation_w": "output.orientation.w",
        "orientation_x": "output.orientation.x",
        "orientation_y": "output.orientation.y",
        "orientation_z": "output.orientation.z",
    }},
}

_MODE_READ = {
    "topic": "/simple_drone/cmd_mode",
    "type": "std_msgs/msg/String",
    "operation": "subscribe",
    "source_name": "cmd_mode",
    "source_ref": _MODE_BIND_REF,
    "type_ref": _TYPE_INCLUDES_REF,
    "result": {"map": {"mode": "output.data"}},
}


class SjtuDrone(RosDriver):
    device_id = "sjtu-drone"
    device_kind = "world.sim"
    mode = "simulated"
    # The card floor is R1; the author declared R1. Model review (2026-11-05):
    # cmd_vel, takeoff, land and reset command the vehicle, and REVIEW.md item 12
    # gives a command on such a topic the robot's hazard however simulated the
    # deployment (a flying vehicle is mobile hardware: R2). The server applies
    # the device risk to every capability. The e-stop is the companion world
    # pause (safety_bindings); no hardware emergency stop is claimed.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeSjtuDrone"}
    tags = ["ros", "ros2", "gazebo", "simulation", "quadrotor", "drone", "topic-control"]
    display_name = "sjtu_drone Gazebo quadrotor simulation"
    vendor = "novog93"
    model = "sjtu_drone quadrotor in Gazebo 11"
    facts = [
        Fact("The shipped model SDF gives the drone plugin's ROS node the namespace /simple_drone.",
             source="upstream_code", ref=_NAMESPACE_REF),
        Fact("The plugin header declares the relative topic defaults cmd_vel, posctrl, imu, takeoff, land, "
             "reset and dronevel_mode.", source="upstream_code", ref=_TOPIC_DEFAULTS_REF),
        Fact("The plugin header declares the relative topic defaults gt_pose, gt_vel, gt_acc, cmd_mode, "
             "state and odom.", source="upstream_code", ref=_TOPIC_DEFAULTS_REF),
        Fact("The plugin header includes geometry_msgs/Twist and Pose, sensor_msgs/Imu, std_msgs/Empty, "
             "Bool, String and Int8, and nav_msgs/Odometry.", source="upstream_code",
             ref="sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:27-36"),
        Fact("The plugin header defines LANDED_MODEL 0, FLYING_MODEL 1, TAKINGOFF_MODEL 2 and "
             "LANDING_MODEL 3.", source="upstream_code", ref=_STATE_ENUM_REF),
        Fact("InitSubscribers creates a geometry_msgs::msg::Twist subscription on the cmd_vel default with "
             "best-effort KeepLast(1) QoS.", source="upstream_code", ref=_CMD_SUB_REF),
        Fact("InitSubscribers creates a std_msgs::msg::Bool subscription on the posctrl default.",
             source="upstream_code", ref=_POSCTRL_SUB_REF),
        Fact("InitSubscribers creates a std_msgs::msg::Empty subscription on the takeoff default.",
             source="upstream_code", ref=_TAKEOFF_SUB_REF),
        Fact("InitSubscribers creates a std_msgs::msg::Empty subscription on the land default.",
             source="upstream_code", ref=_LAND_SUB_REF),
        Fact("InitSubscribers creates a std_msgs::msg::Empty subscription on the reset default.",
             source="upstream_code", ref=_RESET_SUB_REF),
        Fact("InitSubscribers creates a std_msgs::msg::Bool subscription on the dronevel_mode default.",
             source="upstream_code", ref=_VEL_MODE_SUB_REF),
        Fact("InitPublishers creates a geometry_msgs::msg::Pose publisher on the gt_pose default with "
             "queue size 1024.", source="upstream_code", ref=_POSE_PUB_REF),
        Fact("InitPublishers creates a geometry_msgs::msg::Twist publisher on the gt_vel default.",
             source="upstream_code", ref=_VEL_PUB_REF),
        Fact("InitPublishers creates a geometry_msgs::msg::Twist publisher on the gt_acc default.",
             source="upstream_code", ref=_ACC_PUB_REF),
        Fact("InitPublishers creates a std_msgs::msg::String publisher on the cmd_mode default.",
             source="upstream_code", ref=_CMD_MODE_PUB_REF),
        Fact("InitPublishers creates a std_msgs::msg::Int8 publisher on the state default.",
             source="upstream_code", ref=_STATE_PUB_REF),
        Fact("The plugin's ROS setup creates only these topic subscriptions and publications; no service or "
             "action server is created for flight control or stopping.", source="upstream_code",
             ref=_ROS_SETUP_REF),
        Fact("TakeoffCallback changes LANDED_MODEL to TAKINGOFF_MODEL and resets the command timer; it "
             "publishes no acknowledgement.", source="upstream_code", ref=_TAKEOFF_CALLBACK_REF),
        Fact("LandCallback changes FLYING_MODEL or TAKINGOFF_MODEL to LANDING_MODEL and resets the command "
             "timer; it publishes no acknowledgement.", source="upstream_code", ref=_LAND_CALLBACK_REF),
        Fact("ResetCallback logs and calls Reset(); it returns no response.",
             source="upstream_code", ref=_RESET_CALLBACK_REF),
        Fact("The private Reset() resets the roll, pitch, yaw and velocity x, y and z PID controllers, sets the "
             "link force and torque to zero and resets the cached pose, velocity, angular velocity, acceleration "
             "and euler; it does not assign navi_state, cmd_vel, m_posCtrl, m_velMode or the position PID "
             "controllers.", source="upstream_code", ref=_PRIVATE_RESET_REF),
        Fact("DroneSimpleController::Reset() only calls the private Reset().", source="upstream_code",
             ref=_PLUGIN_RESET_HOOK_REF),
        Fact("UpdateDynamics computes the force and torque from the stored cmd_vel: its linear fields are position "
             "targets when m_posCtrl is set and navi_state is FLYING_MODEL; in normal control linear.z drives the "
             "vertical velocity controller and angular.z the yaw controller in every state.",
             source="upstream_code", ref=_FORCE_FROM_CMD_REF),
        Fact("UpdateDynamics adds no force or torque in LANDED_MODEL, the computed force and torque in FLYING_MODEL, 1.5 "
             "times them in TAKINGOFF_MODEL and 0.8 times them in LANDING_MODEL.", source="upstream_code",
             ref=_FORCE_BY_STATE_REF),
        Fact("PosCtrlCallback stores the Bool data in m_posCtrl.", source="upstream_code",
             ref=_POSCTRL_CALLBACK_REF),
        Fact("SwitchModeCallback stores the Bool data in m_velMode and publishes the String 'velocity' or "
             "'position' on cmd_mode.", source="upstream_code", ref=_VEL_MODE_CALLBACK_REF),
        Fact("CmdCallback stores the full Twist and adds drift and small-noise offsets to angular x/y/z and "
             "linear z.", source="upstream_code", ref=_CMD_CALLBACK_REF),
        Fact("UpdateState changes TAKINGOFF_MODEL to FLYING_MODEL after 0.5 s and LANDING_MODEL to "
             "LANDED_MODEL after 1.0 s, then publishes the Int8 navi_state every update.",
             source="upstream_code", ref=_STATE_UPDATE_REF),
        Fact("UpdateDynamics reads the Gazebo world pose and publishes that Pose on gt_pose.",
             source="upstream_code", ref=_POSE_PUBLISH_REF),
        Fact("UpdateDynamics publishes body_vel, computed as pose.Rot().RotateVector(velocity), as the linear "
             "part of a Twist on gt_vel.", source="upstream_code", ref=_VEL_PUBLISH_REF),
        Fact("UpdateDynamics publishes body_acc, computed as pose.Rot().RotateVector(acceleration), as the "
             "linear part of a Twist on gt_acc.", source="upstream_code", ref=_ACC_PUBLISH_REF),
        Fact("The Python helper publishes Empty, Bool and Twist messages on the private (~/) takeoff, land, "
             "reset, posctrl, cmd_vel and dronevel_mode topics.", source="upstream_code",
             ref=_PY_TOPIC_REF),
        Fact("The Python move helper documents linear velocity in m/s and angular velocity in rad/s.",
             source="upstream_code", ref=_PY_MOVE_REF),
        Fact("The Python moveTo helper documents x, y and z as metres and publishes them in the cmd_vel "
             "Twist linear fields.", source="upstream_code", ref=_PY_MOVE_TO_REF),
        Fact("The README lists cmd_vel, land, takeoff, posctrl, dronevel_mode, cmd_mode, state and reset "
             "as the control topics, with their ROS message types.", source="vendor_doc",
             ref=_README_CONTROL_REF),
        Fact("The README lists gt_acc, gt_pose and gt_vel as the ground-truth topic contracts.",
             source="vendor_doc", ref=_README_GROUND_TRUTH_REF),
        Fact("The shipped reset_sim.sh helper calls the /reset_world std_srvs/srv/Empty service.",
             source="upstream_code", ref=_RESET_WORLD_REF),
        Fact("The drone plugin connects its Update to the world-update begin event.", source="upstream_code",
             ref="sjtu_drone_description/src/plugin_drone.cpp:134-135"),
        Fact("Update returns at once when no simulation time passed, and otherwise runs UpdateState and "
             "UpdateDynamics.", source="upstream_code", ref="sjtu_drone_description/src/plugin_drone.cpp:143-154"),
        Fact("In position control, while flying, UpdateDynamics feeds the cmd_vel linear fields to the position "
             "controllers as targets.", source="upstream_code",
             ref="sjtu_drone_description/src/plugin_drone_private.cpp:492-520"),
        Fact("The gazebo launch includes gazebo_ros's gzserver.launch.py with the drone world.",
             source="upstream_code", ref="sjtu_drone_bringup/launch/sjtu_drone_gazebo.launch.py:98-105"),
        Fact("The bringup launch starts the teleop_joystick node or the keyboard teleop node in the model "
             "namespace.", source="upstream_code", ref="sjtu_drone_bringup/launch/sjtu_drone_bringup.launch.py:27-48"),
        Fact("The gazebo_ros init plugin's /reset_world handler resets the world's model entities.",
             source="upstream_code", ref=_INIT + ":321-326"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused: two get_model_list answers 250 ms apart carried the same sim time, so the "
        "drone plugin's update applies no force; it is a frozen sim time, not a measured standstill. No unpause is "
        "offered: an operator lands or re-commands the drone and unpauses outside MHS."
    )
    fidelity = {
        "engine": "analytic:ROS-free scripted contract fake (no Gazebo, no physics, no captured traffic)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "scripted request/response transport with placeholder state values; no physics step, "
                     "no wall-clock pacing and no trajectory replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free scripted transport: it answers the declared endpoints with placeholder "
            "messages and runs no Gazebo, plugin, PID controller, physics, sensor or rosbridge process",
            "the preference in the task card is the upstream Gazebo simulator; it cannot be started here, so "
            "this package uses an F0 contract fake instead of the upstream simulator",
            "the fake does not model takeoff, landing or flight dynamics; it only records the publication "
            "and updates a placeholder state label",
            "the fake's state, pose, mode and message values are test data, not measurements and not captured "
            "traffic",
            "the upstream plugin adds drift and small-noise offsets to cmd_vel; the fake does not",
            "the camera, IMU, sonar, GPS and odometry topics of the upstream simulation are not exposed; "
            "NOT COVERED: the front and bottom sensor_msgs/Image streams",
            "/reset_world (gazebo_ros's init plugin, a companion) resets the model entities, and the plugin's "
            "Reset() keeps navi_state and the stored cmd_vel, so a world reset is not a stop; the stop is the "
            "companion gazebo_ros world pause, confirmed by the E1 stall read-back: the fake keeps a paused flag "
            "that /pause_physics sets and a sim-time stamp that /get_model_list reports and that advances on every "
            "answer unless paused; it runs no Gazebo World::Step",
            "a frozen get_model_list stamp is also what a hung but unpaused gzserver shows (nothing advances then "
            "either); a GUI step or a WorldControl multi_step between the two samples fails the check (fails "
            "closed); the e-stop declares estop_latency_ms 1500 because the pause (400 ms), two read-backs (300 ms "
            "each) and the 250 ms interval exceed the default 1000 ms budget",
            "no unpause is offered: in position control the cmd_vel linear fields are position targets "
            "(plugin_drone_private.cpp:492-520), so a zero Twist is a flight to the world origin; a take-off in "
            "progress continues with 1.5 times the force (573-585, UpdateState 395-416); CmdCallback adds drift and "
            "small noise to every stored command (227-254); and the bringup's teleop publishes on the same topics "
            "(sjtu_drone_bringup.launch.py:27-48); the package cannot clear the stored motion first, so the operator "
            "recovers outside MHS (land or re-command the drone, then the Gazebo GUI play button or ros2 service "
            "call /unpause_physics)",
            "while paused, state and gt_pose (published from the plugin's world update) and /clock are silent and "
            "those reads fail NOT_READY after their timeouts (the fake silences them while its flag is set); the "
            "commands still publish and the plugin stores them for the next unpause",
            "a live world can be unpaused or stepped by the Gazebo GUI, a WorldControl message or any ROS 2 client "
            "of /unpause_physics; MHS does not watch the sim time after the e-stop (safety_status re-reads it only "
            "on request)",
            "the deployment's gazebo_ros and Gazebo must be the pinned 3.9.0 (Humble) and 11.15.1 releases the "
            "companion citations name (the clone also builds on Iron and Rolling; this package is pinned to "
            "Humble); rosbridge cannot read their versions",
            "the fake acknowledges /reset_world and records the reset publication without changing its state "
            "label or stored command, as the plugin's Reset() does; it does not model what the Gazebo world "
            "reset does to the model pose",
            "the fake answers every cmd_mode and cmd_vel subscription at once with its last value; live, the "
            "plugin publishes cmd_mode only from SwitchModeCallback and cmd_vel carries only what clients "
            "publish, so those reads return only when a message arrives while they wait; the last_cmd_vel read is an "
            "explicit capability, not the device resource, so no command waits for it",
        ],
    }

    # The device resource reads no topic: cmd_vel carries only what clients publish and the plugin's outputs are
    # silent while the e-stop holds the world paused.  The last cmd_vel is an explicit read capability below.
    estop_latency_ms = 1500
    commands = {
        "x-cap.novog93.last_cmd_vel.v1": {
            "topic": "/simple_drone/cmd_vel",
            "type": "geometry_msgs/msg/Twist",
            "operation": "subscribe",
            "source_name": "cmd_vel",
            "source_ref": _CMD_BIND_REF,
            "type_ref": _TYPE_INCLUDES_REF,
            "path": "$",
            "timeout_ms": 2000,
            "result": {"map": {"linear": "linear", "angular": "angular"}},
        },
        "x-cap.novog93.takeoff.v1": _TAKEOFF,
        "x-cap.novog93.land.v1": _LAND,
        "x-cap.novog93.reset.v1": _RESET,
        "x-cap.novog93.cmd_vel.v1": _CMD_VEL,
        "x-cap.novog93.posctrl.v1": _POSCTRL,
        "x-cap.novog93.vel_mode.v1": _VEL_MODE,
        "x-cap.novog93.state.v1": _STATE_READ,
        "x-cap.novog93.pose.v1": _POSE_READ,
        "x-cap.novog93.mode.v1": _MODE_READ,
        "x-cap.novog93.reset_world.v1": _RESET_WORLD,
    }
    actions = {
        "x-cap.novog93.takeoff.v1": Action(
            name="takeoff",
            description=(
                "Publish one std_msgs/Empty on /simple_drone/takeoff. The callback only moves the state "
                "machine from LANDED_MODEL to TAKINGOFF_MODEL; the receipt proves the publication, not "
                "that the simulated drone left the ground."
            ),
            output=_PUBLISHED,
            risk="R2",
        ),
        "x-cap.novog93.land.v1": Action(
            name="land",
            description=(
                "Publish one std_msgs/Empty on /simple_drone/land. The callback only moves the state "
                "machine to LANDING_MODEL; the receipt proves the publication, not that the simulated "
                "drone landed."
            ),
            output=_PUBLISHED,
            risk="R2",
        ),
        "x-cap.novog93.reset.v1": Action(
            name="reset",
            description=(
                "Publish one std_msgs/Empty on /simple_drone/reset. The plugin's callback resets the attitude "
                "and velocity PID controllers and the current force and torque but keeps the flight state and "
                "stored cmd_vel; it is not an acknowledged stop or an operator safety reset."
            ),
            output=_PUBLISHED,
            risk="R2",
        ),
        "x-cap.novog93.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            description=(
                "Publish one geometry_msgs/Twist on /simple_drone/cmd_vel. The fields are position "
                "targets in position-control mode and velocity/tilt/rate otherwise; the receipt is a "
                "publication acknowledgement only."
            ),
            input={
                "linear_x": Field(
                    "number", unit="1",
                    description="Twist linear.x (m target or m/s velocity, mode-dependent)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
                "linear_y": Field(
                    "number", unit="1",
                    description="Twist linear.y (m target or m/s velocity, mode-dependent)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
                "linear_z": Field(
                    "number", unit="1",
                    description="Twist linear.z (m target or m/s velocity, mode-dependent)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
                "angular_x": Field(
                    "number", unit="1",
                    description="Twist angular.x (roll tilt or rate, mode-dependent)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
                "angular_y": Field(
                    "number", unit="1",
                    description="Twist angular.y (pitch tilt or rate, mode-dependent)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
                "angular_z": Field(
                    "number", unit="1",
                    description="Twist angular.z (yaw rate)",
                    limit=Limit.operator_required(_CMD_REASON),
                ),
            },
            output={**_PUBLISHED, **{
                "sent_" + axis: Field("number", unit="1", description=f"The {axis.replace('_', '.')} handed to "
                                                                      "rosbridge (the transmitted request)")
                for axis in _AXES}},
            examples=[{"linear_x": 0.0, "linear_y": 0.0, "linear_z": 0.0,
                       "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0}],
            risk="R2",
        ),
        "x-cap.novog93.last_cmd_vel.v1": Action(
            name="read_last_cmd_vel",
            verb="read",
            description="Read the next geometry_msgs/Twist any client publishes on /simple_drone/cmd_vel (it carries "
                        "only client publications; NOT_READY when none arrives in 2 s)",
            output={"linear": _TWIST.properties["linear"], "angular": _TWIST.properties["angular"]},
            risk="R0",
        ),
        "x-cap.novog93.posctrl.v1": Action(
            name="set_position_control",
            description=(
                "Publish one std_msgs/Bool on /simple_drone/posctrl. The callback only stores the flag; "
                "the receipt proves the publication, not the resulting control mode."
            ),
            input={"enabled": Field("boolean", description="True selects position control")},
            output=_PUBLISHED,
            risk="R1",
        ),
        "x-cap.novog93.vel_mode.v1": Action(
            name="set_velocity_mode",
            description=(
                "Publish one std_msgs/Bool on /simple_drone/dronevel_mode. The callback stores the flag "
                "and publishes the resulting cmd_mode String; the receipt proves the publication only."
            ),
            input={"enabled": Field("boolean", description="True selects velocity mode instead of tilt mode")},
            output=_PUBLISHED,
            risk="R1",
        ),
        "x-cap.novog93.state.v1": Action(
            name="read_state",
            verb="read",
            description="Read one std_msgs/Int8 state sample published by the plugin",
            output={"state": _STATE},
            risk="R0",
        ),
        "x-cap.novog93.pose.v1": Action(
            name="read_pose",
            verb="read",
            description="Read one ground-truth geometry_msgs/Pose sample published by the plugin",
            output={
                "x": _POSE.properties["x"],
                "y": _POSE.properties["y"],
                "z": _POSE.properties["z"],
                "orientation_w": _POSE.properties["orientation_w"],
                "orientation_x": _POSE.properties["orientation_x"],
                "orientation_y": _POSE.properties["orientation_y"],
                "orientation_z": _POSE.properties["orientation_z"],
            },
            risk="R0",
        ),
        "x-cap.novog93.mode.v1": Action(
            name="read_mode",
            verb="read",
            description="Read one std_msgs/String cmd_mode sample published by the plugin",
            output={"mode": _MODE},
            risk="R0",
        ),
        "x-cap.novog93.reset_world.v1": Action(
            name="reset_world",
            description=(
                "Call the /reset_world std_srvs/Empty service (gazebo_ros) that the clone's reset_sim.sh uses. "
                "It resets the simulated world, but the plugin keeps its flight state and stored cmd_vel, so a "
                "flying drone keeps flying; it is not a stop."
            ),
            output={"reset": Field(
                "boolean", description="True when the world-reset service returned its empty success response")},
            risk="R1",
        ),
    }
    #: /reset_world stays an ordinary command (model review 2026-11-04): the plugin keeps navi_state and the stored
    #: cmd_vel through a world reset, so it cannot certify a stop.
    # The e-stop pauses the Gazebo world and confirms it by a sim time that no longer advances (companion gazebo_ros,
    # E1 stall read-back); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
