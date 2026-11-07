"""OpenMHS rosbridge driver for the WPR Gazebo mobile-robot simulation.

The pinned repository is a ROS 1 Gazebo simulation environment.  This package
is a configuration-only :class:`RosDriver`; it declares no Python native class,
does not launch Gazebo, and does not import or run the upstream C++ nodes.

The selected runtime surface is the WPR base controller that the shipped robot
models load from ``libwpr_plugin.so``:

* ``/cmd_vel`` (``geometry_msgs/Twist``) is the plugin's velocity subscription;
  its callback stores only ``linear.x``, ``linear.y`` and ``angular.z``;
* ``/odom`` (``nav_msgs/Odometry``) is the plugin's odometry publication;
* ``/wpb_home/pose_diff`` (``geometry_msgs/Pose2D``) is the pose-difference
  publication of the ``wpb_home_sim`` node in the ``wpb_home_mani`` scenario.

The plugin acknowledges nothing and the clone registers no stop service.  The
e-stop is the Gazebo world pause of the simulator's own repository, cited as a
reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic) ``/gazebo/pause_physics``,
confirmed by reading ``/gazebo/get_physics_properties`` back until ``pause`` is
true, and ``/gazebo/unpause_physics`` as the declared re-enable after a reset
(CORE-086).  Gazebo classic 11 is cited for what a paused world does not run.
The pause stops every world update, so the plugin applies no force; it is the
paused flag, not a measured standstill, and any client or the Gazebo GUI can
unpause or step the world.  The plugin keeps a stored command while paused:
the resume command first publishes a zero ``Twist`` on ``/cmd_vel`` (an
unacknowledged publication) and then unpauses.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 9c2861944205b087e55482d46911cb1819532be6; the stop, its read-back,
the re-enable and the facts about them cite the companions at their pins
(``companion:<alias>/<path>:<LINE>``).  The fake transport is ROS-free and all
of its state values are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: WPRPlugin::Load assigns the relative default names "cmd_vel" and "odom";
#: the shipped models configure the same literals through commandTopic and
#: odometryTopic.  The plugin node handle uses the empty default namespace.
_CMD_REF = "src/wpr_plugin.cpp:60"
_ODOM_REF = "src/wpr_plugin.cpp:70"

#: The generated message includes of the plugin header name the two types.
_TWIST_TYPE_REF = "include/wpr_simulation/wpr_plugin.h:49"
_ODOM_TYPE_REF = "include/wpr_simulation/wpr_plugin.h:51"

#: The plugin creates the Twist subscription and advertises Odometry.
_SUBSCRIBE_REF = "src/wpr_plugin.cpp:173-177"
_PUBLISH_REF = "src/wpr_plugin.cpp:178"

#: The callback keeps only these three components; it sends no acknowledgement.
_CALLBACK_REF = "src/wpr_plugin.cpp:237-243"

#: The update loop turns the stored components into a yaw torque and forces
#: and publishes odometry on simulated time.
_UPDATE_REF = "src/wpr_plugin.cpp:186-207"

#: The WPB Home model configures the plugin's command and odometry topics.
_MODEL_REF = "models/wpb_home.model:232-233"

#: wpb_home_sim advertises the pose-difference topic and its Pose2D type.
_POSE_DIFF_REF = "src/wpb_home_sim.cpp:166"
_POSE_DIFF_TYPE_REF = "src/wpb_home_sim.cpp:41"

#: The pose-difference loop computes x, y and theta from tf and publishes them.
_POSE_DIFF_LOOP_REF = "src/wpb_home_sim.cpp:172-187"

#: The ctrl and odom callbacks of wpb_home_sim set and broadcast /pose_reset.
_POSE_RESET_REF = "src/wpb_home_sim.cpp:117-143"

#: Only the controllers launch starts wpb_home_sim.
_SIM_NODE_LAUNCH_REF = "launch/wpb_home_controllers.launch:23"

#: The scenario launch starts Gazebo unpaused and with simulated time.
_LAUNCH_REF = "launch/wpb_simple.launch:5-7"

#: The sim node subscribes to the base odometry and the manipulation topics.
_SIM_SUBS_REF = "src/wpb_home_sim.cpp:163-165"

#: UpdateChild hangs on the world-update event; the plugin serves its callbacks on its own wall-clock queue thread.
_UPDATE_HOOK_REF = "src/wpr_plugin.cpp:182"
_QUEUE_THREAD_REF = "src/wpr_plugin.cpp:245-251"

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
#: The re-enable capability and the zero command it publishes before the unpause.
_RESUME_ID = "x-cap.6-robot.resume.v1"
_CMD_VEL_ID = "x-cap.6-robot.cmd_vel.v1"
_ZERO_TWIST = {"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0}

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


_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector; the clone states no physical unit for this odometry field",
    properties={
        "x": Field("number", unit="1", description="x component of the ROS vector"),
        "y": Field("number", unit="1", description="y component of the ROS vector"),
        "z": Field("number", unit="1", description="z component of the ROS vector"),
    },
)

_QUATERNION = Field(
    "object",
    description="Orientation quaternion from the odometry pose",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose.pose of the simulated WPR base",
    properties={
        "position": _VECTOR3,
        "orientation": _QUATERNION,
    },
)

_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist.twist of the simulated WPR base",
    properties={
        "linear": _VECTOR3,
        "angular": _VECTOR3,
    },
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
    "sent_linear_x": Field("number", unit="1", description="The linear.x handed to rosbridge (the transmitted "
                                                            "request, not a measured velocity)"),
    "sent_linear_y": Field("number", unit="1", description="The linear.y handed to rosbridge (the transmitted "
                                                            "request, not a measured velocity)"),
    "sent_angular_z": Field("number", unit="1", description="The angular.z handed to rosbridge (the transmitted "
                                                             "request, not a measured yaw rate)"),
}

#: The clone states no numeric velocity range or physical unit for the Twist
#: components, so every component is an operator-supplied deployment bound.
#: A site envelope is still not a stop; the missing stop is the package blocker.
_LINEAR_X = Limit.operator_required(
    "the pinned plugin and its text state no numeric range or physical unit for cmd_vel linear.x; "
    "the operator supplies the deployment envelope")
_LINEAR_Y = Limit.operator_required(
    "the pinned plugin and its text state no numeric range or physical unit for cmd_vel linear.y; "
    "the operator supplies the deployment envelope")
_ANGULAR_Z = Limit.operator_required(
    "the pinned plugin and its text state no numeric range or physical unit for cmd_vel angular.z; "
    "the operator supplies the deployment envelope")

_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_REF,
    "type_ref": _TWIST_TYPE_REF,
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

_ODOM_READ = {
    "topic": "/odom",
    "type": "nav_msgs/Odometry",
    "operation": "subscribe",
    "source_name": "odom",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose", "twist": "output.twist.twist"}},
}

_POSE_DIFF_READ = {
    "topic": "/wpb_home/pose_diff",
    "type": "geometry_msgs/Pose2D",
    "operation": "subscribe",
    "source_name": "/wpb_home/pose_diff",
    "source_ref": _POSE_DIFF_REF,
    "type_ref": _POSE_DIFF_TYPE_REF,
    "result": {"map": {"x": "output.x", "y": "output.y", "theta": "output.theta"}},
}


class _ZeroBeforeResume:
    """The declared re-enable (CORE-086) publishes a zero Twist on /cmd_vel before it unpauses the world.

    The receipt of a cmd_vel publication also reports the three components it handed to rosbridge (the
    transmitted request): the device resource reads no topic (a paused world publishes none), so the receipt is
    where a caller sees what a publication sent.

    WPRPlugin stores the last cmd_vel and applies it at every world update with no command timeout
    (src/wpr_plugin.cpp:186-207, 237-243), and its callbacks still run while the world is paused
    (src/wpr_plugin.cpp:245-251), so an unpause alone would resume a command stored before or during the pause
    (SAFE-042). The zero replaces it. It is a topic publication: unacknowledged, handled on the plugin's own queue
    thread, so it is not confirmed before the world runs again. A failed zero publication fails the resume before
    the unpause is sent. Every other call, the e-stop and the reset included, goes to the SDK bridge unchanged.
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
        for key in ("linear_x", "linear_y", "angular_z"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class WprSimulation(RosDriver):
    device_id = "wpr-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    # The command drives a mobile base, so the binding is R2 even though its
    # effect is confined to the simulated world.  The stop is the Gazebo world
    # pause of the companion gazebo_ros (task.json companions), read back.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeWprSimulation"}
    tags = ["ros", "ros1", "simulation", "gazebo", "wpr", "wpb-home", "cmd-vel", "odometry"]
    display_name = "WPR Gazebo mobile-robot simulation"
    vendor = "6-robot"
    model = "WPRPlugin (libwpr_plugin.so) and wpb_home_sim"
    facts = [
        Fact("WPRPlugin::Load assigns the default command topic literal \"cmd_vel\" to command_topic_.",
             source="upstream_code", ref=_CMD_REF),
        Fact("WPRPlugin::Load assigns the default odometry topic literal \"odom\" to odometry_topic_.",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The plugin header includes the generated geometry_msgs/Twist and nav_msgs/Odometry headers.",
             source="upstream_code", ref="include/wpr_simulation/wpr_plugin.h:49-51"),
        Fact("The plugin creates a geometry_msgs::Twist subscriber on command_topic_ and advertises a "
             "nav_msgs::Odometry publisher on odometry_topic_.", source="upstream_code",
             ref="src/wpr_plugin.cpp:173-178"),
        Fact("WPRPlugin::cmdVelCallback stores linear.x, linear.y and angular.z in x_, y_ and rot_ under the "
             "plugin lock and sends no acknowledgement.", source="upstream_code", ref=_CALLBACK_REF),
        Fact("On every world update WPRPlugin::UpdateChild adds a yaw torque from the difference between the "
             "world yaw rate and rot_ and relative forces from x_ and y_ minus the relative linear velocity, "
             "each times its p gain, and publishes odometry when more than 1/odometry_rate_ of simulated time "
             "has passed.", source="upstream_code", ref=_UPDATE_REF),
        Fact("The shipped wpb_home.model configures the WPR plugin with commandTopic cmd_vel and "
             "odometryTopic odom and no robotNamespace override.", source="upstream_code", ref=_MODEL_REF),
        Fact("wpb_home_sim advertises the absolute /wpb_home/pose_diff topic with the geometry_msgs::Pose2D "
             "type.", source="upstream_code", ref=_POSE_DIFF_REF),
        Fact("In a 20 Hz loop, when the /pose_reset to /base_footprint transform is available within 1 s, "
             "wpb_home_sim publishes pose_diff with x and y set to 0.9 times that transform's translation and "
             "theta set to its yaw minus pose_reset.theta.", source="upstream_code", ref=_POSE_DIFF_LOOP_REF),
        Fact("wpb_home_sim subscribes to /wpb_home/mani_ctrl, /wpb_home/ctrl and /odom.",
             source="upstream_code", ref=_SIM_SUBS_REF),
        Fact("A /wpb_home/ctrl message containing 'pose_diff reset' sets pose_reset to the current odometry "
             "pose, and every /odom message re-broadcasts the /odom to /pose_reset transform.",
             source="upstream_code", ref=_POSE_RESET_REF),
        Fact("wpb_home_controllers.launch starts the wpb_home_sim node.", source="upstream_code",
             ref=_SIM_NODE_LAUNCH_REF),
        Fact("The shipped wpb_simple.launch starts the Gazebo empty_world include with paused=false and "
             "use_sim_time=true.", source="upstream_code", ref=_LAUNCH_REF),
        Fact("WPRPlugin connects UpdateChild to the world-update begin event.", source="upstream_code",
             ref=_UPDATE_HOOK_REF),
        Fact("WPRPlugin::QueueThread serves the plugin's callback queue with a 0.01 s wall-clock wait while the "
             "plugin is alive and its node handle is ok.", source="upstream_code", ref=_QUEUE_THREAD_REF),
        Fact("wpb_simple.launch includes gazebo_ros's empty_world.launch.", source="upstream_code",
             ref="launch/wpb_simple.launch:3-10"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so "
        "WPRPlugin applies no force and /odom is silent; it is the paused flag, not a measured standstill, and it "
        "holds until the resume command, the Gazebo GUI or another client unpauses the world (a GUI step advances "
        "it), and the plugin keeps its stored cmd_vel, which the resume zeroes first without an acknowledgement."
    )
    #: The fake is a ROS-free canned transport; it is not a recording of a live
    #: Gazebo session and it runs no physics.  It claims only the wire contract.
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no physics step, pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /cmd_vel, /odom and "
            "/wpb_home/pose_diff endpoints and the three companion Gazebo services and runs no Gazebo physics, "
            "WPRPlugin controller, wpb_home_sim node or wall-clock loop",
            "odometry and pose-difference samples are placeholders and do not establish a trajectory, "
            "sensor frame, collision state or timing",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets, /gazebo/get_physics_properties reports and /gazebo/unpause_physics clears; "
            "it runs no Gazebo World::Step, and its GetPhysicsProperties numbers are placeholders",
            "while paused, a live Gazebo runs no world update, so /odom (published from UpdateChild) and /clock "
            "are silent and an odometry read fails NOT_READY after its 2 s timeout; the fake silences /odom while "
            "its flag is set, the same way",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, "
            "by a WorldControl message or by any ROS client; MHS does not watch the flag after the e-stop "
            "(safety_status re-reads it only on request)",
            "the read-back needs the ODE engine (empty_world.launch's default): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held; a graph "
            "without gazebo_ros has neither service",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name; rosbridge cannot read their versions",
            "the resume publishes a zero Twist before the unpause; it is unacknowledged and the plugin handles it on "
            "its own queue thread, so the stored command may act for a few world steps before it is replaced, and "
            "any other publisher of /cmd_vel (a teleop or navigation node) can store a new command at any time",
            "the shipped Gazebo world and robot model are deployment choices; the declaration assumes the "
            "root namespace used by the shipped wpb_simple/wpb_home_mani launch files",
            "WPRPlugin has no command timeout: it applies the last stored x_, y_ and rot_ at every world "
            "update (wpr_plugin.cpp:186-207, 237-243), so one MHS publication keeps the simulated base moving "
            "until another command arrives",
            "/wpb_home/pose_diff is published only by wpb_home_sim, which only wpb_home_controllers.launch "
            "starts (included by wpb_home_mani, wpb_scene_1 and wpb_table, not by wpb_simple.launch); a "
            "reviewer probe with that topic silent showed mhs.resource.read failing NOT_READY after 2 s and "
            "each command waiting 2 s, so the reviewer removed pose_diff from the resource and kept it only as "
            "the explicit read capability; /odom left the resource for the same reason once the e-stop became "
            "the world pause (the device resource reads no topic, and the cmd_vel receipt reports the values it "
            "sent)",
            "pose_diff passes an upstream convention through unchanged: x and y are 0.9 times the "
            "/pose_reset to /base_footprint translation (wpb_home_sim.cpp:181-182), measured from the frame of "
            "the last 'pose_diff reset' message; before the first reset that frame comes from a "
            "default-constructed static tf::Transform (wpb_home_sim.cpp:57)",
        ],
    }

    #: The device resource reads no topic: /odom (published from UpdateChild) and /wpb_home/pose_diff are silent
    #: while the e-stop holds the world paused, and a resource that waited for them would fail NOT_READY after
    #: every reset and delay every command by its timeout.  Both stay explicit read capabilities below.
    commands = {
        _CMD_VEL_ID: _CMD_VEL,
        "x-cap.6-robot.odometry.v1": _ODOM_READ,
        "x-cap.6-robot.pose_diff.v1": _POSE_DIFF_READ,
        _RESUME_ID: _RESUME,
    }
    actions = {
        "x-cap.6-robot.cmd_vel.v1": Action(
            name="publish_cmd_vel",
            verb="invoke",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint on /cmd_vel. The WPRPlugin callback "
                "stores the components, also while the world is paused; the receipt is transmission evidence "
                "and the values sent, not motion or stopping."
            ),
            input={
                "linear_x": Field("number", unit="1", description="Twist linear.x component",
                                  limit=_LINEAR_X),
                "linear_y": Field("number", unit="1", description="Twist linear.y component",
                                  limit=_LINEAR_Y),
                "angular_z": Field("number", unit="1", description="Twist angular.z component",
                                   limit=_ANGULAR_Z),
            },
            output=_PUBLISHED,
            risk="R2",
        ),
        "x-cap.6-robot.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description=(
                "Read one fresh nav_msgs/Odometry publication from the WPR plugin's /odom topic; a "
                "subscription sample is required, no cached value is returned."
            ),
            output={"pose": _POSE, "twist": _TWIST},
        ),
        "x-cap.6-robot.pose_diff.v1": Action(
            name="read_pose_diff",
            verb="read",
            description=(
                "Read one fresh geometry_msgs/Pose2D pose-difference publication from wpb_home_sim on "
                "/wpb_home/pose_diff."
            ),
            output={"x": Field("number", unit="1", description="Pose-difference x"),
                    "y": Field("number", unit="1", description="Pose-difference y"),
                    "theta": Field("number", unit="rad", description="Pose-difference yaw")},
        ),
        _RESUME_ID: Action(
            name="resume_simulation",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: publish a zero Twist on /cmd_vel, then unpause the "
                "Gazebo world with /gazebo/unpause_physics. WPRPlugin keeps the last cmd_vel it stored and applies "
                "it as soon as the world runs; the zero replaces it, but it is an unacknowledged publication, so a "
                "stored command can still act for a few world steps."
            ),
            output={
                "acknowledged": Field("boolean", description="True once /gazebo/unpause_physics answered"),
                "zero_command_published": Field(
                    "boolean", description="True when the zero Twist was handed to rosbridge before the unpause; "
                                           "a transmission, not a confirmation"),
            },
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding: mhs.safety.reset releases the latch only; the declared resume is the new start (CORE-086).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _ZeroBeforeResume(super().make_bridge(native))
