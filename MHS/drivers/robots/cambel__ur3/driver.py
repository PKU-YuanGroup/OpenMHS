"""OpenMHS rosbridge driver for cambel/ur3's ur_gripper_gz Hand-E simulation.

The pinned repository contains both a real-UR path and a gz-sim bringup.  This
package serves only the simulated Hand-E launch ``ur_gz_control.launch.py``
(ROS 2 Jazzy, Gazebo Harmonic).  The hardware path stays on the registry record
and is not served: there is no hardware backend, and the dashboard Trigger is
not a stop.  The driver declares no Python native class and neither imports
nor launches the upstream code.

The one observation is the relative ``joint_states`` subscription in
``JointControllerBase`` (``sensor_msgs/msg/JointState``).  The launch names a
``joint_state_broadcaster`` spawner; the clone does not contain a literal
publisher topic for that controller, so this package does not claim one.  A
silent topic is a timeout.

The trajectory command is not served.  ``JointTrajectoryController`` builds the
topic from the namespace, the publisher name and ``/joint_trajectory``
(``controllers.py:381``).  That assembled string is not a citable endpoint.

The clone's launch bridges ``/clock`` only.  World pause is a Gazebo Transport
operation.  The e-stop is the gz-sim 8.15.0 WorldControl pause on
``/world/empty/control``, bridged by ros_gz 1.0.25 as
``ros_gz_interfaces/srv/ControlWorld``.  The reply is true when gz-sim queues
the request.  The stop is confirmed by a fresh-sample read-back (E2):
``WorldStatistics.paused`` on ``/world/empty/stats`` must be true in two samples
that arrived at least 40 ms apart, after a discarded first one, within 600 ms.
That flag holds only for the sampled window.  Neither endpoint exists unless
the operator runs ``parameter_bridge`` with the two arguments in
``operator_bridges`` (E3).

No unpause is offered (SAFE-042).  The pause retains a trajectory target:
``JointTrajectoryController.stop`` only calls ``cancel_goal_async`` and does
not wait, and ``SetPaused`` stores ``currentInfo.paused`` and does not send
that cancel.  ``UserCommands::PreUpdate`` still executes queued world edits.
A ``multi_step`` control, the GUI or another client can resume the world.
Operator recovery is outside MHS, after that pending motion is cleared.

Every fact cites the pinned clone at 10f96dc362a7700b14e4a2469c8025134ef3e4f7
or a declared companion.  The fake transport is ROS-free and its numbers are
placeholders.
"""

from mhs.driver import Action, Fact, Field, RosDriver

_README = "README.md:6-7"
_README_PHYSICS = "README.md:196-197"
_README_HARDWARE = "README.md:211"
_LICENSE = "LICENSE:1"
_PACKAGE_XML = "ur_gripper_gz/package.xml:14-16"
_PACKAGE_DEPS = "ur_gripper_gz/package.xml:33-34"
_CLOCK_BRIDGE = "ur_gripper_gz/launch/ur_gz_control.launch.py:65-68"
_HAND_E = "ur_gripper_gz/launch/ur_gz_control.launch.py:72-75"
_GZ_ARGS = "ur_gripper_gz/launch/ur_gz_control.launch.py:87-95"
_SPAWN = "ur_gripper_gz/launch/ur_gz_control.launch.py:98-102"
_JSB = "ur_gripper_gz/launch/ur_gz_control.launch.py:106-113"
_JTC = "ur_gripper_gz/launch/ur_gz_control.launch.py:129-136"
_INACTIVE = "ur_gripper_gz/launch/ur_gz_control.launch.py:137-159"
_GRIPPER = "ur_gripper_gz/launch/ur_gz_control.launch.py:161-170"
_UR_TYPE = "ur_gripper_gz/launch/ur_gz_control.launch.py:174-179"
_CHAIN = "ur_gripper_gz/launch/ur_gz_control.launch.py:186-190"
_FTS = "ur_gripper_gz/launch/ur_gz_control.launch.py:124"
_YAML_NAME = "ur_gripper_gz/config/ur_gz_controllers.yaml:4-5"
_YAML_RATE = "ur_gripper_gz/config/ur_gz_controllers.yaml:8-12"
_YAML_JTC = "ur_gripper_gz/config/ur_gz_controllers.yaml:17-18"
_YAML_GRIPPER = "ur_gripper_gz/config/ur_gz_controllers.yaml:29-33"
_YAML_JOINTS = "ur_gripper_gz/config/ur_gz_controllers.yaml:45-55"
_YAML_TOL = "ur_gripper_gz/config/ur_gz_controllers.yaml:60-62"
_CONST_NAMES = "ur_control/ur_control/constants.py:29-32"
_CONST_JOINTS = "ur_control/ur_control/constants.py:38-43"
_CONST_ORDER = "ur_control/ur_control/constants.py:49-52"
_JS_IMPORT = "ur_control/ur_control/controllers.py:21"
_JS_SUB = "ur_control/ur_control/controllers.py:64"
_JS_RETRY = "ur_control/ur_control/controllers.py:66-71"
_TRAJ = "ur_control/ur_control/controllers.py:377-382"
_STOP = "ur_control/ur_control/controllers.py:493-498"
_REAL = "ur_control/ur_control/ur_services.py:16-24"
_REAL_DEFAULT = "ur_control/ur_control/ur_services.py:38"
_DASH_STOP = "ur_control/ur_control/ur_services.py:51"
_UR5E = "ur_gripper_gz/launch/ur_2f85_gz_control.launch.py:71-73"
_UR5E_TYPE = "ur_gripper_gz/launch/ur_2f85_gz_control.launch.py:105"

_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_USER_CMDS = "companion:gz_sim/src/systems/user_commands/UserCommands.cc:669-699"
_PHYSICS = "companion:gz_sim/src/systems/physics/Physics.cc"
_EMPTY = "companion:gz_sim/examples/worlds/empty.sdf"
_SRV = "companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp"
_SERVICE_FACTORY = "companion:ros_gz/ros_gz_bridge/src/service_factory.hpp"
_CONVERT = "companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp"
_BRIDGE_README = "companion:ros_gz/ros_gz_bridge/README.md"
_BRIDGE_CONFIG = "companion:ros_gz/ros_gz_bridge/src/bridge_config.cpp"
_FACTORY = "companion:ros_gz/ros_gz_bridge/src/factory.hpp"
_INTERFACES = "companion:ros_gz/ros_gz_interfaces"
_NODE_HH = "companion:gz_transport/include/gz/transport/Node.hh"

_WORLD = "/world/empty"
_PAUSE = {
    "service": _WORLD + "/control",
    "type": "ros_gz_interfaces/srv/ControlWorld",
    "source_name": "control",
    "source_ref": _RUN + ":325",
    "type_ref": _SRV + ":43-52",
    "state_ref": _RUN + ":1443",
    "description": "Pause world empty (gz-sim WorldControl through ros_gz; SetPaused in the step loop)",
    "request": {"world_control": {"pause": True}},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 400,
}
_READBACK = {
    "topic": _WORLD + "/stats",
    "type": "ros_gz_interfaces/msg/WorldStatistics",
    "operation": "subscribe",
    "source_name": "stats",
    "source_ref": _RUN + ":807-808",
    "type_ref": _BRIDGE_README + ":52",
    "state_ref": _RUN + ":534",
    "description": "Read WorldStatistics.paused from fresh samples; two samples after the request must report paused true",
    "success": {"path": "paused", "equals": True},
    "fresh": {"after_request": True, "discard_first": True, "consecutive": 2, "within_ms": 600,
              "min_interval_ms": 40},
}

_JOINT_STATES = {
    "topic": "/joint_states",
    "type": "sensor_msgs/msg/JointState",
    "operation": "subscribe",
    "source_name": "joint_states",
    "source_ref": _JS_SUB,
    "type_ref": _JS_IMPORT,
    "result": {"map": {"name": "output.name", "position": "output.position", "velocity": "output.velocity"}},
}

_NAMES = Field(
    "array",
    description="JointState.name from one sample; the fake's six names are placeholders",
    items=Field("string", description="One joint name from the sample"),
)
_NUMBERS = Field(
    "array",
    description="One JointState numeric array; this subscription's source states no unit",
    items=Field("number", description="One element; the source states no unit"),
)


class UrGripperGz(RosDriver):
    device_id = "ur-gripper-gz"
    device_kind = "robot.arm"
    mode = "simulated"
    # The served device is a simulated UR arm.  Item 12 would leave a world-pause-only simulator at R0;
    # the user item for this package rates the arm R2, and the card floor is R1, so the driver declares R2.
    # This package publishes no joint command.
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeUrGripperGz"}
    tags = ["ros", "ros2", "simulation", "gazebo", "ur", "arm"]
    display_name = "cambel ur_gripper_gz Hand-E gz-sim bringup"
    vendor = "cambel"
    model = "UR with Robotiq Hand-E in the gz-sim empty world"
    facts = [
        Fact("README.md states ROS 2 Jazzy on Ubuntu 24.04 with Gazebo Harmonic (gz-sim 8), and points ROS 1 "
             "Noetic or Melodic with Gazebo Classic at the noetic-devel branch.",
             source="vendor_doc", ref=_README),
        Fact("README.md says mimic joints need bullet-featherstone and that both gripper launches pass "
             "--physics-engine gz-physics-bullet-featherstone-plugin.",
             source="vendor_doc", ref=_README_PHYSICS),
        Fact("README.md says the Robotiq real-hardware driver (robotiq_control / pymodbus) is deferred.",
             source="vendor_doc", ref=_README_HARDWARE),
        Fact("LICENSE line 1 is The MIT License (MIT).", source="vendor_doc", ref=_LICENSE),
        Fact("ur_gripper_gz/package.xml declares license BSD and build tool ament_cmake.",
             source="upstream_code", ref=_PACKAGE_XML),
        Fact("ur_gripper_gz/package.xml depends on ros_gz_bridge and ros_gz_sim.",
             source="upstream_code", ref=_PACKAGE_DEPS),
        Fact("ur_gz_control.launch.py starts a ros_gz_bridge parameter_bridge with the argument "
             "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock.",
             source="upstream_code", ref=_CLOCK_BRIDGE),
        Fact("ur_gz_control.launch.py starts ur_control's active_gripper_publisher with gripper robotiq_hande.",
             source="upstream_code", ref=_HAND_E),
        Fact("ur_gz_control.launch.py builds gz_args containing empty.sdf, -r and "
             "gz-physics-bullet-featherstone-plugin, and includes ros_gz_sim's gz_sim.launch.py.",
             source="upstream_code", ref=_GZ_ARGS),
        Fact("ur_gz_control.launch.py spawns the model with -name set to the ur_type launch argument.",
             source="upstream_code", ref=_SPAWN),
        Fact("ur_gz_control.launch.py starts a controller_manager spawner named joint_state_broadcaster.",
             source="upstream_code", ref=_JSB),
        Fact("ur_gz_control.launch.py starts a controller_manager spawner named scaled_joint_trajectory_controller.",
             source="upstream_code", ref=_JTC),
        Fact("ur_gz_control.launch.py spawns forward_velocity_controller and cartesian_compliance_controller "
             "with --inactive.",
             source="upstream_code", ref=_INACTIVE),
        Fact("ur_gz_control.launch.py spawns gripper_controller when load_gripper is true.",
             source="upstream_code", ref=_GRIPPER),
        Fact("ur_gz_control.launch.py defaults ur_type to ur3e, describes that argument as including ur3, and "
             "defaults load_gripper to true.",
             source="upstream_code", ref=_UR_TYPE),
        Fact("ur_gz_control.launch.py registers OnProcessExit so spawn_entity's exit starts jsb_spawner, "
             "jsb_spawner's exit starts fts_spawner and jtc_spawner, and jtc_spawner's exit starts fvc_spawner, "
             "compliance_spawner and gripper_spawner.",
             source="upstream_code", ref=_CHAIN),
        Fact("force_torque_sensor_broadcaster is passed with -c and /controller_manager.",
             source="upstream_code", ref=_FTS),
        Fact("ur_gz_controllers.yaml says the trajectory controller is named scaled_joint_trajectory_controller so "
             "ur_control's Arm drives the simulated robot unchanged.",
             source="upstream_code", ref=_YAML_NAME),
        Fact("ur_gz_controllers.yaml sets controller_manager update_rate 500 and use_sim_time true, and sets "
             "joint_state_broadcaster's type to joint_state_broadcaster/JointStateBroadcaster.",
             source="upstream_code", ref=_YAML_RATE),
        Fact("ur_gz_controllers.yaml sets scaled_joint_trajectory_controller's type to "
             "joint_trajectory_controller/JointTrajectoryController.",
             source="upstream_code", ref=_YAML_JTC),
        Fact("ur_gz_controllers.yaml sets gripper_controller's type to "
             "joint_trajectory_controller/JointTrajectoryController.",
             source="upstream_code", ref=_YAML_GRIPPER),
        Fact("ur_gz_controllers.yaml lists shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, "
             "wrist_2_joint and wrist_3_joint for scaled_joint_trajectory_controller, with command interface position.",
             source="upstream_code", ref=_YAML_JOINTS),
        Fact("ur_gz_controllers.yaml sets stopped_velocity_tolerance 0.05 and goal_time 0.6 on "
             "scaled_joint_trajectory_controller.",
             source="upstream_code", ref=_YAML_TOL),
        Fact("constants.py sets JOINT_POSITION_TRAJECTORY_CONTROLLER and JOINT_VELOCITY_TRAJECTORY_CONTROLLER to "
             "scaled_joint_trajectory_controller and JOINT_STATE_SUBSCRIBER to joint_states.",
             source="upstream_code", ref=_CONST_NAMES),
        Fact("constants.py names shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint "
             "and wrist_3_joint.",
             source="upstream_code", ref=_CONST_JOINTS),
        Fact("constants.py sets JOINT_ORDER to those six joint names.",
             source="upstream_code", ref=_CONST_ORDER),
        Fact("controllers.py imports JointState from sensor_msgs.msg.",
             source="upstream_code", ref=_JS_IMPORT),
        Fact("JointControllerBase creates a JointState subscription on the relative name joint_states with "
             "qos_profile_sensor_data.",
             source="upstream_code", ref=_JS_SUB),
        Fact("If that subscription waits past the timeout, JointControllerBase subscribes again to a topic built as "
             "the namespace plus joint_states.",
             source="upstream_code", ref=_JS_RETRY),
        Fact("JointTrajectoryController defaults publisher_name to scaled_joint_trajectory_controller and builds the "
             "command topic as the namespace plus that name plus /joint_trajectory.",
             source="upstream_code", ref=_TRAJ),
        Fact("JointTrajectoryController.stop calls cancel_goal_async on the goal handle when one exists.",
             source="upstream_code", ref=_STOP),
        Fact("check_for_real_robot returns True without calling the wrapped function when use_real_robot is false.",
             source="upstream_code", ref=_REAL),
        Fact("URServices sets use_real_robot from the parameter use_real_robot with default False.",
             source="upstream_code", ref=_REAL_DEFAULT),
        Fact("URServices creates a std_srvs.srv.Trigger client named stop on the namespace plus "
             "ur_hardware_interface/dashboard/stop.",
             source="upstream_code", ref=_DASH_STOP),
        Fact("ur_2f85_gz_control.launch.py also builds gz_args containing empty.sdf and -r.",
             source="upstream_code", ref=_UR5E),
        Fact("ur_2f85_gz_control.launch.py defaults ur_type to ur5e.",
             source="upstream_code", ref=_UR5E_TYPE),
        Fact("SimulationRunner composes its transport namespace as /world/ followed by the world name.",
             source="upstream_code", ref=_RUN + ":249"),
        Fact("SimulationRunner advertises the control service with OnWorldControl as its callback.",
             source="upstream_code", ref=_RUN + ":325"),
        Fact("OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState.",
             source="upstream_code", ref=_RUN + ":1321-1328"),
        Fact("OnWorldControlState appends the control to worldControls and sets the Boolean reply data to true.",
             source="upstream_code", ref=_RUN + ":1375-1377"),
        Fact("ProcessWorldControl calls SetPaused with the pause flag of each queued control.",
             source="upstream_code", ref=_RUN + ":1440-1443"),
        Fact("A queued control with multi_step greater than zero while paused adds the steps and calls SetPaused false.",
             source="upstream_code", ref=_RUN + ":1445-1452"),
        Fact("SetPaused stores the pause state in currentInfo.paused.",
             source="upstream_code", ref=_RUN + ":1290-1291"),
        Fact("UpdateSystems calls PreUpdate on each system from SystemsPreUpdate.",
             source="upstream_code", ref=_RUN + ":662-684"),
        Fact("UserCommands::PreUpdate takes an unused UpdateInfo, copies pendingCmds and calls Execute on each "
             "command.",
             source="upstream_code", ref=_USER_CMDS),
        Fact("Step calls PublishStats.", source="upstream_code", ref=_RUN + ":1023-1024"),
        Fact("Step calls ProcessMessages.", source="upstream_code", ref=_RUN + ":1063-1064"),
        Fact("While paused the Run loop does not count a processed iteration; without a network manager it calls Step.",
             source="upstream_code", ref=_RUN + ":896-911"),
        Fact("The statistics publisher comment says the GUI listens to these messages for confirmation that pause and "
             "play GUI requests were processed.",
             source="upstream_code", ref=_RUN + ":800-805"),
        Fact("The statistics publisher on the stats topic is limited to 10 messages per second.",
             source="upstream_code", ref=_RUN + ":806-808"),
        Fact("PublishStats copies currentInfo.paused into the WorldStatistics message.",
             source="upstream_code", ref=_RUN + ":534"),
        Fact("UpdateCurrentInfo advances simTime and the iteration count only in the branch that requires the world "
             "not paused.",
             source="upstream_code", ref=_RUN + ":423-429"),
        Fact("The Physics system steps the physics only when not paused.",
             source="upstream_code", ref=_PHYSICS + ":1047-1051"),
        Fact("examples/worlds/empty.sdf names its world empty.",
             source="upstream_code", ref=_EMPTY + ":63"),
        Fact("examples/worlds/empty.sdf loads gz-sim-physics-system, gz-sim-user-commands-system, "
             "gz-sim-scene-broadcaster-system and gz-sim-contact-system.",
             source="upstream_code", ref=_EMPTY + ":68-83"),
        Fact("examples/worlds/empty.sdf then declares a directional light named sun and a model named ground_plane.",
             source="upstream_code", ref=_EMPTY + ":85-99"),
        Fact("The bridge maps ros_gz_interfaces/srv/ControlWorld to a gz.msgs.WorldControl request with a "
             "gz.msgs.Boolean reply.",
             source="upstream_code", ref=_SRV + ":43-52"),
        Fact("The ControlWorld response's success is the gz Boolean reply's data.",
             source="upstream_code", ref=_SRV + ":134-141"),
        Fact("For a failed gz request the ControlWorld response's success is false.",
             source="upstream_code", ref=_SRV + ":170-178"),
        Fact("The service bridge converts each ROS request and sends it with gz Request and a callback that sends "
             "the ROS response.",
             source="upstream_code", ref=_SERVICE_FACTORY + ":56-86"),
        Fact("Node::Request with a callback requests a service using a non-blocking call.",
             source="upstream_code", ref=_NODE_HH + ":662-677"),
        Fact("The WorldStatistics conversion copies the gz header, sim_time, pause_time, real_time and paused into "
             "the ROS message.",
             source="upstream_code", ref=_CONVERT + ":840-844"),
        Fact("ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag.",
             source="upstream_code", ref=_INTERFACES + "/msg/WorldStatistics.msg:1-14"),
        Fact("ControlWorld takes a WorldControl request and answers bool success.",
             source="upstream_code", ref=_INTERFACES + "/srv/ControlWorld.srv:1-3"),
        Fact("WorldControl's fields include pause, step and multi_step.",
             source="upstream_code", ref=_INTERFACES + "/msg/WorldControl.msg:1-3"),
        Fact("The bridge README maps ros_gz_interfaces/msg/WorldStatistics to gz.msgs.WorldStatistics.",
             source="vendor_doc", ref=_BRIDGE_README + ":52"),
        Fact("The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to gz.msgs.WorldControl and "
             "gz.msgs.Boolean.",
             source="vendor_doc", ref=_BRIDGE_README + ":86"),
        Fact("The bridge README's service example starts parameter_bridge with "
             "/world/shapes/control@ros_gz_interfaces/srv/ControlWorld.",
             source="vendor_doc", ref=_BRIDGE_README + ":261-265"),
        Fact("Without a configured QoS profile the bridge's publisher QoS is KeepLast with the publisher queue size.",
             source="upstream_code", ref=_BRIDGE_CONFIG + ":274-279"),
        Fact("The bridge's publisher allows its deadline, depth, durability, history, liveliness and reliability QoS "
             "to be overridden.",
             source="upstream_code", ref=_FACTORY + ":61-82"),
        Fact("The gz-sim 8 CMake project is gz-sim8 version 8.15.0.",
             source="upstream_code", ref="companion:gz_sim/CMakeLists.txt:6"),
        Fact("The gz-sim changelog heading is Gazebo Sim 8.15.0 (2026-08-11).",
             source="upstream_code", ref="companion:gz_sim/Changelog.md:3"),
        Fact("The gz-sim CMake file finds gz-transport13.",
             source="upstream_code", ref="companion:gz_sim/CMakeLists.txt:87"),
        Fact("ros_gz_bridge package.xml declares version 1.0.25.",
             source="upstream_code", ref="companion:ros_gz/ros_gz_bridge/package.xml:5"),
        Fact("ros_gz_bridge CHANGELOG.rst records 1.0.25 (2026-10-13).",
             source="upstream_code", ref="companion:ros_gz/ros_gz_bridge/CHANGELOG.rst:5"),
        Fact("ros_gz_sim package.xml depends on gz_sim_vendor.",
             source="upstream_code", ref="companion:ros_gz/ros_gz_sim/package.xml:32"),
        Fact("The gz-transport 13 CMake project is gz-transport13 version 13.6.0.",
             source="upstream_code", ref="companion:gz_transport/CMakeLists.txt:6"),
        Fact("The gz-transport changelog heading is Gazebo Transport 13.6.0 (2026-08-15).",
             source="upstream_code", ref="companion:gz_transport/Changelog.md:3"),
    ]
    safe_state = (
        "World empty reports paused true only inside the confirmation window of two fresh stats samples 40 ms apart "
        "within 600 ms after the WorldControl pause; it is the paused flag, not a measured standstill, and it needs "
        "the operator bridges; the pause retains trajectory targets; UserCommands executes queued world edits; a "
        "multi_step control, the GUI or another client can resume the world; this package offers no unpause; "
        "recovery outside MHS follows after pending motion is cleared."
    )
    fidelity = {
        "engine": "canned:ROS fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step or state-hash replay; world statistics follow "
                     "the wall clock",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free canned transport: it answers /joint_states and the world-control service and "
            "publishes /world/empty/stats while subscribed, and it runs no gz-sim, ros_gz bridge, controller_manager "
            "or ROS graph",
            "joint name, position and velocity samples are placeholders, including the six JOINT_ORDER strings; the "
            "clone states no unit on the joint_states subscription, and the schema fixes neither a length nor a unit",
            "the clone does not show a publisher of /joint_states: the launch starts a spawner named "
            "joint_state_broadcaster (ur_gz_control.launch.py:106-113) and the yaml sets that controller's type "
            "(ur_gz_controllers.yaml:11-12), and neither line is a topic literal; a withheld sample is a timeout, "
            "and this package does not claim that joint_states goes silent while the world is paused",
            "JointControllerBase retries with a topic built from the namespace (controllers.py:71); this package "
            "serves the relative name on line 64, resolved as /joint_states, and a namespaced deployment that never "
            "publishes that name times out",
            "the trajectory endpoint is assembled (controllers.py:381) and is not published; the launch still starts "
            "scaled_joint_trajectory_controller (ur_gz_control.launch.py:129-136), whose yaml name is the one "
            "ur_control's Arm uses (ur_gz_controllers.yaml:4-5)",
            "the stop reply is true when the control is queued (SimulationRunner.cc:1375-1377); ControlWorld.srv:3 "
            "comments that success means the control was successful, and that comment is the ROS reply text; "
            "confirmation is the E2 paused flag, not the reply",
            "Step calls PublishStats (SimulationRunner.cc:1023-1024) before ProcessMessages (:1063-1064), so the "
            "sample that applies a queued pause still reports the previous flag; the read-back discards the first "
            "sample; the fake uses the same order and a placeholder 100 ms statistics period",
            "the e-stop endpoints exist only while the operator runs ros_gz parameter_bridge with the two arguments "
            "of operator_bridges; the served launch's only parameter_bridge argument is the clock "
            "(ur_gz_control.launch.py:65-68), which this package does not subscribe to; estop_latency_ms 1500 covers "
            "the control call (400 ms) and the read-back bound (600 ms)",
            "freshness is arrival time; the bridged header is the gz header (ros_gz_interfaces.cpp:840); without a "
            "QoS profile the publisher QoS is KeepLast (bridge_config.cpp:274-279), so durability stays the default "
            "volatile and a late subscriber sees no history; the first sample is discarded and a burst restarts the "
            "count; an operator QoS override (factory.hpp:61-82) is not covered beyond that rule",
            "the endpoints use world name empty from the companion empty.sdf (examples/worlds/empty.sdf:63) that the "
            "launch names as a file (ur_gz_control.launch.py:87-89); a different world name means the declared "
            "endpoints do not exist and the e-stop fails closed",
            "the served launch is ur_gz_control.launch.py only; ur_2f85_gz_control.launch.py also passes empty.sdf "
            "and defaults ur_type to ur5e (line 105) and is not served; ur_gz_control defaults ur_type to ur3e "
            "(line 174), and ur3 is an argument; the spawn name is ur_type (line 102) and the world name stays empty",
            "the paused flag holds only for the confirmation window of two fresh samples at least 40 ms apart within "
            "600 ms; it is not a lasting measured standstill",
            "empty.sdf's plugin block is physics, user-commands, scene-broadcaster and contact (lines 68-83), then "
            "the sun light (line 85) and ground_plane (line 99); this package cites no WorldControl GUI plugin in "
            "that file; the GUI note is the statistics-publisher comment (SimulationRunner.cc:800-805)",
            "UserCommands::PreUpdate takes an unused UpdateInfo, copies pendingCmds and calls Execute on each "
            "command (UserCommands.cc:669-699); UpdateSystems calls PreUpdate (SimulationRunner.cc:662-684) from "
            "Step, which the paused Run loop still calls (:896-911), so a queued world edit is still executed while "
            "the world is paused",
            "a queued control with multi_step greater than zero while paused calls SetPaused false "
            "(SimulationRunner.cc:1445-1452); the GUI play path and another client's pause-false ControlWorld resume "
            "the world outside this package",
            "no unpause is offered: the pause retains trajectory targets, because JointTrajectoryController.stop "
            "only calls cancel_goal_async and does not wait (controllers.py:493-498), and SetPaused stores "
            "currentInfo.paused (SimulationRunner.cc:1290-1291) and does not send that cancel, so this package "
            "cannot show that an unpause clears a trajectory the launch's controller accepted; mhs.safety.reset "
            "releases the MHS latch and the world stays paused; operator recovery outside MHS, after that pending "
            "motion is cleared, is to use the GUI play control or a pause-false ControlWorld outside MHS",
            "while the e-stop latch is held, mhs.command of x-cap.cambel.joint-states.v1 is refused with "
            "MHS.SAFETY.ESTOP_ENGAGED, because an extension id is not treated as a read; mhs.safety.reset releases "
            "that refusal and leaves the world paused",
            "a hardware path exists and is not served: check_for_real_robot skips the wrapped call when use_real_robot "
            "is false (ur_services.py:16-24), the parameter defaults false (line 38), the dashboard stop client is a "
            "Trigger (line 51), and README.md:211 defers the Robotiq real-hardware driver; the noetic-devel branch "
            "(README.md:6-7) is not served; there is no hardware backend",
            "the deployment's gz-sim, ros_gz and gz-transport must be the pinned 8.15.0, 1.0.25 and 13.6.0; "
            "LICENSE:1 is the MIT License and ur_gripper_gz/package.xml:14 says BSD; publish_review stays not_required",
        ],
    }
    estop_latency_ms = 1500
    commands = {"x-cap.cambel.joint-states.v1": _JOINT_STATES}
    actions = {
        "x-cap.cambel.joint-states.v1": Action(
            name="read_joint_states",
            verb="read",
            description="Read one sensor_msgs/JointState sample from the relative joint_states subscription",
            output={"name": _NAMES, "position": _NUMBERS, "velocity": _NUMBERS},
        ),
    }
    operator_bridges = [
        {"args": "/world/empty/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE_README + ":86",
         "description": "The world control service: the e-stop pause."},
        {"args": "/world/empty/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
         "ref": _BRIDGE_README + ":52",
         "description": "The world statistics, whose paused flag confirms the e-stop."},
    ]
    safety_bindings = {"estop": _PAUSE, "safe_state": _READBACK}
