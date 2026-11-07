"""OpenMHS rosbridge driver for the CrazyS Crazyflie 2.0 Gazebo simulator.

The upstream is a ROS 1 Gazebo simulation built on RotorS.  This package is a
configuration-only ``RosDriver`` over rosbridge; it declares no Python native
class and does not start or import ROS, Gazebo or any upstream code.

Scope: the Crazyflie direct flight command topic used by the joystick example
(``command/roll_pitch_yawrate_thrust``) and one explicit odometry observation
(``odometry_sensor1/odometry``).  The command is a topic publication, so it is
fire-and-forget: the receipt says the transport accepted the message and
reports the values it sent, not that a controller consumed it, that the vehicle
moved or that it stopped.

The pinned clone exposes no acknowledged stop of its own.  The e-stop is the
Gazebo world pause of the simulator's own repository, cited as a reviewed
companion source fetched at a pinned commit (user decision and authorisation of
2026-11-05; ``task.json`` ``companions`` with ``lock``): gazebo_ros 2.5.21 (ROS
1 Kinetic) ``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true; Gazebo 7.16.1
is cited for what a paused world does not run.  The pause stops every world
update, so the motor models apply no rotor force; it is the paused flag, not a
measured standstill.

No unpause is offered.  The controller node keeps the last
roll/pitch/yaw-rate/thrust reference with no timeout and the motor models their
last rotor speed; the clone states no hover thrust, and a zero thrust reference
is not a hold (the vehicle falls once the world runs), so this package cannot
clear the stored command before an unpause (the orchestrator's SAFE-042
condition).  After ``mhs.safety.reset`` the world stays paused and the operator
recovers outside MHS (see ``safe_state``).  The four command inputs are
``Limit.operator_required``: the clone states no device bound for them.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

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


#: Relative Crazyflie command topic and its message type, both from the clone.
_COMMAND_REF = "rotors_control/include/rotors_control/common.h:40-42"
_COMMAND_TYPE_REF = "rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.h:25"

#: Relative odometry topic published by the Gazebo odometry plugin.
_ODOMETRY_REF = "rotors_description/urdf/mav_generic_odometry_sensor.gazebo:35"
_ODOMETRY_TYPE_REF = "rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.h:27"

#: The joystick's MAX_* values are defaults of configurable joystick parameters and the controller
#: clamps rotor velocities instead of bounding the command, so no input bound is stated in the clone
#: (model review 2026-11-05: the author declared no Limit on these actuating inputs).
_ATTITUDE_LIMIT = Limit.operator_required(
    "the clone states no device bound for the Crazyflie roll, pitch, yaw-rate or thrust command; the "
    "operator supplies the reviewed envelope"
)

_ODOMETRY_ACTION = Action(
    name="read_odometry",
    verb="read",
    description="Read one ideal odometry sample from the simulated Crazyflie",
    output={
        "position": Field(
            "object",
            description="Position in the odometry pose",
            properties={
                "x": Field("number", unit="m", description="Position x"),
                "y": Field("number", unit="m", description="Position y"),
                "z": Field("number", unit="m", description="Position z"),
            },
        ),
        "orientation": Field(
            "object",
            description="Orientation quaternion in the odometry pose",
            properties={
                "x": Field("number", unit="1", description="Quaternion x"),
                "y": Field("number", unit="1", description="Quaternion y"),
                "z": Field("number", unit="1", description="Quaternion z"),
                "w": Field("number", unit="1", description="Quaternion w"),
            },
        ),
        "linear_velocity": Field(
            "object",
            description="Linear velocity in the odometry twist",
            properties={
                "x": Field("number", unit="m/s", description="Linear velocity x"),
                "y": Field("number", unit="m/s", description="Linear velocity y"),
                "z": Field("number", unit="m/s", description="Linear velocity z"),
            },
        ),
        "angular_velocity": Field(
            "object",
            description="Angular velocity in the odometry twist",
            properties={
                "x": Field("number", unit="rad/s", description="Angular velocity x"),
                "y": Field("number", unit="rad/s", description="Angular velocity y"),
                "z": Field("number", unit="rad/s", description="Angular velocity z"),
            },
        ),
        "frame_id": Field("string", description="Frame id of the odometry header"),
    },
)


_COMMAND_ID = "x-cap.gsilano.attitude_thrust.v1"


class _SentReceipt:
    """The receipt of a command publication also reports the four values it handed to rosbridge.

    The device resource reads no topic (a paused world publishes none), so the receipt is where a caller sees what
    a publication sent; it is the transmitted request, not a measurement. Every other call, the e-stop and the
    reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _COMMAND_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        for key in ("roll", "pitch", "yaw_rate", "thrust"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class Crazys(RosDriver):
    device_id = "crazys"
    device_kind = "world.sim"
    mode = "simulated"
    # R2, not R0 (integrator v4, claude-opus-5-5, 2026-11-05; REVIEW.md item 12 and the orchestrator's condition on
    # the Sonnet evidence lens's EP-2): a simulator package's command keeps the robot's hazard unless a cited line shows
    # that only the simulator consumes its topic. The setpoint goes out on the RotorS command topic
    # (rotors_control/include/rotors_control/common.h:40-42), and no fact cites that only a simulator consumes it; the
    # clone also ships a hardware-in-the-loop autopilot interface (rqt_rotors/src/rqt_rotors/hil_plugin.py:45-47,
    # 90-92). A flying vehicle is mobile hardware (R2) however simulated the deployment. The e-stop stays the companion
    # world pause (safety_bindings); no hardware emergency stop is claimed.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeCrazys"}
    tags = ["ros", "ros1", "simulation", "gazebo", "crazyflie", "uav", "quadrotor", "odometry"]
    display_name = "CrazyS Crazyflie 2.0 simulator"
    vendor = "Giuseppe Silano"
    model = "Crazyflie 2.0"
    facts = [
        Fact("The README says the hovering example publishes the reference on command/trajectory, the "
             "position controller reads it with odometry_sensor1/odometry, and the motor speeds go to "
             "command/motor_speed.", source="vendor_doc", ref="README.md:420"),
        Fact("The Crazyflie command topic constant is documented as "
             "\"command/roll_pitch_yawrate_thrust\" in the RotorS control common header.",
             source="upstream_code", ref=_COMMAND_REF),
        Fact("The Crazyflie roll/pitch/yaw-rate/thrust node subscribes to the command topic with queue "
             "size 1 and to odometry with queue size 1.",
             source="upstream_code",
             ref="rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:35-38"),
        Fact("The command message type is mav_msgs/RollPitchYawrateThrustCrazyflie.",
             source="upstream_code", ref=_COMMAND_TYPE_REF),
        Fact("The joystick interface fills the command's roll, pitch, yaw_rate and thrust fields.",
             source="upstream_code", ref="rotors_joy_interface/src/joy_crazyflie.cpp:30-36"),
        Fact("Joy::StopMav sets roll, pitch, yaw_rate and thrust to zero; it is a local joystick method, "
             "not a ROS service or action.", source="upstream_code",
             ref="rotors_joy_interface/src/joy_crazyflie.cpp:61-66"),
        Fact("The launch file defaults mav_name to crazyflie2.",
             source="upstream_code", ref="rotors_gazebo/launch/crazyflie2_with_joy.launch:3"),
        Fact("The joystick launch groups the Crazyflie nodes under the mav_name namespace.",
             source="upstream_code", ref="rotors_gazebo/launch/crazyflie2_with_joy.launch:29"),
        Fact("The launch remaps the controller's odometry to odometry_sensor1/odometry.",
             source="upstream_code", ref="rotors_gazebo/launch/crazyflie2_with_joy.launch:45"),
        Fact("The generic odometry sensor macro is configured with odometry_topic "
             "odometry_sensor1/odometry.", source="upstream_code", ref=_ODOMETRY_REF),
        Fact("The odometry type used by the Crazyflie controller is nav_msgs/Odometry.",
             source="upstream_code", ref=_ODOMETRY_TYPE_REF),
        Fact("hovering_example calls /gazebo/unpause_physics with a std_srvs/Empty request.",
             source="upstream_code", ref="rotors_gazebo/src/nodes/hovering_example.cpp:41-42"),
        Fact("The rqt_rotors HIL plugin names the MAVROS services /mavros/cmd/arming, /mavros/cmd/command and "
             "/mavros/set_mode.",
             source="upstream_code", ref="rqt_rotors/src/rqt_rotors/hil_plugin.py:45-47"),
        Fact("The HIL plugin creates ServiceProxy clients for the arming, command and set_mode services.",
             source="upstream_code", ref="rqt_rotors/src/rqt_rotors/hil_plugin.py:90-92"),
        Fact("The HIL plugin's arm button calls the arming service with True.",
             source="upstream_code", ref="rqt_rotors/src/rqt_rotors/hil_plugin.py:104-105"),
        Fact("The joystick launch fixes paused to true and passes it to the gazebo_ros empty_world launch.",
             source="upstream_code", ref="rotors_gazebo/launch/crazyflie2_with_joy.launch:9-26"),
        Fact("The joystick launch starts joy_node and rotors_joy_interface_crazyflie in the mav_name group.",
             source="upstream_code", ref="rotors_gazebo/launch/crazyflie2_with_joy.launch:39-41"),
        Fact("Joy::JoyCallback sets the command fields from the joystick axes and publishes the command on "
             "every joystick message.",
             source="upstream_code", ref="rotors_joy_interface/src/joy_crazyflie.cpp:68-102"),
        Fact("The bag plugin advertises its recording service with GazeboBagPlugin::RecordingServiceCallback.",
             source="upstream_code", ref="rotors_gazebo_plugins/src/gazebo_bag_plugin.cpp:111-113"),
        Fact("RecordingServiceCallback starts or stops bag recording according to req.record.",
             source="upstream_code", ref="rotors_gazebo_plugins/src/gazebo_bag_plugin.cpp:411-431"),
        Fact("The octomap plugin advertises a service named world/get_octomap unless the octomapServiceName "
             "parameter overrides it.",
             source="upstream_code", ref="rotors_gazebo_plugins/src/gazebo_octomap_plugin.cpp:43-52"),
        Fact("The octomap service callback builds the octomap and writes it to req.filename when one is given.",
             source="upstream_code", ref="rotors_gazebo_plugins/src/gazebo_octomap_plugin.cpp:57-74"),
        Fact("The Crazyflie controller returns zero rotor velocities while controller_active_ is false.",
             source="upstream_code",
             ref="rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:65-69"),
        Fact("SetRollPitchYawrateThrust stores the command and sets controller_active_ to true.",
             source="upstream_code",
             ref="rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:222-228"),
        Fact("The Crazyflie controller clamps each rotor velocity to the range 0 to "
             "MAX_PROPELLERS_ANGULAR_VELOCITY.",
             source="upstream_code",
             ref="rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:80-106"),
        Fact("The joystick reads max_roll, max_pitch, max_yaw_rate and max_thrust as private parameters "
             "with the MAX_ROLL, MAX_PITCH, MAX_YAWRATE and MAX_THRUST defaults.",
             source="upstream_code", ref="rotors_joy_interface/src/joy_crazyflie.cpp:47-50"),
        Fact("joy_crazyflie.cpp defines MAX_THRUST as 8162.0 with the comment propeller angular velocities "
             "[PWM], MAX_ROLL and MAX_PITCH as 30 degrees in radians and MAX_YAWRATE as 200 degrees per second "
             "in radians.",
             source="upstream_code", ref="rotors_joy_interface/src/joy_crazyflie.cpp:22-25"),
        Fact("The Crazyflie node's command callback converts each roll/pitch/yaw-rate/thrust message and passes it "
             "to SetRollPitchYawrateThrust.", source="upstream_code",
             ref="rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:93-99"),
        Fact("The Crazyflie node computes rotor velocities and publishes them on the actuators topic only from its "
             "odometry callback.", source="upstream_code",
             ref="rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:102-126"),
        Fact("For each rotor the motor model stores the commanded rotor speed, capped at its maximum, as its "
             "reference.", source="upstream_code", ref="rotors_gazebo_plugins/src/gazebo_motor_model.cpp:237-239"),
        Fact("The Crazyflie basic world selects the ODE physics engine.", source="upstream_code",
             ref="rotors_gazebo/worlds/basic_crazyflie.world:27"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so the "
        "motor models apply no rotor force and odometry is silent; it is the paused flag, not a measured "
        "standstill. No unpause is offered: an operator re-commands or lands the vehicle and unpauses outside MHS "
        "(Gazebo GUI or rosservice call gazebo/unpause_physics)."
    )
    fidelity = {
        "engine": "analytic:ROS-free transport model (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step, controller or pacing; the "
                     "placeholder odometry shifts by a small amount proportional to the command only to "
                     "make it observable",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic ROS-free transport model, not a recording and not Gazebo; it answers "
            "the declared command publication and odometry subscription and runs no Crazyflie dynamics, "
            "controller, physics, sensors, world or ROS graph",
            "the command is a fire-and-forget publication; the fake reports only that the transport accepted "
            "the message and never that a controller consumed it, that the vehicle moved or that it stopped",
            "the odometry starts from placeholder values and shifts by a small placeholder amount "
            "proportional to the command while the world runs; this is an analytic stand-in for the simulator's "
            "response, not physics, a controller or simulation time",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step",
            "no unpause is offered: the controller node keeps the last roll/pitch/yaw-rate/thrust reference with no "
            "timeout (SetRollPitchYawrateThrust, roll_pitch_yawrate_thrust_crazyflie.cpp:223-228) and the motor "
            "models their last rotor speed (gazebo_motor_model.cpp:237-239); the clone states no hover thrust and a "
            "zero thrust is not a hold, so the package cannot clear the stored command before an unpause; the "
            "operator recovers outside MHS (a new reference or a landing by the joystick, then the Gazebo GUI play "
            "button or rosservice call gazebo/unpause_physics)",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, by "
            "a WorldControl message, by hovering_example or by any ROS client; MHS does not watch the flag after the "
            "e-stop (safety_status re-reads it only on request)",
            "the read-back needs the ODE engine (the clone's worlds and empty_world.launch's default): with another "
            "engine get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.5.21 (Kinetic) and 7.16.1 releases the "
            "companion citations name (the clone's master is the Kinetic + Gazebo 7 line; its Noetic line is another "
            "branch); rosbridge cannot read their versions",
            "the default command/trajectory waypoint path, command/motor_speed, Gazebo pause/unpause, TF, "
            "IMU, camera/depth, octomap and every other topic are NOT COVERED",
            "the joystick launch also starts joy_node and rotors_joy_interface_crazyflie, which publish on the "
            "same command topic on every joystick message, so a driver publication can be overwritten",
            "the joystick launch starts Gazebo paused until hovering_example unpauses it; while physics is paused "
            "(also after the e-stop) the odometry topic is silent and the odometry read fails NOT_READY at the 2 s "
            "wire default; the device resource reads no topic, so commands and resets do not wait for it, and each "
            "command receipt reports the values it sent",
            "the rqt_rotors HIL plugin arms and mode-switches a MAVROS autopilot through /mavros services; it is "
            "a hardware-in-the-loop path outside this package and is not simulated by the fake",
            "the four command inputs are operator_required; site-limits.example.json is an example overlay "
            "for the fake gate only",
        ],
    }
    # The device resource reads no topic: the odometry is published from the world update, so it is silent while
    # the e-stop holds the world paused, and a resource that waited for it would fail NOT_READY after every reset and
    # delay every command by its timeout.  The odometry stays an explicit read capability; the command receipt
    # reports the values it sent.
    commands = {
        "x-cap.gsilano.attitude_thrust.v1": {
            "topic": "/crazyflie2/command/roll_pitch_yawrate_thrust",
            "type": "mav_msgs/RollPitchYawrateThrustCrazyflie",
            "source_name": "command/roll_pitch_yawrate_thrust",
            "source_ref": _COMMAND_REF,
            "type_ref": _COMMAND_TYPE_REF,
            "message": {},
            "args": {
                "roll": {"from": "input.roll"},
                "pitch": {"from": "input.pitch"},
                "yaw_rate": {"from": "input.yaw_rate"},
                "thrust": {"from": "input.thrust"},
            },
            "result": {"map": {"published": "published", "confirmed": "confirmed"}},
        },
        "x-cap.gsilano.odometry.v1": {
            "topic": "/crazyflie2/odometry_sensor1/odometry",
            "type": "nav_msgs/Odometry",
            "source_name": "odometry_sensor1/odometry",
            "source_ref": _ODOMETRY_REF,
            "type_ref": _ODOMETRY_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {
                "position": "pose.pose.position",
                "orientation": "pose.pose.orientation",
                "linear_velocity": "twist.twist.linear",
                "angular_velocity": "twist.twist.angular",
                "frame_id": "header.frame_id",
            }},
        },
    }
    actions = {
        "x-cap.gsilano.attitude_thrust.v1": Action(
            name="publish_attitude_thrust",
            description=("Publish a roll/pitch/yaw-rate/thrust setpoint on the Crazyflie command topic; "
                         "publication is fire-and-forget and does not confirm flight or stopping"),
            input={
                "roll": Field("number", unit="rad",
                              description="Desired roll attitude in radians", limit=_ATTITUDE_LIMIT),
                "pitch": Field("number", unit="rad",
                               description="Desired pitch attitude in radians", limit=_ATTITUDE_LIMIT),
                "yaw_rate": Field("number", unit="rad/s",
                                  description="Desired yaw rate in radians per second", limit=_ATTITUDE_LIMIT),
                "thrust": Field("number", unit="1",
                                description=("Thrust command on the upstream joystick's configurable "
                                             "PWM-like scale; the controller saturates its rotor output"),
                                limit=_ATTITUDE_LIMIT),
            },
            output={
                "published": Field("boolean",
                                   description="True once rosbridge accepted the publication"),
                "confirmed": Field("boolean",
                                   description="Always false: a topic publication has no controller or "
                                               "simulator acknowledgement"),
                "sent_roll": Field("number", unit="rad", description="The roll handed to rosbridge (the "
                                                                      "transmitted request, not a measured attitude)"),
                "sent_pitch": Field("number", unit="rad", description="The pitch handed to rosbridge (the "
                                                                       "transmitted request, not a measured attitude)"),
                "sent_yaw_rate": Field("number", unit="rad/s", description="The yaw rate handed to rosbridge (the "
                                                                            "transmitted request)"),
                "sent_thrust": Field("number", unit="1", description="The thrust handed to rosbridge (the "
                                                                      "transmitted request)"),
            },
        ),
        "x-cap.gsilano.odometry.v1": _ODOMETRY_ACTION,
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
