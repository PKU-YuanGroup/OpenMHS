"""OpenMHS rosbridge driver for the pinned TortoiseBot ROS 2 simulation surface.

The upstream repository is a ROS 2 Humble / Ignition Fortress workspace for a
low-cost differential-drive mobile robot.  It contains no Python device class
and no ROS service or action server for the robot base.  The executable
interface in the pinned clone is the Ignition Gazebo ROS 2 topic graph:

* ``/cmd_vel`` carries ``geometry_msgs/msg/Twist`` from ROS 2 to the
  Ignition DiffDrive system; that system caps linear and angular velocity and
  publishes ``/odom``;
* ``/clock`` is the simulation clock, ``/scan`` is the 2-D lidar stream, and
  ``/camera/image_raw`` is the camera stream.

This package selects the simulation environment, not the physical robot, but
nothing in its bindings tells them apart: the clone's real-robot bringup
(``tortoisebot_bringup/launch/autobringup.launch.py``) starts the
``differential.py`` node, which drives the Raspberry Pi GPIO motors from the same
``cmd_vel`` topic, so a rosbridge endpoint on a real TortoiseBot would move the
real base (where no world exists and the e-stop below fails closed).  It
exposes one velocity publication and three fresh observations.

The clone has no stop of its own.  The e-stop is the Ignition world pause of the
simulator's own repository, cited as reviewed companion sources fetched at
pinned commits (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): ignition-gazebo 6.18.0 (Fortress) serves the
WorldControl service ``/world/default/control``, and ros_gz 0.244.27 (Humble)
bridges it as ``ros_gz_interfaces/srv/ControlWorld``.  Its reply is true for any
request the simulator queued, so it confirms nothing; the stop is confirmed by a
fresh-sample topic read-back (E2): ``WorldStatistics.paused`` on
``/world/default/stats`` must be true in two samples that arrived at least 40 ms
apart, after a discarded first one, within 600 ms.  Neither endpoint exists
unless the operator runs ros_gz's ``parameter_bridge`` with the two arguments in
``operator_bridges`` (E3); without them the e-stop fails closed.

The declared re-enable (CORE-086) publishes a zero Twist on ``/cmd_vel`` and then
unpauses the world: DiffDrive keeps the last Twist it received and applies it as
soon as the world runs, so the zero replaces it (unacknowledged; the simulation
launch has no command timeout).  The odometry left the device resource: a
paused world does not publish it, and a reset device must stay readable; it is
the explicit read ``x-cap.rigbetellabs.odom.v1``, and the velocity receipt
reports the values it sent.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at eae9f74a17213adb4dcc8552d65236d5549ebf62.  The fake transport is
ROS-free; no ROS graph, Ignition process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The ros_gz_bridge argument list names the absolute ROS endpoints and their
#: ROS 2 message types.  These cited lines are the wire declarations.
_CMD_VEL_REF = "tortoisebot_gazebo/launch/ignition_sim.launch.py:74"
_ODOM_REF = "tortoisebot_gazebo/launch/ignition_sim.launch.py:75"
_CLOCK_REF = "tortoisebot_gazebo/launch/ignition_sim.launch.py:76"
_SCAN_NAME_REF = "tortoisebot_gazebo/launch/ignition_sim.launch.py:34"
_SCAN_TYPE_REF = "tortoisebot_gazebo/launch/ignition_sim.launch.py:78"

#: The Ignition DiffDrive system consumes /cmd_vel, publishes /odom and
#: declares the two magnitude caps used below.
_LINEAR_LIMIT_REF = "tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:37-38"
_ANGULAR_LIMIT_REF = "tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:39-40"
_SCAN_SENSOR_REF = "tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:85-113"

#: The README states that the simulation runs in Ignition Fortress.
_README_SIM_REF = "README.md:38"

#: Both shipped worlds are named default, and the clone itself composes /world/default/... names.
_WORLD_SDF_REF = "tortoisebot_gazebo/worlds/nav2_test_world.sdf:4"

# -- Companion sources (task.json companions with lock; user decision and authorisation of 2026-11-05) -----------
#: ignition-gazebo 6.18.0 (Fortress) at b90cd2c4, fetched under work/companions: the world runner, its control
#: service and its statistics, and the systems a paused world does not run.
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_DIFF = "companion:gz_sim/src/systems/diff_drive/DiffDrive.cc"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
#: ros_gz 0.244.27 (Humble) at 856e319e, fetched under work/companions: the bridge's service and message mappings.
_SRV = "companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp"
_SERVICE_FACTORY = "companion:ros_gz/ros_gz_bridge/src/service_factory.hpp"
_CONVERT = "companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp"
_BRIDGE_README = "companion:ros_gz/ros_gz_bridge/README.md"
_FACTORY = "companion:ros_gz/ros_gz_bridge/src/factory.hpp"
_INTERFACES = "companion:ros_gz/ros_gz_interfaces"

_WORLD = "/world/default"
#: The e-stop: a WorldControl request with pause true; the simulator queues it and applies it in the step loop.
_PAUSE = {
    "service": _WORLD + "/control",
    "type": "ros_gz_interfaces/srv/ControlWorld",
    "source_name": "control",
    "source_ref": _RUN + ":214",
    "type_ref": _SRV + ":43-52",
    "state_ref": _RUN + ":1242",
    "description": "Pause the Ignition world (WorldControl through ros_gz: SetPaused(true) in the step loop)",
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
    "source_ref": _RUN + ":650-651",
    "type_ref": _BRIDGE_README + ":55",
    "state_ref": _RUN + ":430",
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
    "source_ref": _RUN + ":214",
    "type_ref": _SRV + ":43-52",
    "description": "Unpause the Ignition world (WorldControl through ros_gz: SetPaused(false))",
    "request": {"world_control": {"pause": False}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 400,
    "result": {"acknowledged": {"value": True}},
}
_RESUME_ID = "x-cap.rigbetellabs.resume.v1"
_VEL_ID = "x-cap.rigbetellabs.vel.v1"
_ZERO_TWIST = {"linear_velocity": 0.0, "angular_velocity": 0.0}

#: Facts about the companions, each one clause on its cited range.
_COMPANION_FACTS = [
    Fact("SimulationRunner composes its transport namespace as /world/ followed by the world name.",
         source="upstream_code", ref=_RUN + ":122"),
    Fact("SimulationRunner advertises the control service with OnWorldControl as its callback.",
         source="upstream_code", ref=_RUN + ":214"),
    Fact("OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState.",
         source="upstream_code", ref=_RUN + ":1120-1127"),
    Fact("OnWorldControlState appends the control to worldControls and sets the Boolean reply to true.",
         source="upstream_code", ref=_RUN + ":1174-1176"),
    Fact("ProcessWorldControl calls SetPaused with the pause flag of each queued control.",
         source="upstream_code", ref=_RUN + ":1239-1242"),
    Fact("A queued control with multi_step on a paused world adds the steps and unpauses the world so that stepping "
         "can occur.", source="upstream_code", ref=_RUN + ":1244-1251"),
    Fact("SetPaused stores the pause state in currentInfo.paused.", source="upstream_code", ref=_RUN + ":1088-1089"),
    Fact("Step publishes the world statistics.", source="upstream_code", ref=_RUN + ":826-827"),
    Fact("Step processes the world control messages.", source="upstream_code", ref=_RUN + ":867-868"),
    Fact("The Run loop calls Step on every iteration and counts a processed iteration only while not paused.",
         source="upstream_code", ref=_RUN + ":732-746"),
    Fact("The statistics publisher on the stats topic is limited to 10 messages per second.",
         source="upstream_code", ref=_RUN + ":649-651"),
    Fact("PublishStats copies currentInfo.paused into the WorldStatistics message.", source="upstream_code",
         ref=_RUN + ":430"),
    Fact("UpdateCurrentInfo advances the simulation time and the iteration count only while not paused.",
         source="upstream_code", ref=_RUN + ":345-350"),
    Fact("The Physics system steps the physics only when not paused.", source="upstream_code",
         ref=_PHYSICS + ":855-859"),
    Fact("DiffDrive's PreUpdate returns early while paused.", source="upstream_code", ref=_DIFF + ":450-452"),
    Fact("DiffDrive's PostUpdate returns early while paused.", source="upstream_code", ref=_DIFF + ":518-520"),
    Fact("DiffDrive's cmd_vel callback stores the received Twist as its target velocity while enabled.",
         source="upstream_code", ref=_DIFF + ":654-661"),
    Fact("The bridge maps ros_gz_interfaces/srv/ControlWorld to an ignition.msgs.WorldControl request with an "
         "ignition.msgs.Boolean reply.", source="upstream_code", ref=_SRV + ":42-52"),
    Fact("The ControlWorld response's success is the Boolean reply's data.", source="upstream_code",
         ref=_SRV + ":134-141"),
    Fact("For a failed request the ControlWorld response's success is false.", source="upstream_code",
         ref=_SRV + ":170-178"),
    Fact("The service bridge converts each ROS request and sends it with Request and a callback that sends the ROS "
         "response.", source="upstream_code", ref=_SERVICE_FACTORY + ":56-86"),
    Fact("The WorldStatistics conversion copies the Ignition header into the ROS header and copies paused.",
         source="upstream_code", ref=_CONVERT + ":823-827"),
    Fact("ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag.",
         source="upstream_code", ref=_INTERFACES + "/msg/WorldStatistics.msg:1-14"),
    Fact("ControlWorld takes a WorldControl request and answers bool success.", source="upstream_code",
         ref=_INTERFACES + "/srv/ControlWorld.srv:1-3"),
    Fact("WorldControl's fields include pause, step and multi_step.", source="upstream_code",
         ref=_INTERFACES + "/msg/WorldControl.msg:1-3"),
    Fact("The bridge README maps ros_gz_interfaces/msg/WorldStatistics to ignition.msgs.WorldStatistics.",
         source="vendor_doc", ref=_BRIDGE_README + ":55"),
    Fact("The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to ignition.msgs.WorldControl and "
         "ignition.msgs.Boolean.", source="vendor_doc", ref=_BRIDGE_README + ":78"),
    Fact("The bridge README's service example starts parameter_bridge with a /world/<name>/control ControlWorld "
         "argument.", source="vendor_doc", ref=_BRIDGE_README + ":241-245"),
    Fact("The bridge's publisher QoS is KeepLast with the queue size, and its depth, durability, history and "
         "reliability may be overridden.", source="upstream_code", ref=_FACTORY + ":60-80"),
]


class _ZeroBeforeResume:
    """The declared re-enable (CORE-086) publishes a zero Twist on /cmd_vel before it unpauses the world.

    The receipt of a velocity publication also reports the two components it handed to rosbridge (the transmitted
    request): the device resource reads no topic (a paused world publishes no odometry), so the receipt is where a
    caller sees what a publication sent.

    DiffDrive stores the last Twist it received (companion DiffDrive.cc:654-661) and applies it as soon as the world
    runs, and the bridge forwards /cmd_vel while the world is paused, so an unpause alone would resume a command
    stored before or during the pause (SAFE-042). The zero replaces it. It is a topic publication: unacknowledged and
    handled by the bridge and the transport callback, so it is not confirmed before the world runs again. A failed zero
    publication fails the resume before the unpause is sent. Every other call, the e-stop and the reset included, goes
    to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        if capability_id == _VEL_ID:
            return self._sent(self._inner.call(capability_id, args, ctx), args)
        if capability_id != _RESUME_ID:
            return self._inner.call(capability_id, args, ctx)
        published = self._inner.call(_VEL_ID, dict(_ZERO_TWIST), ctx)
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

_LINEAR_LIMIT = Limit(
    min=-0.23,
    max=0.23,
    unit="m/s",
    source="upstream_code",
    ref=_LINEAR_LIMIT_REF,
    reason="the Ignition DiffDrive system declares max_linear_velocity 0.23 and "
           "min_linear_velocity -0.23",
)
_ANGULAR_LIMIT = Limit(
    min=-1.5,
    max=1.5,
    unit="rad/s",
    source="upstream_code",
    ref=_ANGULAR_LIMIT_REF,
    reason="the Ignition DiffDrive system declares max_angular_velocity 1.5 and "
           "min_angular_velocity -1.5",
)

_CLOCK_TIME = Field(
    "object",
    description="Simulation clock sample from rosgraph_msgs/Clock",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns",
                         description="Nanoseconds within the simulated second"),
    },
)

_PUBLISHED = {
    "published": Field("boolean",
                       description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no motion, "
                                   "arrival or stop confirmation"),
}

#: One explicit geometry_msgs/Twist publication on the bridged command topic.
#: The Ignition DiffDrive system consumes it; it sends no reply on /cmd_vel.
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

#: The raw odometry published by the Ignition DiffDrive system.
_ODOM = {
    "topic": "/odom",
    "type": "nav_msgs/msg/Odometry",
    "operation": "subscribe",
    "source_ref": _ODOM_REF,
    "path": "$",
    "result": {"map": {
        "x": "output.pose.pose.position.x",
        "y": "output.pose.pose.position.y",
        "linear_velocity": "output.twist.twist.linear.x",
        "angular_velocity": "output.twist.twist.angular.z",
    }},
}

#: The 2-D lidar stream from the Ignition gpu_lidar sensor.  The type is
#: declared on the bridge line while the name is bound in the launch script.
_SCAN = {
    "topic": "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "operation": "subscribe",
    "source_ref": _SCAN_NAME_REF,
    "type_ref": _SCAN_TYPE_REF,
    "path": "$",
    "result": {"map": {
        "frame_id": "output.header.frame_id",
        "angle_min": "output.angle_min",
        "angle_max": "output.angle_max",
        "range_min": "output.range_min",
        "range_max": "output.range_max",
        "ranges": "output.ranges",
    }},
}


class Tortoisebot(RosDriver):
    device_id = "tortoisebot"
    device_kind = "world.sim"
    mode = "simulated"
    #: The command surface can drive a simulated mobile base.  The catalogue
    #: mobile-base class is R2; the pinned clone has no ROS service or action
    #: that acknowledges a stop, so this package cannot prove the independent
    #: stop that an R2 motion binding needs.  It records that gap instead of
    #: declaring a zero-Twist publication as a safe state.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeTortoisebot"}
    tags = ["ros", "ros2", "ignition", "gazebo", "simulation", "tortoisebot",
            "cmd-vel", "odometry", "clock", "scan"]
    display_name = "TortoiseBot Ignition simulation environment"
    vendor = "Rigbetella Labs"
    model = "TortoiseBot differential-drive robot in Ignition Fortress"
    facts = [
        Fact("The ros_gz_bridge parameter_bridge declares /cmd_vel as geometry_msgs/msg/Twist in the "
             "ROS to Ignition direction, /odom as nav_msgs/msg/Odometry and /clock as "
             "rosgraph_msgs/msg/Clock in the Ignition to ROS direction.",
             source="upstream_code", ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:74-76"),
        Fact("The launch script binds the scan endpoint name /scan.",
             source="upstream_code",
             ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:34"),
        Fact("The ros_gz_bridge declares the scan bridge as sensor_msgs/msg/LaserScan.",
             source="upstream_code",
             ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:78"),
        Fact("The Ignition DiffDrive system plugin takes its commands from the /cmd_vel topic and names "
             "/odom as its odometry topic.",
             source="upstream_code",
             ref="tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:24-35"),
        Fact("The Ignition DiffDrive system names frame_id odom and child_frame_id base_link.",
             source="upstream_code",
             ref="tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:49-50"),
        Fact("The DiffDrive system declares max_linear_velocity 0.23 and min_linear_velocity -0.23 m/s.",
             source="upstream_code", ref=_LINEAR_LIMIT_REF),
        Fact("The DiffDrive system declares max_angular_velocity 1.5 and min_angular_velocity -1.5 rad/s.",
             source="upstream_code", ref=_ANGULAR_LIMIT_REF),
        Fact("The DiffDrive system configures wheel_separation 0.17186 m and wheel_radius 0.0325 m.",
             source="upstream_code",
             ref="tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:31-32"),
        Fact("The DiffDrive system publishes odometry at 50 Hz.",
             source="upstream_code",
             ref="tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:51"),
        Fact("The gpu_lidar sensor ydlidar has update_rate 10.0 and topic /scan.",
             source="upstream_code",
             ref="tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:86-90"),
        Fact("The gpu_lidar sensor publishes 360 horizontal samples between -3.14159 and 3.14159 rad "
             "with a 0.3 to 12.0 m range and 0.01 m resolution.",
             source="upstream_code", ref=_SCAN_SENSOR_REF),
        Fact("The README states that TortoiseBot uses Ignition Fortress as its simulation backend.",
             source="vendor_doc", ref=_README_SIM_REF),
        Fact("The real-robot firmware script differential.py imports RPi.GPIO and defines the motor "
             "enable and direction pins.", source="upstream_code",
             ref="tortoisebot_firmware/scripts/differential.py:6-16"),
        Fact("The Differential node subscribes Twist on cmd_vel and publishes lpwm, rpwm, ldir and rdir.", source="upstream_code",
             ref="tortoisebot_firmware/scripts/differential.py:102-111"),
        Fact("The Differential callback computes the wheel velocities from linear.x and angular.z and calls "
             "stop when both are zero, otherwise wheel_vel_executer.", source="upstream_code",
             ref="tortoisebot_firmware/scripts/differential.py:113-130"),
        Fact("autobringup.launch.py starts tortoisebot_firmware's differential.py as node differential "
             "unless use_sim_time is set.", source="upstream_code",
             ref="tortoisebot_bringup/launch/autobringup.launch.py:76-82"),
        Fact("The Ignition launch's default world is worlds/nav2_test_world.sdf.", source="upstream_code",
             ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:22"),
        Fact("nav2_test_world.sdf names its world default.", source="upstream_code", ref=_WORLD_SDF_REF),
        Fact("room2.sdf names its world default.", source="upstream_code",
             ref="tortoisebot_gazebo/worlds/room2.sdf:2"),
        Fact("The launch's joint-state bridge reads /world/default/model/tortoisebot/joint_state.",
             source="upstream_code", ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:99-102"),
        Fact("The launch runs ign gazebo -r with the GUI when gui is true and with -s when it is false.",
             source="upstream_code", ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:111-121"),
        Fact("The launch's main bridge sets QoS overrides for its /tf_static, /scan and /odom publishers.",
             source="upstream_code", ref="tortoisebot_gazebo/launch/ignition_sim.launch.py:86-91"),
        Fact("The README names ROS 2 Humble.", source="vendor_doc", ref="README.md:1"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The world default is paused: after the WorldControl pause two fresh stats samples, 40 ms or more apart "
        "within 600 ms, reported paused true, so the world does not step and DiffDrive applies no velocity; it is the "
        "paused flag in that window, not a measured standstill, it needs the operator-run ros_gz bridges, and the GUI, "
        "a WorldControl client or a step request can unpause or step the world."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned topic replies with no Ignition physics, DiffDrive integration, "
                     "lidar raycast or state-hash replay; its world statistics follow the wall clock",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract stand-in, not a recording of captured traffic: it answers "
            "the declared subscriptions and services and records the declared publication, but runs no Ignition "
            "Gazebo, ros_gz_bridge, physics, DiffDrive system, sensor model or ROS graph",
            "the /odom pose and twist, /clock time and /scan ranges are placeholders; the fake returns "
            "an 8-element placeholder scan array while the pinned gpu_lidar sensor declares 360 samples "
            "(tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:90-99)",
            "one subscription reply is not the pinned 50 Hz odometry or 10 Hz scan stream; no timing, "
            "drop or QoS behaviour of those streams is modeled",
            "the camera stream /camera/image_raw, the TF tree, Nav2, AMCL and Cartographer are outside "
            "this package and are not covered",
            "the binding cannot tell the simulation from the real robot: autobringup.launch.py:76-82 starts "
            "differential.py, which drives the Raspberry Pi GPIO motors from the same cmd_vel topic "
            "(differential.py:102-130), so a rosbridge endpoint on a real TortoiseBot moves the real base, where no "
            "world exists and the e-stop fails closed",
            "the bridge refuses non-finite numbers, so a scan whose ranges contain inf or NaN (for example a "
            "beam without a return) fails the read without output instead of being served as data",
            "the stop is the companion Ignition world pause (WorldControl through ros_gz ControlWorld), whose reply is "
            "true for any request the simulator queued (SimulationRunner.cc:1174-1176); it is confirmed by the E2 "
            "read-back: the fake keeps a paused flag that the control request sets after its next statistics sample "
            "and publishes /world/default/stats every 100 ms (placeholder) while subscribed; it runs no "
            "SimulationRunner",
            "the e-stop endpoints exist only while the operator runs ros_gz's parameter_bridge with the two "
            "arguments of operator_bridges (the clone's bridges carry topics only, ignition_sim.launch.py:69-109); "
            "without them the control call is not answered and the read-back sees no sample, so the e-stop fails "
            "closed; the declared estop_latency_ms 1500 covers the control call (400 ms) and the read-back bound "
            "(600 ms)",
            "the read-back's freshness is the arrival time only: the bridged WorldStatistics header is the Ignition "
            "header, which PublishStats does not stamp (ros_gz convert copies it, ros_gz_interfaces.cpp:823); the "
            "bridge's publisher QoS sets only KeepLast with the queue size (factory.hpp:60-80), so its durability "
            "stays rclcpp's default, volatile, which replays no history to a late subscriber; the first sample is "
            "discarded and a burst of samples restarts the count; a QoS override of the stats publisher to "
            "a deeper transient-local history (the clone's own bridge overrides other publishers, "
            "ignition_sim.launch.py:86-91) is not covered beyond that burst rule",
            "the endpoints name the world default, the name of both shipped worlds (nav2_test_world.sdf:4, "
            "room2.sdf:2) that the clone itself composes (ignition_sim.launch.py:99-102); a world with another name "
            "has other endpoints, and the e-stop fails closed",
            "a live world can be unpaused or stepped by the Ignition GUI that the launch starts when gui is true "
            "(ignition_sim.launch.py:111-115), a WorldControl multi_step (SimulationRunner.cc:1244-1251) or any client "
            "of the control service; MHS does not watch the flag after the e-stop (safety_status re-reads it only on "
            "request)",
            "while paused, DiffDrive does not publish /odom (DiffDrive.cc:518-520) and sensors update on simulation "
            "time, which a paused world does not advance (SimulationRunner.cc:345-350); the fake silences /odom and "
            "/scan while paused, their reads fail NOT_READY after their timeouts, and the device resource reads no "
            "topic; /clock keeps the frozen time",
            "the resume publishes a zero Twist before the unpause: DiffDrive keeps the last Twist "
            "(DiffDrive.cc:654-661) and the bridge forwards /cmd_vel while paused; the zero is unacknowledged and the "
            "simulation launch has no command timeout; the teleop keyboard and firmware/scripts/1ms.py also publish "
            "cmd_vel; the world resumes from the state it paused in, body velocities included",
            "the deployment's ignition-gazebo and ros_gz must be the pinned 6.18.0 and 0.244.27 releases (ROS 2 Humble "
            "with Ignition Fortress); rosbridge cannot read the versions",
        ],
    }

    # The device resource reads no topic: /odom and /scan are published from world updates, so they are silent while
    # the e-stop holds the world paused; a resource that waited for them would fail NOT_READY after every reset and
    # delay every command by its timeout.  They stay explicit read capabilities below.
    estop_latency_ms = 1500
    commands = {
        _VEL_ID: _CMD_VEL,
        "x-cap.rigbetellabs.odom.v1": _ODOM,
        "x-cap.rigbetellabs.clock.v1": _CLOCK,
        "x-cap.rigbetellabs.scan.v1": _SCAN,
        _RESUME_ID: _RESUME,
    }
    actions = {
        "x-cap.rigbetellabs.vel.v1": Action(
            name="publish_velocity",
            verb="invoke",
            risk="R2",
            max_duration_ms=2000,
            description="Publish one geometry_msgs/Twist velocity command on /cmd_vel; the publication "
                        "is transmission only and returns no motion or stop confirmation",
            input={
                "linear_velocity": Field(
                    "number", unit="m/s", limit=_LINEAR_LIMIT,
                    description="Forward velocity in the base frame"),
                "angular_velocity": Field(
                    "number", unit="rad/s", limit=_ANGULAR_LIMIT,
                    description="Yaw rate about the base z axis"),
            },
            output={**_PUBLISHED,
                    "sent_linear_velocity": Field("number", unit="m/s", description="The linear.x handed to rosbridge "
                                                                                    "(the transmitted request)"),
                    "sent_angular_velocity": Field("number", unit="rad/s", description="The angular.z handed to "
                                                                                       "rosbridge (the transmitted "
                                                                                       "request)")},
        ),
        "x-cap.rigbetellabs.odom.v1": Action(
            name="read_odometry",
            verb="read",
            max_duration_ms=2000,
            description="Read one fresh nav_msgs/Odometry sample from the Ignition DiffDrive system (silent, and "
                        "NOT_READY, while the world is paused)",
            output={
                "x": Field("number", unit="m", description="Position x in the odometry frame"),
                "y": Field("number", unit="m", description="Position y in the odometry frame"),
                "linear_velocity": Field("number", unit="m/s",
                                         description="Linear velocity x in the odometry frame"),
                "angular_velocity": Field("number", unit="rad/s",
                                          description="Angular velocity z in the odometry frame"),
            },
        ),
        "x-cap.rigbetellabs.clock.v1": Action(
            name="read_clock",
            verb="read",
            max_duration_ms=2000,
            description="Read one simulated ROS clock sample from the /clock bridge",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.rigbetellabs.scan.v1": Action(
            name="read_scan",
            verb="read",
            max_duration_ms=2000,
            description="Read one fresh sensor_msgs/LaserScan sample from the simulated 2-D lidar",
            output={
                "frame_id": Field("string", description="LaserScan header.frame_id"),
                "angle_min": Field("number", unit="rad", description="Start angle of the scan"),
                "angle_max": Field("number", unit="rad", description="End angle of the scan"),
                "range_min": Field("number", unit="m", description="Minimum measurable range"),
                "range_max": Field("number", unit="m", description="Maximum measurable range"),
                "ranges": Field("array", unit="m", items=Field("number", unit="m"),
                                description="Range measurements in publisher order"),
            },
        ),
        _RESUME_ID: Action(
            name="resume_simulation",
            verb="invoke",
            reenable=True,
            description=(
                "The declared re-enable after a safety reset: publish a zero Twist on /cmd_vel, then unpause the "
                "world with a WorldControl request (pause false) on /world/default/control. DiffDrive keeps the last "
                "Twist it received and applies it as soon as the world runs; the zero replaces it, but it is an "
                "unacknowledged publication, so a stored command can still act for a few world steps."
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
        {"args": "/world/default/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE_README + ":78",
         "description": "The world control service: the e-stop pause and the resume."},
        {"args": "/world/default/stats@ros_gz_interfaces/msg/WorldStatistics[ignition.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":55",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    # The e-stop pauses the world and confirms it by the paused flag in fresh statistics samples (companion
    # ignition-gazebo and ros_gz, E2); anything else leaves the e-stop unconfirmed with the latch held and a
    # background retry. No reset binding: mhs.safety.reset releases the latch only; the declared resume is the new
    # start (CORE-086).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _ZeroBeforeResume(super().make_bridge(native))
