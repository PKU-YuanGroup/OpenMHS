"""OpenMHS rosbridge driver for the AgileX Scout V2 empty world in ugv_gazebo_sim.

The pinned repository is a ROS 1 catkin workspace of Gazebo bringups, not a
Python package.  This package is a configuration-only :class:`RosDriver`.  It
declares no Python native class and it does not launch Gazebo or rosbridge.

The served surface is ``scout/scout_gazebo_sim/launch/scout_empty_world.launch``
only (Scout V2).  That file includes gazebo_ros ``empty_world.launch`` and
``spawn_scout_v2.launch``.  The live model plugin is ``gazebo_ros_control``
(``libgazebo_ros_control.so``).  The ``libgazebo_ros_skid_steer_drive.so`` and
``libgazebo_ros_planar_move.so`` blocks in ``scout_v2.gazebo`` are inside XML
comments, so this package does not bind them and does not claim the odometry
topics those comments name.

The motion command is a ``geometry_msgs/Twist`` publication on ``/cmd_vel``.
``ScoutSkidSteer`` builds ``cmd_topic_`` as ``robot_name_ + "/cmd_vel"`` and
``TwistCmdCallback`` turns ``linear.x`` and ``angular.z`` into four
``std_msgs/Float64`` wheel-velocity publications.  The callback keeps no Twist.
The launch default ``robot_namespace`` is ``/``, so the concatenated C++ string
is ``//cmd_vel``.  This package binds the absolute name ``/cmd_vel``, which is
the literal suffix on that line.  It does not cite a ROS name-cleaning
function.  If the private ``robot_namespace`` parameter is absent, the C++
default is the string ``scout_default`` and the topic is the relative name
``scout_default/cmd_vel``, which this package does not bind.

The e-stop is the Gazebo world pause of the simulator repository, cited as a
reviewed companion (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): gazebo_ros 2.8.7 (ROS 1 Melodic)
``/gazebo/pause_physics``, confirmed by ``/gazebo/get_physics_properties`` until
``pause`` is true.  That value is the World pause flag at the read-back, not a
measured standstill and not a promise that controllers stay idle.
``World::Step`` still calls ``Update`` while paused when ``stepInc`` is
positive or ``needsReset`` is true (``World.cc:691-697``), and ``SetPaused``
does not clear pending steps (``World.cc:1428-1436``).  Another client can
resume the world.  MHS does not monitor the flag afterwards.

No unpause is offered.  The four ``velocity_controllers/JointVelocityController``
entries in ``scout_v2_control.yaml`` are implemented by ``ros-controllers``,
which this clone does not contain (the Scout README installs
``ros-melodic-ros-controllers``).  A zero Twist does publish four zero
``Float64`` values from the in-repo callback, and that is all this package can
show.  It cannot show that those publications replace a held controller
setpoint, so it cannot clear a stored wheel command before an unpause
(SAFE-042).  After ``mhs.safety.reset`` the world stays paused and the operator
recovers outside MHS.

``/gazebo/model_states`` is documented in the facts only.  The package clone
never names that topic, and a command binding may not cite a companion
(``ROS_COMPANION_SCOPE``).  The topic is published from ``WorldUpdateBegin``
after the first subscriber.  That callback runs from ``World::Update``, which
still runs while paused when a step is pending or a reset is due.  The
device resource reads no topic.  The command receipt reports the values it
sent.  ``joint_states`` is not bound: the yaml names
``joint_state_controller/JointStateController`` and a publish rate, and it does
not name a topic.

No numeric velocity bound is stated for the Twist.  ``SCOUT_WHEELBASE`` and
``SCOUT_WHEEL_RADIUS`` are kinematics, and the yaml PID gains are controller
gains.  ``linear_x`` and ``angular_z`` use
:meth:`mhs.driver.Limit.operator_required`.

The fake is a ROS-free analytic stand-in, not captured traffic.  It claims F0
contract evidence.  No ROS graph, Gazebo or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Package surface (pinned ugv_gazebo_sim, Scout V2 empty world only) -----
_LAUNCH = "scout/scout_gazebo_sim/launch/scout_empty_world.launch"
_SPAWN = "scout/scout_gazebo_sim/launch/spawn_scout_v2.launch"
_CPP = "scout/scout_gazebo_sim/src/scout_skid_steer.cpp"
_NODE = "scout/scout_gazebo_sim/src/scout_skid_steer_controller.cpp"
_HPP = "scout/scout_gazebo_sim/include/scout_gazebo/scout_skid_steer.hpp"
_GAZEBO = "scout/scout_description/urdf/scout_v2.gazebo"
_YAML = "scout/scout_gazebo_sim/config/scout_v2_control.yaml"
_PKG = "scout/scout_gazebo_sim/package.xml"
_README = "scout/README.md"

# -- Companion sources (task.json companions; user decision 2026-11-05) ------
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_EMPTY = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

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

_COMPANION_FACTS = [
    Fact("The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the "
         "arguments already name it.", source="upstream_code",
         ref="companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24"),
    Fact("empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the "
         "physics engine argument -e $(arg physics).", source="upstream_code", ref=_EMPTY + ":46-48"),
    Fact("empty_world.launch defaults its physics argument to ode.", source="upstream_code", ref=_EMPTY + ":15"),
    Fact("empty_world.launch defaults its gui argument to true.", source="upstream_code", ref=_EMPTY + ":8"),
    Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
         source="upstream_code", ref=_EMPTY + ":51-54"),
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":127-128"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":147"),
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
    Fact("The API plugin advertises the relative name model_states as gazebo_msgs::ModelStates on gazebo_queue_.",
         source="upstream_code", ref=_API + ":382-388"),
    Fact("onModelStatesConnect connects publishModelStates to WorldUpdateBegin when the subscriber count becomes 1.",
         source="upstream_code", ref=_API + ":554-558"),
    Fact("publishModelStates appends each model's GetName, a pose taken from WorldPose and a twist taken from "
         "WorldLinearVel and WorldAngularVel, then publishes the ModelStates message.",
         source="upstream_code", ref=_API + ":2203-2244"),
    Fact("ModelStates.msg declares name, pose and twist arrays, and its comments call pose and twist desired.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/msg/ModelStates.msg:1-4"),
    Fact("gazebo_ros_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS_CONTROL + ":196-199"),
    Fact("gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands "
         "to the simulated joints.", source="upstream_code", ref=_ROS_CONTROL + ":211-257"),
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

_CMD_VEL_ID = "x-cap.agilexrobotics.cmd_vel.v1"

# The constructor writes the absolute-looking suffix "/cmd_vel".  The launch
# default robot_namespace is "/", so the C++ expression concatenates "//cmd_vel".
# The bound endpoint is the suffix literal.  This package does not cite ROS
# name cleaning.  linear.y is not an input: TwistCmdCallback reads only
# linear.x and angular.z (scout_skid_steer.cpp:41-42).
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "source_name": "/cmd_vel",
    "source_ref": _CPP + ":22",
    "type_ref": _CPP + ":12",
    "operation": "publish",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "angular.z": {"from": "input.angular_z"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

_LINEAR_X = Limit.operator_required(
    "the pinned Scout V2 sources state no numeric range or physical unit for cmd_vel linear.x; "
    "SCOUT_WHEELBASE and SCOUT_WHEEL_RADIUS are kinematics and the yaml PID gains are controller gains"
)
_ANGULAR_Z = Limit.operator_required(
    "the pinned Scout V2 sources state no numeric range or physical unit for cmd_vel angular.z; "
    "SCOUT_WHEELBASE and SCOUT_WHEEL_RADIUS are kinematics and the yaml PID gains are controller gains"
)


class _SentReceipt:
    """The receipt of a /cmd_vel publication also reports the components it handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees what a publication sent.  It is the
    transmitted request, not a measurement and not a claim that a JointVelocityController replaced a held setpoint.
    Every other call, the e-stop and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _CMD_VEL_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        output["sent_linear_x"] = float(values["linear_x"])
        output["sent_angular_z"] = float(values["angular_z"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class ScoutV2EmptyWorld(RosDriver):
    device_id = "scout-v2-gazebo"
    device_kind = "world.sim"
    mode = "simulated"
    # cmd_vel commands a mobile base.  The effect is confined to the simulated world.  The stop is the companion
    # gazebo_ros world pause, read back.  The card's risk_floor is R0; this binding is R2 (REVIEW.md item 12).
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeScoutV2EmptyWorld"}
    tags = ["ros", "ros1", "simulation", "gazebo", "scout", "scout-v2", "cmd-vel"]
    display_name = "AgileX Scout V2 Gazebo empty world"
    vendor = "AgileX Robotics"
    model = "Scout V2 (scout_empty_world.launch)"
    facts = [
        Fact("scout_empty_world.launch defaults robot_namespace to /.", source="upstream_code", ref=_LAUNCH + ":3"),
        Fact("scout_empty_world.launch defaults world_name to $(find scout_gazebo_sim)worlds/weston_robot_empty.world.",
             source="upstream_code", ref=_LAUNCH + ":6"),
        Fact("scout_empty_world.launch includes $(find gazebo_ros)/launch/empty_world.launch.",
             source="upstream_code", ref=_LAUNCH + ":7"),
        Fact("That include passes paused false, use_sim_time true, gui true, headless false and debug false.",
             source="upstream_code", ref=_LAUNCH + ":8-13"),
        Fact("scout_empty_world.launch includes spawn_scout_v2.launch.", source="upstream_code", ref=_LAUNCH + ":16"),
        Fact("spawn_scout_v2.launch defines arg paused with default true.",
             source="upstream_code", ref=_SPAWN + ":11"),
        Fact("spawn_model is invoked with -unpause and -model 'scout$(arg robot_namespace)'.",
             source="upstream_code", ref=_SPAWN + ":21-28"),
        Fact("spawn_scout_v2.launch loads scout_v2_control.yaml onto the parameter server.",
             source="upstream_code", ref=_SPAWN + ":31"),
        Fact("controller_spawner is started with scout_state_controller and the four scout_motor_fr, fl, rl and rr "
             "controllers.", source="upstream_code", ref=_SPAWN + ":34"),
        Fact("The scout_skid_steer_controller node sets the private robot_namespace parameter from the launch arg.",
             source="upstream_code", ref=_SPAWN + ":37-38"),
        Fact("scout_v2.gazebo loads the plugin gazebo_ros_control from libgazebo_ros_control.so.",
             source="upstream_code", ref=_GAZEBO + ":26-30"),
        Fact("The skid_steer_drive_controller block that names libgazebo_ros_skid_steer_drive.so is inside an XML "
             "comment.", source="upstream_code", ref=_GAZEBO + ":43-63"),
        Fact("The object_controller block that names libgazebo_ros_planar_move.so is inside an XML comment.",
             source="upstream_code", ref=_GAZEBO + ":65-73"),
        Fact("ScoutSkidSteer sets cmd_topic_ to robot_name_ concatenated with the literal /cmd_vel.",
             source="upstream_code", ref=_CPP + ":22"),
        Fact("ScoutSkidSteer sets the four motor command topics to robot_name_ concatenated with "
             "/scout_motor_fr_controller/command, /scout_motor_fl_controller/command, "
             "/scout_motor_rl_controller/command and /scout_motor_rr_controller/command.",
             source="upstream_code", ref=_CPP + ":18-21"),
        Fact("SetupSubscription subscribes to cmd_topic_ as geometry_msgs::Twist with queue size 5.",
             source="upstream_code", ref=_CPP + ":27-28"),
        Fact("SetupSubscription advertises four std_msgs::Float64 publishers on the motor command topics.",
             source="upstream_code", ref=_CPP + ":31-34"),
        Fact("scout_skid_steer.cpp includes geometry_msgs/Twist.h and std_msgs/Float64.h.",
             source="upstream_code", ref=_CPP + ":12-13"),
        Fact("TwistCmdCallback reads linear.x and angular.z, sets k to 1.4, and publishes four Float64 commands.",
             source="upstream_code", ref=_CPP + ":37-57"),
        Fact("The header sets SCOUT_WHEELBASE to 0.498 and SCOUT_WHEEL_RADIUS to 0.16459.",
             source="upstream_code", ref=_HPP + ":33-34"),
        Fact("The header includes geometry_msgs/Twist.h.", source="upstream_code", ref=_HPP + ":13"),
        Fact("The header declares TwistCmdCallback.", source="upstream_code", ref=_HPP + ":45"),
        Fact("scout_skid_steer_controller initialises the node name scout_odom and reads the private parameter "
             "robot_namespace with default string scout_default.", source="upstream_code", ref=_NODE + ":14-20"),
        Fact("The node then calls SetupSubscription and ros::spin.", source="upstream_code", ref=_NODE + ":24-27"),
        Fact("scout_v2_control.yaml sets scout_state_controller to joint_state_controller/JointStateController with "
             "publish_rate 50 and names no topic.", source="upstream_code", ref=_YAML + ":2-4"),
        Fact("scout_v2_control.yaml sets four controllers to velocity_controllers/JointVelocityController.",
             source="upstream_code", ref=_YAML + ":11-40"),
        Fact("scout_gazebo_sim package.xml declares the license BSD.", source="upstream_code", ref=_PKG + ":10"),
        Fact("scout_gazebo_sim package.xml buildtool_depend is catkin.", source="upstream_code", ref=_PKG + ":16"),
        Fact("scout_gazebo_sim package.xml run_depend entries include gazebo_ros and gazebo_ros_control.",
             source="upstream_code", ref=_PKG + ":24-25"),
        Fact("The Scout README names ROS Melodic on the development-environment line.",
             source="upstream_code", ref=_README + ":23"),
        Fact("The Scout README installs ros-melodic-ros-controllers with apt-get.",
             source="upstream_code", ref=_README + ":36"),
        Fact("The Scout README installs ros-melodic-gazebo-ros with apt-get.",
             source="upstream_code", ref=_README + ":42"),
        Fact("The Scout README installs ros-melodic-gazebo-ros-control with apt-get.",
             source="upstream_code", ref=_README + ":48"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "Read-back of get_physics_properties observed pause true, only the World pause flag at that call and not a "
        "measured standstill: a pending stepInc, needsReset, a manual step, a reset or a callback can still run "
        "World::Update (World.cc:691-697), SetPaused does not clear pending steps (World.cc:1428-1436), another "
        "client can resume the world, and MHS does not monitor the flag afterwards."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge fake (no Gazebo or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven fake with no physics step, pacing or controller dynamics; it is not a replay of "
                     "captured ROS traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake answers /cmd_vel and the two companion Gazebo services; it runs no Gazebo, ros_control "
            "controller or Scout dynamics",
            "a /cmd_vel publication is recorded as the transmitted Twist; the fake does not apply wheel velocities "
            "and does not claim that a JointVelocityController replaced a held setpoint",
            "TwistCmdCallback publishes four Float64 values from linear.x and angular.z with k = 1.4 "
            "(scout_skid_steer.cpp:37-57) and stores no Twist; a zero Twist therefore publishes four zeros, which "
            "is not evidence about the external velocity controllers",
            "no unpause is offered: spawn_scout_v2.launch passes -unpause to spawn_model (spawn_scout_v2.launch:25), "
            "and unpausePhysics exists in the companion (gazebo_ros_api_plugin.cpp:1668-1672); this package calls "
            "neither, because the controller source is not in the clone",
            "the stop is the companion gazebo_ros world pause; the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step",
            "publishModelStates runs from WorldUpdateBegin, which World::Update fires; Update still runs while "
            "paused when stepInc > 0 or needsReset is true (World.cc:691-697), and SetPaused does not clear "
            "stepInc (World.cc:1428-1436); /gazebo/model_states is not a command of this package "
            "(the clone never names it, and a command binding may not cite the companion)",
            "the device resource reads no topic, so a command and a reset do not wait on a silent publisher; the "
            "cmd_vel receipt reports the values it sent",
            "World::Step still calls ProcessMessages while paused, and a WorldControl multi_step runs steps while "
            "paused (World.cc:691-718 and 1462-1477); the Gazebo GUI that empty_world.launch opens by default, or "
            "any other client, can unpause or step the world; MHS does not watch the flag after the e-stop",
            "scout_skid_steer_controller runs ros::spin in its own process (scout_skid_steer_controller.cpp:27), so "
            "it can receive a Twist while Gazebo is paused; whether the external controllers apply the resulting "
            "Float64 publications is not in this clone",
            "the read-back needs the ODE engine (empty_world.launch's default physics): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and 9.19.0 releases the "
            "companion citations name; rosbridge cannot read their versions",
            "scout_empty_world.launch writes world_name as $(find scout_gazebo_sim)worlds/weston_robot_empty.world, "
            "with no slash between the package find and worlds/ (scout_empty_world.launch:6); this package does "
            "not launch Gazebo and does not patch that line",
            "the served launch is scout_empty_world.launch only; the other product directories of this repository "
            "are outside this package",
            "the joint_state_controller publish_rate is 50 and the yaml names no joint_states topic, so this "
            "package does not bind /joint_states",
        ],
    }

    # The device resource reads no topic.  model_states is published from WorldUpdateBegin, which runs from
    # World::Update, including while paused when stepInc > 0 or needsReset is true.  The clone never names that
    # topic, so it is not an explicit read either.
    commands = {_CMD_VEL_ID: _CMD_VEL}
    actions = {
        _CMD_VEL_ID: Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description="Publish geometry_msgs/Twist linear.x and angular.z on /cmd_vel. TwistCmdCallback converts "
                        "them to four Float64 wheel commands and stores no Twist. The receipt is transmission "
                        "evidence and the values sent, not a measured velocity and not a cleared controller.",
            input={
                "linear_x": Field("number", unit="1",
                                  description="Twist linear.x. The clone states no physical unit.",
                                  limit=_LINEAR_X),
                "angular_z": Field("number", unit="1",
                                   description="Twist angular.z. The clone states no physical unit.",
                                   limit=_ANGULAR_Z),
            },
            output={
                "published": Field("boolean", description="True when the rosbridge publication was transmitted"),
                "confirmed": Field("boolean",
                                   description="Always false: the command topic has no execution acknowledgement"),
                "sent_linear_x": Field("number", unit="1",
                                       description="The linear.x handed to rosbridge (the transmitted request, not "
                                                   "a measured velocity)"),
                "sent_angular_z": Field("number", unit="1",
                                        description="The angular.z handed to rosbridge (the transmitted request, not "
                                                    "a measured yaw rate)"),
            },
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back.  A failed pause or a read-back other than
    # pause true leaves the e-stop unconfirmed with the latch held.  No reset binding and no re-enable:
    # mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
