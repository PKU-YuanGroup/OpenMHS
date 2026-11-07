"""OpenMHS rosbridge driver for the pinned will0103 ROS 2 mobile manipulator.

The pinned repository is a ROS 2 Jazzy / Gazebo Harmonic simulation.  It is not
a Python native class: Gazebo owns the world and the differential drive, and
``my_cpp_pkg`` serves one ROS 2 action, ``/move_robot``.  This package is a
configuration-only :class:`RosDriver`.  It declares no Python native class and
neither imports nor launches the upstream code.

The command surface is that action.  Its receipt reports the goal it handed to
rosbridge (the transmitted request, not a measurement).  The device resource
reads no topic: the topics a pause silences are not a resource.

The clone has no stop of its own.  The e-stop is the Gazebo world pause of the
simulator's own repository, cited as reviewed companion sources fetched at
pinned commits (user decision and authorisation of 2026-11-05; ``task.json``
``companions`` with ``lock``): gz-sim 8.15.0 (Harmonic) serves the WorldControl
service ``/world/empty/control``, and ros_gz 1.0.25 (Jazzy) bridges it as
``ros_gz_interfaces/srv/ControlWorld``.  Its reply is true for any request
gz-sim queued, so it confirms nothing; the stop is confirmed by a fresh-sample
topic read-back (E2): ``WorldStatistics.paused`` on ``/world/empty/stats`` must
be true in two samples that arrived at least 40 ms apart, after a discarded
first one, within 600 ms.  Neither endpoint exists unless the operator runs
ros_gz's ``parameter_bridge`` with the two arguments in ``operator_bridges``
(E3).  The clone's ``gazebo_bridge.yaml`` does not bridge them.  Without the
operator bridges the e-stop fails closed.

No unpause is offered (the orchestrator's SAFE-042 condition).  DiffDrive
stores the last Twist and applies it only while the world runs, the joint
position controllers store the arm targets, and ``move_robot`` times its queue
on the node clock and keeps publishing.  A zero Twist cannot be held while that
queue is still running, and the arm targets cannot be cleared from here, so
the operator recovers outside MHS (see ``safe_state`` and ``facts.md``).

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 6f49e8f3b306a864d8d139d2dc270afebecea819.  The fake transport is
ROS-free and its numbers are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The node creates its MoveRobot action server on the relative name
#: "move_robot"; the generated action header gives the fully qualified type.
_MOVE_ROBOT_REF = "src/my_cpp_pkg/src/move_robot.cpp:27-32"
_MOVE_ROBOT_TYPE_REF = "src/my_cpp_pkg/src/move_robot.cpp:8"

#: The pinned source states no velocity or duration bound.  These are
#: operator-supplied deployment envelopes, not device facts.
_LINEAR_REASON = (
    "The pinned node reads linear_vel_x without a bound; the operator supplies the deployed "
    "simulated-base speed envelope."
)
_ANGULAR_REASON = (
    "The pinned node reads angular_vel_z without a bound; the operator supplies the deployed "
    "simulated-base turn-rate envelope."
)
_DURATION_REASON = (
    "The pinned node loops for the goal duration without a bound; the operator supplies the "
    "per-goal duration envelope."
)

#: ROS 2 native action binding.  The goal fields are flat in MoveRobot.action;
#: the result is unwrapped before the success predicate and result mapping.
_MOVE_ROBOT = {
    "action": "/move_robot",
    "profile": "ros2-native",
    "type": "my_robot_interfaces/action/MoveRobot",
    "source_name": "move_robot",
    "source_ref": _MOVE_ROBOT_REF,
    "type_ref": _MOVE_ROBOT_TYPE_REF,
    "args": {
        "linear_vel_x": {"from": "input.linear_vel_x"},
        "angular_vel_z": {"from": "input.angular_vel_z"},
        "duration": {"from": "input.duration"},
    },
    "result": {"map": {"success": "success", "message": "message"}},
    "success": {"path": "success", "equals": True},
}

#: The only world file names the world empty, so the control endpoints name it.
_WORLD_SDF_REF = "src/my_robot_bringup/worlds/project_world.sdf:2"
_LAUNCH_REF = "src/my_robot_bringup/launch/project_robot_gazebo.launch.xml:10-12"
_BRIDGE_LAUNCH_REF = "src/my_robot_bringup/launch/project_robot_gazebo.launch.xml:19-21"
_BRIDGE_YAML_REF = "src/my_robot_bringup/config/gazebo_bridge.yaml:1-47"
_DIFF_XACRO_REF = "src/my_robot_description/urdf/mobile_base_gazebo.xacro:10-20"
_ARM_XACRO_REF = "src/my_robot_description/urdf/arm_gazebo.xacro:14-29"

# -- Companion sources (task.json companions with lock; user decision and authorisation of 2026-11-05) -----------
#: gz-sim 8.15.0 (Harmonic) at 446a4433, fetched under work/companions: the world runner, its control service and
#: its statistics, and the systems a paused world does not run.
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_DIFF = "companion:gz_sim/src/systems/diff_drive/DiffDrive.cc"
_UTIL = "companion:gz_sim/src/Util.cc"
_JOINT_POSITION = "companion:gz_sim/src/systems/joint_position_controller/JointPositionController.cc"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
_GUI = "companion:gz_sim/src/gui/Gui.cc"
_GUI_CONFIG = "companion:gz_sim/src/gui/gui.config"
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

_WORLD = "/world/empty"
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

_GOAL = "x-cap.will0103.move-robot.v1"


class _GoalReceipt:
    """The MoveRobot receipt also reports the goal handed to rosbridge.

    The device resource reads no topic, so the receipt is where a caller sees what the action sent.  The three
    ``sent_*`` fields are the transmitted request, not a measurement and not a motion confirmation.  Every other
    call, the e-stop and the reset included, goes to the SDK bridge unchanged.
    """

    def __init__(self, inner):
        self._inner = inner

    def call(self, capability_id, args=None, ctx=None):
        output = self._inner.call(capability_id, args, ctx)
        if capability_id != _GOAL:
            return output
        body = dict(args or {})
        output = dict(output)
        output["sent_linear_vel_x"] = float(body["linear_vel_x"])
        output["sent_angular_vel_z"] = float(body["angular_vel_z"])
        output["sent_duration"] = float(body["duration"])
        return output

    def __getattr__(self, name):
        return getattr(self._inner, name)


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
    Fact("SetPaused stops the real-time stopwatch while the runner is running and the world is paused.",
         source="upstream_code", ref=_RUN + ":1282-1284"),
    Fact("SetPaused stores the pause state in currentInfo.paused.", source="upstream_code", ref=_RUN + ":1290-1291"),
    Fact("Step publishes the world statistics.", source="upstream_code", ref=_RUN + ":1023-1024"),
    Fact("Step processes the world control messages.", source="upstream_code", ref=_RUN + ":1063-1064"),
    Fact("The Run loop calls Step on every iteration and counts a processed iteration only while not paused.",
         source="upstream_code", ref=_RUN + ":896-911"),
    Fact("The statistics publisher on the stats topic is limited to 10 messages per second.",
         source="upstream_code", ref=_RUN + ":806-808"),
    Fact("PublishStats copies currentInfo.paused into the WorldStatistics message.", source="upstream_code",
         ref=_RUN + ":534"),
    Fact("UpdateCurrentInfo assigns currentInfo.realTime from the real-time stopwatch on every update.",
         source="upstream_code", ref=_RUN + ":418"),
    Fact("UpdateCurrentInfo advances the simulation time and the iteration count only while not paused.",
         source="upstream_code", ref=_RUN + ":423-429"),
    Fact("The Physics system steps the physics only when not paused.", source="upstream_code",
         ref=_PHYSICS + ":1047-1051"),
    Fact("DiffDrive subscribes once, to the topic validTopic returns from a candidate list of an optional SDF "
         "topic and then /model/ followed by the model name and /cmd_vel.",
         source="upstream_code", ref=_DIFF + ":335-344"),
    Fact("validTopic returns the first candidate that AsValidTopic accepts.",
         source="upstream_code", ref=_UTIL + ":623-640"),
    Fact("DiffDrive's Configure sets enabled true.", source="upstream_code", ref=_DIFF + ":358"),
    Fact("OnCmdVel stores the Twist in targetVel while the system is enabled.", source="upstream_code",
         ref=_DIFF + ":637-644"),
    Fact("OnEnable stores the enable flag and, when disabled, zeros targetVel.", source="upstream_code",
         ref=_DIFF + ":647-656"),
    Fact("DiffDrive's PreUpdate returns early while paused.", source="upstream_code", ref=_DIFF + ":451-453"),
    Fact("DiffDrive's PostUpdate returns early while paused, before UpdateVelocity.", source="upstream_code",
         ref=_DIFF + ":501-505"),
    Fact("UpdateVelocity reads the stored targetVel linear x and angular z.", source="upstream_code",
         ref=_DIFF + ":605-616"),
    Fact("The joint position controller's position callback stores the commanded position.", source="upstream_code",
         ref=_JOINT_POSITION + ":489-492"),
    Fact("The joint position controller's PreUpdate returns early while paused.", source="upstream_code",
         ref=_JOINT_POSITION + ":395-397"),
    Fact("defaultGuiConfigFile uses gui.config unless the caller passes playback or a custom path.",
         source="upstream_code", ref=_GUI + ":58-73"),
    Fact("The default gui.config WorldControl plugin sets play_pause, step, start_paused and use_event.",
         source="upstream_code", ref=_GUI_CONFIG + ":123-141"),
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


class Ros2MobileManipulator(RosDriver):
    device_id = "mobile_manipulator"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeRos2MobileManipulator"}
    tags = [
        "ros", "ros2", "simulation", "gazebo", "mobile-base", "mobile-manipulator", "action",
    ]
    display_name = "will0103 ROS 2 mobile manipulator simulation"
    vendor = "will0103"
    model = "my_robot"
    facts = [
        Fact(
            "The node creates its MoveRobot action server on the relative name move_robot with a "
            "reentrant callback group.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:27-32",
        ),
        Fact(
            "The MoveRobot action goal declares three float64 fields: linear_vel_x, angular_vel_z and "
            "duration.",
            source="upstream_code",
            ref="src/my_robot_interfaces/action/MoveRobot.action:1-5",
        ),
        Fact(
            "The MoveRobot action result declares a bool success and a string message.",
            source="upstream_code",
            ref="src/my_robot_interfaces/action/MoveRobot.action:5-8",
        ),
        Fact(
            "The MoveRobot feedback declares an int64 progress value.",
            source="upstream_code",
            ref="src/my_robot_interfaces/action/MoveRobot.action:9-11",
        ),
        Fact(
            "The goal response callback accepts every goal without inspecting its values.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:71-77",
        ),
        Fact(
            "The accept callback pushes every accepted goal handle onto goal_queue_.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:86-93",
        ),
        Fact(
            "The queue thread polls goal_queue_ at 1000 Hz and runs each popped goal's execute_callback "
            "to completion before it pops the next.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:95-115",
        ),
        Fact(
            "The execute loop publishes the goal's linear.x and angular.z on cmd_vel at 10 Hz and "
            "publishes a zero Twist on normal completion.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:119-158",
        ),
        Fact(
            "The execute loop checks is_canceling, publishes a zero Twist, sets success false and "
            "returns a canceled result.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:141-150",
        ),
        Fact(
            "The execute loop starts its duration from this->now().",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:128-131",
        ),
        Fact(
            "The cancel response callback accepts every cancellation request without inspecting the "
            "goal handle.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:79-84",
        ),
        Fact(
            "The node constructor creates the MoveRobot action server and the joint, wheel and hand "
            "publishers; it creates no stop service and no stop action.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:20-34",
        ),
        Fact(
            "The bridge maps the ROS /cmd_vel topic to the Gazebo /model/my_robot/cmd_vel topic as "
            "geometry_msgs/msg/Twist in the ROS_TO_GZ direction.",
            source="upstream_code",
            ref="src/my_robot_bringup/config/gazebo_bridge.yaml:19-23",
        ),
        Fact(
            "The bridge configuration names /clock, /joint_states, /tf, /cmd_vel, the two camera topics "
            "and the two joint command topics.",
            source="upstream_code",
            ref=_BRIDGE_YAML_REF,
        ),
        Fact(
            "The bringup launch starts robot_state_publisher, Gazebo, the robot spawner, ros_gz_bridge "
            "and RViz, but not the move_robot node.",
            source="upstream_code",
            ref="src/my_robot_bringup/launch/project_robot_gazebo.launch.xml:1-27",
        ),
        Fact(
            "The bringup launch includes ros_gz_sim gz_sim.launch.py with project_world.sdf and -r.",
            source="upstream_code",
            ref=_LAUNCH_REF,
        ),
        Fact(
            "The bringup launch starts ros_gz_bridge parameter_bridge with the bridge configuration file.",
            source="upstream_code",
            ref=_BRIDGE_LAUNCH_REF,
        ),
        Fact(
            "project_world.sdf names its world empty.",
            source="upstream_code",
            ref=_WORLD_SDF_REF,
        ),
        Fact(
            "The world file loads the Physics, UserCommands, SceneBroadcaster, Contact and Sensors plugins.",
            source="upstream_code",
            ref="src/my_robot_bringup/worlds/project_world.sdf:8-14",
        ),
        Fact(
            "The DiffDrive plugin names the left and right wheel joints and sets no topic element.",
            source="upstream_code",
            ref=_DIFF_XACRO_REF,
        ),
        Fact(
            "The arm description loads joint position controllers on armbase_forearm_joint and "
            "forearm_hand_joint.",
            source="upstream_code",
            ref=_ARM_XACRO_REF,
        ),
        Fact(
            "The README's Move Mobile Base example publishes /cmd_vel directly with ros2 topic pub -r 1.",
            source="vendor_doc",
            ref="README.md:130-140",
        ),
        Fact(
            "A startup timer publishes forearm and hand joint positions through the joint command "
            "publishers; it is startup initialisation, not a stop path.",
            source="upstream_code",
            ref="src/my_cpp_pkg/src/move_robot.cpp:33-68",
        ),
        Fact(
            "The README describes a ROS 2 Jazzy and Gazebo Harmonic mobile-manipulator simulation with "
            "a custom action server, goal queueing, progress feedback and goal cancellation.",
            source="vendor_doc",
            ref="README.md:7-9",
        ),
        Fact(
            "The README's environment list names ROS 2 Jazzy and Gazebo Harmonic.",
            source="vendor_doc",
            ref="README.md:86-88",
        ),
        Fact(
            "The README's install steps source /opt/ros/jazzy/setup.bash.",
            source="vendor_doc",
            ref="README.md:103",
        ),
        Fact(
            "The README's send_goal example targets the /move_robot action with the MoveRobot "
            "interface.",
            source="vendor_doc",
            ref="README.md:122-127",
        ),
        Fact(
            "my_robot_bringup depends on ament_cmake, ros_gz_sim and ros_gz_bridge.",
            source="upstream_code",
            ref="src/my_robot_bringup/package.xml:10-16",
        ),
        Fact(
            "my_robot_bringup's license element is a TODO license declaration.",
            source="upstream_code",
            ref="src/my_robot_bringup/package.xml:8",
        ),
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The world empty is paused: after the WorldControl pause two fresh stats samples, 40 ms or more apart within "
        "600 ms, reported paused true, so the world does not step and the differential drive applies no stored twist; "
        "it is the paused flag in that window, not a measured standstill, it needs the operator-run ros_gz bridges, "
        "and no unpause is offered: the stored twist, the arm joint targets and a still-running move_robot queue act "
        "when the operator resumes the world."
    )
    #: The fake is a ROS-free recording of the declared action wire plus a canned
    #: paused flag.  It runs no Gazebo Harmonic physics.
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned action terminals and world statistics that follow the wall clock; no "
                     "physics step, controller loop or state hash is modelled",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers send_action_goal and "
            "cancel_action_goal for /move_robot and a canned /world/empty control service and stats topic, and "
            "runs no Gazebo Harmonic world, physics, sensors, ros_gz_bridge, differential-drive controller or "
            "action-server queue timing",
            "the fake completes a default goal immediately and can hold one active goal only to "
            "exercise cancellation; it does not reproduce the upstream 10 Hz command loop, the "
            "1000 Hz queue thread or the startup joint timers",
            "the upstream action publishes geometry_msgs/Twist on cmd_vel, but the fake records no "
            "Gazebo base motion, pose, odometry or collision state; each MoveRobot receipt reports the goal it "
            "handed to rosbridge (sent_linear_vel_x, sent_angular_vel_z, sent_duration), which is the transmitted "
            "request, not a measurement",
            "the arm command topics /forearm_joint/cmd_pos and /hand_joint/cmd_pos, /joint_states, "
            "/tf, /camera/image_raw and /camera/camera_info are not bound",
            "the fake's canned result strings and status values are test data, not device facts, "
            "limits or a motion envelope",
            "the action cancel path publishes a zero Twist and cancels the running goal, but queued "
            "goals remain; the fake models that queue so cancellation is not claimed as a stop",
            "a cancel request for a queued goal is accepted at once, but the goal ends "
            "canceled only when the queue thread pops it after every goal ahead of it, so an MHS cancel "
            "waits for other clients' goals (move_robot.cpp:79-84, :95-115, :141-150); any client, "
            "including the README's ros2 topic pub example, can publish /cmd_vel directly, and the "
            "bringup launch does not start move_robot, so the operator starts it separately",
            "the stop is the companion gz-sim world pause (WorldControl through ros_gz ControlWorld), whose reply is "
            "true for any request gz-sim queued (SimulationRunner.cc:1375-1377); it is confirmed by the E2 read-back: "
            "the fake keeps a paused flag that the control request sets after its next statistics sample and "
            "publishes /world/empty/stats every 100 ms (placeholder) while subscribed; it runs no SimulationRunner",
            "the e-stop endpoints exist only while the operator runs ros_gz's parameter_bridge with the two "
            "arguments of operator_bridges; gazebo_bridge.yaml:1-47 names /clock, /joint_states, /tf, /cmd_vel, the "
            "camera topics and the two joint commands, and does not name /world/empty/control or /world/empty/stats; "
            "a second bridge of names the launch already bridges would be another path; without the operator bridges "
            "the control call is not answered and the read-back sees no sample, so the e-stop fails closed; the "
            "declared estop_latency_ms 1500 covers the control call (400 ms) and the read-back bound (600 ms)",
            "the read-back's freshness is the arrival time only: the bridged WorldStatistics header is the gz header, "
            "which PublishStats does not stamp (ros_gz convert copies it, ros_gz_interfaces.cpp:840); sim_time and "
            "iterations advance only while not paused (SimulationRunner.cc:423-429); real_time is assigned from the "
            "stopwatch on every update (SimulationRunner.cc:418) and SetPaused stops that stopwatch while the runner "
            "is running and paused (SimulationRunner.cc:1282-1284), so those fields are not a freshness stamp; the "
            "bridge's default publisher QoS sets only KeepLast with the queue size "
            "(bridge_config.cpp:274-279), so its durability stays rclcpp's default, volatile, which replays no "
            "history to a late subscriber; the first sample is discarded and a burst of samples restarts the count; "
            "an operator QoS override of the stats publisher (factory.hpp:61-82) to a deeper transient-local "
            "history is not covered beyond that burst rule",
            "the endpoints name the only world in the clone, empty (project_world.sdf:2); a launch that loads "
            "another world name does not serve these endpoints and the e-stop fails closed",
            "the world SDF embeds no GUI plugin (project_world.sdf plugins at :8-14, and a search of the 237-line "
            "file finds no gui element); gz-sim's default GUI config is gui.config when the caller passes neither "
            "playback nor a custom path (Gui.cc:58-73), and that file's WorldControl plugin has play_pause and step "
            "(gui.config:123-141)",
            "a live world can be unpaused or stepped by that GUI, a WorldControl multi_step "
            "(SimulationRunner.cc:1445-1452) or any client of the control service; MHS does not watch the flag after "
            "the confirmation window, and safety_status reports that retained confirmation with no fresh observation "
            "of an external unpause",
            "no unpause is offered: DiffDrive stores the Twist in targetVel while enabled (DiffDrive.cc:637-644; "
            "Configure sets enabled true at :358) and PreUpdate and PostUpdate return while paused (:451-453, "
            ":501-505) before UpdateVelocity reads the stored linear x and angular z (:605-616), so the stored twist "
            "resumes when the world runs; OnEnable zeros targetVel only when the system is disabled (:647-656), and "
            "this package does not bind that enable topic; the joint position controller stores the commanded "
            "position (JointPositionController.cc:489-492) and its PreUpdate returns while paused (:395-397); the "
            "move_robot execute loop times the goal with this->now() (move_robot.cpp:128-131) and keeps publishing "
            "the goal Twist at 10 Hz until the duration elapses, and the clone contains no use_sim_time, so the "
            "queue keeps running on the node clock while the world is paused and overwrites a zero Twist; the "
            "bringup launch does not start move_robot; after mhs.safety.reset the world stays paused, and the "
            "operator zeros the /cmd_vel stream, stops or lets the move_robot queue drain, resets the arm targets, "
            "then unpauses outside MHS (the GUI play button or a ControlWorld request with pause false)",
            "the deployment's gz-sim, ros_gz and gz-transport must be the pinned 8.15.0, 1.0.25 and 13.6.0 releases "
            "(ROS 2 Jazzy with Gazebo Harmonic; README.md:7, :86-88, :103); rosbridge cannot read the versions",
            "no live ROS graph, rosbridge server, Gazebo world or hardware was contacted; the "
            "package is model-authored and remains contract_checked",
        ],
    }

    #: Action-only declaration: the stock server snapshots an empty resource
    #: state.  The goal-sent fields on the receipt are what shows the invoke.
    parameters = {}
    reads = {}
    commands = {
        "x-cap.will0103.move-robot.v1": _MOVE_ROBOT,
    }
    actions = {
        "x-cap.will0103.move-robot.v1": Action(
            name="move_robot",
            verb="invoke",
            cancellable=True,
            risk="R2",
            description="Send one MoveRobot velocity/duration goal to the ROS 2 /move_robot action server.",
            input={
                "linear_vel_x": Field(
                    "number",
                    unit="m/s",
                    description="Commanded forward velocity, mapped to the MoveRobot linear_vel_x goal field",
                    limit=Limit.operator_required(_LINEAR_REASON),
                ),
                "angular_vel_z": Field(
                    "number",
                    unit="rad/s",
                    description="Commanded turn rate, mapped to the MoveRobot angular_vel_z goal field",
                    limit=Limit.operator_required(_ANGULAR_REASON),
                ),
                "duration": Field(
                    "number",
                    unit="s",
                    description="Goal duration, mapped to the MoveRobot duration goal field",
                    limit=Limit.operator_required(_DURATION_REASON),
                ),
            },
            output={
                "success": Field(
                    "boolean",
                    description="Upstream result success flag; true only when the execute loop completes normally",
                ),
                "message": Field(
                    "string",
                    description="Upstream terminal result message; the cancel path sets success false",
                ),
                "sent_linear_vel_x": Field(
                    "number",
                    unit="m/s",
                    description="The linear_vel_x handed to rosbridge (the transmitted request, not a measurement)",
                ),
                "sent_angular_vel_z": Field(
                    "number",
                    unit="rad/s",
                    description="The angular_vel_z handed to rosbridge (the transmitted request, not a measurement)",
                ),
                "sent_duration": Field(
                    "number",
                    unit="s",
                    description="The duration handed to rosbridge (the transmitted request, not a measurement)",
                ),
            },
        ),
    }
    estop_latency_ms = 1500
    #: E3: the bridges the operator runs (ros_gz parameter_bridge, one argument each); the package never starts them.
    operator_bridges = [
        {"args": "/world/empty/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE_README + ":86",
         "description": "The world control service: the e-stop pause."},
        {"args": "/world/empty/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":52",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    # The e-stop pauses the world and confirms it by the paused flag in fresh statistics samples (companion gz-sim
    # and ros_gz, E2); anything else leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}

    def make_bridge(self, native):
        return _GoalReceipt(super().make_bridge(native))
