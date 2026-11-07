"""OpenMHS rosbridge driver for the pinned Spot ROS 2 / Ignition Fortress simulation.

The upstream repository is a ROS 2 Humble simulation of the Boston Dynamics Spot
quadruped with the CHAMP controller.  It contains no Python device class and no
ROS service or action that stops the base.  The executable interface in the
pinned clone is the topic graph:

* ``/cmd_vel`` carries ``geometry_msgs/msg/Twist`` to the CHAMP controller, whose
  callback stores ``linear.x``, ``linear.y`` and ``angular.z`` in ``req_vel_``;
* ``/spot/odometry``, ``/spot/joint_states`` and ``/clock`` are bridged observations.

The clone has no stop of its own.  The e-stop is the Ignition world pause of the
simulator's own repository, cited as reviewed companion sources fetched at
pinned commits (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): ignition-gazebo 6.18.0 (Fortress) serves the
WorldControl service ``/world/simple_tunnel/control``, and ros_gz 0.244.27
(Humble) bridges it as ``ros_gz_interfaces/srv/ControlWorld``.  Its reply is true
for any request the simulator queued, so it confirms nothing; the stop is
confirmed by a fresh-sample topic read-back (E2): ``WorldStatistics.paused`` on
``/world/simple_tunnel/stats`` must be true in two samples that arrived at least
40 ms apart, after a discarded first one, within 600 ms.  Neither endpoint
exists unless the operator runs ros_gz's ``parameter_bridge`` with the two
arguments in ``operator_bridges`` (E3); without them the e-stop fails closed.
The clone's own ``spot_bridge.yaml`` does not bridge those two endpoints.

No unpause is offered, neither as a re-enable nor as an ordinary command
(REVIEW.md item 13).  The ``/cmd_vel`` callback stores the Twist in ``req_vel_``
and a wall timer keeps publishing joint trajectories from it.  The
JointTrajectoryController returns while the world is paused and, once the world
runs, applies the trajectory and joint targets it still holds.  A zero Twist
does not clear those targets before an unpause.  ``mhs.safety.reset`` releases
the latch and leaves the world paused.  The operator zeros ``/cmd_vel``, lets
the wall timer replace the trajectory, and unpauses outside MHS.  Odometry,
joint states and the clock leave the device resource: odometry is silent while
the world is paused, and a reset must not wait on the streams that keep
publishing.

Only the default world name ``simple_tunnel`` is bound.  ``edgar_mine`` and
``electrical_substation_v3`` use other endpoint names, and the e-stop fails
closed there.  The launch passes no ``-r``, and ``Server::Run`` starts paused
when that flag is 0, so a real server starts paused; the fake starts unpaused
so the explicit reads can be exercised before an e-stop.  The operator's first
unpause of that server is outside MHS as well.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 23166d6efd67724edc1ce41e9ee4bb909cf9a2f9.  The fake transport is
ROS-free; no ROS graph, Ignition process, simulator or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The launch remaps the controller's relative ``cmd_vel/smooth`` subscription
#: to the absolute ``/cmd_vel`` endpoint.
_CMD_VEL_REF = "spot_bringup/launch/spot.gazebo.launch.py:112"

#: The Twist include proves the message type used by the subscription.
_TWIST_TYPE_REF = "champ_base/include/quadruped_controller.h:43"

#: The bridge config declares the three observations with their ROS types.
_CLOCK_REF = "spot_bringup/config/spot_bridge.yaml:3-6"
_JOINT_STATE_REF = "spot_bringup/config/spot_bridge.yaml:8-11"
_ODOMETRY_REF = "spot_bringup/config/spot_bridge.yaml:13-16"

#: The launch starts the quadruped controller with the simulation parameters.
_CONTROLLER_LAUNCH_REF = "spot_bringup/launch/spot.gazebo.launch.py:95-114"

#: The controller creates the Twist subscription on the relative topic.
_CMD_VEL_SUBSCRIPTION_REF = "champ_base/src/quadruped_controller.cpp:69-70"

#: The callback copies the three Twist components into persistent gait state.
_CMD_VEL_CALLBACK_REF = "champ_base/src/quadruped_controller.cpp:116-121"

#: The leg controller clamps the stored request to the configured gait limits.
_VELOCITY_CLAMP_REF = "champ/include/champ/leg_controller/leg_controller.h:95-98"

#: The deployed gait configuration loaded by the launch file.
_GAIT_CONFIG_REF = "champ_config/config/gait/gait.yaml:7-9"

#: The control loop converts the stored request to joint trajectories.
_CONTROL_LOOP_REF = "champ_base/src/quadruped_controller.cpp:101-113"

#: The trajectory publication names the ROS-to-Gazebo controller bridge.
_TRAJECTORY_REF = "champ_base/src/quadruped_controller.cpp:145-160"
_TRAJECTORY_BRIDGE_REF = "spot_bringup/config/spot_bridge.yaml:76-80"

#: The world loads the physics, sensor, scene-broadcaster and user-command systems.
_WORLD_REF = "spot_gazebo/worlds/simple_tunnel.sdf:5-24"

#: The README states that the body camera and depth sensors are disabled.
_README_CAMERAS_REF = "README.md:22"

# -- Companion sources (task.json companions with lock; user decision and authorisation of 2026-11-05) -----------
#: ignition-gazebo 6.18.0 (Fortress) at b90cd2c4, fetched under work/companions.
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
_ODOM_SYS = "companion:gz_sim/src/systems/odometry_publisher/OdometryPublisher.cc"
_JOINT_STATE_SYS = "companion:gz_sim/src/systems/joint_state_publisher/JointStatePublisher.cc"
_TRAJ_SYS = "companion:gz_sim/src/systems/joint_traj_control/JointTrajectoryController.cc"
_SERVER_HH = "companion:gz_sim/include/gz/sim/Server.hh"
_SERVER_CC = "companion:gz_sim/src/Server.cc"
_GZ_CC = "companion:gz_sim/src/gz.cc"
_GZ_CMD = "companion:gz_sim/src/cmd/cmdgazebo.rb.in"
#: ros_gz 0.244.27 (Humble) at 856e319e, fetched under work/companions.
_SRV = "companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp"
_SERVICE_FACTORY = "companion:ros_gz/ros_gz_bridge/src/service_factory.hpp"
_CONVERT = "companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp"
_BRIDGE_README = "companion:ros_gz/ros_gz_bridge/README.md"
_FACTORY = "companion:ros_gz/ros_gz_bridge/src/factory.hpp"
_PARAM_BRIDGE = "companion:ros_gz/ros_gz_bridge/src/parameter_bridge.cpp"
_INTERFACES = "companion:ros_gz/ros_gz_interfaces"
_GZ_SIM_LAUNCH = "companion:ros_gz/ros_gz_sim/launch/gz_sim.launch.py.in"

_WORLD = "/world/simple_tunnel"
#: The e-stop: a WorldControl request with pause true.  The simulator queues it and applies it in the step loop.
_PAUSE = {
    "service": _WORLD + "/control",
    "type": "ros_gz_interfaces/srv/ControlWorld",
    "source_name": "control",
    "source_ref": _RUN + ":214",
    "type_ref": _SRV + ":43-52",
    "state_ref": _RUN + ":1242",
    "description": "Pause the Ignition world simple_tunnel (WorldControl through ros_gz: SetPaused(true) in the step loop)",
    "request": {"world_control": {"pause": True}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 400,
}
#: The read-back that confirms it (E2): WorldStatistics.paused, in fresh samples.
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
_VEL_ID = "x-cap.justyx404.cmd_vel.v1"
_ODOM_ID = "x-cap.justyx404.odometry.v1"
_JOINTS_ID = "x-cap.justyx404.joint_states.v1"
_CLOCK_ID = "x-cap.justyx404.clock.v1"

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
    Fact("PublishStats publishes the clock message after the statistics, and the comment says the clock is not "
         "throttled.", source="upstream_code", ref=_RUN + ":444-445"),
    Fact("PublishStats sets the clock message's sim time from the current info.", source="upstream_code",
         ref=_RUN + ":449-450"),
    Fact("PublishStats sets the clock message's system time from IGN_SYSTEM_TIME.", source="upstream_code",
         ref=_RUN + ":451-453"),
    Fact("The Physics system steps the physics only when not paused.", source="upstream_code",
         ref=_PHYSICS + ":855-859"),
    Fact("OdometryPublisher::PostUpdate returns immediately when paused.", source="upstream_code",
         ref=_ODOM_SYS + ":302-304"),
    Fact("JointTrajectoryController::PreUpdate returns when paused.", source="upstream_code",
         ref=_TRAJ_SYS + ":438-441"),
    Fact("PreUpdate calls SetTarget with the current trajectory point when a target update is required, and then "
         "Update on each actuated joint.", source="upstream_code", ref=_TRAJ_SYS + ":498-519"),
    Fact("A new JointTrajectory resets the stored trajectory and then copies the message's joint names and points.",
         source="upstream_code", ref=_TRAJ_SYS + ":677-688"),
    Fact("JointStatePublisher::PostUpdate stamps the model message from the simulation time.",
         source="upstream_code", ref=_JOINT_STATE_SYS + ":186-189"),
    Fact("Server::Run's third argument _paused defaults to true.", source="upstream_code", ref=_SERVER_HH + ":150-152"),
    Fact("Server::Run calls SetPaused with _paused on each simulation runner.", source="upstream_code",
         ref=_SERVER_CC + ":174-179"),
    Fact("gz.cc calls server.Run with the third argument _run == 0.", source="upstream_code", ref=_GZ_CC + ":408"),
    Fact("The ign gazebo usage text describes -r as run simulation on start.", source="upstream_code",
         ref=_GZ_CMD + ":116"),
    Fact("The ign gazebo command defaults the run option to 0.", source="upstream_code", ref=_GZ_CMD + ":229"),
    Fact("The -r option sets run to 1.", source="upstream_code", ref=_GZ_CMD + ":262-263"),
    Fact("The ros_gz_sim launch declares gz_args with an empty default.", source="upstream_code",
         ref=_GZ_SIM_LAUNCH + ":167"),
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
    Fact("The parameter_bridge usage shows a Gazebo-to-ROS argument with an opening bracket.",
         source="upstream_code", ref=_PARAM_BRIDGE + ":51-53"),
    Fact("The parameter_bridge usage shows a service bridge argument for ControlWorld.",
         source="upstream_code", ref=_PARAM_BRIDGE + ":57-61"),
    Fact("The bridge's publisher QoS is KeepLast with the queue size, and its depth, durability, history and "
         "reliability may be overridden.", source="upstream_code", ref=_FACTORY + ":60-80"),
]


class _VelocityReceipt:
    """A velocity publication's receipt names the three Twist components handed to rosbridge.

    The rosbridge publish result carries published and confirmed.  The three sent fields are the arguments of this
    call.  The wrapper sends no other command.  It never publishes a zero on the caller's behalf and never unpauses
    the world.  A caller invoke of the velocity capability still passes through the server envelope; this annotation
    does not.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _VEL_ID:
            return output
        output = dict(output)
        values = dict(args or {})
        for key in ("linear_velocity", "lateral_velocity", "angular_velocity"):
            output["sent_" + key] = float(values[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: Model review: the gait caps live only in the launch-loaded parameter file
#: (gait.yaml:7-9), no line of the clone shows the negative bounds (they are the
#: negation in leg_controller.h:96-98), and the controller clamps a larger
#: request instead of refusing it.  The envelope is therefore operator_required;
#: site-limits.example.json copies the gait.yaml caps as an example overlay.
_VELOCITY_LIMIT_REASON = (
    "the clone states the CHAMP gait caps (max_linear_velocity_x 1.5, max_linear_velocity_y 0.25, "
    "max_angular_velocity_z 1.0) only in the launch-loaded parameter file champ_config/config/gait/gait.yaml:7-9; "
    "no line shows the negative bounds, which are the negation in leg_controller.h:96-98, and the controller "
    "clamps a larger request instead of refusing it, so the operator supplies the deployment's envelope"
)
_LINEAR_LIMIT = Limit.operator_required(_VELOCITY_LIMIT_REASON)
_LATERAL_LIMIT = Limit.operator_required(_VELOCITY_LIMIT_REASON)
_ANGULAR_LIMIT = Limit.operator_required(_VELOCITY_LIMIT_REASON)

_PUBLISHED = {
    "published": Field("boolean",
                       description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_POSITION = Field(
    "object",
    description="Cartesian position in the odometry frame",
    properties={
        "x": Field("number", unit="m", description="X position"),
        "y": Field("number", unit="m", description="Y position"),
        "z": Field("number", unit="m", description="Z position"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Quaternion orientation in the odometry frame",
    properties={
        "x": Field("number", unit="1", description="Quaternion x component"),
        "y": Field("number", unit="1", description="Quaternion y component"),
        "z": Field("number", unit="1", description="Quaternion z component"),
        "w": Field("number", unit="1", description="Quaternion w component"),
    },
)

_LINEAR_VECTOR = Field(
    "object",
    description="Linear velocity vector",
    properties={
        "x": Field("number", unit="m/s", description="X component"),
        "y": Field("number", unit="m/s", description="Y component"),
        "z": Field("number", unit="m/s", description="Z component"),
    },
)

_ANGULAR_VECTOR = Field(
    "object",
    description="Angular velocity vector",
    properties={
        "x": Field("number", unit="rad/s", description="X component"),
        "y": Field("number", unit="rad/s", description="Y component"),
        "z": Field("number", unit="rad/s", description="Z component"),
    },
)

_ODOM_TWIST = Field(
    "object",
    description="Body twist reported by the simulated odometry",
    properties={
        "linear": _LINEAR_VECTOR,
        "angular": _ANGULAR_VECTOR,
    },
)

_JOINT_NAMES = Field(
    "array",
    description="Joint names in the order of the position array",
    items=Field("string", description="One joint name"),
)

_JOINT_POSITIONS = Field(
    "array",
    unit="rad",
    description="Joint positions in the publisher's joint order",
    items=Field("number", unit="rad", description="One joint position"),
)

#: ROS 2 builtin_interfaces/Time fields (sec, nanosec).
_SIM_TIME = Field(
    "object",
    description="Simulated ROS 2 clock sample (builtin_interfaces/Time)",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the second"),
    },
)

#: One persistent Twist publication.  The three mapped components are exactly
#: the fields the upstream callback reads; the rest stay at the zero template.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TWIST_TYPE_REF,
    "operation": "publish",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_velocity"},
        "linear.y": {"from": "input.lateral_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

_ODOMETRY = {
    "topic": "/spot/odometry",
    "type": "nav_msgs/msg/Odometry",
    "source_ref": _ODOMETRY_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "position": "pose.pose.position",
        "orientation": "pose.pose.orientation",
        "twist": "twist.twist",
    }},
}

_JOINT_STATES = {
    "topic": "/spot/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "source_ref": _JOINT_STATE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"names": "name", "positions": "position"}},
}

_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "source_ref": _CLOCK_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {"sim_time": "clock"}},
}


class SpotGazeboRos2(RosDriver):
    device_id = "spot-gazebo"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeSpotGazeboRos2"}
    display_name = "Spot quadruped in an Ignition/Gazebo ROS 2 simulation"
    vendor = "justyx404"
    model = "Boston Dynamics Spot (CHAMP simulation)"
    tags = ["ros", "ros2", "gazebo", "ignition", "simulation", "spot", "quadruped", "mobile-base", "cmd-vel"]

    facts = [
        Fact("The launch starts ros_gz_sim with the selected world file through the ros_gz_sim include.",
             source="upstream_code", ref="spot_bringup/launch/spot.gazebo.launch.py:33-48"),
        Fact("The launch's gz_args value is a path join of the spot_gazebo worlds directory and the world file.",
             source="upstream_code", ref="spot_bringup/launch/spot.gazebo.launch.py:40-45"),
        Fact("The launch starts the ros_gz_bridge parameter_bridge with spot_bridge.yaml as its config file.",
             source="upstream_code", ref="spot_bringup/launch/spot.gazebo.launch.py:50-61"),
        Fact("spot_bridge.yaml maps /clock, /spot/joint_states and /spot/odometry from Gazebo to ROS with "
             "rosgraph_msgs/msg/Clock, sensor_msgs/msg/JointState and nav_msgs/msg/Odometry.",
             source="upstream_code", ref="spot_bringup/config/spot_bridge.yaml:3-16"),
        Fact("The launch starts champ_base/quadruped_controller_node with gazebo true, publish_joint_states "
             "false, publish_joint_control true, joint_controller_topic /spot/joint_trajectory, and remaps "
             "/cmd_vel/smooth to /cmd_vel.",
             source="upstream_code", ref=_CONTROLLER_LAUNCH_REF),
        Fact("The quadruped controller creates a geometry_msgs::msg::Twist subscription on the relative "
             "cmd_vel/smooth topic with queue size 10.", source="upstream_code", ref=_CMD_VEL_SUBSCRIPTION_REF),
        Fact("The controller header includes geometry_msgs/msg/twist.hpp for the Twist subscription.",
             source="upstream_code", ref=_TWIST_TYPE_REF),
        Fact("The cmd_vel callback copies linear.x, linear.y and angular.z into the persistent req_vel_ member "
             "and stores no receive time or stale-command deadline.",
             source="upstream_code", ref=_CMD_VEL_CALLBACK_REF),
        Fact("controlLoop_ calls leg_controller_.velocityCommand with the stored req_vel_, solves the inverse "
             "kinematics and calls publishJoints_.", source="upstream_code", ref=_CONTROL_LOOP_REF),
        Fact("The constructor initialises loop_rate to 200.0.", source="upstream_code",
             ref="champ_base/src/quadruped_controller.cpp:49"),
        Fact("The constructor runs controlLoop_ from a wall timer whose period is 1000/loop_rate milliseconds.",
             source="upstream_code", ref="champ_base/src/quadruped_controller.cpp:94-97"),
        Fact("LegController::velocityCommand caps linear.x, linear.y and angular.z to the negated and positive "
             "configured gait maxima.", source="upstream_code", ref=_VELOCITY_CLAMP_REF),
        Fact("The gait configuration sets max_linear_velocity_x to 1.5, max_linear_velocity_y to 0.25 and "
             "max_angular_velocity_z to 1.0.", source="upstream_code", ref=_GAIT_CONFIG_REF),
        Fact("The launch loads champ_config/config/gait/gait.yaml as the controller's gait ParameterFile.",
             source="upstream_code", ref="spot_bringup/launch/spot.gazebo.launch.py:90-91"),
        Fact("publishJoints_ builds a trajectory_msgs/msg/JointTrajectory with 12 positions and a zero header "
             "stamp.", source="upstream_code", ref=_TRAJECTORY_REF),
        Fact("spot_bridge.yaml maps /spot/joint_trajectory from ROS to Gazebo with "
             "trajectory_msgs/msg/JointTrajectory.", source="upstream_code", ref=_TRAJECTORY_BRIDGE_REF),
        Fact("The simple_tunnel world loads the Physics, Sensors, SceneBroadcaster and UserCommands systems.",
             source="upstream_code", ref=_WORLD_REF),
        Fact("simple_tunnel.sdf names its world simple_tunnel.", source="upstream_code",
             ref="spot_gazebo/worlds/simple_tunnel.sdf:3"),
        Fact("edgar_mine.sdf names its world edgar_mine.", source="upstream_code",
             ref="spot_gazebo/worlds/edgar_mine.sdf:3"),
        Fact("electrical_substation.sdf names its world electrical_substation_v3.", source="upstream_code",
             ref="spot_gazebo/worlds/electrical_substation.sdf:3"),
        Fact("The simple_tunnel world file loads a plugin named World control from filename WorldControl.",
             source="upstream_code", ref="spot_gazebo/worlds/simple_tunnel.sdf:84-85"),
        Fact("The simple_tunnel WorldControl GUI sets play_pause true, step true and start_paused false.",
             source="upstream_code", ref="spot_gazebo/worlds/simple_tunnel.sdf:101-103"),
        Fact("The edgar_mine world file sets play_pause true, step true and start_paused true.",
             source="upstream_code", ref="spot_gazebo/worlds/edgar_mine.sdf:93-95"),
        Fact("The Spot model loads a JointStatePublisher on model/spot/joint_state.", source="upstream_code",
             ref="spot_description/models/spot/model.sdf:1874-1878"),
        Fact("The Spot model loads an OdometryPublisher on /model/spot/odometry.", source="upstream_code",
             ref="spot_description/models/spot/model.sdf:1881-1886"),
        Fact("The Spot model loads a JointTrajectoryController on model/spot/joint_trajectory.",
             source="upstream_code", ref="spot_description/models/spot/model.sdf:1891-1894"),
        Fact("The README names a ROS 2 Humble simulation package.", source="vendor_doc", ref="README.md:3"),
        Fact("The README lists Gazebo Fortress among the install requirements.", source="vendor_doc",
             ref="README.md:53"),
        Fact("The README's navigation steps launch spot_navigation online_async_launch.py.", source="vendor_doc",
             ref="README.md:105"),
        Fact("The README's navigation steps launch spot_navigation localization_launch.py.", source="vendor_doc",
             ref="README.md:110"),
        Fact("far_planner.launch.py starts a node from package spot_navigation.", source="upstream_code",
             ref="spot_bringup/launch/far_planner.launch.py:82"),
        Fact("The README states that all body camera and depth sensors are not used and are disabled to save "
             "computation.", source="vendor_doc", ref=_README_CAMERAS_REF),
        *_COMPANION_FACTS,
    ]

    safe_state = (
        "The world simple_tunnel is paused: after the WorldControl pause two fresh stats samples, 40 ms or more "
        "apart within 600 ms, reported paused true, so the world does not step; it is the paused flag in that "
        "window, not a measured standstill, it needs the operator-run ros_gz bridges, and no unpause is offered "
        "because CHAMP keeps req_vel_ and the JointTrajectoryController keeps its targets, so the operator zeros "
        "/cmd_vel and unpauses outside MHS."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned topic replies with no Ignition physics, CHAMP gait or state-hash replay; "
                     "its world statistics follow the wall clock",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free contract stand-in, not a recording of captured traffic: it answers the declared "
            "subscriptions and services and records the declared publication, but runs no Ignition Gazebo, "
            "ros_gz_bridge, physics, CHAMP controller or ROS graph",
            "the odometry, joint-state and clock samples are placeholders; the fake echoes a received /cmd_vel into "
            "the placeholder odometry twist only so a later read can show it, and that echo is not measured motion",
            "the /cmd_vel command is a persistent Twist with no acknowledgement; the receipt reports the three "
            "components handed to rosbridge (sent_linear_velocity, sent_lateral_velocity, sent_angular_velocity) "
            "and confirmed is always false",
            "the velocity envelope is operator_required: the CHAMP gait caps live in the launch-loaded gait.yaml, "
            "which the controller clamps to rather than refusing; site-limits.example.json copies them as an "
            "example, and a deployment that loads another ParameterFile has another envelope; a caller invoke of "
            "the velocity capability without an overlay is LIMITS_UNSET",
            "the controller runs on a wall timer (period 1000/loop_rate ms, loop_rate 200.0, "
            "quadruped_controller.cpp:49, 94-97) and keeps applying the stored req_vel_ and publishing joint "
            "trajectories; the JointTrajectoryController returns while paused (JointTrajectoryController.cc:438-441) "
            "so joints do not move until the world steps, and a new trajectory resets the stored points and replaces "
            "them (677-688) rather than replaying a queue",
            "the stop is the companion Ignition world pause (WorldControl through ros_gz ControlWorld) on "
            "/world/simple_tunnel/control, whose reply is true for any request the simulator queued "
            "(SimulationRunner.cc:1174-1176); it is confirmed by the E2 read-back of paused on "
            "/world/simple_tunnel/stats; the fake keeps a paused flag that the control request sets after its next "
            "statistics sample and publishes stats every 100 ms (placeholder) while subscribed",
            "the e-stop endpoints exist only while the operator runs ros_gz's parameter_bridge with the two "
            "arguments of operator_bridges (the clone's spot_bridge.yaml:3-16 and 76-80 bridge topics only, not the "
            "control service or the stats topic); without them the control call is not answered and the read-back "
            "sees no sample, so the e-stop fails closed; the declared estop_latency_ms 1500 covers the control call "
            "(400 ms) and the read-back bound (600 ms)",
            "the read-back's freshness is the arrival time only: PublishStats sets sim time, real time, iterations "
            "and paused and the only header write in that range is the optional step key (SimulationRunner.cc:420-436); "
            "the WorldStatistics conversion copies that header (ros_gz_interfaces.cpp:823-827); the bridge's publisher "
            "QoS sets only KeepLast with the queue size (factory.hpp:60-80), so its durability stays rclcpp's default, "
            "volatile; the first sample is discarded and a burst of samples restarts the count",
            "the endpoints name the world simple_tunnel (simple_tunnel.sdf:3), the launch default "
            "(spot.gazebo.launch.py:14-18); edgar_mine.sdf:3 and electrical_substation.sdf:3 name other worlds, so "
            "those launches have other endpoints and the e-stop fails closed",
            "a live world can be unpaused or stepped by the WorldControl GUI (simple_tunnel.sdf:84-85 and 101-103 "
            "set play_pause and step true; that file's start_paused is false, edgar_mine.sdf:93-95 sets start_paused "
            "true, and electrical_substation.sdf contains no start_paused property), by a WorldControl multi_step "
            "(SimulationRunner.cc:1244-1251) or by any client of the control service; MHS does not watch the flag "
            "after the e-stop",
            "the launch's gz_args is only the world path (spot.gazebo.launch.py:40-45) and passes no -r; the ign "
            "gazebo command defaults run to 0 (cmdgazebo.rb.in:229) and -r sets it to 1 (262-263); gz.cc:408 calls "
            "server.Run with _run == 0, and Server::Run's _paused defaults to true and is applied with SetPaused "
            "(Server.hh:150-152, Server.cc:174-179), so a real server starts paused; the ros_gz_sim launch's gz_args "
            "default is empty (gz_sim.launch.py.in:167); the GUI start_paused property is not that server flag; the "
            "fake starts unpaused so the explicit reads succeed before an e-stop; the package offers no unpause, so "
            "the operator's first unpause of a real server is outside MHS",
            "while paused, OdometryPublisher::PostUpdate returns immediately (OdometryPublisher.cc:302-304), so "
            "/model/spot/odometry, bridged to /spot/odometry, is silent and its read fails NOT_READY; "
            "PublishStats still publishes /clock, unthrottled, with sim time that does not advance while paused and "
            "with system time from IGN_SYSTEM_TIME (SimulationRunner.cc:444-453); JointStatePublisher::PostUpdate "
            "stamps from sim time and the function has no paused return before that stamp "
            "(JointStatePublisher.cc:140-189), so /spot/joint_states keeps being published; the fake silences only "
            "/spot/odometry while paused and keeps answering /clock and /spot/joint_states; none of the three is a "
            "device-resource read, so a reset does not wait on them",
            "no unpause is offered, neither as a re-enable nor as an ordinary command: the callback stores "
            "linear.x, linear.y and angular.z in req_vel_ (quadruped_controller.cpp:116-121) and a wall timer keeps "
            "calling controlLoop_ (:94-97, :101-113); JointTrajectoryController::PreUpdate returns while paused "
            "(:438-441) and, once that return is passed, SetTarget applies the stored trajectory point and Update "
            "runs (:498-519); a new trajectory resets then replaces the points (:677-688), but a zero Twist is "
            "unacknowledged and does not clear those joint targets before an unpause; after mhs.safety.reset the "
            "world stays paused, and the operator zeros /cmd_vel, lets the wall timer replace the trajectory, then "
            "unpauses outside MHS (the GUI play control or a ControlWorld request with pause false); the README "
            "names spot_navigation launches (README.md:105, 110) and far_planner.launch.py:82 names package "
            "spot_navigation, but the clone's top-level directories do not include a spot_navigation source tree, "
            "and any other publisher of /cmd_vel changes req_vel_",
            "the deployment's ignition-gazebo and ros_gz must be the pinned 6.18.0 and 0.244.27 releases (ROS 2 "
            "Humble with Ignition Fortress); rosbridge cannot read the versions",
            "camera, depth, lidar, IMU, TF, navigation and the /spot/joint_trajectory publication are not commands "
            "of this package; the README states the body camera and depth sensors are disabled (README.md:22)",
        ],
    }

    # The device resource reads no topic.  /spot/odometry is silent while the e-stop holds the world paused, so a
    # resource that waited for it would fail NOT_READY after every reset.  /clock and /spot/joint_states keep
    # publishing, and leaving them out of the resource means a reset does not wait on them either.  All three stay
    # explicit read capabilities below.
    estop_latency_ms = 1500
    commands = {
        _VEL_ID: _CMD_VEL,
        _ODOM_ID: _ODOMETRY,
        _JOINTS_ID: _JOINT_STATES,
        _CLOCK_ID: _CLOCK,
    }
    actions = {
        _VEL_ID: Action(
            name="publish_velocity",
            verb="invoke",
            risk="R2",
            max_duration_ms=2000,
            description="Publish one geometry_msgs/Twist on /cmd_vel; the receipt reports transmission and the "
                        "three components handed to rosbridge, not motion, arrival or a stop",
            input={
                "linear_velocity": Field(
                    "number", unit="m/s", limit=_LINEAR_LIMIT,
                    description="Body-frame forward velocity; the callback uses twist.linear.x"),
                "lateral_velocity": Field(
                    "number", unit="m/s", limit=_LATERAL_LIMIT,
                    description="Body-frame lateral velocity; the callback uses twist.linear.y"),
                "angular_velocity": Field(
                    "number", unit="rad/s", limit=_ANGULAR_LIMIT,
                    description="Body-frame yaw rate; the callback uses twist.angular.z"),
            },
            output={
                **_PUBLISHED,
                "sent_linear_velocity": Field(
                    "number", unit="m/s",
                    description="The linear.x handed to rosbridge (the transmitted request)"),
                "sent_lateral_velocity": Field(
                    "number", unit="m/s",
                    description="The linear.y handed to rosbridge (the transmitted request)"),
                "sent_angular_velocity": Field(
                    "number", unit="rad/s",
                    description="The angular.z handed to rosbridge (the transmitted request)"),
            },
        ),
        _ODOM_ID: Action(
            name="read_odometry",
            verb="read",
            risk="R0",
            max_duration_ms=2000,
            description="Read one nav_msgs/Odometry sample from /spot/odometry (silent, and NOT_READY, while the "
                        "world is paused)",
            output={"position": _POSITION, "orientation": _ORIENTATION, "twist": _ODOM_TWIST},
        ),
        _JOINTS_ID: Action(
            name="read_joint_states",
            verb="read",
            risk="R0",
            max_duration_ms=2000,
            description="Read one sensor_msgs/JointState sample from /spot/joint_states; the publisher does not "
                        "return while paused, so a paused world can still answer",
            output={"names": _JOINT_NAMES, "positions": _JOINT_POSITIONS},
        ),
        _CLOCK_ID: Action(
            name="read_sim_clock",
            verb="read",
            risk="R0",
            max_duration_ms=2000,
            description="Read one rosgraph_msgs/Clock sample from /clock; PublishStats keeps publishing it while "
                        "paused, with sim time that does not advance",
            output={"sim_time": _SIM_TIME},
        ),
    }
    #: E3: the bridges the operator runs (ros_gz parameter_bridge, one argument each).  The package never starts them.
    operator_bridges = [
        {"args": "/world/simple_tunnel/control@ros_gz_interfaces/srv/ControlWorld",
         "ref": _BRIDGE_README + ":78",
         "description": "The world control service: the e-stop pause."},
        {"args": "/world/simple_tunnel/stats@ros_gz_interfaces/msg/WorldStatistics[ignition.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":55",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    # The e-stop pauses the world and confirms it by the paused flag in fresh statistics samples.  No reset binding
    # and no re-enable: mhs.safety.reset releases the latch only, and the world stays paused (REVIEW.md item 13).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _VelocityReceipt(super().make_bridge(native))
