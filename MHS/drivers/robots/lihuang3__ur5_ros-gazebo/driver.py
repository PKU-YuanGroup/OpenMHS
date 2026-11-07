"""OpenMHS rosbridge driver for the UR5 vacuum-gripper array of gh.lihuang3/ur5_ros-gazebo.

The pinned repository is a ROS 1 / Gazebo pick-and-place demonstration.  The
UR5 arm is moved by the clone's own Python nodes through the MoveIt
``moveit_commander`` client; the clone declares no ROS service or action for
arm motion.  The ROS-callable device surface that the clone does declare is
the array of nine Gazebo vacuum-gripper plugins: each plugin is configured by
``src/ur_description/ur5.urdf.xacro`` and the gripper node waits for and calls
the matching ``on`` and ``off`` ``std_srvs/Empty`` services.  The same node
subscribes to the first plugin's ``grasping`` Bool topic.  The vision and
block-pose nodes publish the ``cxy`` ``ur5_notebook/Tracker`` and
``blocks_poses`` topics used by the demonstration.

This package is a configuration-only :class:`RosDriver`; it declares no Python
native class, does not launch Gazebo or MoveIt, and does not import or run
upstream code.  The arm motion, the MoveIt planning/execution path, the
camera image stream, block spawning and the remaining Gazebo services are NOT
COVERED.

The clone offers no acknowledged stop of its own (the vacuum ``off`` services
release the payload and do not stop the arm).  The e-stop is the Gazebo world
pause of the simulator's own repository, cited as a reviewed companion source
fetched at a pinned commit (user decision and authorisation of 2026-11-05;
``task.json`` ``companions`` with ``lock``): gazebo_ros 2.5.21 (ROS 1 Kinetic)
``/gazebo/pause_physics``, confirmed by reading
``/gazebo/get_physics_properties`` back until ``pause`` is true; Gazebo 7.16.1
is cited for what a paused world does not run.  The pause stops every world
update: the arm's ros_control controllers, the vacuum plugins and the physics.
It is the paused flag, not a measured standstill, and it keeps each vacuum
channel's state (releasing it would drop the payload).  The vacuum plugin
itself is gazebo_ros's, so its facts cite the same companion.

No unpause is offered.  On an unpause the arm resumes the MoveIt trajectory
``ur5_mp`` sent through the arm controller and each vacuum channel acts with its
stored state; this package commands neither the trajectory nor (safely) the
vacuum, so it cannot clear them first (the orchestrator's SAFE-042 condition).
After ``mhs.safety.reset`` the world stays paused; the vacuum services still
answer (their queue thread runs while paused) and the operator recovers outside
MHS (see ``safe_state``).

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 2f7b9b056bb41b9412f86589a60e25ba2816b78b; the stop, its read-back and
the facts about them cite the companions at their pins.  The fake is a ROS-free
analytic transport; no ROS graph, Gazebo, MoveIt, simulator or hardware is
contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

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

_VACUUM = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp"
_ROS_CONTROL = "companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp"
_PLUGIN_FACTS = [
    Fact("The vacuum gripper plugin advertises its grasping Bool topic and its on and off std_srvs::Empty services on "
         "a custom callback queue.", source="upstream_code", ref=_VACUUM + ":116-133"),
    Fact("The vacuum gripper plugin serves that queue on its own thread and connects UpdateChild to the world-update "
         "begin event.", source="upstream_code", ref=_VACUUM + ":136-142"),
    Fact("The on service sets the stored status to true and the off service sets it to false.",
         source="upstream_code", ref=_VACUUM + ":147-168"),
    Fact("UpdateChild publishes grasping false when the status is off; when it is on it pulls every link within "
         "0.05 m of the gripper link with a force of at most 20 and publishes grasping true for such a link.",
         source="upstream_code", ref=_VACUUM + ":172-230"),
    Fact("The vacuum plugin's queue thread serves its callbacks with a 0.01 s wall-clock wait while its node handle "
         "is ok.", source="upstream_code", ref=_VACUUM + ":235-243"),
    Fact("gazebo_ros_control connects its Update to the world-update begin event.", source="upstream_code",
         ref=_ROS_CONTROL + ":208-211"),
    Fact("gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands "
         "to the simulated joints.", source="upstream_code", ref=_ROS_CONTROL + ":223-270"),
]

#: The gripper node imports the service and message types it uses.
_EMPTY_IMPORT = "ur5_gripper.py:11"
_BOOL_IMPORT = "ur5_gripper.py:10"
_TRACKER_IMPORT = "ur5_mp.py:31"

#: The nine vacuum-gripper services declared by the node, in channel order.
#: Each line is the wait_for_service call that names the absolute service.
_ON_REFS = [
    "ur5_gripper.py:20",
    "ur5_gripper.py:32",
    "ur5_gripper.py:44",
    "ur5_gripper.py:56",
    "ur5_gripper.py:68",
    "ur5_gripper.py:80",
    "ur5_gripper.py:92",
    "ur5_gripper.py:104",
    "ur5_gripper.py:116",
]
_OFF_REFS = [
    "ur5_gripper.py:128",
    "ur5_gripper.py:137",
    "ur5_gripper.py:146",
    "ur5_gripper.py:155",
    "ur5_gripper.py:164",
    "ur5_gripper.py:173",
    "ur5_gripper.py:182",
    "ur5_gripper.py:191",
    "ur5_gripper.py:200",
]
_ON_SERVICES = [f"/ur5/vacuum_gripper{'' if index == 0 else index}/on" for index in range(9)]
_OFF_SERVICES = [f"/ur5/vacuum_gripper{'' if index == 0 else index}/off" for index in range(9)]

#: The first plugin publishes its grasp state on /ur5/vacuum_gripper/grasping.
_GRASPING = {
    "topic": "/ur5/vacuum_gripper/grasping",
    "type": "std_msgs/Bool",
    "source_name": "/ur5/vacuum_gripper/grasping",
    "source_ref": "ur5_gripper.py:235",
    "type_ref": _BOOL_IMPORT,
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {"map": {"grasping": "data"}},
}

#: The vision and motion nodes use the relative topic cxy for the Tracker.
_TRACKER = {
    "topic": "/cxy",
    "type": "ur5_notebook/Tracker",
    "source_name": "cxy",
    "source_ref": "ur5_mp.py:44",
    "type_ref": _TRACKER_IMPORT,
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {
        "map": {
            "x": "x",
            "y": "y",
            "z": "z",
            "error_x": "error_x",
            "error_y": "error_y",
            "error_z": "error_z",
            "flag1": "flag1",
            "flag2": "flag2",
            "flag3": "flag3",
        }
    },
}

#: The block-pose node publishes its own message on the relative topic blocks_poses.
_BLOCK_POSES = {
    "topic": "/blocks_poses",
    "type": "ur5_notebook/blocks_poses",
    "source_name": "blocks_poses",
    "source_ref": "blocks_poses_publisher.cpp:113",
    "type_ref": "blocks_poses_publisher.cpp:14",
    "operation": "subscribe",
    "timeout_ms": 2000,
    "path": "$",
    "result": {"map": {"x": "x", "y": "y", "z": "z"}},
}

_ACKNOWLEDGED = Field(
    "boolean",
    description="True once the upstream std_srvs/Empty service acknowledged the call; "
                "the empty response is not a measured vacuum or grasp state",
)

_GRASPING_FIELD = Field(
    "boolean",
    description="True when the first vacuum gripper plugin reports a grasp on its Bool topic; "
                "this is the plugin's report, not a measured pressure",
)

_TRACKER_FIELDS = {
    "x": Field("number", description="Tracker x coordinate in the published image frame"),
    "y": Field("number", description="Tracker y coordinate in the published image frame"),
    "z": Field("number", description="Tracker z coordinate in the published image frame"),
    "error_x": Field("number", description="Tracker x error reported by the vision node"),
    "error_y": Field("number", description="Tracker y error reported by the vision node"),
    "error_z": Field("number", description="Tracker z error reported by the vision node"),
    "flag1": Field("boolean", description="Tracker flag1 set by the vision node"),
    "flag2": Field("boolean", description="Tracker flag2 set by the motion node"),
    "flag3": Field("boolean", description="Tracker flag3; not set by the shipped nodes"),
}

_BLOCK_FIELDS = {
    "x": Field("array", items=Field("number", description="Block x coordinate in the world"),
               description="Block x coordinates in the published order"),
    "y": Field("array", items=Field("number", description="Block y coordinate in the world"),
               description="Block y coordinates in the published order"),
    "z": Field("array", items=Field("number", description="Block z coordinate in the world"),
               description="Block z coordinates in the published order"),
}


def _service_binding(service, source_ref):
    """One fixed std_srvs/Empty call; the empty response is the only reply."""
    return {
        "service": service,
        "type": "std_srvs/Empty",
        "source_name": service,
        "source_ref": source_ref,
        "type_ref": _EMPTY_IMPORT,
        "success": {"path": "$", "equals": {}},
        "timeout_ms": 5000,
        "result": {"acknowledged": {"value": True}},
    }


def _commands():
    commands = {}
    for index, (service, ref) in enumerate(zip(_ON_SERVICES, _ON_REFS)):
        commands[f"x-cap.lihuang3.vacuum_gripper_{index}_on.v1"] = _service_binding(service, ref)
    for index, (service, ref) in enumerate(zip(_OFF_SERVICES, _OFF_REFS)):
        commands[f"x-cap.lihuang3.vacuum_gripper_{index}_off.v1"] = _service_binding(service, ref)
    commands["x-cap.lihuang3.grasping.v1"] = _GRASPING
    commands["x-cap.lihuang3.tracker.v1"] = _TRACKER
    commands["x-cap.lihuang3.block_poses.v1"] = _BLOCK_POSES
    return commands


def _actions():
    actions = {}
    for index in range(9):
        actions[f"x-cap.lihuang3.vacuum_gripper_{index}_on.v1"] = Action(
            name=f"vacuum_gripper_{index}_on",
            verb="invoke",
            description=(
                f"Call the acknowledged {_ON_SERVICES[index]} std_srvs/Empty service; the empty reply "
                "confirms only that the plugin handler returned"
            ),
            output={"acknowledged": _ACKNOWLEDGED},
        )
        actions[f"x-cap.lihuang3.vacuum_gripper_{index}_off.v1"] = Action(
            name=f"vacuum_gripper_{index}_off",
            verb="invoke",
            description=(
                f"Release vacuum channel {index} through the {_OFF_SERVICES[index]} std_srvs/Empty "
                "service; a held object may drop, the arm is not stopped, and this is not a safe state"
            ),
            output={"acknowledged": _ACKNOWLEDGED},
        )
    actions["x-cap.lihuang3.grasping.v1"] = Action(
        name="read_grasping",
        verb="read",
        description="Read one /ur5/vacuum_gripper/grasping Bool sample; an explicit observation, "
                    "not the automatic resource snapshot",
        output={"grasping": _GRASPING_FIELD},
    )
    actions["x-cap.lihuang3.tracker.v1"] = Action(
        name="read_tracker",
        verb="read",
        description="Read one /cxy Tracker sample published by the vision node",
        output=_TRACKER_FIELDS,
    )
    actions["x-cap.lihuang3.block_poses.v1"] = Action(
        name="read_block_poses",
        verb="read",
        description="Read one /blocks_poses sample published by the block-pose node",
        output=_BLOCK_FIELDS,
    )
    return actions


class Ur5VacuumGripper(RosDriver):
    device_id = "ur5-vacuum-gripper"
    device_kind = "robot.gripper"
    mode = "simulated"
    # The demo is a UR5 arm whose vacuum array picks and drops a box; a dropped
    # payload is an R2 hazard even though this package commands only vacuum.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeUr5VacuumGripper"}
    tags = ["ros", "ros1", "gazebo", "ur5", "vacuum-gripper", "pick-and-place"]
    display_name = "UR5 vacuum gripper array (Gazebo)"
    vendor = "lihuang3"
    facts = [
        Fact("The README describes the repository as a UR5 pick-and-place demonstration in ROS and Gazebo "
             "using a USB camera and vacuum grippers.",
             source="vendor_doc", ref="README.md:1"),
        Fact("The README says the default ur_description files include no camera or vacuum gripper modules and "
             "tells the user to copy the clone's common.gazebo.xacro and ur5.urdf.xacro over them.",
             source="vendor_doc", ref="README.md:46-49"),
        Fact("The initialization launch starts Gazebo, uploads the robot description from the ur_description "
             "package, starts the UR5 arm controller and MoveIt, then starts the blocks_spawner, "
             "blocks_poses_publisher, ur5_vision, ur5_mp and ur5_gripper nodes.",
             source="upstream_code", ref="launch/initialize.launch:9-54"),
        Fact("The launch loads the arm controller from the ur_gazebo package and remaps /follow_joint_trajectory "
             "to /arm_controller/follow_joint_trajectory when sim is true.",
             source="upstream_code", ref="launch/initialize.launch:27-33"),
        Fact("The URDF declares the libgazebo_ros_vacuum_gripper.so plugin for the first gripper with "
             "robotNamespace /ur5/vacuum_gripper and topicName grasping.",
             source="upstream_code", ref="src/ur_description/ur5.urdf.xacro:357-363"),
        Fact("The URDF declares further vacuum-gripper plugins under /ur5/vacuum_gripper1 through "
             "/ur5/vacuum_gripper8; the channel-3 plugin also names its topic grasping2.",
             source="upstream_code", ref="src/ur_description/ur5.urdf.xacro:396-675"),
        Fact("The first vacuum plugin config sets maxForce 50, maxDistance 0.05 and minDistance 0.01.",
             source="upstream_code", ref="src/ur_description/ur5.urdf.xacro:361-363"),
        Fact("The gripper node waits for the absolute /ur5/vacuum_gripper/on service and calls it with an "
             "Empty service proxy.",
             source="upstream_code", ref="ur5_gripper.py:20-26"),
        Fact("The gripper node waits for the absolute /ur5/vacuum_gripper/off service and calls it with an "
             "Empty service proxy.",
             source="upstream_code", ref="ur5_gripper.py:128-134"),
        Fact("The gripper node defines on and off functions for the eight additional channels, each naming "
             "/ur5/vacuum_gripperN/on or /ur5/vacuum_gripperN/off.",
             source="upstream_code", ref="ur5_gripper.py:32-208"),
        Fact("The gripper node imports Empty from std_srvs.srv and Bool from std_msgs.msg.",
             source="upstream_code", ref="ur5_gripper.py:10-11"),
        Fact("The gripper node subscribes to /ur5/vacuum_gripper/grasping with the Bool type.",
             source="upstream_code", ref="ur5_gripper.py:235"),
        Fact("The trigger callback calls every gripper on function when msg.flag2 is true and every off "
             "function otherwise.",
             source="upstream_code", ref="ur5_gripper.py:208-230"),
        Fact("The gripper node subscribes trigger to the relative cxy1 Tracker topic.",
             source="upstream_code", ref="ur5_gripper.py:237"),
        Fact("The vision node subscribes to /ur5/usbcam/image_raw with the Image type and publishes the "
             "relative topic cxy with the Tracker type.",
             source="upstream_code", ref="ur5_vision.py:47-48"),
        Fact("The motion node subscribes to the relative cxy Tracker topic and publishes the relative cxy1 "
             "Tracker topic.",
             source="upstream_code", ref="ur5_mp.py:44-45"),
        Fact("The motion node constructs MoveGroupCommander('manipulator') and executes plans through the "
             "MoveIt client.",
             source="upstream_code", ref="ur5_mp.py:62-141"),
        Fact("The motion node registers cleanup with rospy.on_shutdown.",
             source="upstream_code", ref="ur5_mp.py:57"),
        Fact("cleanup calls self.arm.stop() and shuts down MoveIt.",
             source="upstream_code", ref="ur5_mp.py:149-158"),
        Fact("The motion node publishes the tracker with cxy_pub with flag2 1 when len(self.pointx) is 11, and "
             "with flag2 0 after it has executed the lift, transition, end-state and retreat plans.",
             source="upstream_code", ref="ur5_mp.py:203-262"),
        Fact("The motion node's header states that the program is distributed under the GNU General Public "
             "License, version 2 or later.",
             source="upstream_code", ref="ur5_mp.py:10-22"),
        Fact("The Tracker message declares float64 x, y, z, error_x, error_y and error_z and bool flag1, "
             "flag2 and flag3.",
             source="upstream_code", ref="msg/Tracker.msg:1-12"),
        Fact("The block-pose node subscribes to /current_blocks and /gazebo/model_states and advertises the "
             "relative blocks_poses topic with the ur5_notebook/blocks_poses type.",
             source="upstream_code", ref="blocks_poses_publisher.cpp:108-113"),
        Fact("The blocks_poses message declares float64 arrays x, y and z.",
             source="upstream_code", ref="msg/blocks_poses.msg:1-7"),
        Fact("The camera plugin declares cameraName ur5/usbcam and imageTopicName image_raw with an 800 by "
             "800 R8G8B8 image at 30 Hz.",
             source="upstream_code", ref="src/ur_description/common.gazebo.xacro:40-71"),
        Fact("The package manifest leaves the license field as TODO.",
             source="upstream_code", ref="package.xml:15"),
        Fact("The initialization launch includes gazebo_ros's empty_world.launch with the world worlds/empty.world "
             "and paused and gui arguments that default to false and true.", source="upstream_code",
             ref="launch/initialize.launch:5-16"),
        *_PLUGIN_FACTS,
        *_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back: no world update runs, so the "
        "arm controller, the vacuum plugins and the physics are frozen and each vacuum channel keeps its state; it "
        "is the paused flag, not a measured standstill. No unpause is offered: an operator stops ur5_mp and its "
        "MoveIt goal and unpauses outside MHS."
    )
    fidelity = {
        "engine": "analytic:ROS contract fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven contract fake with no Gazebo physics, gripper attachment, MoveIt planner "
                     "or wall-clock pacing; placeholder observations do not establish grasp or motion replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free analytic transport: it answers the declared services and subscriptions "
            "and runs no Gazebo, vacuum-gripper plugin, ODE physics, MoveIt, camera or wall-clock loop",
            "the vacuum on/off handlers flip placeholder flags; the fake models no suction, contact, "
            "attachment, mass or object release, so a receipt does not prove a grasp",
            "the grasping, cxy and blocks_poses values are placeholders; they do not establish a live "
            "perception or block state",
            "the package exposes the nine vacuum on/off services, the first grasping topic, the cxy tracker "
            "topic and the blocks_poses topic; the UR5 arm motion through MoveIt and the trajectory "
            "controller, the camera image stream, block spawning, the Gazebo model services and the "
            "remaining gripper grasping topics are NOT COVERED",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports; it runs no Gazebo World::Step; "
            "the vacuum off services are not a stop (they release the payload and do not stop the arm)",
            "no unpause is offered: on an unpause the arm controller resumes the MoveIt trajectory ur5_mp sent "
            "(gazebo_ros_control updates the controllers from the world update) and each vacuum channel acts with "
            "its stored status (gazebo_ros_vacuum_gripper.cpp:147-168, 172-230); the package cannot clear the "
            "trajectory and must not release the vacuum (the payload would drop), so the operator recovers outside "
            "MHS: stop or restart ur5_mp and MoveIt (rospy.on_shutdown runs self.arm.stop(), ur5_mp.py:57, 149-158), "
            "then press play in the Gazebo GUI or call rosservice call gazebo/unpause_physics",
            "while paused the vacuum services still answer (the plugin's queue thread runs on the wall clock), so a "
            "vacuum command after the reset changes the stored status that acts on the next unpause; the grasping, "
            "cxy and blocks_poses topics come from world-update plugins and the camera, so they are silent while "
            "paused and those reads fail NOT_READY (the fake silences them while its flag is set); "
            "ur5_gripper.py still switches every channel on again whenever ur5_mp publishes flag2 true on cxy1 "
            "(ur5_gripper.py:208-237, ur5_mp.py:211-213)",
            "a live world can be unpaused or stepped by the Gazebo GUI that empty_world.launch opens by default, by "
            "a WorldControl message or by any ROS client; MHS does not watch the flag after the e-stop "
            "(safety_status re-reads it only on request)",
            "the read-back needs the ODE engine (empty_world.launch's default physics): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.5.21 (Kinetic) and 7.16.1 releases the "
            "companion citations name; rosbridge cannot read their versions",
            "the vacuum plugins and the camera exist only after the user copies the clone's "
            "src/ur_description xacro files over the installed universal_robot ur_description, which "
            "initialize.launch uploads (README.md:46-49, launch/initialize.launch:20-22); otherwise no vacuum "
            "service or grasping topic exists and every vacuum call or grasping read fails",
            "the fake reports grasping as the first channel's on state and answers an Empty call with a "
            "non-empty rejection value; the upstream plugin reports a grasp only for an object in range and an "
            "Empty response has no fields, so those two fake paths exercise the package's predicates only",
            "no real ROS graph, Gazebo, MoveIt, simulator or hardware was contacted; evidence is F0 "
            "contract_checked only",
        ],
    }

    commands = _commands()
    actions = _actions()
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
