"""OpenMHS rosbridge driver for the ME5413 Gazebo world (gh.nus-advanced-robotics-centre/me5413_final_project).

The pinned upstream is a ROS 1 catkin workspace: a Gazebo world and robot
description, a Gazebo world plugin (``libobject_spawner_gz_plugin.so``) and an
RViz panel.  This package is a configuration-only :class:`RosDriver`; it
declares no Python native class and neither imports nor launches the upstream
code.  The operator runs ``roslaunch me5413_world world.launch`` and rosbridge
separately.

The plugin's ROS surface is the environment control surface of the 2526
course world:

* ``/rviz_panel/respawn_objects`` (``std_msgs/Int16``): the RViz panel
  publishes 1 to regenerate the random objects and 0 to clear them.
* ``/cmd_unblock`` (``std_msgs/Bool``): the student publishes true to remove
  the orange barrel once for a 10 s window.
* ``/gazebo/delete_model`` (``gazebo_msgs/DeleteModel``): the plugin's
  acknowledged service client used by every delete path.
* ``/gazebo/ground_truth/box_markers`` (``visualization_msgs/MarkerArray``)
  and ``/box_odom`` (``nav_msgs/Odometry``): the plugin's observations.

The moving red obstacle is the ``planar_box`` model spawned by
``world.launch``; the world plugin drives it through ``/box_cmd_vel``.  Deleting
that model through ``/gazebo/delete_model`` is offered as an ordinary, one-shot
command, not as a stop.  The clone offers no stop service.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic) ``/gazebo/pause_physics``,
confirmed by reading ``/gazebo/get_physics_properties`` back until ``pause`` is
true.  The pause stops every model update: the planar_box (moved only by
gazebo_ros_planar_move from the world update) and the Jackal stop moving, and
``/box_odom`` goes silent.  It is the paused flag, not a measured standstill.
It does not stop the plugin's ``respawnCmdCallback`` and
``openBridgeCallback``, which sleep on the wall clock and whose delete and
spawn requests a paused world still processes, so a callback already running
completes its bounded world edits during the pause, and any client or the
Gazebo GUI can unpause or step the world.

No unpause is offered (the orchestrator's SAFE-042 condition, the same rule as
the seven lock-companion Gazebo packages).  ``gazebo_ros_planar_move`` keeps
the velocity ``boxOdomCallback`` publishes
(``object_spawner_gz_plugin.cpp:372-387`` stores nothing itself; it publishes
``linear.y`` of plus or minus 2.0, and ``gazebo_ros_planar_move.cpp:242-249``
stores that twist and ``198-208`` applies it on the world update).  The URDF
sets no ``cmdTimeout`` (``planar_box.urdf.xacro:36-42``) and the plugin default
``cmd_timeout_`` is -1 (``gazebo_ros_planar_move.cpp:117``), so the update does
not zero that velocity.  This package does not publish ``/box_cmd_vel``.
``spawn_jackal.launch`` includes ``jackal_control``'s control and teleop
launches (``spawn_jackal.launch:23-26``), which are not in this clone, so this
package cannot clear the Jackal controller's command either.  After
``mhs.safety.reset`` the world stays paused.  The operator deletes
``planar_box`` (this package's remove command still applies while the world is
paused, or the GUI does it) and stops the Jackal controller and teleop nodes
outside MHS, then unpauses with the Gazebo GUI (``world.launch:9`` sets
``gui`` true) or ``rosservice call /gazebo/unpause_physics``.  The earlier
re-enable ``x-cap.nus-advanced-robotics-centre.resume.v1`` was removed for
that reason.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 9fd6ce2643f7dc9ed6e074ea559d3af29ef4968b; the stop, its read-back and
the facts about them cite the companions at their pins.  The fake transport is
ROS-free and every invented value is a placeholder; no ROS graph, simulator or
hardware run is claimed.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: ObjectSpawner::Load declares the plugin's ROS clients, publishers and
#: subscribers.  Lines 35-42 are the complete ROS surface used here.
_LOAD_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:35-42"

#: The acknowledged DeleteModel service client and its message include.
_DELETE_SERVICE_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:35"
_DELETE_TYPE_REF = "src/me5413_world/include/me5413_world/object_spawner_gz_plugin.hpp:32"

#: ``deleteObject`` fills ``request.model_name`` and checks ``response.success``.
_DELETE_CALL_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:207-216"

#: The RViz panel advertises the Int16 command topic with queue size 1.
_RESPAWN_REF = "src/interactive_tools/src/rviz_panel.cpp:25"
#: The panel's regenerate and clear buttons publish 1 and 0.
_RESPAWN_VALUES_REF = "src/interactive_tools/src/rviz_panel.cpp:117-130"

#: The plugin subscribes to the unblock topic and its Bool include.
_UNBLOCK_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:39"
_UNBLOCK_TYPE_REF = "src/me5413_world/include/me5413_world/object_spawner_gz_plugin.hpp:20"

#: The plugin's observations: the MarkerArray publisher and the Odometry
#: subscriber (with the type include on line 23).
_MARKERS_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:42"
_ODOM_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:41"
_ODOM_TYPE_REF = "src/me5413_world/include/me5413_world/object_spawner_gz_plugin.hpp:23"

#: The moving red obstacle is spawned as the model named planar_box.
_PLANAR_BOX_REF = "src/me5413_world/launch/world.launch:19-27"

#: The respawn callback's multi-step delete/sleep/spawn sequence.
_RESPAWN_CALLBACK_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:309-345"
#: The unblock callback's blocking ten-second sleep before respawning.
_UNBLOCK_CALLBACK_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:347-370"
#: The box odometry callback continuously republishes a nonzero twist.
_BOX_MOTION_REF = "src/me5413_world/src/object_spawner_gz_plugin.cpp:372-388"

#: The world is launched with use_sim_time true and starts unpaused.
_WORLD_REF = "src/me5413_world/launch/world.launch:1-13"

# -- Companion sources (task.json companions; user decision 2026-11-05) -----------------------------------------
#: gazebo_ros 2.9.3 (ROS 1 Noetic) at cd9cc952: the API plugin serves the pause and its read-back.
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
_LAUNCH = "companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch"
#: Gazebo classic 11.15.1 at b22c6e15: the world step the pause gates.
_WORLD = "companion:gazebo_classic/gazebo/physics/World.cc"

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
    Fact("The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_.",
         source="upstream_code", ref=_API + ":501-507"),
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
#: The planar_box's motion plugin (companion gazebo_ros_pkgs) and the DeleteModel server's wait.
_PLANAR_MOVE = "companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_planar_move.cpp"
_ME5413_COMPANION_FACTS = [
    Fact("GazeboRosPlanarMove connects UpdateChild to the world-update begin event.", source="upstream_code",
         ref=_PLANAR_MOVE + ":174-177"),
    Fact("UpdateChild sets the model's linear and angular velocity from the stored x_, y_ and rot_.",
         source="upstream_code", ref=_PLANAR_MOVE + ":198-208"),
    Fact("cmdVelCallback stores linear.x, linear.y and angular.z of the received Twist in x_, y_ and rot_.",
         source="upstream_code", ref=_PLANAR_MOVE + ":242-250"),
    Fact("The API plugin advertises the delete_model service on gazebo_queue_, the queue the pause uses.",
         source="upstream_code", ref=_API + ":293-299"),
    Fact("deleteModel publishes an entity_delete request, then loops, sleeping 1 ms per round, until the model is "
         "gone or ROS time passes its 60 s timeout.", source="upstream_code", ref=_API + ":851-878"),
]

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_DELETE_OUTPUT = {
    "success": Field("boolean", description="The DeleteModel response success flag"),
    "status_message": Field("string", description="The DeleteModel response status message"),
}

_POSE = Field(
    "object",
    description="nav_msgs/Odometry pose selected from message field pose.pose",
    properties={
        "position": Field(
            "object",
            description="Position in the odometry frame",
            properties={
                "x": Field("number", unit="m", description="Position x"),
                "y": Field("number", unit="m", description="Position y"),
                "z": Field("number", unit="m", description="Position z"),
            },
        ),
        "orientation": Field(
            "object",
            description="Orientation as a quaternion",
            properties={
                "x": Field("number", unit="1", description="Quaternion x"),
                "y": Field("number", unit="1", description="Quaternion y"),
                "z": Field("number", unit="1", description="Quaternion z"),
                "w": Field("number", unit="1", description="Quaternion w"),
            },
        ),
    },
)

_MARKERS = Field(
    "array",
    description="MarkerArray markers in wire order",
    items=Field("object", description="One visualization_msgs/Marker object as published by the plugin"),
)

_REMOVE_MOVING_OBSTACLE = {
    "service": "/gazebo/delete_model",
    "type": "gazebo_msgs/DeleteModel",
    "source_ref": _DELETE_SERVICE_REF,
    "type_ref": _DELETE_TYPE_REF,
    "request": {"model_name": "planar_box"},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "status_message": "status_message"}},
}

_DELETE_MODEL = {
    "service": "/gazebo/delete_model",
    "type": "gazebo_msgs/DeleteModel",
    "source_ref": _DELETE_SERVICE_REF,
    "type_ref": _DELETE_TYPE_REF,
    "args": {"model_name": {"from": "input.model_name"}},
    "success": {"path": "success", "equals": True},
    "result": {"map": {"success": "success", "status_message": "status_message"}},
}

_CLEAR_OBJECTS = {
    "topic": "/rviz_panel/respawn_objects",
    "type": "std_msgs/Int16",
    "operation": "publish",
    "source_ref": _RESPAWN_REF,
    "message": {"data": 0},
}

_REGENERATE_OBJECTS = {
    "topic": "/rviz_panel/respawn_objects",
    "type": "std_msgs/Int16",
    "operation": "publish",
    "source_ref": _RESPAWN_REF,
    "message": {"data": 1},
}

_OPEN_EXIT = {
    "topic": "/cmd_unblock",
    "type": "std_msgs/Bool",
    "operation": "publish",
    "source_ref": _UNBLOCK_REF,
    "type_ref": _UNBLOCK_TYPE_REF,
    "message": {"data": True},
}

_BOX_ODOM = {
    "topic": "/box_odom",
    "type": "nav_msgs/Odometry",
    "operation": "subscribe",
    "source_ref": _ODOM_REF,
    "type_ref": _ODOM_TYPE_REF,
    "result": {"map": {"pose": "output.pose.pose"}},
}

_BOX_MARKERS = {
    "topic": "/gazebo/ground_truth/box_markers",
    "type": "visualization_msgs/MarkerArray",
    "operation": "subscribe",
    "source_ref": _MARKERS_REF,
    "result": {"map": {"markers": "output.markers"}},
}


class Me5413World(RosDriver):
    device_id = "me5413_world"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeMe5413FinalProject"}
    display_name = "ME5413 Gazebo course world"
    vendor = "NUS Advanced Robotics Centre"
    model = "me5413_world (ROS Noetic / Gazebo 11)"
    tags = ["ros", "ros1", "gazebo", "simulation", "course-world", "object-spawner"]
    facts = [
        Fact("ObjectSpawner::Load creates the /gazebo/delete_model DeleteModel service client, a "
             "0.1 s timer, the Gazebo factory publisher, the /rviz_panel/respawn_objects and "
             "/cmd_unblock subscriptions, the /box_cmd_vel publisher, the /box_odom subscription "
             "and the /gazebo/ground_truth/box_markers publisher.",
             source="upstream_code", ref=_LOAD_REF),
        Fact("The plugin include object_spawner_gz_plugin.hpp includes std_msgs/Int16.h, std_msgs/Bool.h, "
             "visualization_msgs/MarkerArray.h, geometry_msgs/Twist.h, nav_msgs/Odometry.h and "
             "gazebo_msgs/DeleteModel.h.",
             source="upstream_code",
             ref="src/me5413_world/include/me5413_world/object_spawner_gz_plugin.hpp:19-32"),
        Fact("ObjectSpawner::deleteObject fills gazebo_msgs::DeleteModel request.model_name, calls "
             "clt_delete_objects_ and logs success only when response.success is true.",
             source="upstream_code", ref=_DELETE_CALL_REF),
        Fact("The RViz control panel advertises a std_msgs/Int16 publisher on the absolute topic "
             "/rviz_panel/respawn_objects with queue size 1.",
             source="upstream_code", ref=_RESPAWN_REF),
        Fact("The panel's regenerate button publishes data 1 and its clear button publishes data 0 on "
             "the respawn topic.",
             source="upstream_code", ref=_RESPAWN_VALUES_REF),
        Fact("The world plugin subscribes to the absolute /cmd_unblock topic.",
             source="upstream_code", ref=_UNBLOCK_REF),
        Fact("Load creates a 0.1 s timer whose callback publishes box_markers_msg_ as "
             "visualization_msgs/MarkerArray on the absolute /gazebo/ground_truth/box_markers topic.",
             source="upstream_code", ref="src/me5413_world/src/object_spawner_gz_plugin.cpp:36-53"),
        Fact("The plugin subscribes to the absolute /box_odom topic.",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The red obstacle is spawned by gazebo_ros spawn_model as the model named planar_box at "
             "x 6.0, y 0.0, z 3.5 from planar_box.urdf.xacro.",
             source="upstream_code", ref=_PLANAR_BOX_REF),
        Fact("respawnCmdCallback executes deleteCone, deleteRandomCone and deleteBoxes with "
             "common::Time::MSleep(500) between them for command 0, and repeats that sequence then "
             "spawnRandomCone, spawnCone and spawnRandomBoxes for command 1; the callback has no "
             "cancellation check.",
             source="upstream_code", ref=_RESPAWN_CALLBACK_REF),
        Fact("openBridgeCallback deletes the cone, calls common::Time::Sleep(10) and respawns the cone "
             "inside the same subscriber callback; this blocking ten-second path has no cancellation "
             "check.",
             source="upstream_code", ref=_UNBLOCK_CALLBACK_REF),
        Fact("boxOdomCallback reads pose.pose.position.y and, for every /box_odom message, publishes a "
             "geometry_msgs/Twist with linear.y plus or minus the SPEED constant 2.0 on /box_cmd_vel.",
             source="upstream_code", ref=_BOX_MOTION_REF),
        Fact("planar_box.urdf.xacro loads libgazebo_ros_planar_move.so with commandTopic box_cmd_vel, "
             "odometryTopic box_odom and odometryRate 20.0.",
             source="upstream_code", ref="src/me5413_world/launch/include/planar_box.urdf.xacro:36-42"),
        Fact("world.launch includes launch/include/spawn_jackal.launch to add the Jackal robot.",
             source="upstream_code", ref="src/me5413_world/launch/world.launch:15-16"),
        Fact("spawn_jackal.launch includes jackal_control's control.launch and teleop.launch and spawns the "
             "model jackal with gazebo_ros spawn_model.",
             source="upstream_code", ref="src/me5413_world/launch/include/spawn_jackal.launch:23-30"),
        Fact("world.launch sets /use_sim_time true and launches gazebo_ros empty_world.launch with "
             "paused=false, use_sim_time=true and the me5413_project_2526.world file.",
             source="upstream_code", ref=_WORLD_REF),
        Fact("The README tells students to unblock the lower-level exit by publishing a true "
             "std_msgs/Bool message to /cmd_unblock and states that the unblock lasts 10 s.",
             source="vendor_doc", ref="README.md:180-181"),
        Fact("The README asks students not to use ground truth topics such as /gazebo/ground_truth/state or "
             "/box_odom.", source="vendor_doc", ref="README.md:188"),
        Fact("Load creates the marker timer with a 0.1 s ros::Duration on the plugin's node handle.",
             source="upstream_code", ref="src/me5413_world/src/object_spawner_gz_plugin.cpp:36"),
        *_COMPANION_FACTS,
        *_ME5413_COMPANION_FACTS,
    ]
    #: The clone offers no Gazebo pause, stop or cancel endpoint; the companion gazebo_ros does.  Deleting
    #: planar_box removes one moving obstacle but stops none of the activity this package commands.
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back; the paused flag, not a measured "
        "standstill. No unpause is offered: the box velocity stays stored and jackal_control is outside the clone. "
        "The Gazebo GUI or another client can unpause or step the world (a step advances it). A running respawn or "
        "unblock callback still completes its world edits. After mhs.safety.reset the world stays paused; delete "
        "planar_box, stop the Jackal nodes and unpause outside MHS (world.launch:9)."
    )
    fidelity = {
        "engine": "canned:ROS recording transport (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies; no Gazebo physics, plugin callback, object spawner "
                     "randomisation or wall-clock pacing is modelled",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it records the declared publications and "
            "answers the declared subscriptions and the DeleteModel service; it runs no Gazebo world, "
            "physics, object spawner, RViz panel or ROS graph",
            "the box_odom and box_markers samples are placeholders and do not advance with the live "
            "world; the real MarkerArray content is scene-dependent and the 2526 plugin clears its "
            "markers without repopulating them",
            "the fake does not model the multi-step respawn callback, the blocking ten-second unblock "
            "callback, the random object selection or the /box_cmd_vel motion loop",
            "the stop is the companion gazebo_ros world pause: the fake keeps a paused flag that "
            "/gazebo/pause_physics sets and /gazebo/get_physics_properties reports, and it does not serve "
            "/gazebo/unpause_physics; it runs no Gazebo World::Step, and its GetPhysicsProperties numbers are "
            "placeholders; deleting planar_box (an ordinary command here) stops none of the activity this "
            "package commands",
            "while paused, a live Gazebo runs no model update, so /box_odom is silent (and the 0.1 s marker timer, "
            "on simulated time, waits); both reads fail NOT_READY after their timeout; the fake silences both "
            "while its flag is set; the device resource reads no topic",
            "a paused world still processes delete and spawn requests, and the plugin's respawn and unblock "
            "callbacks sleep on the wall clock, so a callback already running completes its bounded world edits "
            "during the pause; the latch refuses this driver's own publications until the reset",
            "a live world can be unpaused or stepped by the Gazebo GUI that world.launch opens, by a WorldControl "
            "message or by any ROS client; MHS does not watch the flag after the e-stop",
            "the pause runs on the gazebo_ros callback queue one request at a time, so a delete still waiting for "
            "its world edit delays it; the e-stop then exceeds its 500 ms timeout and stays unconfirmed with the "
            "latch held and a background retry",
            "the read-back needs the ODE engine (empty_world.launch's default): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held; a graph "
            "without gazebo_ros has neither service",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name; rosbridge cannot read their versions",
            "no unpause is offered (SAFE-042): gazebo_ros_planar_move keeps the velocity boxOdomCallback publishes "
            "on /box_cmd_vel (object_spawner_gz_plugin.cpp:372-387 publishes linear.y of plus or minus 2.0; "
            "gazebo_ros_planar_move.cpp:242-249 stores it and 198-208 applies it on the world update). "
            "planar_box.urdf.xacro:36-42 sets no cmdTimeout, and the plugin default cmd_timeout_ is -1 "
            "(gazebo_ros_planar_move.cpp:117), so UpdateChild does not zero the stored velocity. This "
            "package does not publish that topic. spawn_jackal.launch includes jackal_control's control.launch "
            "and teleop.launch (spawn_jackal.launch:23-26), which are not in this clone, so the Jackal "
            "controller's command cannot be cleared here either. After mhs.safety.reset the world stays paused; "
            "the operator deletes planar_box (the remove command still applies while paused) and stops those "
            "Jackal nodes outside MHS, then unpauses with the Gazebo GUI (world.launch:9, gui true) or "
            "rosservice call /gazebo/unpause_physics",
            "the planar_box deletion is one-shot: the clone declares no respawn for it, and the fake answers a "
            "repeat delete of the absent model with success false, as the package expects of gazebo_ros",
            "delete_model accepts any model name, including the Jackal robot that world.launch spawns, and the "
            "world offers no declared way to restore a deleted model",
            "the Jackal robot (jackal_control, outside the clone) is neither served nor stopped by this package",
            "the clone exposes no ROS service or action that pauses or steps Gazebo (the pause is the companion's), "
            "so the primary environment step and the blocking callbacks are out of scope",
        ],
    }

    commands = {
        "x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1": _REMOVE_MOVING_OBSTACLE,
        "x-cap.nus-advanced-robotics-centre.clear_objects.v1": _CLEAR_OBJECTS,
        "x-cap.nus-advanced-robotics-centre.regenerate_objects.v1": _REGENERATE_OBJECTS,
        "x-cap.nus-advanced-robotics-centre.open_exit.v1": _OPEN_EXIT,
        "x-cap.nus-advanced-robotics-centre.delete_model.v1": _DELETE_MODEL,
        "x-cap.nus-advanced-robotics-centre.box_odom.v1": _BOX_ODOM,
        "x-cap.nus-advanced-robotics-centre.box_markers.v1": _BOX_MARKERS,
    }
    actions = {
        "x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1": Action(
            name="remove_moving_obstacle",
            description="Delete the moving planar_box obstacle once with the acknowledged DeleteModel service; "
                        "this is not a stop",
            output=_DELETE_OUTPUT,
        ),
        "x-cap.nus-advanced-robotics-centre.clear_objects.v1": Action(
            name="clear_objects",
            description="Publish Int16 0 on the RViz panel's respawn topic to delete the random objects",
            output=_PUBLISHED,
        ),
        "x-cap.nus-advanced-robotics-centre.regenerate_objects.v1": Action(
            name="regenerate_objects",
            description="Publish Int16 1 on the RViz panel's respawn topic to regenerate the random objects",
            output=_PUBLISHED,
        ),
        "x-cap.nus-advanced-robotics-centre.open_exit.v1": Action(
            name="open_exit",
            description="Publish Bool true on /cmd_unblock to request the one-time exit removal",
            output=_PUBLISHED,
        ),
        "x-cap.nus-advanced-robotics-centre.delete_model.v1": Action(
            name="delete_model",
            description="Delete one named Gazebo model through the acknowledged DeleteModel service",
            input={
                "model_name": Field("string", description="Gazebo model name to delete; the clone "
                                                         "states no name set or length bound"),
            },
            output=_DELETE_OUTPUT,
        ),
        "x-cap.nus-advanced-robotics-centre.box_odom.v1": Action(
            name="read_box_odom",
            description="Read one fresh /box_odom sample published by the object spawner plugin",
            output={"pose": _POSE},
        ),
        "x-cap.nus-advanced-robotics-centre.box_markers.v1": Action(
            name="read_box_markers",
            description="Read one fresh /gazebo/ground_truth/box_markers sample",
            output={"markers": _MARKERS},
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    # No unpause is offered (SAFE-042: the planar_box velocity and the Jackal controller cannot be cleared first).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
