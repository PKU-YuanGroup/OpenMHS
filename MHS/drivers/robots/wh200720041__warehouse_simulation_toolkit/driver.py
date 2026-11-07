"""OpenMHS rosbridge driver for the warehouse_simulation_toolkit Gazebo environment.

The pinned repository is a ROS 1 catkin package that supplies a Gazebo world,
a Pioneer 3DX robot model, a 2-D laser, an IMU and a keyboard teleop.  The
teleop is the only C++ node in the clone.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class, starts no
Gazebo process and imports no ROS code.

The clone's only in-package command endpoint is the relative ``cmd_vel``
publication of the teleop (``src/key_control.cpp:178``).  The robot model
configures the Gazebo differential-drive plugin to subscribe to that topic
(``urdf/pioneer3dx_body.xacro:331``).  The package registers no acknowledged
stop service or action, and a zero-velocity publication is not an acknowledged
stop.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic, the README's ``ROS Noetic``)
``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true.  That flag is
``world_->IsPaused()``.  Ordinary ``World::Step`` updates are suspended while
it is true, except when ``stepInc`` is greater than 0 or a reset is due
(``World.cc:835-837``).  The read-back does not prove those exceptions did not
run, and it is not a measured standstill.  Another client can unpause the
world; MHS does not read the flag again.

No unpause is offered.  ``cmdVelCallback`` stores ``linear.x`` and ``angular.z``
with no timeout (``gazebo_ros_diff_drive.cpp:335-340``).  Stopping publishers
does not clear the stored ``x_`` and ``rot_``, and ``UpdateChild`` applies them
again when updates resume (``:269-289``, ``:324-333``).  Publishing zero can
replace those fields, but the publication is unacknowledged and is not proof
they are clear.  The shipped launch starts ``move_base`` at the root namespace
with ``respawn="true"``; this package cannot cancel it.  Before any manual
unpause the operator prevents that respawn and clears or reinitializes the
retained command outside MHS (see ``safe_state``).  After ``mhs.safety.reset``
the latch is released and the world stays paused.  The device resource reads
no topic, and the cmd_vel receipt reports the two values it sent.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 18df8ce6dde61711e0705f3bd872465a01bd01a2; the stop, its read-back and
the facts about them cite the companions at their pins.  The fake is a
ROS-free canned transport; no ROS graph, Gazebo process or hardware is
contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: TeleopTurtle advertises geometry_msgs::Twist on the relative topic "cmd_vel".
_CMD_VEL_REF = "src/key_control.cpp:178"

#: geometry_msgs/Twist is included at the top of the teleop source.
_TWIST_TYPE_REF = "src/key_control.cpp:2"

#: The Gazebo differential-drive plugin subscribes to commandTopic cmd_vel.
_PLUGIN_REF = "urdf/pioneer3dx_body.xacro:320-341"

#: The teleop's key loop publishes the scaled Twist only after a key change.
_TELEOP_LOOP_REF = "src/key_control.cpp:227-269"

#: The constructor's scale defaults are teleop settings, not device bounds.
_SCALE_REF = "src/key_control.cpp:170-176"

#: The clone builds one executable; there is no stop node or server target.
_BUILD_REF = "CMakeLists.txt:30-31"

#: The shipped launch starts Gazebo, gmapping, move_base and RViz.
_LAUNCH_REF = "launch/warehouse_simulation.launch:8-67"

#: The key_control node block is commented out in the shipped launch.
_KEY_NODE_REF = "launch/warehouse_simulation.launch:25-27"

#: The laser and IMU are model sensors, not command channels.
_LASER_REF = "urdf/pioneer3dx_body.xacro:253-282"
_IMU_REF = "urdf/pioneer3dx_body.xacro:231-246"
_COSTMAP_SCAN_REF = "param/costmap_common_params.yaml:19-22"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.9.3 (ROS 1 Noetic) at cd9cc952: the API plugin serves the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 11.15.1 at b22c6e15: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"
#: The gazebo_ros differential-drive plugin (companion gazebo_ros_pkgs) that the Pioneer 3DX xacro loads.
_DIFF_DRIVE = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp"

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
_DIFF_DRIVE_FACTS = [
    Fact("GazeboRosDiffDrive subscribes to its command topic with cmdVelCallback on the plugin's own callback "
         "queue.", source="upstream_code", ref=_DIFF_DRIVE + ":159-164"),
    Fact("GazeboRosDiffDrive connects UpdateChild to the world-update begin event.", source="upstream_code",
         ref=_DIFF_DRIVE + ":177-179"),
    Fact("When seconds_since_last_update is greater than update_period_, UpdateChild calls getWheelVelocities and, "
         "when wheel_accel is 0 or a wheel is within 0.01 of its target speed, sets both wheel joint velocities.",
         source="upstream_code", ref=_DIFF_DRIVE + ":269-289"),
    Fact("getWheelVelocities derives both wheel speeds from the stored x_ and rot_.", source="upstream_code",
         ref=_DIFF_DRIVE + ":324-333"),
    Fact("cmdVelCallback stores linear.x in x_ and angular.z in rot_.", source="upstream_code",
         ref=_DIFF_DRIVE + ":335-340"),
    Fact("QueueThread serves the plugin's callback queue with a 0.01 s wall-clock wait while the plugin is alive.",
         source="upstream_code", ref=_DIFF_DRIVE + ":342-349"),
]

#: The clone states no numeric velocity range or physical unit for the Twist
#: components.  keyLoop assigns per-key literals, then multiplies by the scale
#: parameters (src/key_control.cpp:232-264).  Those scales are not a device
#: bound.  The operator supplies the deployment envelope.
_LINEAR_LIMIT = Limit.operator_required(
    "the pinned teleop sets linear_ to the per-key literals 0.7, 0.0 or -0.0 and multiplies "
    "by scale_linear (default 2.0); the clone states no numeric cmd_vel linear.x range or clamp, "
    "so the operator supplies the signed deployment envelope")
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned teleop sets angular_ to the per-key literals 0.3, -0.3 or 0.0 and multiplies "
    "by scale_angular (default 2.0); the clone states no numeric cmd_vel angular.z range or clamp, "
    "so the operator supplies the signed deployment envelope")

#: The teleop's publisher is the only in-clone command endpoint.  The message is
#: a geometry_msgs/Twist; only linear.x and angular.z are populated by the node.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
}

_CMD_VEL_ID = "x-cap.wh200720041.cmd_vel.v1"

_PUBLISHED = {
    "published": Field("boolean",
                       description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution "
                                   "confirmation, motion measurement or stop proof"),
    "sent_linear_velocity": Field("number", unit="1",
                                  description="The linear.x handed to rosbridge (the transmitted request, not a "
                                              "measured speed; the clone states no unit)"),
    "sent_angular_velocity": Field("number", unit="1",
                                   description="The angular.z handed to rosbridge (the transmitted request, not a "
                                               "measured rate; the clone states no unit)"),
}


class _SentTwist:
    """The cmd_vel receipt also reports the two values it handed to rosbridge (the transmitted request).

    The device resource reads no topic (a paused world publishes no odometry), so the receipt is where a caller
    sees what a publication sent. Every other call, the e-stop and the reset included, goes to the SDK bridge
    unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _CMD_VEL_ID or not isinstance(output, dict):
            return output
        output = dict(output)
        values = dict(args or {})
        output["sent_linear_velocity"] = float(values["linear_velocity"])
        output["sent_angular_velocity"] = float(values["angular_velocity"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class WarehouseSimulationToolkit(RosDriver):
    device_id = "warehouse-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    # The command drives a mobile base in the Gazebo world on the generic root
    # /cmd_vel that real mobile bases also consume, so the binding carries the
    # mobile-base hazard (REVIEW.md item 12): R2, above the card's R0 floor.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeWarehouseSimulationToolkit"}
    tags = ["ros", "ros1", "simulation", "gazebo", "warehouse", "pioneer3dx", "cmd-vel",
            "teleop", "stop"]
    display_name = "Warehouse Simulation Toolkit (Gazebo, Pioneer 3DX)"
    vendor = "wh200720041"
    model = "Pioneer 3DX in warehouse.world"
    facts = [
        Fact("The README names Ubuntu 64-bit 20.04 as the prerequisite.", source="vendor_doc", ref="README.md:28"),
        Fact("The README names ROS Noetic as the prerequisite.", source="vendor_doc", ref="README.md:30"),
        Fact("The README installs ros-noetic-hector-trajectory-server, ros-noetic-slam-gmapping and "
             "ros-noetic-navigation with apt-get.", source="vendor_doc", ref="README.md:34"),
        Fact("The shipped launch includes gazebo_ros empty_world.launch with worlds/warehouse.world, paused=false "
             "and gui=true.", source="upstream_code", ref="launch/warehouse_simulation.launch:8-12"),
        Fact("warehouse.world sets the physics type to ode.", source="upstream_code", ref="worlds/warehouse.world:67"),
        Fact("The launch spawns the pioneer3dx model from urdf/pioneer3dx.xacro and starts "
             "robot_state_publisher under the /pioneer3dx namespace.",
             source="upstream_code", ref="launch/warehouse_simulation.launch:19-23"),
        Fact("The shipped launch starts slam_gmapping, move_base, rviz and "
             "hector_trajectory_server; its key_control node block is commented out.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The shipped launch starts move_base at the root namespace with respawn true and no remap.",
             source="upstream_code", ref="launch/warehouse_simulation.launch:45-60"),
        Fact("The key_control node block in the shipped launch is inside an XML comment, so the "
             "teleop is not started by default.",
             source="upstream_code", ref=_KEY_NODE_REF),
        Fact("The Pioneer 3DX differential-drive plugin sets commandTopic cmd_vel, "
             "odometryTopic odom, robotNamespace /, wheelSeparation 0.32, wheelDiameter 0.18, "
             "wheelAcceleration 0 and updateRate 100.0.",
             source="upstream_code", ref=_PLUGIN_REF),
        Fact("key_control.cpp includes geometry_msgs/Twist.h.",
             source="upstream_code", ref=_TWIST_TYPE_REF),
        Fact("TeleopTurtle's constructor advertises geometry_msgs::Twist on the relative topic "
             "\"cmd_vel\" with queue size 1.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The teleop reads the scale_linear and scale_angular parameters with constructor "
             "defaults 2.0; they are not device bounds, and the clone states no numeric cmd_vel range.",
             source="upstream_code", ref=_SCALE_REF),
        Fact("keyLoop sets linear_ and angular_ to the per-key literals 0.7, 0.3, 0.0, -0.3 or -0.0, "
             "publishes twist.linear.x as l_scale_*linear_ and twist.angular.z as a_scale_*angular_ "
             "only after a recognized key, and the q key returns without publishing a zero.",
             source="upstream_code", ref=_TELEOP_LOOP_REF),
        Fact("The package builds exactly one executable, key_control, from src/key_control.cpp.",
             source="upstream_code", ref=_BUILD_REF),
        Fact("The laser sensor is configured with 360 samples, 0.0 to 6.28319 rad, a 0.120 to "
             "10.0 m range, a 5 Hz update rate and topicName scan.",
             source="upstream_code", ref=_LASER_REF),
        Fact("The IMU sensor is configured at 10 Hz with its Gazebo ROS plugin at 20 Hz on "
             "topicName imu.",
             source="upstream_code", ref=_IMU_REF),
        Fact("The local costmap observation source is named scan, declares data_type LaserScan and "
             "uses the relative topic scan.",
             source="upstream_code", ref=_COSTMAP_SCAN_REF),
        *_COMPANION_FACTS,
        *_DIFF_DRIVE_FACTS,
    ]
    safe_state = (
        "get_physics_properties read pause true (IsPaused). Ordinary World::Step updates stay suspended while that "
        "flag is true, except stepInc > 0 or a Gazebo reset (needsReset). Not a measured standstill. Other clients "
        "can unpause; MHS does not read the flag again. No unpause is bound. Before any manual unpause the operator "
        "prevents publisher respawn, including move_base, and clears or reinitializes stored x_ and rot_. Publishing "
        "zero is unacknowledged and does not prove they are clear."
    )
    #: The fake is a ROS-free canned transport; it is not a recording of a live
    #: Gazebo session and it runs no physics or sensors.  It claims F0 only.
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned responses with no physics step, wheel integration, "
                     "sensor model or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the declared /cmd_vel publication and the two "
            "companion Gazebo services, and runs no Gazebo physics, differential-drive plugin, laser, IMU or "
            "gmapping/move_base node",
            "the fake records the published Twist but has no robot pose, wheel state, sensor "
            "sample or physics timestep; it cannot establish motion, arrival or stopping; the cmd_vel receipt "
            "reports the values it sent, not a measurement",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step, "
            "and its GetPhysicsProperties numbers are placeholders",
            "no unpause is bound. Stopping publishers does not clear the plugin's stored x_ and rot_ "
            "(gazebo_ros_diff_drive.cpp:335-340); UpdateChild applies them again when updates resume "
            "(:269-289, speeds from :324-333). Publishing zero can replace those fields but is unacknowledged and "
            "is not proof they are clear. move_base starts at the root namespace with respawn true "
            "(warehouse_simulation.launch:45-60) and this package cannot cancel it. Before any manual unpause the "
            "operator prevents that respawn and clears or reinitializes the retained command outside MHS",
            "move_base's velocity output topic is set outside the clone (the navigation stack); started at the root "
            "namespace without a remap it is expected on /cmd_vel, a second commander of the same plugin (not cited)",
            "while pause is true, ordinary World::Step updates are suspended (World.cc:835-854), so /odom, /scan, "
            "/imu and /clock are not produced by those updates; a pending step (stepInc > 0), a manual WorldControl "
            "step or a Gazebo reset (needsReset) still calls Update. The read-back observes only IsPaused(). The "
            "package declares no read of those topics and the device resource reads no topic",
            "another client can unpause or step the world after the e-stop: the Gazebo GUI the shipped launch opens "
            "(gui true), a WorldControl message, or any ROS client. MHS does not read the paused flag again",
            "the read-back needs the ODE engine (warehouse.world sets ode): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name; rosbridge cannot read their versions",
            "upstream timing values (the drive plugin's updateRate 100.0, the 5 Hz laser and the "
            "10 Hz IMU with its 20 Hz plugin) are source facts, not this fake's timing",
            "only /cmd_vel and the two companion world services are exposed; /scan, /odom, /imu, /tf, /map, the "
            "move_base action and the Gazebo reset and spawn services are NOT COVERED",
        ],
    }

    # The clone's only in-package command endpoint.  There is no read-only topic
    # whose topic name and message type both appear in the pinned text, so the
    # driver is action-only and its main resource snapshot is empty; the receipt
    # reports what each publication sent.
    commands = {
        _CMD_VEL_ID: _CMD_VEL,
    }
    actions = {
        _CMD_VEL_ID: Action(
            name="publish_cmd_vel",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint on /cmd_vel for the Gazebo "
                "differential-drive subscription. The receipt is transmission evidence only, not "
                "motion, arrival or stopping."
            ),
            input={
                "linear_velocity": Field(
                    "number",
                    unit="1",
                    description="Twist.linear.x component; the clone states no physical unit",
                    limit=_LINEAR_LIMIT,
                ),
                "angular_velocity": Field(
                    "number",
                    unit="1",
                    description="Twist.angular.z component; the clone states no physical unit",
                    limit=_ANGULAR_LIMIT,
                ),
            },
            output=_PUBLISHED,
            examples=[{"linear_velocity": 0.0, "angular_velocity": 0.0}],
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentTwist(super().make_bridge(native))
