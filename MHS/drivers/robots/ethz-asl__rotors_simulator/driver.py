"""OpenMHS rosbridge driver for the RotorS Gazebo MAV simulator (gh.ethz-asl/rotors_simulator).

The pinned upstream is a ROS 1 / Gazebo simulator made of C++ Gazebo plugins
and controller nodes.  This package is a configuration-only :class:`RosDriver`
over rosbridge; it declares no Python native class, does not launch Gazebo and
neither imports nor runs the clone's nodes or plugins.

Its surface is what the pinned clone names:

* ``/firefly/odometry_sensor1/odometry`` (``nav_msgs/Odometry``) is the
  generic odometry sensor mounted by the hovering launch;
* ``/firefly/imu`` (``sensor_msgs/Imu``) is the ADIS16448 IMU mounted by the
  firefly model.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source fetched at a pinned commit (user decision and
authorisation of 2026-11-05; ``task.json`` ``companions`` with ``lock``):
gazebo_ros 2.5.21 (ROS 1 Kinetic) ``/gazebo/pause_physics``, confirmed by
reading ``/gazebo/get_physics_properties`` back until ``pause`` is true; Gazebo
7.16.1 is cited for what a paused world does not run.  The pause stops every
world update, so the motor model applies no rotor force; it is the paused flag,
not a measured standstill.

No unpause is offered.  The world resumes the clone's lee position controller
waypoint and the motor model's last rotor-speed reference when it is unpaused,
and this package commands neither, so it cannot clear them first (the
orchestrator's SAFE-042 condition): after ``mhs.safety.reset`` the world stays
paused, and the operator recovers outside MHS (see ``safe_state``).  The
earlier ``x-cap.ethz-asl.sim_start.v1`` (the same unpause) was removed for that
reason.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at ``cd813b7a8c375d677352aa20ad20047feb661126``; the stop, its read-back
and the facts about them cite the companions at their pins
(``companion:<alias>/<path>:<LINE>``).  The fake transport is ROS-free; no ROS
graph, Gazebo process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references (paths are relative to the clone root)
# ---------------------------------------------------------------------------

_README_SIM = "README.md:4"
_README_SENSORS = "README.md:7"
_README_PAUSED = "README.md:145-150"
_UNPAUSE_CALL = "rotors_gazebo/src/hovering_example.cpp:41-50"
_WAYPOINT = "rotors_gazebo/src/hovering_example.cpp:60-82"
_LAUNCH_DEFAULT = "rotors_gazebo/launch/mav_hovering_example.launch:2-35"
_LAUNCH_EMPTY_WORLD = "rotors_gazebo/launch/mav_hovering_example.launch:16-22"
_LAUNCH_HOVERING = "rotors_gazebo/launch/mav_hovering_example.launch:37"
_SPAWN_NAMESPACE = "rotors_gazebo/launch/spawn_mav.launch:5"
_SPAWN_PASS = "rotors_gazebo/launch/spawn_mav.launch:26"
_ROS_NODE_HANDLE = "rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:71-72"
_ROS_ADVERTISE = "rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:147-148"
_ODOM_MACRO = "rotors_description/urdf/mav_generic_odometry_sensor.gazebo:27-35"
_ODOM_PLUGIN = "rotors_gazebo_plugins/src/gazebo_odometry_plugin.cpp:574-583"
_ODOM_UPDATE = "rotors_gazebo_plugins/src/gazebo_odometry_plugin.cpp:231-232"
_ODOM_CONVERT = "rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:235-237"
_ODOM_TYPE = "rotors_gazebo_plugins/include/rotors_gazebo_plugins/gazebo_ros_interface_plugin.h:68"
_IMU_DEFAULT = "rotors_description/urdf/component_snippets.xacro:848-854"
_IMU_PLUGIN = "rotors_gazebo_plugins/src/gazebo_imu_plugin.cpp:350-357"
_IMU_CONVERT = "rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:203-205"
_IMU_TYPE = "rotors_gazebo_plugins/include/rotors_gazebo_plugins/gazebo_ros_interface_plugin.h:71"
_MOTOR_UPDATE = "rotors_gazebo_plugins/src/gazebo_motor_model.cpp:202-203"
_MOTOR_ON_UPDATE = "rotors_gazebo_plugins/src/gazebo_motor_model.cpp:212-226"
_MOTOR_REFERENCE = "rotors_gazebo_plugins/src/gazebo_motor_model.cpp:344-348"
_CONTROLLER_WAYPOINT = "rotors_control/src/nodes/lee_position_controller_node.cpp:144-146"
_CONTROLLER_ODOMETRY = "rotors_control/src/nodes/lee_position_controller_node.cpp:173-192"
_WORLD_PHYSICS = "rotors_gazebo/worlds/basic.world:22"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.5.21 (ROS 1 Kinetic) at 98bb3d0a, fetched under work/companions: the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 7.16.1 at 6fea5977, fetched under work/companions: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
_PAUSE = {
    "service": "/gazebo/pause_physics",
    "type": "std_srvs/Empty",
    "source_name": "pause_physics",
    "source_ref": _API + ":469-475",
    "type_ref": _API + ":471",
    "state_ref": _API + ":1692-1696",
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
    "source_ref": _API + ":360-366",
    "type_ref": _API + ":362",
    "state_ref": _API + ":1460",
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
    Fact("empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the "
         "physics engine argument -e $(arg physics).", source="upstream_code", ref=_LAUNCH + ":42-44"),
    Fact("empty_world.launch defaults its physics argument to ode.", source="upstream_code", ref=_LAUNCH + ":15"),
    Fact("empty_world.launch defaults its gui argument to true.", source="upstream_code", ref=_LAUNCH + ":8"),
    Fact("When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient.",
         source="upstream_code", ref=_LAUNCH + ":47-50"),
    Fact("The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet.",
         source="upstream_code", ref=_API + ":122-123"),
    Fact("The API plugin creates its node handle in the private namespace ~ and advertises its topics and services "
         "there.", source="upstream_code", ref=_API + ":141"),
    Fact("The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback "
         "queue gazebo_queue_.", source="upstream_code", ref=_API + ":469-475"),
    Fact("The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties "
         "type on gazebo_queue_.", source="upstream_code", ref=_API + ":360-366"),
    Fact("gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is "
         "ok.", source="upstream_code", ref=_API + ":237-244"),
    Fact("pausePhysics calls world_->SetPaused(true) and returns true.", source="upstream_code",
         ref=_API + ":1692-1696"),
    Fact("unpausePhysics calls world_->SetPaused(false) and returns true.", source="upstream_code",
         ref=_API + ":1698-1702"),
    Fact("getPhysicsProperties sets res.pause to world_->IsPaused().", source="upstream_code", ref=_API + ":1460"),
    Fact("getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it "
         "sets success false and returns false.", source="upstream_code", ref=_API + ":1467-1499"),
    Fact("The GetPhysicsProperties response field pause is true if the physics engine is paused.",
         source="upstream_code", ref="companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4"),
    Fact("Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the "
         "API plugin connects publishSimTime.", source="upstream_code", ref=_API + ":199-202"),
    Fact("World::Step advances simulation time and calls Update only when the world is not paused, a step increment "
         "is pending or a reset is due; otherwise it adds the step to the pause time.", source="upstream_code",
         ref=_WORLD + ":615-634"),
    Fact("World::Step holds worldUpdateMutex while it steps the world.", source="upstream_code",
         ref=_WORLD + ":607"),
    Fact("World::SetPaused stores the paused flag under worldUpdateMutex.", source="upstream_code",
         ref=_WORLD + ":1306-1314"),
    Fact("World::IsPaused returns the stored paused flag.", source="upstream_code", ref=_WORLD + ":1300-1303"),
    Fact("World::Update fires the worldUpdateBegin event and then updates every model.", source="upstream_code",
         ref=_WORLD + ":690-695"),
    Fact("World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed "
         "on every step, paused or not.", source="upstream_code", ref=_WORLD + ":615-637"),
    Fact("A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the "
         "number of steps to run while paused.", source="upstream_code", ref=_WORLD + ":1340-1355"),
]

# ---------------------------------------------------------------------------
# ROS message fields
# ---------------------------------------------------------------------------

_VECTOR3 = Field(
    "object",
    description="Three-component ROS vector field; the clone states no physical unit for this raw message value",
    properties={
        "x": Field("number", unit="1", description="x component of the raw ROS vector"),
        "y": Field("number", unit="1", description="y component of the raw ROS vector"),
        "z": Field("number", unit="1", description="z component of the raw ROS vector"),
    },
)

_QUATERNION = Field(
    "object",
    description="ROS orientation quaternion; the clone states no physical unit for this raw message value",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_ODOMETRY = {
    "topic": "/firefly/odometry_sensor1/odometry",
    "type": "nav_msgs/Odometry",
    "source_name": "odometry_sensor1/odometry",
    "source_ref": _ODOM_MACRO,
    "type_ref": _ODOM_TYPE,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"pose": "pose.pose", "twist": "twist.twist"}},
    "timeout_ms": 2000,
}

_IMU = {
    "topic": "/firefly/imu",
    "type": "sensor_msgs/Imu",
    "source_name": "imu",
    "source_ref": _IMU_DEFAULT,
    "type_ref": _IMU_TYPE,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "orientation": "orientation",
        "angular_velocity": "angular_velocity",
        "linear_acceleration": "linear_acceleration",
    }},
    "timeout_ms": 2000,
}


class RotorsSimulator(RosDriver):
    device_id = "rotors_simulator"
    device_kind = "world.sim"
    mode = "simulated"
    #: Only state observations and the world pause are exposed; no MAV motion command is declared, so this is R0
    #: simulated state (MHS-004 R0).
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeRotorsSimulator"}
    tags = ["ros", "ros1", "simulation", "gazebo", "rotors", "mav", "odometry", "imu"]
    display_name = "RotorS Gazebo MAV simulator"
    vendor = "ethz-asl"
    model = "RotorS Gazebo MAV models"
    facts = [
        Fact("The README describes RotorS as a MAV Gazebo simulator.",
             source="vendor_doc", ref=_README_SIM),
        Fact("The README lists a simulated IMU and a generic odometry sensor among the sensors that can be "
             "mounted on the multirotor.", source="vendor_doc", ref=_README_SENSORS),
        Fact("The README states the simulator starts by default in paused mode and documents the Gazebo GUI play "
             "button or a rosservice call to gazebo/unpause_physics as the ways to start it.",
             source="vendor_doc", ref=_README_PAUSED),
        Fact("hovering_example.cpp calls the absolute /gazebo/unpause_physics service with an empty std_srvs::Empty "
             "request and retries the call while it returns false.", source="upstream_code", ref=_UNPAUSE_CALL),
        Fact("After unpausing, hovering_example.cpp waits 5 s and publishes one MultiDOFJointTrajectory waypoint, "
             "by default the position (0, 0, 1) with yaw 0.", source="upstream_code", ref=_WAYPOINT),
        Fact("The hovering launch defaults mav_name to firefly, starts Gazebo with paused=true, places the "
             "spawned MAV and the controller in the firefly namespace, and remaps the controller's odometry "
             "topic to odometry_sensor1/odometry.", source="upstream_code", ref=_LAUNCH_DEFAULT),
        Fact("The hovering launch includes gazebo_ros's empty_world.launch with its world, paused and gui "
             "arguments.", source="upstream_code", ref=_LAUNCH_EMPTY_WORLD),
        Fact("The hovering launch starts the hovering_example node.", source="upstream_code", ref=_LAUNCH_HOVERING),
        Fact("spawn_mav.launch defaults namespace to mav_name.", source="upstream_code", ref=_SPAWN_NAMESPACE),
        Fact("spawn_mav.launch passes namespace into the xacro namespace argument.",
             source="upstream_code", ref=_SPAWN_PASS),
        Fact("GazeboRosInterfacePlugin creates its ROS node handle at the root namespace.",
             source="upstream_code", ref=_ROS_NODE_HANDLE),
        Fact("GazeboRosInterfacePlugin advertises each connected ROS topic on that root node handle.",
             source="upstream_code", ref=_ROS_ADVERTISE),
        Fact("The generic odometry macro passes the robot namespace and odometry_topic "
             "odometry_sensor1/odometry to the odometry plugin.",
             source="upstream_code", ref=_ODOM_MACRO),
        Fact("gazebo_odometry_plugin advertises the Gazebo odometry topic as ~/<namespace>/<odometry topic> and "
             "connects the ROS topic <namespace>/<odometry topic>.", source="upstream_code", ref=_ODOM_PLUGIN),
        Fact("gazebo_odometry_plugin connects its OnUpdate to the world-update begin event.",
             source="upstream_code", ref=_ODOM_UPDATE),
        Fact("GazeboRosInterfacePlugin converts gz_geometry_msgs::Odometry to nav_msgs::Odometry for the "
             "connected ROS odometry topic.", source="upstream_code", ref=_ODOM_CONVERT),
        Fact("The ROS interface plugin includes nav_msgs/Odometry.h.", source="upstream_code", ref=_ODOM_TYPE),
        Fact("The default IMU macro passes imu_topic imu to the IMU plugin.",
             source="upstream_code", ref=_IMU_DEFAULT),
        Fact("gazebo_imu_plugin advertises the Gazebo IMU topic as ~/<namespace>/<imu topic> and connects the "
             "ROS topic <namespace>/<imu topic>.", source="upstream_code", ref=_IMU_PLUGIN),
        Fact("GazeboRosInterfacePlugin converts gz_sensor_msgs::Imu to sensor_msgs::Imu for the connected ROS "
             "IMU topic.", source="upstream_code", ref=_IMU_CONVERT),
        Fact("The ROS interface plugin includes sensor_msgs/Imu.h.", source="upstream_code", ref=_IMU_TYPE),
        Fact("The motor model connects its OnUpdate to the world-update begin event.", source="upstream_code",
             ref=_MOTOR_UPDATE),
        Fact("The motor model's OnUpdate computes the sampling time from the simulation time and applies the rotor "
             "forces and moments.", source="upstream_code", ref=_MOTOR_ON_UPDATE),
        Fact("For a velocity motor the motor model stores the commanded rotor speed, capped at its maximum, as its "
             "reference input.", source="upstream_code", ref=_MOTOR_REFERENCE),
        Fact("The lee position controller node sets the first point of a received trajectory as its controller's "
             "trajectory point.", source="upstream_code", ref=_CONTROLLER_WAYPOINT),
        Fact("The lee position controller node computes rotor velocities and publishes them only from its odometry "
             "callback.", source="upstream_code", ref=_CONTROLLER_ODOMETRY),
        Fact("The clone's basic world selects the ODE physics engine.", source="upstream_code", ref=_WORLD_PHYSICS),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so the "
        "motor model applies no rotor force and odometry and IMU are silent; it is the paused flag, not a measured "
        "standstill. No unpause is offered: an operator restarts or re-commands the controller and unpauses outside "
        "MHS (README.md:145-150)."
    )
    fidelity = {
        "engine": "analytic:ROS-free recording fake for the Gazebo ROS contract (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no Gazebo physics, controller, sensor model or "
                     "wall-clock pacing; placeholder samples do not establish trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free ros_transport handler: it answers the odometry and IMU subscriptions and the two "
            "companion Gazebo services and records them, but it runs no Gazebo world, physics engine, plugin, "
            "controller or wall-clock loop",
            "every odometry, IMU and GetPhysicsProperties value is a placeholder; a live run needs the operator's "
            "RotorS Gazebo graph and rosbridge endpoint",
            "the fake starts running so the observations can be exercised; the documented upstream default is "
            "paused (the hovering launch's paused=true, unpaused by hovering_example), and that startup is not "
            "modelled as evidence",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step",
            "while paused, a live Gazebo runs no world update, so odometry and IMU (published from the plugins' "
            "world-update callbacks) and /clock are silent and both reads fail NOT_READY after their 2 s timeout; "
            "the fake silences them while its flag is set",
            "no unpause is offered: unpausing resumes the lee position controller's last waypoint (by default the "
            "hover point hovering_example published) and the motor model's last rotor-speed reference, which this "
            "package does not command and cannot clear first; the operator recovers outside MHS by restarting or "
            "re-commanding the controller and then unpausing with the Gazebo GUI or rosservice call "
            "gazebo/unpause_physics (README.md:145-150)",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, by "
            "a WorldControl message, by hovering_example (at its start) or by any ROS client; MHS does not watch the "
            "flag after the e-stop (safety_status re-reads it only on request)",
            "the read-back needs the ODE engine (the clone's worlds and empty_world.launch's default): with another "
            "engine get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.5.21 (Kinetic) and 7.16.1 releases the "
            "companion citations name; rosbridge cannot read their versions",
            "the /firefly namespace is the documented default of the hovering launch; a deployment that changes "
            "mav_name or uses another launch must expose the resolved endpoints",
            "ROS parameters, QoS, namespaces, remapping, TF, cameras, the VI sensor, the MAVLink interface, the "
            "trajectory and motor-speed command topics and all other RotorS plugins are NOT COVERED",
        ],
    }

    commands = {
        "x-cap.ethz-asl.odometry.v1": _ODOMETRY,
        "x-cap.ethz-asl.imu.v1": _IMU,
    }
    actions = {
        "x-cap.ethz-asl.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one nav_msgs/Odometry sample from the firefly odometry sensor topic (silent, and "
                        "NOT_READY, while the world is paused)",
            output={"pose": Field(
                        "object",
                        description="nav_msgs/Odometry pose.pose of the simulated MAV",
                        properties={"position": _VECTOR3, "orientation": _QUATERNION}),
                    "twist": Field(
                        "object",
                        description="nav_msgs/Odometry twist.twist of the simulated MAV",
                        properties={"linear": _VECTOR3, "angular": _VECTOR3})},
        ),
        "x-cap.ethz-asl.imu.v1": Action(
            name="read_imu",
            verb="read",
            description="Read one sensor_msgs/Imu sample from the firefly IMU topic (silent, and NOT_READY, while "
                        "the world is paused)",
            output={"orientation": _QUATERNION,
                    "angular_velocity": _VECTOR3,
                    "linear_acceleration": _VECTOR3},
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
