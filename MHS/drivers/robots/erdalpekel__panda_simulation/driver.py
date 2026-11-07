"""OpenMHS rosbridge driver for gh.erdalpekel/panda_simulation (Panda in Gazebo).

The pinned repository is a ROS 1 catkin workspace, not a Python package.  Its
``simulation.launch`` starts Gazebo, spawns the Franka Emika Panda model,
spawns the ``joint_state_controller`` and ``panda_arm_controller`` controllers,
loads the custom ``joint_position_controller`` stopped, starts the
``robot_state_initializer_node`` and robot_control_node, and starts rosbridge on
port 9090.  This package is a configuration-only :class:`RosDriver`; it
declares no Python native class and does not launch Gazebo, MoveIt or rosbridge.

The scope is the simulated arm's joint-state resource, the custom controller's
open-loop joint-position command topic, and the upstream
``/robot_control_stop`` service as an ordinary request.  That service callback
calls ``move_group_arm->stop()`` for the ``panda_arm`` MoveIt planning group and
returns true unconditionally, so its acknowledgement confirms nothing, and it
does not reach the custom ``joint_position_controller`` that this package's
joint-position command drives, which, while running, keeps applying its last
``command_``.  It is therefore bound neither as the e-stop nor as a safe-state
action (model review 2026-11-05).

The e-stop is the Gazebo world pause of the simulator's own repository, cited as
a reviewed companion source fetched at a pinned commit (user decision and
authorisation of 2026-11-05; ``task.json`` ``companions`` with ``lock``):
gazebo_ros 2.8.7 (ROS 1 Melodic) ``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true; Gazebo 9.19.0
is cited for what a paused world does not run.  The pause stops every world
update, so gazebo_ros_control updates no controller and writes no joint
command; it is the paused flag, not a measured standstill.

No unpause is offered.  On an unpause the trajectory controller resumes any
accepted MoveIt trajectory and the custom joint_position_controller, if it runs,
its stored ``command_``; no command value means "hold" (it writes ``(command_ -
position) * gain``) and the current position is not observable while paused, so
this package cannot clear them first (the orchestrator's SAFE-042 condition).
After ``mhs.safety.reset`` the world stays paused and the operator recovers
outside MHS (see ``safe_state``).  The joint states left the device resource:
they are published from the world update and are silent while paused; they stay
an explicit read capability, and the command receipt reports what it sent.

The normal ``panda_arm_controller`` follow_joint_trajectory action is not
declared: the pinned clone writes the external controller type and the goal and
result topic suffixes, but it never declares that action root endpoint, so a
binding would have to guess it.  The custom position command topic is cited
directly in the initializer source.

No joint travel bound is stated in this clone: the Panda joint limits live in
the external ``franka_description``/``panda_moveit_config`` repositories.  The
joint-position command input therefore uses
:meth:`mhs.driver.Limit.operator_required`, so every motion call is refused
``MHS.SAFETY.LIMITS_UNSET`` until an operator supplies a reviewed
``site-limits.json``.

The fake is a ROS-free analytic stand-in, not a recording of captured traffic.
It models only the pinned wire contract and claims F0 contract evidence.  No
ROS graph, Gazebo simulation or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.8.7 (ROS 1 Melodic) at 0667c5e5, fetched under work/companions: the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
#: Gazebo classic 9.19.0 at e4400ae7, fetched under work/companions: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

#: The e-stop: pause_physics (std_srvs/Empty) sets the world's paused flag.
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
#: The read-back that confirms it: get_physics_properties reports the paused flag (res.pause = IsPaused()).
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

#: The custom JointPositionController stores Float64MultiArray.data as its
#: command_ and, only while the controller is running, writes
#: (command_ - position) * gain to each joint's position interface; the
#: initializer declares and publishes on this absolute topic with the
#: std_msgs/Float64MultiArray type.
_JOINT_COMMAND = {
    "topic": "/joint_position_controller/command",
    "type": "std_msgs/Float64MultiArray",
    "source_name": "/joint_position_controller/command",
    "source_ref": "panda_simulation/src/robot_state_initializer.cpp:12-17",
    "operation": "publish",
    "args": {"data": {"from": "input.joint_positions"}},
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: The CollisionDetector subscribes to the absolute /joint_states topic.  The
#: type is declared by the sensor_msgs/JointState include in its own header.
_JOINT_STATE = {
    "topic": "/joint_states",
    "type": "sensor_msgs/JointState",
    "source_name": "/joint_states",
    "source_ref": "panda_safety/src/CollisionDetector.cpp:293",
    "type_ref": "panda_safety/include/panda_safety/CollisionDetector.h:23",
    "path": "position",
}

#: robot_control_node advertises constants::service_endpoints::ROBOT_STOP; the
#: constant is "/robot_control_stop" and the request/response definition is
#: an empty panda_msgs/RobotStopMsg service.
_STOP = {
    "service": "/robot_control_stop",
    "type": "panda_msgs/RobotStopMsg",
    "source_name": "/robot_control_stop",
    "source_ref": "panda_utils/include/panda_utils/constants.h:125-127",
    "type_ref": "panda_safety/include/panda_safety/CollisionDetector.h:15",
    "success": {"path": "$", "equals": {}},
}

#: The joint-state read capability: the whole message, mapped to its position array.
_JOINT_STATE_READ = dict(_JOINT_STATE, operation="subscribe", path="$",
                         result={"map": {"joint_positions": "position"}})

_JOINT_COMMAND_ID = "x-cap.erdalpekel.joint_position_command.v1"


class _SentReceipt:
    """The receipt of a joint-position publication also reports the positions it handed to rosbridge.

    The device resource reads no topic (a paused world publishes none), so the receipt is where a caller sees what
    a publication sent; it is the transmitted request, not a measurement. Every other call, the e-stop and the
    reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _JOINT_COMMAND_ID:
            return output
        output = dict(output)
        output["sent_joint_positions"] = [float(value) for value in dict(args or {})["joint_positions"]]
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


#: The ordinary command adds the output mapping.  It is not a safety binding:
#: the callback acknowledges unconditionally and does not stop the custom
#: joint-position controller (model review 2026-11-05).
_STOP_COMMAND = dict(_STOP, result={"acknowledged": {"value": True}})

#: The clone never states the Panda joint travel range; the external
#: franka_description and panda_moveit_config repositories own it.  A value
#: copied from a controller gain, a ready-state constant or a default is not a
#: device bound.
_JOINT_LIMIT = Limit.operator_required(
    "the pinned clone states no Panda joint travel bound; the joint limits live in the external "
    "franka_description and panda_moveit_config repositories, so an operator must supply the reviewed "
    "site envelope"
)


class PandaSimulation(RosDriver):
    device_id = "panda_simulation"
    device_kind = "robot.arm"
    mode = "simulated"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakePandaSimulation"}
    tags = ["ros", "ros1", "simulation", "gazebo", "panda", "franka", "joint-position", "stop"]
    display_name = "Panda arm in Gazebo simulation"
    vendor = "erdalpekel"
    model = "Franka Emika Panda"
    facts = [
        Fact("simulation.launch includes gazebo_ros/empty_world.launch, spawns the model named panda from the "
             "robot_description parameter, and spawns joint_state_controller and panda_arm_controller.",
             source="upstream_code", ref="panda_simulation/launch/simulation.launch:14-31"),
        Fact("simulation.launch starts rosbridge_websocket with argument port 9090.",
             source="upstream_code", ref="panda_simulation/launch/simulation.launch:59-62"),
        Fact("panda_control.yaml configures joint_state_controller with publish_rate 100 and panda_arm_controller "
             "as a position_controllers/JointTrajectoryController for panda_joint1 through panda_joint7.",
             source="upstream_code", ref="panda_simulation/config/panda_control.yaml:1-20"),
        Fact("panda_control.yaml configures joint_position_controller as panda_simulation/JointPositionController "
             "with joint_names panda_joint1 through panda_joint7 and seven gains of 1.",
             source="upstream_code", ref="panda_simulation/config/panda_control.yaml:29-42"),
        Fact("simulation.launch loads joint_position_controller stopped and starts robot_state_initializer_node.",
             source="upstream_code", ref="panda_simulation/launch/simulation.launch:53-57"),
        Fact("JointPositionController subscribes to the relative name command with std_msgs/Float64MultiArray.",
             source="upstream_code", ref="panda_simulation/src/joint_position_controller.cpp:32-33"),
        Fact("JointPositionController::setCommandCallback assigns msg->data to command_.",
             source="upstream_code", ref="panda_simulation/src/joint_position_controller.cpp:47"),
        Fact("JointPositionController::init fills command_ with each joint's position at load time.",
             source="upstream_code", ref="panda_simulation/src/joint_position_controller.cpp:28-30"),
        Fact("JointPositionController::update writes (command_[i] - position) * gains_vec_[i] as each joint "
             "handle's command.",
             source="upstream_code", ref="panda_simulation/src/joint_position_controller.cpp:38-45"),
        Fact("JointPositionController::starting and ::stopping have empty bodies.",
             source="upstream_code", ref="panda_simulation/src/joint_position_controller.cpp:49-51"),
        Fact("robot_state_initializer names the absolute topic /joint_position_controller/command and advertises it "
             "as std_msgs/Float64MultiArray.",
             source="upstream_code", ref="panda_simulation/src/robot_state_initializer.cpp:12-17"),
        Fact("robot_state_initializer switches the trajectory controllers out, publishes panda_ready_state on the "
             "joint-position command topic, sleeps 1 second, then restores the trajectory controllers.",
             source="upstream_code", ref="panda_simulation/src/robot_state_initializer.cpp:22-71"),
        Fact("The stop callback calls move_group_arm->stop(), logs a message and returns true without "
             "checking any result.",
             source="upstream_code", ref="panda_simulation/src/robot_control_node.cpp:56-61"),
        Fact("robot_control_node advertises constants::service_endpoints::ROBOT_STOP through ros::ServiceServer.",
             source="upstream_code", ref="panda_simulation/src/robot_control_node.cpp:133"),
        Fact("The clone defines service_endpoints::ROBOT_STOP as the absolute name /robot_control_stop.",
             source="upstream_code", ref="panda_utils/include/panda_utils/constants.h:125-127"),
        Fact("RobotStopMsg.srv declares no request fields and no response fields.",
             source="upstream_code", ref="panda_msgs/srv/RobotStopMsg.srv:1"),
        Fact("The clone defines PLANNING_GROUP_ARM as panda_arm.",
             source="upstream_code", ref="panda_utils/include/panda_utils/constants.h:114"),
        Fact("robot_control_node constructs MoveGroupInterface for PLANNING_GROUP_ARM.",
             source="upstream_code", ref="panda_simulation/src/robot_control_node.cpp:73"),
        Fact("CollisionDetector subscribes to the absolute /joint_states topic with queue size 1.",
             source="upstream_code", ref="panda_safety/src/CollisionDetector.cpp:293"),
        Fact("CollisionDetector.h includes sensor_msgs/JointState.h.",
             source="upstream_code", ref="panda_safety/include/panda_safety/CollisionDetector.h:23"),
        Fact("CollisionDetector comments that /joint_states publishes the fingers at positions 0 and 1 and sets "
             "index_link_start to 2 for the arm joints.",
             source="upstream_code", ref="panda_safety/src/CollisionDetector.cpp:40-41"),
        Fact("CollisionDetector's joint-state callback stores the complete sensor_msgs/JointState including its "
             "position array.",
             source="upstream_code", ref="panda_safety/src/CollisionDetector.cpp:557-569"),
        Fact("CollisionDetector skips the first two position entries when it feeds the Panda arm joint group.",
             source="upstream_code", ref="panda_safety/src/CollisionDetector.cpp:522-527"),
        Fact("robot_state_initializer uses the /controller_manager/switch_controller service of type "
             "controller_manager_msgs/SwitchController.",
             source="upstream_code", ref="panda_simulation/src/robot_state_initializer.cpp:1-17"),
        Fact("simulation.launch relays joint_states to joint_states_desired with topic_tools/relay.",
             source="upstream_code", ref="panda_simulation/launch/simulation.launch:48"),
        Fact("robot_control_node waits for a planning_scene subscriber and only advertises the stop service inside "
             "the home-directory branch after building the planning scene.",
             source="upstream_code", ref="panda_simulation/src/robot_control_node.cpp:75-133"),
        Fact("When ~/.panda_simulation does not exist, robot_control_node creates ~/.panda_core instead and then "
             "iterates the ~/.panda_simulation directory.",
             source="upstream_code", ref="panda_simulation/src/robot_control_node.cpp:82-108"),
        Fact("CollisionDetector calls /robot_control_stop when it counts collisions for the currently executed "
             "trajectory.",
             source="upstream_code", ref="panda_safety/src/CollisionDetector.cpp:485-493"),
        Fact("simulation.launch includes gazebo_ros's empty_world.launch with its gui, paused and use_sim_time "
             "arguments.", source="upstream_code", ref="panda_simulation/launch/simulation.launch:15-21"),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so no "
        "controller is updated and no joint command is written; it is the paused flag, not a measured standstill. "
        "No unpause is offered: an operator stops the trajectory (/robot_control_stop) and the custom controller "
        "and unpauses outside MHS."
    )
    fidelity = {
        "engine": "analytic:ROS-free rosbridge fake (no Gazebo, MoveIt or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven fake with placeholder joint values and no physics step, pacing, controller "
                     "dynamics or trajectory execution; it is not a replay of captured ROS traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic stand-in: it answers the declared /joint_states subscription, the "
            "joint-position command publication, the /robot_control_stop service and the two companion Gazebo "
            "services; it runs no Gazebo, ros_control controller, MoveIt planning group or Panda dynamics",
            "the joint values are placeholders and do not come from a live /joint_states publisher; the fake "
            "updates them only when it receives a joint-position publication",
            "the fake never executes a trajectory and never moves the simulated arm; /robot_control_stop only sets "
            "a placeholder stopped flag and acknowledges the empty service response",
            "the fake copies a joint-position publication into its placeholder joint values at once; upstream the "
            "data only replaces the controller's command_, which the controller acts on only while it is running, "
            "writing (command_ - position) * gain to each joint's position interface on every update",
            "/robot_control_stop returns true unconditionally after move_group_arm->stop() and does not reach the "
            "custom joint_position_controller, so it is an ordinary request, not the stop",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step",
            "no unpause is offered: on an unpause the trajectory controller resumes any accepted MoveIt trajectory "
            "and the custom controller, if running, its stored command_ (joint_position_controller.cpp:38-47); no "
            "command value means hold and positions are not observable while paused, so the package cannot clear "
            "them first; the operator recovers outside MHS (/robot_control_stop or stopping move_group, the custom "
            "controller switched off, then the Gazebo GUI play button or rosservice call gazebo/unpause_physics)",
            "while paused /joint_states (published by joint_state_controller from gazebo_ros_control's world update) "
            "and /clock are silent: the joint-state read fails NOT_READY after its timeout (the fake silences it "
            "while its flag is set); the device resource reads no topic, so commands and resets do not wait for it, "
            "and the joint-position receipt reports the values it sent",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, by "
            "a WorldControl message or by any ROS or rosbridge client (simulation.launch starts rosbridge on port "
            "9090); MHS does not watch the flag after the e-stop (safety_status re-reads it only on request)",
            "the read-back needs the ODE engine (empty_world.launch's default physics): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and 9.19.0 releases the "
            "companion citations name; rosbridge cannot read their versions",
            "the pinned launch uses the external panda_moveit_config and franka_description packages; their "
            "trajectory action, joint limits and robot model are outside the pinned clone and this package",
            "the normal panda_arm_controller follow_joint_trajectory action interface is not declared because the "
            "pinned clone does not declare its action root endpoint; the custom position command topic is the only "
            "directly cited joint command",
            "the launch loads joint_position_controller stopped and the initializer switches it in only briefly; a "
            "deployment must activate that controller before a joint-position publication reaches it",
        ],
    }

    # The device resource reads no topic: /joint_states is published from the world update, so it is silent while
    # the e-stop holds the world paused, and a resource that waited for it would fail NOT_READY after every reset
    # and delay every command by its timeout.  It stays an explicit read capability below.
    commands = {
        "x-cap.erdalpekel.joint_position_command.v1": _JOINT_COMMAND,
        "x-cap.erdalpekel.robot_stop.v1": _STOP_COMMAND,
        "x-cap.erdalpekel.joint_states.v1": _JOINT_STATE_READ,
    }
    actions = {
        "x-cap.erdalpekel.joint_position_command.v1": Action(
            name="command_joint_positions",
            verb="invoke",
            description="Publish seven arm joint positions to the custom joint-position controller; the topic has "
                        "no acknowledgement, so the output reports publication only",
            input={
                "joint_positions": Field(
                    "array",
                    unit="rad",
                    description="Seven arm joint positions in panda_joint1..panda_joint7 order, applied by the "
                                "custom JointPositionController",
                    items=Field("number", unit="rad"),
                    length=7,
                    limit=_JOINT_LIMIT,
                ),
            },
            output={
                "published": Field("boolean", description="True when the rosbridge publication was transmitted"),
                "confirmed": Field("boolean",
                                   description="Always false: the command topic has no execution acknowledgement"),
                "sent_joint_positions": Field(
                    "array", unit="rad", items=Field("number", unit="rad"),
                    description="The seven joint positions handed to rosbridge (the transmitted request, not a "
                                "measured position)"),
            },
        ),
        "x-cap.erdalpekel.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one fresh /joint_states sample (silent, and NOT_READY, while the world is paused)",
            output={"joint_positions": Field(
                "array", unit="rad", items=Field("number", unit="rad"),
                description="Joint positions from /joint_states; the clone publishes the two finger joints first, "
                            "so the arm joints begin at index 2")},
        ),
        "x-cap.erdalpekel.robot_stop.v1": Action(
            name="stop_robot",
            verb="invoke",
            description="Call /robot_control_stop: its callback calls move_group_arm->stop() for the panda_arm "
                        "MoveIt group and returns true unconditionally; not a stop of the joint-position command "
                        "and not a safe state",
            output={"acknowledged": Field(
                "boolean",
                description="True when the empty RobotStopMsg callback returned true after calling "
                            "move_group_arm->stop()",
            )},
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    # /robot_control_stop stays an ordinary command: it acknowledges unconditionally (model review 2026-11-05).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _SentReceipt(super().make_bridge(native))
