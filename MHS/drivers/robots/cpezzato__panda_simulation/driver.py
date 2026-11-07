"""OpenMHS rosbridge driver for the cpezzato Panda active-inference simulation.

The pinned repository is a ROS 1 Gazebo simulation of a Franka Emika Panda
arm.  The launch file starts Gazebo paused, spawns the seven effort
controllers plus the joint-state controller under ``/robot1``, and starts the
``panda_control_AIC`` active-inference controller.  The controller subscribes
to ``/robot1/joint_states`` and publishes a torque command for every joint on
``/robot1/panda_joint<N>_controller/command`` at 1 kHz.

This package is a configuration-only :class:`RosDriver`; it declares no Python
native class, imports no ROS, starts no Gazebo process and launches no
controller.  It binds the published joint state, the controller's free-energy
output and one publication capability per effort topic.  The effort inputs are
``Limit.operator_required``: the xacro limit lines state an unsigned effort
attribute and no signed command bound (model review 2026-11-05).

The pinned clone exposes no service, action or reset endpoint that could stop
the AIC loop, and a single effort publication does not stop it.  The e-stop is
the Gazebo world pause of the simulator's own repository, cited as a reviewed
companion source fetched at a pinned commit (user decision and authorisation
of 2026-11-05; ``task.json`` ``companions`` with ``lock``): gazebo_ros 2.5.21
(ROS 1 Kinetic, the README's ``ros-kinetic-desktop-full``)
``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true; Gazebo 7.16.1
is cited for what a paused world does.  World::Step still updates when a step
is pending or a reset is due; otherwise gazebo_ros_control updates no
controller and writes no effort to any joint, whatever the AIC publishes.  The
paused flag is not a measured standstill.

No unpause is offered.  Stopping panda_control_AIC does not clear the effort
controllers' retained commands or the AIC torque state ``u``: the destructor is
empty, main returns without clearing it, and each cycle updates ``u`` from its
previous value.  The package cannot clear that state, so it offers no
re-enable (the orchestrator's SAFE-042 condition).  After ``mhs.safety.reset``
the world stays paused until an operator-reviewed procedure has independently
verified that those retained controller commands are cleared or reinitialized.
This package does not provide that procedure.  The joint states are published
from the world update and are silent while paused; they were already an
explicit read, the device resource reads no topic, and each effort receipt
reports the value it sent.  ``safety_status`` returns the cached confirmation
and does not call ``get_physics_properties`` again, so it cannot detect an
external unpause or step.

Every endpoint and type of the package's own surface cites the pinned clone at
58e1675a372bfef5a30b4dfd6bd5c898f8c012c9; the stop, its read-back and the facts
about them cite the companions at their pins.  The fake transport is
ROS-free; no ROS graph, Gazebo world, controller or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# ---------------------------------------------------------------------------
# Pinned source references
# ---------------------------------------------------------------------------

#: The constructor creates the seven absolute effort publishers and the
#: absolute joint-state subscriber; each line shows the endpoint and type.
_EFFORT_FIRST_LINE = 18       # /robot1/panda_joint1_controller/command
_EFFORT_LAST_LINE = 24        # /robot1/panda_joint7_controller/command
_JOINT_STATE_REF = "panda_control/src/classes/AIC.cpp:25"
_JOINT_STATE_TYPE_REF = "panda_control/include/AIC.h:23"
_FREE_ENERGY_REF = "panda_control/src/classes/AIC.cpp:27"
_FREE_ENERGY_PUBLISH_REF = "panda_control/src/classes/AIC.cpp:137-149"
_JOINT_CALLBACK_REF = "panda_control/src/classes/AIC.cpp:45-51"
_TORQUE_PUBLISH_REF = "panda_control/src/classes/AIC.cpp:152-162"
_TORQUE_STATE_REF = "panda_control/src/classes/AIC.cpp:153-154"
_AIC_CONSTRUCTOR_REF = "panda_control/src/classes/AIC.cpp:15-42"
_AIC_LOOP_REF = "panda_control/src/AIC_controller.cpp:61-92"
_AIC_GOALS_REF = "panda_control/src/AIC_controller.cpp:29-59"

#: The launch file puts the controllers under /robot1 and starts the AIC node.
_LAUNCH_GROUP_REF = "panda_simulation/launch/simulation.launch:23-43"
_LAUNCH_AIC_REF = "panda_simulation/launch/simulation.launch:49-51"
_LAUNCH_PAUSED_REF = "panda_simulation/launch/simulation.launch:5-19"

#: The controller configuration states the joint names and publish rate.
_JOINT_STATE_CONFIG_REF = "panda_simulation/config/panda_control.yaml:2-4"
_EFFORT_CONFIG_REF = "panda_simulation/config/panda_control.yaml:6-37"

#: The launched description is panda_arm_world.urdf.xacro.  The hand
#: instantiation is commented out.  The panda_arm macro still declares joint8.
_MODEL_REF = "franka_description/robots/panda_arm_world.urdf.xacro:25-30"
#: panda_arm.xacro still declares ${arm_id}_joint8 as revolute, effort 1, range 0 to 0.1.
_JOINT8_REF = "franka_description/robots/panda_arm.xacro:269-276"
#: The transmission macro loads gazebo_ros_control and gives every joint an effort interface.
_PLUGIN_REF = "franka_description/robots/panda.transmission.xacro:7-11"
_TRANSMISSION_REF = "franka_description/robots/panda.transmission.xacro:14-100"

#: The README states the launch starts Gazebo paused and runs the AIC node by
#: default, and that the operator presses play.
_README_REF = "README.md:66"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.5.21 (ROS 1 Kinetic) at 98bb3d0a, fetched under work/companions: the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
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
    Fact("empty_world.launch passes -u to the server when its paused argument is true.", source="upstream_code",
         ref=_LAUNCH + ":29-30"),
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
    Fact("gazebo_ros_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS_CONTROL + ":208-211"),
    Fact("gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands "
         "to the simulated joints.", source="upstream_code", ref=_ROS_CONTROL + ":223-270"),
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

#: Each xacro joint limit line states an unsigned effort attribute (87 for
#: joints 1-4, 12 for joints 5-7) and no signed command bound, so it cannot
#: source a -87..87 or -12..12 envelope (model review 2026-11-05: the author's
#: signed Limits cited lines that do not show the negative bound).  The effort
#: inputs are therefore operator_required; the xacro values stay a fact.
_EFFORT_LIMIT = Limit.operator_required(
    "the xacro states an unsigned effort attribute (87 or 12) and no signed command bound; the operator "
    "supplies the reviewed effort envelope"
)
_EFFORT_LIMITS = {joint: _EFFORT_LIMIT for joint in range(1, 8)}

#: ROS 1 std_msgs/Header as rosbridge delivers it (seq, stamp secs/nsecs, frame_id).
_HEADER_FIELD = Field(
    "object",
    description="ROS 1 std_msgs/Header of the joint-state sample",
    properties={
        "seq": Field("integer", unit="1", description="Publisher sequence number"),
        "stamp": Field(
            "object",
            description="ROS 1 time of the sample",
            properties={
                "secs": Field("integer", unit="s", description="Whole seconds"),
                "nsecs": Field("integer", unit="ns", description="Nanoseconds within the second"),
            },
        ),
        "frame_id": Field("string", description="Frame id set by the publisher"),
    },
)

#: One sensor_msgs/JointState sample.  The AIC callback reads indices 0..6.
#: The hand instantiation is commented out, and the panda_arm macro still
#: declares joint8.
_JOINT_STATE_FIELD = Field(
    "object",
    description="One sensor_msgs/JointState sample from /robot1/joint_states",
    properties={
        "header": _HEADER_FIELD,
        "name": Field("array", description="Joint names in publisher order",
                      items=Field("string", description="One joint name")),
        "position": Field("array", unit="rad", description="Joint positions in publisher order",
                          items=Field("number", unit="rad", description="One joint position")),
        "velocity": Field("array", unit="rad/s", description="Joint velocities in publisher order",
                          items=Field("number", unit="rad/s", description="One joint velocity")),
        "effort": Field("array", unit="N.m", description="Joint efforts in publisher order",
                        items=Field("number", unit="N.m", description="One joint effort")),
    },
)

_JOINT_STATE_COMMAND = {
    "topic": "/robot1/joint_states",
    "type": "sensor_msgs/JointState",
    "source_ref": _JOINT_STATE_REF,
    "type_ref": _JOINT_STATE_TYPE_REF,
    "operation": "subscribe",
    "result": {"map": {"joint_state": "output.$"}},
}

_FREE_ENERGY_COMMAND = {
    "topic": "/panda_free_energy",
    "type": "std_msgs/Float64",
    "source_name": "panda_free_energy",
    "source_ref": _FREE_ENERGY_REF,
    "operation": "subscribe",
    "result": {"map": {"free_energy": "output.data"}},
}

_PUBLISHED = Field("boolean", description="True when the rosbridge publication was handed to the transport")
_CONFIRMED = Field("boolean",
                   description="Always false for a topic publication: rosbridge carries no execution confirmation")
_SENT = Field("number", unit="N.m",
              description="The effort handed to rosbridge (the transmitted request, not a measured or applied torque)")


def _effort_binding(joint: int) -> dict:
    """Bind one absolute effort publication exactly as the AIC creates it."""
    return {
        "topic": f"/robot1/panda_joint{joint}_controller/command",
        "type": "std_msgs/Float64",
        "source_ref": f"panda_control/src/classes/AIC.cpp:{_EFFORT_FIRST_LINE + joint - 1}",
        "operation": "publish",
        "args": {"data": {"from": "input.effort"}},
        "result": {"map": {"published": "published", "confirmed": "confirmed"}},
    }


def _effort_action(joint: int) -> Action:
    """Describe one joint-effort publication; its envelope is operator_required."""
    return Action(
        name=f"set_joint{joint}_effort",
        description=(f"Publish one effort command for panda_joint{joint} on "
                     f"/robot1/panda_joint{joint}_controller/command; the AIC node may overwrite it, and while the "
                     "world is paused no effort reaches the joint"),
        input={"effort": Field("number", unit="N.m",
                               description=f"Joint torque command for panda_joint{joint}",
                               limit=_EFFORT_LIMITS[joint])},
        output={"published": _PUBLISHED, "confirmed": _CONFIRMED, "sent_effort": _SENT},
    )


_EFFORT_IDS = frozenset(f"x-cap.cpezzato.joint{joint}_effort.v1" for joint in range(1, 8))


class _SentEffort:
    """The receipt of an effort publication also reports the effort it handed to rosbridge.

    The device resource reads no topic (a paused world publishes no joint state), so the receipt is where a caller
    sees what a publication sent; it is the transmitted request, not a measurement. Every other call, the e-stop and
    the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id not in _EFFORT_IDS or not isinstance(output, dict):
            return output
        output = dict(output)
        output["sent_effort"] = float(dict(args or {})["effort"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


class PandaSimulation(RosDriver):
    """Configuration-only ROS 1 rosbridge driver for the Panda simulation."""

    device_id = "panda_simulation"
    device_kind = "robot.arm"
    mode = "simulated"
    #: A moving robot arm is at least R2 even when the only backend exercised
    #: here is the F0 recording fake; the seven effort topics are joint commands
    #: a real arm's controller would also consume (REVIEW.md item 12).
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakePandaSimulation"}
    tags = ["ros", "ros1", "gazebo", "simulation", "panda", "franka", "active-inference",
            "joint-state", "effort", "stop"]
    display_name = "Panda active-inference simulation"
    vendor = "cpezzato"
    model = "Franka Emika Panda 7-DOF"

    facts = [
        Fact("The README states that the launch file starts a Gazebo simulation in pause with a "
             "single robot, runs the panda_control_AIC node by default, and the operator presses play.",
             source="vendor_doc", ref=_README_REF),
        Fact("The README's installation asks for ros-kinetic-desktop-full.", source="vendor_doc", ref="README.md:41"),
        Fact("The README sources /opt/ros/kinetic/setup.bash inside the container image.", source="vendor_doc",
             ref="README.md:54"),
        Fact("The README's troubleshooting says that with ROS Melodic and Gazebo 9 the robot meshes will probably not "
             "be shown and tells the user to remove the transparent attribute in the visual .dae files.",
             source="vendor_doc", ref="README.md:73"),
        Fact("simulation.launch declares the paused argument with default true and passes it to the "
             "gazebo_ros empty_world launch.", source="upstream_code", ref=_LAUNCH_PAUSED_REF),
        Fact("simulation.launch declares use_sim_time with default true and passes it to the gazebo_ros empty_world "
             "launch.", source="upstream_code", ref="panda_simulation/launch/simulation.launch:6-17"),
        Fact("simulation.launch loads the robot description under /robot1 and spawns the "
             "joint_state_controller plus one effort controller for each of the seven panda joints.",
             source="upstream_code", ref=_LAUNCH_GROUP_REF),
        Fact("simulation.launch starts the panda_control_AIC node without a namespace and leaves the "
             "MRAC node commented out.", source="upstream_code", ref=_LAUNCH_AIC_REF),
        Fact("panda_control.yaml configures joint_state_controller as "
             "joint_state_controller/JointStateController with publish_rate 1000.",
             source="upstream_code", ref=_JOINT_STATE_CONFIG_REF),
        Fact("panda_control.yaml configures panda_joint1 through panda_joint7 each as an "
             "effort_controllers/JointEffortController on that joint.",
             source="upstream_code", ref=_EFFORT_CONFIG_REF),
        Fact("panda_arm_world.urdf.xacro instantiates panda_arm and the gazebo and transmission macros, "
             "and the hand instantiation is commented out.", source="upstream_code", ref=_MODEL_REF),
        Fact("The panda_arm macro declares ${arm_id}_joint8 as revolute with effort 1, lower 0 and upper 0.1.",
             source="upstream_code", ref=_JOINT8_REF),
        Fact("The panda transmission macro loads the gazebo_ros_control plugin from libgazebo_ros_control.so.",
             source="upstream_code", ref=_PLUGIN_REF),
        Fact("The panda transmission macro declares hardware_interface/EffortJointInterface transmissions for "
             "joint1 through joint8.", source="upstream_code", ref=_TRANSMISSION_REF),
        Fact("The AIC constructor creates seven absolute std_msgs/Float64 publishers named "
             "/robot1/panda_joint1..7_controller/command, subscribes to /robot1/joint_states, and also "
             "creates publishers for panda_free_energy and the controller's belief and sensory-error "
             "topics; it creates no service server.", source="upstream_code", ref=_AIC_CONSTRUCTOR_REF),
        Fact("The AIC constructor subscribes to the absolute /robot1/joint_states and passes "
             "AIC::jointStatesCallback as its handler.", source="upstream_code", ref=_JOINT_STATE_REF),
        Fact("AIC.h includes sensor_msgs/JointState.h, which declares the type used by the joint-state "
             "subscription.", source="upstream_code", ref=_JOINT_STATE_TYPE_REF),
        Fact("AIC::jointStatesCallback copies position[i] and velocity[i] for i from 0 to 6 without "
             "reading the joint names.",
             source="upstream_code", ref=_JOINT_CALLBACK_REF),
        Fact("AIC::computeActions computes one torque per joint and publishes the seven values through "
             "tauPub1 to tauPub7.",
             source="upstream_code", ref=_TORQUE_PUBLISH_REF),
        Fact("AIC::computeActions updates the torque vector u from its previous value by a gradient step on the "
             "position and velocity errors.", source="upstream_code", ref=_TORQUE_STATE_REF),
        Fact("AIC::minimiseF calls computeActions, then publishes the free-energy scalar through IFE_pub "
             "and the sensory prediction error and belief arrays.",
             source="upstream_code", ref=_FREE_ENERGY_PUBLISH_REF),
        Fact("The AIC main loop runs at ros::Rate(1000), calls minimiseF while the node is alive, and "
             "cycles between hardcoded desired joint positions every 6000 cycles; it has no service, "
             "action, cancellation or reset path.", source="upstream_code", ref=_AIC_LOOP_REF),
        Fact("The AIC desired joint positions are hardcoded in main and are not read from a parameter, "
             "topic or service.", source="upstream_code", ref=_AIC_GOALS_REF),
        Fact("The Panda arm xacro states effort 87 on the joint1, joint2, joint3 and joint4 limit lines "
             "and effort 12 on the joint5, joint6 and joint7 limit lines.",
             source="upstream_code", ref="franka_description/robots/panda_arm.xacro:103-259"),
        *_COMPANION_FACTS,
    ]

    safe_state = (
        "The Gazebo world is paused and the read-back reported pause true. World::Step still updates when a step "
        "is pending or a reset is due; otherwise gazebo_ros_control writes no effort. The flag is not a measured "
        "standstill. No unpause is offered. Stopping panda_control_AIC does not clear retained joint effort or "
        "the AIC torque state u. The world stays paused until an operator-reviewed procedure has independently "
        "verified that those retained controller commands are cleared or reinitialized."
    )

    #: The deployed fake is an event-driven recording transport, not Gazebo.
    fidelity = {
        "engine": "analytic:ROS recording fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step or pacing; placeholder joint "
                     "samples do not establish trajectory, torque or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared joint-state and "
            "free-energy subscriptions, records the declared effort publications and answers the two companion "
            "Gazebo services; it runs no Gazebo, physics step, controller manager, AIC loop or MoveIt",
            "the joint positions, velocities, efforts and free energy are placeholders; a live run must "
            "receive them from the operator's Gazebo and panda_control nodes",
            "the AIC publishes torques at ros::Rate(1000) (AIC_controller.cpp:62; the torque update is AIC.cpp:154 "
            "and the publishes are AIC.cpp:157-162) and will overwrite a single driver publication on the next "
            "cycle; the fake records the publication but does not model that race or any motion",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step, "
            "and its GetPhysicsProperties numbers are placeholders",
            "no unpause is offered: stopping panda_control_AIC does not clear retained joint_effort_command_ "
            "(default_robot_hw_sim.cpp:315-316 applies the last command on the next update unless e_stop_active_) "
            "or the AIC torque state u (AIC.cpp:43 is an empty destructor and AIC_controller.cpp:93 returns "
            "without clearing it; AIC.cpp:154 updates u from its previous value and AIC.cpp:157-162 publishes it). "
            "The world stays paused until an operator-reviewed procedure has independently verified that those "
            "retained controller commands are cleared or reinitialized. This package does not provide that procedure",
            "while paused, with no step pending and no reset due, /robot1/joint_states (published by "
            "joint_state_controller from gazebo_ros_control's world update) and /clock are silent: the joint-state "
            "read fails NOT_READY after its 2 s timeout (the "
            "fake silences it while its flag is set); the device resource reads no topic, and each effort receipt "
            "reports the value it sent",
            "the AIC loop is paced by ros::Rate(1000) at AIC_controller.cpp:62 under use_sim_time true; whether it "
            "keeps publishing while /clock is silent is roscpp behaviour outside the clone and the companions, so "
            "the fake keeps answering /panda_free_energy while paused and a live free-energy read while paused is "
            "unverified. A confirmed pause writes no effort unless a step is pending or a reset is due",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, by "
            "a WorldControl message or by any ROS client; safety_status returns the cached confirmation and does "
            "not call get_physics_properties again, so it cannot detect an external unpause or step",
            "the read-back needs the ODE engine (empty_world.launch's default physics): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.5.21 (Kinetic) and 7.16.1 releases the "
            "companion citations name; the README also mentions ROS Melodic with Gazebo 9 (README.md:73), a "
            "deployment this package does not serve; rosbridge cannot read their versions",
            "the launch starts Gazebo paused (the README says to press play), so a live joint-state sample may "
            "not arrive until the world runs; the e-stop's read-back already reads pause true then",
            "camera, depth, TF, collision detection, MoveIt planning, the box publisher and the web UI "
            "are outside this package",
            "the effort envelope is operator_required: the xacro effort attribute is unsigned and no signed "
            "command bound is stated; site-limits.example.json is an example overlay only",
        ],
    }

    # The observation capabilities are explicit subscribe actions so the empty
    # resource snapshot never waits for a topic that a paused Gazebo does not publish.
    commands = {
        "x-cap.cpezzato.joint_state.v1": _JOINT_STATE_COMMAND,
        "x-cap.cpezzato.free_energy.v1": _FREE_ENERGY_COMMAND,
    }
    commands.update({f"x-cap.cpezzato.joint{joint}_effort.v1": _effort_binding(joint)
                     for joint in range(1, 8)})

    actions = {
        "x-cap.cpezzato.joint_state.v1": Action(
            name="read_joint_state",
            verb="read",
            description="Read one sensor_msgs/JointState sample published on /robot1/joint_states (silent, and "
                        "NOT_READY, while the world is paused)",
            output={"joint_state": _JOINT_STATE_FIELD},
        ),
        "x-cap.cpezzato.free_energy.v1": Action(
            name="read_free_energy",
            verb="read",
            description="Read one free-energy scalar published by the AIC on /panda_free_energy",
            output={"free_energy": Field("number", unit="1",
                                         description="Free-energy scalar from the AIC node")},
        ),
    }
    actions.update({f"x-cap.cpezzato.joint{joint}_effort.v1": _effort_action(joint)
                    for joint in range(1, 8)})

    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentEffort(super().make_bridge(native))
