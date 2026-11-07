"""OpenMHS rosbridge driver for the Care-O-bot Gazebo simulation assets.

The pinned repository is a ROS 1 simulation environment: it ships Gazebo
worlds, object models and launch files, and its ``cob_gazebo_tools`` scripts
manipulate the running Gazebo world through the standard ``gazebo_ros``
services and topics.  This package is a configuration-only
:class:`RosDriver`; it declares no Python native class, does not launch
Gazebo and does not import the upstream scripts.  The operator runs the
upstream launch files and rosbridge separately.

The selected runtime surface is the one the pinned object tools actually use:

* ``/gazebo/get_world_properties`` (``gazebo_msgs/GetWorldProperties``) is the
  model-name observation, read from ``spawn_object.py``;
* ``/gazebo/get_model_state`` (``gazebo_msgs/GetModelState``) is the fixed
  pose observation for the model the robot launch spawns as ``robot``;
* ``/gazebo/delete_model`` (``gazebo_msgs/DeleteModel``) is the acknowledged
  model-removal service;
* ``/gazebo/set_model_state`` (``gazebo_msgs/ModelState``) is the publication
  the move tool uses.  A publication is transmission evidence only.

The spawn endpoint in ``spawn_object.py`` is assembled at runtime from the
model type (``'/gazebo/spawn_' + model_type + '_model'``), so the clone has
no fixed spawn endpoint literal to cite; the package deliberately does not
declare a spawn command.  The clone declares no pause, reset or stop service.

The e-stop is the Gazebo world pause of the simulator's own repository, cited
as a reviewed companion source (user decision of 2026-11-05; ``task.json``
``companions``): gazebo_ros 2.9.3 (ROS 1 Noetic) ``/gazebo/pause_physics``,
confirmed by reading ``/gazebo/get_physics_properties`` back until ``pause`` is
true.  The pause stops every model and controller update, the robot's
included; it is the paused flag, not a measured standstill.  The package's own
commands are discrete world edits that still act on a paused world (the latch
refuses them from this driver until the reset), and any client or the Gazebo
GUI can unpause, step or edit the world.  The clone's CI builds for ROS
Noetic; the package serves that profile only.

No unpause is offered (the orchestrator's SAFE-042 condition, the same rule as
the seven lock-companion Gazebo packages).  This package publishes no
controller command.  ``robot.launch`` includes ``cob_bringup``, which is not in
this clone (``cob_gazebo/package.xml:18``, ``robot.launch:12``), and the
component test addresses ``JointTrajectory`` topics
``/<component>_controller/command`` (``component_test.py:78-81``).  The world
launches spawn controllers this package does not command: position controllers
in ``ipa-apartment.xml:13-14`` and velocity controllers in ``ipa-kitchen.xml:14``
and ``automotive-assembly-line.xml:15``.  ``elevator.py:64-66`` publishes
``Float64`` 0, the close position, after the open position 0.87 (lines 51-55).
That close publish moves the door.
After ``mhs.safety.reset`` the world stays paused.  The operator
stops those controller nodes outside MHS, then unpauses with the Gazebo GUI
(``world.launch:14`` defaults ``gui`` to true) or ``rosservice call
/gazebo/unpause_physics``.  The earlier re-enable ``x-cap.ipa320.resume.v1``
was removed for that reason.

Every endpoint, type and fact of the package's own surface cites the pinned
clone at 907144342c0351c9427ddd960ef4dfe013847113; the stop, its read-back and
the facts about them cite the companions at their pins.  The fake transport is
ROS-free and every invented state value is a placeholder.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: spawn_object.py imports GetWorldProperties and queries the absolute service.
_WORLD_PROPERTIES_REF = "cob_gazebo_tools/scripts/spawn_object.py:123-128"
_WORLD_NAMES_REF = "cob_gazebo_tools/scripts/spawn_object.py:135-138"
_WORLD_PROPERTIES_TYPE_REF = "cob_gazebo_tools/scripts/spawn_object.py:26"

#: move_object.py imports the state types and creates the service proxies and
#: the ModelState publisher on the same absolute endpoint.
_GET_STATE_REF = "cob_gazebo_tools/scripts/move_object.py:50-51"
_GET_MODEL_STATE_TYPE_REF = "cob_gazebo_tools/scripts/move_object.py:30"
_SET_STATE_PUBLISH_REF = "cob_gazebo_tools/scripts/move_object.py:54"
_MODEL_STATE_TYPE_REF = "cob_gazebo_tools/scripts/move_object.py:32"
_GET_STATE_REQUEST_REF = "cob_gazebo_tools/scripts/move_object.py:78-86"
_GET_STATE_SUCCESS_REF = "cob_gazebo_tools/scripts/move_object.py:61-65"
_STATE_MESSAGE_REF = "cob_gazebo_tools/scripts/move_object.py:127-143"
_REFERENCE_FRAME_REF = "cob_gazebo_tools/scripts/move_object.py:140"
_CARTESIAN_UNIT_REF = "cob_gazebo_tools/scripts/move_object.py:280-290"
_MOVE_PROXIES_REF = "cob_gazebo_tools/scripts/move_object.py:50-54"

#: remove_object.py imports DeleteModel and waits for the absolute service.
_DELETE_REF = "cob_gazebo_tools/scripts/remove_object.py:118-124"
_DELETE_TYPE_REF = "cob_gazebo_tools/scripts/remove_object.py:23"

#: The robot launch spawns the Gazebo model with the fixed name "robot".
_ROBOT_MODEL_REF = "cob_gazebo/launch/robot.launch:17"

#: The metapackage description names the stack as Care-O-bot simulation
#: packages and its dependencies are the world, object and tool packages.
_METAPACKAGE_REF = "cob_simulation/package.xml:3-4"
_METAPACKAGE_DEPS_REF = "cob_simulation/package.xml:13-18"

#: The world launch starts gazebo_ros empty_world.launch with the paused and
#: use_sim_time arguments; it does not expose a runtime pause service here.
_WORLD_LAUNCH_REF = "cob_gazebo_worlds/launch/world.launch:26-34"

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
#: What the package's own commands do to a paused world (companion gazebo_ros).
_COB_COMPANION_FACTS = [
    Fact("The API plugin advertises the set_model_state service on gazebo_queue_, the queue the pause uses.",
         source="upstream_code", ref=_API + ":439-445"),
    Fact("The API plugin subscribes to the set_model_state topic on gazebo_queue_ with updateModelState as the "
         "callback.", source="upstream_code", ref=_API + ":483-489"),
    Fact("updateModelState passes the received ModelState to setModelState.", source="upstream_code",
         ref=_API + ":1663-1669"),
    Fact("setModelState records whether the world is paused, pauses it, sets the model pose, then restores the "
         "recorded paused state.", source="upstream_code", ref=_API + ":1642-1645"),
    Fact("deleteModel publishes an entity_delete request, then loops, sleeping 1 ms per round, until the model is "
         "gone or ROS time passes its 60 s timeout.", source="upstream_code", ref=_API + ":851-878"),
]

_POSITION = Field(
    "object",
    description="Pose position in the Gazebo world frame",
    properties={
        "x": Field("number", unit="m", description="Position x in the Gazebo world frame"),
        "y": Field("number", unit="m", description="Position y in the Gazebo world frame"),
        "z": Field("number", unit="m", description="Position z in the Gazebo world frame"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Pose orientation as a quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_WORLD_NAMES = Field(
    "array",
    items=Field("string", description="One model name reported by Gazebo"),
    description="Model names returned by /gazebo/get_world_properties",
)

_ROBOT_POSE = Field(
    "object",
    description="Pose of the model named robot in the Gazebo world frame",
    properties={"position": _POSITION, "orientation": _ORIENTATION},
)

_DELETE_OUTPUT = {
    "success": Field("boolean", description="The DeleteModel response success flag"),
    "status_message": Field("string", description="The DeleteModel response status text"),
}

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the ModelState publication"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}


class CobSimulation(RosDriver):
    device_id = "cob-simulation"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeCobSimulation"}
    tags = ["ros", "ros1", "gazebo", "simulation", "care-o-bot", "world", "models"]
    display_name = "Care-O-bot Gazebo simulation scene"
    vendor = "Fraunhofer IPA"
    facts = [
        Fact("The cob_simulation metapackage describes itself as packages to work with the Care-O-bot "
             "within simulation environments such as Gazebo.",
             source="upstream_code", ref=_METAPACKAGE_REF),
        Fact("The cob_simulation metapackage depends on cob_bringup_sim, cob_gazebo, cob_gazebo_objects, "
             "cob_gazebo_tools and cob_gazebo_worlds.",
             source="upstream_code", ref=_METAPACKAGE_DEPS_REF),
        Fact("The world launch includes gazebo_ros/empty_world.launch with the world_name, paused, "
             "use_sim_time and gui arguments.",
             source="upstream_code", ref=_WORLD_LAUNCH_REF),
        Fact("The robot launch runs the gazebo_ros spawn_model node with -urdf -param robot_description "
             "and -model robot.",
             source="upstream_code", ref=_ROBOT_MODEL_REF),
        Fact("spawn_object.py waits for /gazebo/get_world_properties and creates a GetWorldProperties "
             "ServiceProxy on that absolute name.",
             source="upstream_code", ref=_WORLD_PROPERTIES_REF),
        Fact("spawn_object.py reads world_properties.model_names only when world_properties.success is "
             "true, and otherwise uses an empty model list.",
             source="upstream_code", ref=_WORLD_NAMES_REF),
        Fact("move_object.py creates a GetModelState ServiceProxy on /gazebo/get_model_state and a "
             "SetModelState ServiceProxy and ModelState publisher on /gazebo/set_model_state.",
             source="upstream_code", ref=_MOVE_PROXIES_REF),
        Fact("move_object.py's get_model_state sends a request with only model_name set and returns the "
             "GetModelState response.",
             source="upstream_code", ref=_GET_STATE_REQUEST_REF),
        Fact("move_object.py's start-up loop calls get_model_state for its model and keeps waiting while the "
             "response's success is false.",
             source="upstream_code", ref=_GET_STATE_SUCCESS_REF),
        Fact("move_object.py builds a ModelState with model_name, a Pose whose position is x/y and whose "
             "orientation is a yaw quaternion, and reference_frame 'world', then publishes it.",
             source="upstream_code", ref=_STATE_MESSAGE_REF),
        Fact("move_object.py sets reference_frame to 'world' for its ModelState messages.",
             source="upstream_code", ref=_REFERENCE_FRAME_REF),
        Fact("move_object.py documents polygon points as forming a polygon in [m] and the initialpose "
             "argument as a Cartesian Pose.",
             source="upstream_code", ref=_CARTESIAN_UNIT_REF),
        Fact("remove_object.py creates a gazebo/delete_model ServiceProxy, waits for the absolute "
             "/gazebo/delete_model service, and calls it with the model name.",
             source="upstream_code", ref=_DELETE_REF),
        Fact("spawn_object.py assembles its spawn endpoint at runtime as '/gazebo/spawn_' + model_type + "
             "'_model'; the clone has no fixed spawn endpoint literal.",
             source="upstream_code", ref="cob_gazebo_tools/scripts/spawn_object.py:205-211"),
        Fact("The clone's CI workflow builds for the single ROS distro noetic.", source="upstream_code",
             ref=".github/workflows/main.yml:26-29"),
        *_COMPANION_FACTS,
        *_COB_COMPANION_FACTS,
    ]
    safe_state = (
        "The Gazebo world is paused and get_physics_properties read pause true back; the paused flag, not a measured "
        "standstill. No unpause is offered: controllers this package does not command keep their last command "
        "(robot.launch:12, ipa-apartment.xml:13-14). The Gazebo GUI or another client can unpause or step the world "
        "(a step advances it). World edits still act while paused. After mhs.safety.reset the world stays paused; "
        "the operator stops those nodes, then unpauses outside MHS (world.launch:14)."
    )
    parameters = {"model_names": _WORLD_NAMES, "robot_pose": _ROBOT_POSE}
    reads = {
        "model_names": {
            "service": "/gazebo/get_world_properties",
            "type": "gazebo_msgs/GetWorldProperties",
            "request": {},
            "path": "model_names",
            # spawn_object.py uses model_names only when success is true (135-138).
            "success": {"path": "success", "equals": True},
            "source_ref": _WORLD_PROPERTIES_REF,
            "type_ref": _WORLD_PROPERTIES_TYPE_REF,
            "timeout_ms": 2000,
        },
        "robot_pose": {
            "service": "/gazebo/get_model_state",
            "type": "gazebo_msgs/GetModelState",
            "request": {"model_name": "robot"},
            "path": "pose",
            # move_object.py keeps waiting while the response's success is false
            # (61-65); a refused read is never returned as a default pose.
            "success": {"path": "success", "equals": True},
            "source_ref": _GET_STATE_REF,
            "type_ref": _GET_MODEL_STATE_TYPE_REF,
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.ipa320.delete_model.v1": {
            "service": "/gazebo/delete_model",
            "type": "gazebo_msgs/DeleteModel",
            "args": {"model_name": {"from": "input.model_name"}},
            "success": {"path": "success", "equals": True},
            "result": {"map": {"success": "success", "status_message": "status_message"}},
            "source_ref": _DELETE_REF,
            "type_ref": _DELETE_TYPE_REF,
        },
        "x-cap.ipa320.set_model_state.v1": {
            "topic": "/gazebo/set_model_state",
            "type": "gazebo_msgs/ModelState",
            "operation": "publish",
            "args": {
                "model_name": {"from": "input.model_name"},
                "pose.position.x": {"from": "input.position_x"},
                "pose.position.y": {"from": "input.position_y"},
                "pose.position.z": {"from": "input.position_z"},
                "pose.orientation.x": {"from": "input.orientation_x"},
                "pose.orientation.y": {"from": "input.orientation_y"},
                "pose.orientation.z": {"from": "input.orientation_z"},
                "pose.orientation.w": {"from": "input.orientation_w"},
            },
            "message": {
                "model_name": "",
                "pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "twist": {
                    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
                "reference_frame": "world",
            },
            "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
            "source_ref": _SET_STATE_PUBLISH_REF,
            "type_ref": _MODEL_STATE_TYPE_REF,
        },
    }
    actions = {
        "x-cap.ipa320.delete_model.v1": Action(
            name="delete_model",
            verb="invoke",
            description=(
                "Call the acknowledged gazebo_msgs/DeleteModel service to remove one model from the "
                "running Gazebo world; the output is the service's own success and status text"
            ),
            input={
                "model_name": Field("string", description="Gazebo model name to remove"),
            },
            output=_DELETE_OUTPUT,
            examples=[{"model_name": "apple_juice_box"}, {"model_name": "basmati_rice"}],
        ),
        "x-cap.ipa320.set_model_state.v1": Action(
            name="publish_model_state",
            verb="invoke",
            description=(
                "Publish one gazebo_msgs/ModelState on /gazebo/set_model_state with the same fields the "
                "move tool publishes; the receipt confirms rosbridge transmission only, not that Gazebo "
                "moved the model or reached the pose"
            ),
            input={
                "model_name": Field("string", description="Gazebo model name to move"),
                "position_x": Field("number", unit="m", description="Target position x in the Gazebo world frame"),
                "position_y": Field("number", unit="m", description="Target position y in the Gazebo world frame"),
                "position_z": Field("number", unit="m", description="Target position z in the Gazebo world frame"),
                "orientation_x": Field("number", unit="1", description="Target orientation quaternion x"),
                "orientation_y": Field("number", unit="1", description="Target orientation quaternion y"),
                "orientation_z": Field("number", unit="1", description="Target orientation quaternion z"),
                "orientation_w": Field("number", unit="1", description="Target orientation quaternion w"),
            },
            output=_PUBLISHED,
            examples=[
                {"model_name": "robot", "position_x": 1.0, "position_y": 2.0, "position_z": 0.1,
                 "orientation_x": 0.0, "orientation_y": 0.0, "orientation_z": 0.0, "orientation_w": 1.0},
                {"model_name": "robot", "position_x": 2.0, "position_y": 3.0, "position_z": 0.1,
                 "orientation_x": 0.0, "orientation_y": 0.0, "orientation_z": 0.0, "orientation_w": 1.0},
            ],
        ),
    }
    # The e-stop pauses the Gazebo world and reads the paused flag back (companion gazebo_ros); a failed pause or a
    # read-back other than pause true leaves the e-stop unconfirmed with the latch held and a background retry.
    # No reset binding and no re-enable: mhs.safety.reset releases the latch only and the world stays paused.
    # No unpause is offered (SAFE-042: the controllers this package does not command cannot be cleared first).
    # The two service reads keep answering while the world is paused (they run on the plugin's own queue).
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with no physics step, collision or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared get_world_properties, "
            "get_model_state, delete_model and set_model_state endpoints and runs no Gazebo physics, "
            "controllers, sensors or object dynamics",
            "the model list and robot pose in the fake are placeholders; a live run must receive them "
            "from the operator's Gazebo instance",
            "the /gazebo/* service and topic implementations are in gazebo_ros, outside the pinned clone; "
            "the clone proves the client endpoint names and types; only the stop, its read-back and the facts "
            "cite gazebo_ros itself (the companion source)",
            "spawn_object.py's spawn service is assembled at runtime from the model type, so no fixed "
            "spawn endpoint is declared or exercised; model spawning is NOT COVERED",
            "the fake answers a delete of an absent model with success, while gazebo_ros 2.9.3 answers success "
            "false with 'DeleteModel: model does not exist' (companion api plugin 824-830), so a live delete of an "
            "absent model is a failed receipt",
            "the stop is the companion gazebo_ros world pause (the pinned clone declares no pause, unpause, reset "
            "or stop service): the fake keeps a paused flag that /gazebo/pause_physics sets and "
            "/gazebo/get_physics_properties reports, and it does not serve /gazebo/unpause_physics; it runs no "
            "Gazebo World::Step, and its GetPhysicsProperties numbers are placeholders",
            "a paused world still applies world edits: set_model_state teleports the model and restores the "
            "recorded paused state, and delete requests are processed on every step; the latch refuses this "
            "driver's edits until the reset, but other clients and the Gazebo GUI can edit, step or unpause the "
            "world at any time, and MHS does not watch the flag after the e-stop",
            "the pause runs on the gazebo_ros callback queue one request at a time (gazeboQueueThread), so a "
            "spawn or delete still waiting for its world edit delays it; the e-stop then exceeds its 500 ms "
            "timeout and stays unconfirmed with the latch held and a background retry",
            "the read-back needs the ODE engine (empty_world.launch's default): with another engine "
            "get_physics_properties returns false and the e-stop stays unconfirmed with the latch held; a graph "
            "without gazebo_ros has neither service",
            "the deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases the companion "
            "citations name, and the clone's README table names only older distros; the CI line (Noetic) is the "
            "profile served, and a Melodic or Kinetic deployment is out of profile",
            "no unpause is offered (SAFE-042): this package publishes no controller command. robot.launch includes "
            "cob_bringup, an exec_depend that is not in this clone (cob_gazebo/package.xml:18, robot.launch:12), "
            "and the component test addresses JointTrajectory topics /<component>_controller/command "
            "(component_test.py:78-81). The world launches spawn controllers this package does not command: "
            "position controllers in ipa-apartment.xml:13-14 and velocity controllers in ipa-kitchen.xml:14 and "
            "automotive-assembly-line.xml:15. elevator.py:64-66 publishes Float64 0, the close position, after "
            "the open position 0.87 (lines 51-55); that close publish moves the door, so it cannot clear a stored command. Those commands "
            "act again when the world runs. After mhs.safety.reset the world "
            "stays paused; the operator stops those controller nodes outside MHS, then unpauses with the Gazebo "
            "GUI (world.launch:14, gui defaults true) or rosservice call /gazebo/unpause_physics",
            "the set_model_state command is a topic publication, so the receipt is transmission evidence "
            "only and does not prove that Gazebo applied the pose",
            "the fixed get_model_state read names the model robot from the robot launch; a deployment "
            "that renames the spawned model must not use that read",
            "both service reads require the response's success flag, so a GetModelState reply for a model "
            "that does not exist is refused instead of being returned as a default zero pose",
        ],
    }
