"""OpenMHS rosbridge driver for the Virtual RobotX (VRX) simulation environment.

The pinned repository is the VRX Gazebo Harmonic / ROS 2 Jazzy simulator.  It
is not a ROS node with a Python native class: Gazebo owns the world, physics
and model spawn, and the repository bridges a selected set of Gazebo topics to
ROS 2 through ``ros_gz_bridge``.  This package is therefore a configuration-only
:class:`RosDriver`; it declares no Python native class and neither imports nor
launches the upstream code.

Scope is the competition bridge that ``vrx_gz.launch.competition_bridges``
always starts: the simulated clock (``/clock``) and the scoring plugin's task
information (``/vrx/task/info``).  It also declares the ROS command surface that
the shipped WAM-V launch creates for the two aft thrusters and their joint
position controllers (``/wamv/thrusters/{left,right}/{thrust,pos}``).  Each
command's receipt reports the value it handed to rosbridge; the device resource
reads no topic (the earlier command-echo reads subscribed to command topics that
nothing publishes on a schedule, and a paused world publishes no observation).

The clone has no stop of its own: world pause, step and reset are Gazebo
Transport operations.  The e-stop is the Gazebo world pause of the simulator's
own repository, cited as reviewed companion sources fetched at pinned commits
(user decision and authorisation of 2026-11-05; ``task.json`` ``companions``
with ``lock``): gz-sim 8.15.0 (Harmonic) serves the WorldControl service
``/world/sydney_regatta/control``, and ros_gz 1.0.25 (Jazzy) bridges it as
``ros_gz_interfaces/srv/ControlWorld``.  Its reply is true for any request
gz-sim queued, so it confirms nothing; the stop is confirmed by a fresh-sample
topic read-back (E2): ``WorldStatistics.paused`` on
``/world/sydney_regatta/stats`` must be true in two samples that arrived at
least 40 ms apart, after a discarded first one, within 600 ms.  Neither
endpoint exists unless the operator runs ros_gz's ``parameter_bridge`` with the
two arguments in ``operator_bridges`` (E3); without them the e-stop fails
closed.

No unpause is offered (the orchestrator's SAFE-042 condition): the Thruster
system keeps the last thrust command and the joint position controllers the
last angle target, and buoyancy, waves and wind act on the hull as soon as the
world runs.  A zero thrust would replace the stored thrust (unacknowledged), but
a stored angle target cannot be cleared without a joint reading the clone does
not bridge, so the operator recovers outside MHS (see ``safe_state`` and
``facts.md``).

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 7609d1bd90ce7edb29d040a082f949e8b089c864.  The fake transport is
ROS-free and its numbers are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: Gazebo and ROS 2 versions stated by the README.
_README_REF = "README.md:14-16"

#: competition_bridges always starts the clock and task-info bridges and wraps
#: them in a ros_gz_bridge parameter_bridge node.
_COMPETITION_BRIDGES_REF = "vrx_gz/src/vrx_gz/launch.py:255-259"
_BRIDGE_NODE_REF = "vrx_gz/src/vrx_gz/launch.py:311-318"

#: The exact bridge definitions: names, types and directions.
_CLOCK_REF = "vrx_gz/src/vrx_gz/bridges.py:88-94"
_TASK_INFO_REF = "vrx_gz/src/vrx_gz/bridges.py:96-102"

#: ScoringPlugin's task-info publisher and its message fields.
_TASK_TOPIC_REF = "vrx_gz/src/ScoringPlugin.cc:80"
_TASK_PUBLISHER_REF = "vrx_gz/src/ScoringPlugin.cc:441-442"
_TASK_FIELDS_REF = "vrx_gz/src/ScoringPlugin.cc:314-336"

#: Model.bridges only adds cmd_vel for UAV models; the USV branch is empty.
_MODEL_TYPES_REF = "vrx_gz/src/vrx_gz/model.py:36-44"
_MODEL_UAV_REF = "vrx_gz/src/vrx_gz/model.py:60-64"
_MODEL_BRIDGES_REF = "vrx_gz/src/vrx_gz/model.py:81-93"

#: The default WAM-V is spawned with the model name used as the ROS namespace.
_SPAWN_NAMESPACE_REF = "vrx_gz/src/vrx_gz/launch.py:384-387"
_DEFAULT_NAME_REF = "vrx_gz/launch/competition.launch.py:112-119"

#: The Gazebo simulator is started through ros_gz_sim's gz_sim launch; the
#: paused flag is a launch argument, not a ROS service.
_SIM_LAUNCH_REF = "vrx_gz/src/vrx_gz/launch.py:214-230"

#: The thruster payload detection and bridge declarations.
_PAYLOAD_DETECT_REF = "vrx_gz/src/vrx_gz/model.py:296-313"
_PAYLOAD_DISPATCH_REF = "vrx_gz/src/vrx_gz/payload_bridges.py:229-236"
_THRUST_BRIDGE_REF = "vrx_gz/src/vrx_gz/payload_bridges.py:152-158"
_POS_BRIDGE_REF = "vrx_gz/src/vrx_gz/payload_bridges.py:160-172"

#: The shipped teleop configuration names the resolved ROS topics and type.
_LEFT_THRUST_REF = "vrx_gz/config/wamv.yaml:80-81"
_RIGHT_THRUST_REF = "vrx_gz/config/wamv.yaml:91-92"
_LEFT_POS_REF = "vrx_gz/config/wamv.yaml:102-103"
_RIGHT_POS_REF = "vrx_gz/config/wamv.yaml:113-114"

#: The Gazebo-side thruster and joint-position-controller topics.
_THRUSTER_PLUGIN_REF = "vrx_urdf/wamv_gazebo/urdf/thruster_layouts/wamv_gazebo_thruster_config.xacro:10-24"
_POSITION_PLUGIN_REF = "vrx_urdf/wamv_gazebo/urdf/thruster_layouts/wamv_gazebo_thruster_config.xacro:26-34"

_THRUST_REASON = (
    "the pinned clone states no numeric range or physical unit for the Float64 thruster command; "
    "the operator supplies the deployment envelope in site-limits.json")
_POSITION_REASON = (
    "the pinned clone states no numeric range or unit for the Float64 joint-position command; "
    "the operator supplies the deployment envelope in site-limits.json")

#: The default world and its SDF name: the world control endpoints name it.
_WORLD_ARGUMENT_REF = "vrx_gz/launch/competition.launch.py:68-71"
_WORLD_SDF_REF = "vrx_gz/worlds/sydney_regatta.sdf:4"

# -- Companion sources (task.json companions with lock; user decision and authorisation of 2026-11-05) -----------
#: gz-sim 8.15.0 (Harmonic) at 446a4433, fetched under work/companions: the world runner, its control service and
#: its statistics, and the systems a paused world does not run.
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_THRUSTER = "companion:gz_sim/src/systems/thruster/Thruster.cc"
_JOINT_POSITION = "companion:gz_sim/src/systems/joint_position_controller/JointPositionController.cc"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
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

_WORLD = "/world/sydney_regatta"
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
    Fact("The Thruster system's thrust callback stores the clamped thrust command.", source="upstream_code",
         ref=_THRUSTER + ":517-526"),
    Fact("The Thruster system's PreUpdate returns early while paused.", source="upstream_code",
         ref=_THRUSTER + ":634-639"),
    Fact("The joint position controller's position callback stores the commanded position.", source="upstream_code",
         ref=_JOINT_POSITION + ":489-492"),
    Fact("The joint position controller's PreUpdate returns early while paused.", source="upstream_code",
         ref=_JOINT_POSITION + ":395-397"),
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
    Fact("ros_gz_interfaces ParamVec carries a header and rcl_interfaces Parameter entries.", source="upstream_code",
         ref=_INTERFACES + "/msg/ParamVec.msg:3-7"),
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

_SENT_VALUE = {
    "x-cap.osrf.left-thrust.v1": "thrust",
    "x-cap.osrf.right-thrust.v1": "thrust",
    "x-cap.osrf.left-thrust-position.v1": "position",
    "x-cap.osrf.right-thrust-position.v1": "position",
}


class _SentReceipt:
    """The receipt of a thruster or joint-position publication also reports the value it handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees what a publication sent; it is the
    transmitted request, not a measurement. Every other call, the e-stop and the reset included, goes to the SDK bridge
    unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        key = _SENT_VALUE.get(capability_id)
        if key is None:
            return output
        output = dict(output)
        output["sent_" + key] = float(dict(args or {})[key])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)

_CLOCK_TIME = Field(
    "object",
    description="rosgraph_msgs/msg/Clock clock field (builtin_interfaces/Time) as forwarded by the ros_gz bridge",
    properties={
        "sec": Field("integer", unit="s", description="Whole seconds of simulated time"),
        "nanosec": Field("integer", unit="ns", description="Nanoseconds within the simulated second"),
    },
)

_TASK_PARAMS = Field(
    "array",
    description=("ros_gz_interfaces/ParamVec.params entries: one Param name/value object per scoring-plugin "
                 "field (the plugin sets name, state, ready_time, running_time, elapsed_time, remaining_time, "
                 "timed_out, num_collisions and score)"),
    items=Field("object", description="One Param entry as forwarded by the ros_gz bridge"),
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_CLOCK = {
    "topic": "/clock",
    "type": "rosgraph_msgs/msg/Clock",
    "source_name": "/clock",
    "source_ref": _CLOCK_REF,
    "operation": "subscribe",
    "path": "clock",
    "result": {"map": {"sim_time": "output.$"}},
}

_TASK_INFO = {
    "topic": "/vrx/task/info",
    "type": "ros_gz_interfaces/msg/ParamVec",
    "source_name": "/vrx/task/info",
    "source_ref": _TASK_INFO_REF,
    "operation": "subscribe",
    "path": "params",
    "result": {"map": {"params": "output.$"}},
}

_LEFT_THRUST = {
    "topic": "/wamv/thrusters/left/thrust",
    "type": "std_msgs/msg/Float64",
    "source_name": "/wamv/thrusters/left/thrust",
    "source_ref": _LEFT_THRUST_REF,
    "type_ref": _THRUST_BRIDGE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.thrust"}},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

_RIGHT_THRUST = {
    "topic": "/wamv/thrusters/right/thrust",
    "type": "std_msgs/msg/Float64",
    "source_name": "/wamv/thrusters/right/thrust",
    "source_ref": _RIGHT_THRUST_REF,
    "type_ref": _THRUST_BRIDGE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.thrust"}},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

_LEFT_POS = {
    "topic": "/wamv/thrusters/left/pos",
    "type": "std_msgs/msg/Float64",
    "source_name": "/wamv/thrusters/left/pos",
    "source_ref": _LEFT_POS_REF,
    "type_ref": _POS_BRIDGE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.position"}},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

_RIGHT_POS = {
    "topic": "/wamv/thrusters/right/pos",
    "type": "std_msgs/msg/Float64",
    "source_name": "/wamv/thrusters/right/pos",
    "source_ref": _RIGHT_POS_REF,
    "type_ref": _POS_BRIDGE_REF,
    "operation": "publish",
    "message": {"data": 0.0},
    "args": {"data": {"from": "input.position"}},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}


class Vrx(RosDriver):
    device_id = "vrx"
    device_kind = "world.sim"
    mode = "simulated"
    # The thruster commands drive a simulated mobile vessel, so the command
    # binding carries at least the mobile-base risk.  The clone declares no
    # acknowledged stop for it; that missing stop is the package blocker.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeVrx"}
    tags = ["ros", "ros2", "simulation", "gazebo", "vrx", "usv", "clock", "task-info", "thrusters"]
    display_name = "Virtual RobotX (VRX) simulation environment"
    vendor = "Open Source Robotics Foundation"
    model = "Gazebo Harmonic + ROS 2 Jazzy"
    facts = [
        Fact("README.md states that the repository is ported to Gazebo Harmonic and ROS 2 Jazzy.",
             source="upstream_code", ref=_README_REF),
        Fact("competition_bridges always includes the clock and task_info bridges in its bridge list.",
             source="upstream_code", ref=_COMPETITION_BRIDGES_REF),
        Fact("competition_bridges constructs one ros_gz_bridge parameter_bridge Node with the arguments and "
             "remappings of its bridge list.",
             source="upstream_code", ref=_BRIDGE_NODE_REF),
        Fact("bridges.clock maps Gazebo /clock to ROS /clock as rosgraph_msgs/msg/Clock with the GZ_TO_ROS "
             "direction.", source="upstream_code", ref=_CLOCK_REF),
        Fact("bridges.task_info maps Gazebo /vrx/task/info to ROS /vrx/task/info as "
             "ros_gz_interfaces/msg/ParamVec with the GZ_TO_ROS direction.",
             source="upstream_code", ref=_TASK_INFO_REF),
        Fact("ScoringPlugin defaults its task-info topic to /vrx/task/info.",
             source="upstream_code", ref=_TASK_TOPIC_REF),
        Fact("ScoringPlugin advertises a Gazebo msgs::Param publisher on the task-info topic.",
             source="upstream_code", ref=_TASK_PUBLISHER_REF),
        Fact("ScoringPlugin::UpdateTaskMessage sets state, elapsed_time, remaining_time, timed_out, "
             "num_collisions and score, and PublishStats publishes them at 1 Hz.",
             source="upstream_code", ref=_TASK_FIELDS_REF),
        Fact("Model.is_UAV recognizes vrx_hexrotor and vrx_quadrotor, while Model.is_USV recognizes usv and "
             "wam-v.", source="upstream_code", ref=_MODEL_TYPES_REF),
        Fact("Model.is_UAV returns whether the model type is in UAVS and is_USV whether it is in USVS.",
             source="upstream_code", ref=_MODEL_UAV_REF),
        Fact("Model.bridges appends cmd_vel only inside the is_UAV branch; the is_USV branch performs no "
             "command bridge.", source="upstream_code", ref=_MODEL_BRIDGES_REF),
        Fact("launch.spawn places the bridge and helper nodes in a PushRosNamespace(model.model_name) group.",
             source="upstream_code", ref=_SPAWN_NAMESPACE_REF),
        Fact("competition.launch.py defaults the spawned robot name to wamv and its model type to wam-v.",
             source="upstream_code", ref=_DEFAULT_NAME_REF),
        Fact("launch.simulation starts ros_gz_sim's gz_sim launch and passes -r unless the launch was given "
             "paused; the paused flag is a launch argument, not a ROS service.",
             source="upstream_code", ref=_SIM_LAUNCH_REF),
        Fact("Model.payload_from_sdf records each gz::sim::systems::Thruster and JointPositionController "
             "plugin as a thruster_thrust_<name> or thruster_rotate_<name> payload entry.",
             source="upstream_code", ref=_PAYLOAD_DETECT_REF),
        Fact("payload_bridges dispatches thruster_thrust_* entries to thrust() and thruster_rotate_* entries to "
             "thrust_joint_pos().", source="upstream_code", ref=_PAYLOAD_DISPATCH_REF),
        Fact("payload_bridges.thrust maps ROS thrusters/<side>/thrust to Gazebo "
             "<model>/thrusters/<side>/thrust as std_msgs/msg/Float64 with the ROS_TO_GZ direction.",
             source="upstream_code", ref=_THRUST_BRIDGE_REF),
        Fact("payload_bridges.thrust_joint_pos maps ROS thrusters/<side>/pos to Gazebo "
             "<model>/thrusters/<side>/pos as std_msgs/msg/Float64 with the ROS_TO_GZ direction.",
             source="upstream_code", ref=_POS_BRIDGE_REF),
        Fact("The shipped wamv.yaml teleop configuration names /wamv/thrusters/left/thrust with "
             "std_msgs/msg/Float64.", source="upstream_code", ref=_LEFT_THRUST_REF),
        Fact("The shipped wamv.yaml teleop configuration names /wamv/thrusters/right/thrust with "
             "std_msgs/msg/Float64.", source="upstream_code", ref=_RIGHT_THRUST_REF),
        Fact("The shipped wamv.yaml teleop configuration names /wamv/thrusters/left/pos with "
             "std_msgs/msg/Float64.", source="upstream_code", ref=_LEFT_POS_REF),
        Fact("The shipped wamv.yaml teleop configuration names /wamv/thrusters/right/pos with "
             "std_msgs/msg/Float64.", source="upstream_code", ref=_RIGHT_POS_REF),
        Fact("The WAM-V thruster macro configures gz-sim-thruster-system on topic "
             "thrusters/<name>/thrust with velocity_control true.",
             source="upstream_code", ref=_THRUSTER_PLUGIN_REF),
        Fact("The WAM-V thruster macro configures gz-sim-joint-position-controller-system on topic "
             "<namespace>/thrusters/<name>/pos.", source="upstream_code", ref=_POSITION_PLUGIN_REF),
        Fact("competition.launch.py declares the world argument with the default sydney_regatta.",
             source="upstream_code", ref=_WORLD_ARGUMENT_REF),
        Fact("sydney_regatta.sdf names its world sydney_regatta.", source="upstream_code", ref=_WORLD_SDF_REF),
        Fact("navigation_task.sdf also names its world sydney_regatta.", source="upstream_code",
             ref="vrx_gz/worlds/navigation_task.sdf:4"),
        Fact("The sydney_regatta GUI configuration loads the WorldControl plugin with play/pause and step enabled.",
             source="upstream_code", ref="vrx_gz/worlds/sydney_regatta.sdf:115-134"),
        Fact("ScoringPlugin's PreUpdate updates the time from the simulation time, updates the task state and calls "
             "PublishStats.", source="upstream_code", ref="vrx_gz/src/ScoringPlugin.cc:463-478"),
        Fact("ScoringPlugin's PublishStats publishes the task message once per second of the plugin's current time.",
             source="upstream_code", ref="vrx_gz/src/ScoringPlugin.cc:327-337"),
        Fact("The README names a humble branch for users who continue with Gazebo Garden and ROS 2 Humble.",
             source="vendor_doc", ref="README.md:18"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The world sydney_regatta is paused: after the WorldControl pause two fresh stats samples, 40 ms or more "
        "apart within 600 ms, reported paused true, so the world does not step and the thrusters apply no thrust; it "
        "is the paused flag in that window, not a measured standstill, it needs the operator-run ros_gz bridges, and "
        "no unpause is offered: stored thrust and angle targets, waves and wind act when the operator resumes it."
    )
    #: The checked backend is a ROS-free canned transport, not the upstream
    #: simulator: it runs no Gazebo physics, sensors, waves or thrusters.
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step or state-hash replay; its world statistics "
                     "follow the wall clock",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers the /clock and /vrx/task/info "
            "subscriptions and records the four /wamv thruster publications, but runs no Gazebo physics, "
            "thruster system, buoyancy, waves, wind, contacts, sensors or ROS graph",
            "clock samples and task-info entries are placeholders; a live run must receive /clock and "
            "/vrx/task/info from the operator's ros_gz_bridge and scoring plugin",
            "the task-info topic is published by a scoring plugin once per second of simulation time "
            "(ScoringPlugin.cc:327-337); worlds without that plugin or a competition bridge, and a paused world, "
            "publish no fresh task sample and the explicit observation must time out",
            "the /wamv thruster topics exist only when the shipped launch detects the Thruster and "
            "JointPositionController plugins and pushes the model name as the ROS namespace; the package "
            "assumes the default name wamv, and a renamed model requires matching endpoint configuration",
            "a thruster publication is transmission-only; the fake does not model the gz thruster system's "
            "max_thrust_cmd clamp or any resulting motion; each receipt reports the value it handed to rosbridge",
            "the stop is the companion gz-sim world pause (WorldControl through ros_gz ControlWorld), whose reply is "
            "true for any request gz-sim queued (SimulationRunner.cc:1375-1377); it is confirmed by the E2 read-back: "
            "the fake keeps a paused flag that the control request sets after its next statistics sample and "
            "publishes /world/sydney_regatta/stats every 100 ms (placeholder) while subscribed; it runs no "
            "SimulationRunner",
            "the e-stop endpoints exist only while the operator runs ros_gz's parameter_bridge with the two "
            "arguments of operator_bridges (competition_bridges and spawn bridge topics only, launch.py:255-259, "
            "311-318, 346-363); without them the control call is not answered and the read-back sees no sample, so "
            "the e-stop fails closed; the declared estop_latency_ms 1500 covers the control call (400 ms) and the "
            "read-back bound (600 ms)",
            "the read-back's freshness is the arrival time only: the bridged WorldStatistics header is the gz header, "
            "which PublishStats does not stamp (ros_gz convert copies it, ros_gz_interfaces.cpp:840); the bridge's "
            "default publisher QoS sets only KeepLast with the queue size (bridge_config.cpp:274-279), so its "
            "durability stays rclcpp's default, volatile, which replays no history to a late subscriber; the first "
            "sample is discarded and a burst of samples restarts the count; "
            "an operator QoS override of the stats publisher (factory.hpp:61-82) to a deeper transient-local "
            "history is not covered beyond that burst rule",
            "the endpoints name the default world sydney_regatta (competition.launch.py:68-71, "
            "sydney_regatta.sdf:4; navigation_task.sdf reuses the name); the other task worlds carry their own names, "
            "and with them the declared endpoints do not exist and the e-stop fails closed",
            "a live world can be unpaused or stepped by the Gazebo GUI's world control (play, pause and step, "
            "sydney_regatta.sdf:115-134), a WorldControl multi_step (SimulationRunner.cc:1445-1452) or any client of "
            "the control service; MHS does not watch the flag after the e-stop (safety_status re-reads it only on "
            "request)",
            "no unpause is offered: the Thruster system stores the last thrust command (Thruster.cc:517-526) and the "
            "joint position controller the last angle target (JointPositionController.cc:489-492), and buoyancy, "
            "waves and wind act on the hull as soon as the world steps; a zero thrust on both sides would replace the "
            "stored thrust only unacknowledged, and the angle target cannot be cleared without a joint reading this "
            "package does not have; after mhs.safety.reset the world stays paused, commands are stored for the next "
            "unpause, and the operator publishes zero thrust (and the wanted angles), checks the GUI and other "
            "publishers (the joystick teleop, wamv.yaml:75-119), then unpauses outside MHS (the GUI play button or a "
            "ControlWorld request with pause false)",
            "the deployment's gz-sim, ros_gz and gz-transport must be the pinned 8.15.0, 1.0.25 and 13.6.0 releases "
            "(ROS 2 Jazzy with Gazebo Harmonic); the README names a humble branch for Gazebo Garden and ROS 2 Humble "
            "(README.md:18), which this package does not serve; rosbridge cannot read the versions",
        ],
    }
    # The device resource reads no topic (the earlier command-echo reads subscribed to command topics that nothing
    # publishes on a schedule); each command's receipt reports the value it sent.
    estop_latency_ms = 1500
    commands = {
        "x-cap.osrf.clock.v1": _CLOCK,
        "x-cap.osrf.task-info.v1": _TASK_INFO,
        "x-cap.osrf.left-thrust.v1": _LEFT_THRUST,
        "x-cap.osrf.right-thrust.v1": _RIGHT_THRUST,
        "x-cap.osrf.left-thrust-position.v1": _LEFT_POS,
        "x-cap.osrf.right-thrust-position.v1": _RIGHT_POS,
    }
    actions = {
        "x-cap.osrf.clock.v1": Action(
            name="read_sim_clock",
            verb="read",
            description="Read one simulated ROS clock sample from the VRX ros_gz clock bridge",
            output={"sim_time": _CLOCK_TIME},
        ),
        "x-cap.osrf.task-info.v1": Action(
            name="read_task_info",
            verb="read",
            description=("Read one fresh /vrx/task/info ParamVec sample published by the VRX scoring plugin "
                         "through the competition bridge"),
            output={"params": _TASK_PARAMS},
        ),
        "x-cap.osrf.left-thrust.v1": Action(
            name="publish_left_thrust",
            verb="invoke",
            description=("Publish one Float64 command on /wamv/thrusters/left/thrust; the receipt is "
                         "transmission evidence only, not motion, thrust attainment or stopping."),
            input={"thrust": Field("number", unit="1",
                                   description="std_msgs/Float64 data forwarded to the left thruster topic",
                                   limit=Limit.operator_required(_THRUST_REASON))},
            output={**_PUBLISHED, "sent_thrust": Field("number", unit="1", description="The data handed to "
                                                                                     "rosbridge (the transmitted "
                                                                                     "request)")},
            risk="R2",
        ),
        "x-cap.osrf.right-thrust.v1": Action(
            name="publish_right_thrust",
            verb="invoke",
            description=("Publish one Float64 command on /wamv/thrusters/right/thrust; the receipt is "
                         "transmission evidence only, not motion, thrust attainment or stopping."),
            input={"thrust": Field("number", unit="1",
                                   description="std_msgs/Float64 data forwarded to the right thruster topic",
                                   limit=Limit.operator_required(_THRUST_REASON))},
            output={**_PUBLISHED, "sent_thrust": Field("number", unit="1", description="The data handed to "
                                                                                     "rosbridge (the transmitted "
                                                                                     "request)")},
            risk="R2",
        ),
        "x-cap.osrf.left-thrust-position.v1": Action(
            name="publish_left_thrust_position",
            verb="invoke",
            description=("Publish one Float64 command on /wamv/thrusters/left/pos; the receipt is "
                         "transmission evidence only, not joint motion or stopping."),
            input={"position": Field("number", unit="1",
                                     description="std_msgs/Float64 data forwarded to the left thruster "
                                                 "joint-position-controller topic",
                                     limit=Limit.operator_required(_POSITION_REASON))},
            output={**_PUBLISHED, "sent_position": Field("number", unit="1", description="The data handed to "
                                                                                         "rosbridge (the transmitted "
                                                                                         "request)")},
            risk="R2",
        ),
        "x-cap.osrf.right-thrust-position.v1": Action(
            name="publish_right_thrust_position",
            verb="invoke",
            description=("Publish one Float64 command on /wamv/thrusters/right/pos; the receipt is "
                         "transmission evidence only, not joint motion or stopping."),
            input={"position": Field("number", unit="1",
                                     description="std_msgs/Float64 data forwarded to the right thruster "
                                                 "joint-position-controller topic",
                                     limit=Limit.operator_required(_POSITION_REASON))},
            output={**_PUBLISHED, "sent_position": Field("number", unit="1", description="The data handed to "
                                                                                         "rosbridge (the transmitted "
                                                                                         "request)")},
            risk="R2",
        ),
    }
    #: E3: the bridges the operator runs (ros_gz parameter_bridge, one argument each); the package never starts them.
    operator_bridges = [
        {"args": "/world/sydney_regatta/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE_README + ":86",
         "description": "The world control service: the e-stop pause."},
        {"args": "/world/sydney_regatta/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":52",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    # The e-stop pauses the world and confirms it by the paused flag in fresh statistics samples (companion gz-sim
    # and ros_gz, E2); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
