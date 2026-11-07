"""OpenMHS rosbridge driver for the Gazebo object-state plugins in gh.jerry-liubb/gazebo_grasp.

The pinned repository is a MoveIt/Gazebo grasping demo.  Its own arm and hand
motion is provided by external MoveIt and ros_control nodes; the clone names the
controllers, their action namespace follow_joint_trajectory and the short type
FollowJointTrajectory, but no fully qualified action type, and it declares no
acknowledged ROS stop.  The package therefore serves the source-backed
**object-state observation** surface of the vendored gazebo-pkgs: the
``gazebo_state_plugins/GazeboObjectInfo`` world plugin and the
``gazebo_test_tools`` mock recognizer.  The repository's own README demo
(``demo_gazebo.launch``) loads neither: the plugin exists only when the operator
starts Gazebo with the ``libgazebo_world_plugin_loader.so`` system plugin and
loads ``plugin_loader.launch``'s parameters first.

Scope is the ``object_msgs/ObjectInfo`` service on ``/gazebo_objects/get_info``
and the ``object_msgs/Object`` topic on ``/gazebo_objects``.  The service is the
primary observation because the shipped config sets ``publish_world_objects:
false``; the topic is an explicit observation that stays silent unless the
operator enables the state plugin's publisher or a client registers an object
with the upstream ``FakeObjectRecognizer``'s recognize_object service.  There is
no actuation command, so the runtime's software latch is the whole safety path;
no native stop is claimed.  The reported origin is the world pose of the model's
last collision element (``origin_init`` is never set, GazeboObjectInfo.cpp:189-227).

Model review (2026-11-05): facts narrowed to their lines, the origin fact
corrected, the README demo's missing plugin loader, the topic's publishers and
the vendored licence statements disclosed.

Every endpoint and type cites the pinned clone at
0bd506d52c7e0a1791a0488afab5c31fc34e2347.  The fake is a ROS-free recording
transport; no Gazebo world, plugin, ROS graph or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, RosDriver

#: GazeboObjectInfo is a Gazebo world plugin.
_PLUGIN_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:24"

#: It creates the /gazebo_state_plugins node handle and reads the three
#: object-info parameters.
_NODE_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:32"
_DEFAULTS_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:11-14"
_PARAMS_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:34-44"

#: The publisher is conditional on publish_world_objects; the service is
#: always advertised.
_PUBLISH_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:48-51"
_SERVICE_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:56"
_SERVICE_TYPE_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/include/gazebo_state_plugins/GazeboObjectInfo.h:9"
_TOPIC_TYPE_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/include/gazebo_state_plugins/GazeboObjectInfo.h:8"

#: The service callback and the object constructor.
_CALLBACK_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:59-75"
_BUILD_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:177-250"

#: The shipped configuration chooses absolute names and disables the
#: continuous topic publisher.
_CONFIG_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:4"
_TOPIC_CONFIG_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:8"
_SERVICE_CONFIG_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:12"
_FRAME_CONFIG_REF = "gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:16"

#: The message and service definitions.
_INFO_SRV_REF = "general-message-pkgs-master/object_msgs/srv/ObjectInfo.srv:1-23"
_OBJECT_MSG_REF = "general-message-pkgs-master/object_msgs/msg/Object.msg:1-75"

#: The upstream mock recognizer provides the same /gazebo_objects topic (for
#: objects registered through its recognition service); its launch file loads
#: the state-plugin parameters and starts the mock together.
_RECOGNIZER_REF = "gazebo-pkgs-noetic/gazebo_test_tools/config/FakeObjectRecognizer.yaml:3"
_RECOGNIZER_TOPIC_REF = "gazebo-pkgs-noetic/gazebo_test_tools/config/FakeObjectRecognizer.yaml:5-7"
_LAUNCH_REF = "gazebo-pkgs-noetic/gazebo_test_tools/launch/gazebo_fake_object_recognition.launch:6-14"

#: The arm and hand controllers are external MoveIt/ros_control nodes.  The
#: clone names them with action_ns follow_joint_trajectory and the short type
#: FollowJointTrajectory, but no fully qualified ROS type and no stop, so this
#: package does not bind them.
_CONTROLLER_REF = "lora_moveit_config/config/ros_controllers.yaml:1-2"
_HAND_CONTROLLER_REF = "lora_moveit_config/config/ros_controllers.yaml:41-42"
_SIMPLE_ARM_REF = "lora_moveit_config/config/simple_moveit_controllers.yaml:2-4"
_SIMPLE_HAND_REF = "lora_moveit_config/config/simple_moveit_controllers.yaml:13-15"
_CLIENT_REF = "demo.py:13-14"

#: The world's fixed-step physics is a source fact, not the fake's timing.
_WORLD_REF = "inspire_hand_description/worlds/demo_world.world:72-76"

#: The service request fields: name and get_geometry.  The package fixes
#: get_geometry to false, which the schema says returns only the pose fields.
_OBJECT_INFO = {
    "service": "/gazebo_objects/get_info",
    "type": "object_msgs/ObjectInfo",
    "source_ref": _SERVICE_CONFIG_REF,
    "type_ref": _SERVICE_TYPE_REF,
    "operation": "read",
    "request": {"get_geometry": False},
    "args": {"name": {"from": "input.name"}},
    "success": {"path": "success", "equals": True},
    "result": {
        "map": {
            "success": "success",
            "error_code": "error_code",
            "name": "object.name",
            "frame_id": "object.header.frame_id",
            "x": "object.origin.position.x",
            "y": "object.origin.position.y",
            "z": "object.origin.position.z",
        }
    },
    "timeout_ms": 2000,
}

_OBJECTS = {
    "topic": "/gazebo_objects",
    "type": "object_msgs/Object",
    "source_ref": _TOPIC_CONFIG_REF,
    "type_ref": _TOPIC_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "timeout_ms": 2000,
    "result": {
        "map": {
            "name": "name",
            "frame_id": "header.frame_id",
            "x": "origin.position.x",
            "y": "origin.position.y",
            "z": "origin.position.z",
        }
    },
}

_POSE_FIELDS = {
    "name": Field("string", description="Object/model name reported by Gazebo"),
    "frame_id": Field("string", description="Frame in which the pose is expressed"),
    "x": Field("number", unit="m", description="Object origin x: world pose of the model's last collision"),
    "y": Field("number", unit="m", description="Object origin y: world pose of the model's last collision"),
    "z": Field("number", unit="m", description="Object origin z: world pose of the model's last collision"),
}


class GazeboGraspObjectState(RosDriver):
    device_id = "gazebo-grasp-object-state"
    device_kind = "sensor"
    mode = "simulated"
    risk = "R0"
    ros_version = 1
    backends = {"fake": ".fake:FakeGazeboGrasp"}
    tags = ["ros", "ros1", "gazebo", "simulation", "object-state", "object-info", "grasp"]
    display_name = "Gazebo object state (gazebo_grasp)"
    vendor = "jerry-liubb"
    model = "gazebo_state_plugins/GazeboObjectInfo with gazebo_test_tools"
    facts = [
        Fact("GazeboObjectInfo is a Gazebo world plugin registered with GZ_REGISTER_WORLD_PLUGIN.",
             source="upstream_code", ref=_PLUGIN_REF),
        Fact("GazeboObjectInfo::Load creates a ros::NodeHandle named /gazebo_state_plugins.",
             source="upstream_code", ref=_NODE_REF),
        Fact("The plugin defaults are publish_world_objects false, world_objects_topic world/objects, "
             "request_object_service world/request_object and objects_frame_id world.",
             source="upstream_code", ref=_DEFAULTS_REF),
        Fact("GazeboObjectInfo::Load reads the publish_world_objects, world_objects_topic, "
             "request_object_service and objects_frame_id parameters.",
             source="upstream_code", ref=_PARAMS_REF),
        Fact("GazeboObjectInfo::Load connects the world-update callback and advertises the "
             "WORLD_OBJECTS_TOPIC publisher only when publish_world_objects is true.",
             source="upstream_code", ref=_PUBLISH_REF),
        Fact("GazeboObjectInfo::Load advertises the REQUEST_OBJECTS_TOPIC service with the "
             "GazeboObjectInfo::requestObject callback.",
             source="upstream_code", ref=_SERVICE_REF),
        Fact("The object_msgs/ObjectInfo type is included from object_msgs/ObjectInfo.h.",
             source="upstream_code", ref=_SERVICE_TYPE_REF),
        Fact("The object_msgs/Object type is included from object_msgs/Object.h.",
             source="upstream_code", ref=_TOPIC_TYPE_REF),
        Fact("requestObject returns success=false with OBJECT_NOT_FOUND for a missing model, and "
             "otherwise success=true, NO_ERROR and an object built by createBoundingBoxObject.",
             source="upstream_code", ref=_CALLBACK_REF),
        Fact("createBoundingBoxObject sets the object name, header stamp and frame, one primitive pose per "
             "collision (collision pose plus link world pose), primitive_origin ORIGIN_AVERAGE, mesh_origin "
             "ORIGIN_UNDEFINED and content SHAPE or POSE; it assigns origin for every collision because "
             "origin_init is never set to true, so origin holds the last collision's pose.",
             source="upstream_code", ref=_BUILD_REF),
        Fact("advertEvent publishes every generated object and onWorldUpdate generates one object per world "
             "model; both return early while the objects topic has no subscriber.",
             source="upstream_code", ref="gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:78-105"),
        Fact("The shipped GazeboObjectInfo.yaml sets publish_world_objects false.",
             source="upstream_code", ref=_CONFIG_REF),
        Fact("The shipped GazeboObjectInfo.yaml names the object topic /gazebo_objects.",
             source="upstream_code", ref=_TOPIC_CONFIG_REF),
        Fact("The shipped GazeboObjectInfo.yaml names the object-info service /gazebo_objects/get_info.",
             source="upstream_code", ref=_SERVICE_CONFIG_REF),
        Fact("The shipped GazeboObjectInfo.yaml sets objects_frame_id to world.",
             source="upstream_code", ref=_FRAME_CONFIG_REF),
        Fact("ObjectInfo.srv declares name and get_geometry in the request and success, object and "
             "error_code in the response; get_geometry=false returns only pose fields.",
             source="upstream_code", ref=_INFO_SRV_REF),
        Fact("Object.msg carries a Header, name, object type, primitive, mesh and plane arrays with their "
             "poses, primitive_origin, mesh_origin, origin, content and the content and origin-mode "
             "constants.",
             source="upstream_code", ref=_OBJECT_MSG_REF),
        Fact("The FakeObjectRecognizer configuration names the recognize_object service "
             "/gazebo_test_tools/recognize_object.",
             source="upstream_code", ref=_RECOGNIZER_REF),
        Fact("The FakeObjectRecognizer configuration publishes object_msgs/Object information on "
             "/gazebo_objects after an object has been recognized.",
             source="upstream_code", ref=_RECOGNIZER_TOPIC_REF),
        Fact("FakeObjectRecognizer's timer republishes only the objects added through its recognize_object "
             "service with republish set, and only while its objects topic has a subscriber.",
             source="upstream_code",
             ref="gazebo-pkgs-noetic/gazebo_test_tools/src/FakeObjectRecognizer.cpp:46-92"),
        Fact("gazebo_fake_object_recognition.launch includes plugin_loader.launch and "
             "fake_object_recognizer.launch with the default FakeObjectRecognizer.yaml.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("plugin_loader.launch loads WorldPlugins.yaml, GazeboObjectInfo.yaml and "
             "GazeboMapPublisher.yaml into the gazebo_state_plugins namespace.",
             source="upstream_code",
             ref="gazebo-pkgs-noetic/gazebo_state_plugins/launch/plugin_loader.launch:2-4"),
        Fact("WorldPlugins.yaml lists gazebo_object_info with file libgazebo_object_info.so as the world "
             "plugin to load.",
             source="upstream_code", ref="gazebo-pkgs-noetic/gazebo_state_plugins/config/WorldPlugins.yaml:10-12"),
        Fact("GazeboPluginLoader is a system plugin that has to be loaded together with Gazebo, for example "
             "gzserver -s libgazebo_world_plugin_loader.so.",
             source="upstream_code",
             ref="gazebo-pkgs-noetic/gazebo_world_plugin_loader/include/gazebo_world_plugin_loader/"
                 "GazeboPluginLoader.h:31-34"),
        Fact("GazeboPluginLoader::onWorldCreate reads world_name and the world_plugins list from the "
             "/gazebo_state_plugins parameter namespace.",
             source="upstream_code",
             ref="gazebo-pkgs-noetic/gazebo_world_plugin_loader/src/GazeboPluginLoader.cpp:19-38"),
        Fact("The README runs roslaunch lora_moveit_config demo_gazebo.launch and then python demo.py.",
             source="vendor_doc", ref="README.md:19-29"),
        Fact("gazebo.launch starts Gazebo through gazebo_ros empty_world.launch with pass_all_args and "
             "paused true; its arguments are gazebo_gui, paused, world_name, world_pose and "
             "initial_joint_positions.",
             source="upstream_code", ref="lora_moveit_config/launch/gazebo.launch:3-13"),
        Fact("ros_controllers.yaml declares arm_controller as a position_controllers/JointTrajectoryController.",
             source="upstream_code", ref=_CONTROLLER_REF),
        Fact("ros_controllers.yaml declares hand_controller as a position_controllers/JointTrajectoryController.",
             source="upstream_code", ref=_HAND_CONTROLLER_REF),
        Fact("simple_moveit_controllers.yaml names arm_controller with action_ns "
             "follow_joint_trajectory and plugin type FollowJointTrajectory.",
             source="upstream_code", ref=_SIMPLE_ARM_REF),
        Fact("simple_moveit_controllers.yaml names hand_controller with action_ns "
             "follow_joint_trajectory and plugin type FollowJointTrajectory.",
             source="upstream_code", ref=_SIMPLE_HAND_REF),
        Fact("demo.py constructs MoveGroupCommander objects for the arm and hand groups.",
             source="upstream_code", ref=_CLIENT_REF),
        Fact("The demo world declares a 0.001 s maximum physics step, real-time factor 1 and 1000 Hz "
             "real-time update rate.",
             source="upstream_code", ref=_WORLD_REF),
        Fact("The vendored gazebo-pkgs-noetic directory carries a BSD 3-Clause License file.",
             source="vendor_doc", ref="gazebo-pkgs-noetic/LICENSE:1-3"),
        Fact("The gazebo_state_plugins package.xml declares the licence GPLv3.",
             source="upstream_code", ref="gazebo-pkgs-noetic/gazebo_state_plugins/package.xml:15"),
        Fact("The vendored general-message-pkgs-master directory carries a BSD 3-Clause License file.",
             source="vendor_doc", ref="general-message-pkgs-master/LICENSE:1-3"),
        Fact("The object_msgs package.xml declares the licence string LPGv3.",
             source="upstream_code", ref="general-message-pkgs-master/object_msgs/package.xml:20"),
    ]
    safe_state = (
        "The package is observation-only: the runtime latches in software and refuses further "
        "observations; no actuator is driven, so no native stop is reached and no motion is commanded."
    )
    fidelity = {
        "engine": "analytic:ROS recording fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven recording fake with placeholder object poses; no physics step, "
                     "object dynamics, controller, wall-clock pacing or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared "
            "/gazebo_objects/get_info service and /gazebo_objects subscription with placeholder "
            "objects; it runs no Gazebo world, object physics, state plugin or object recognizer",
            "the object name and pose are placeholders; a live run must receive them from the "
            "operator's Gazebo world and the gazebo_state_plugins/GazeboObjectInfo plugin",
            "the shipped config sets publish_world_objects false, so /gazebo_objects is silent unless the "
            "operator enables the state plugin publisher (then one message per world model every 0.2 s, and "
            "a read returns whichever object arrives first) or a client registers an object through "
            "/gazebo_test_tools/recognize_object; otherwise every topic read waits 2 s and fails NOT_READY",
            "the repository's README demo (demo_gazebo.launch, gazebo.launch) starts Gazebo without the "
            "libgazebo_world_plugin_loader.so system plugin and loads no gazebo_state_plugins parameters, "
            "so neither endpoint exists in that deployment; the operator must start gzserver with the "
            "loader and load plugin_loader.launch (or gazebo_fake_object_recognition.launch) first",
            "the plugin's origin is the world pose of the model's last collision element, not the model "
            "frame (origin_init is never set to true), and a model without collisions is answered with "
            "success true and a zero origin; the fake's poses are placeholders and do not model either",
            "the clone's Object.msg carries primitive, mesh and plane geometry arrays; this package "
            "fixes get_geometry=false and carries only the object name, frame and origin pose; "
            "NOT COVERED: the primitive, mesh and plane arrays",
            "the arm and hand MoveIt/ros_control trajectory controllers are external and their "
            "action endpoints and types are not declared in the clone; they are NOT COVERED, so "
            "this is an object-state sensor, not a robot-arm motion driver",
            "the grasp fix plugin, contact handling, the map publisher, TF, Gazebo physics, cameras "
            "and depth sensors are NOT COVERED",
        ],
    }
    commands = {
        "x-cap.jerry-liubb.object_info.v1": _OBJECT_INFO,
        "x-cap.jerry-liubb.objects.v1": _OBJECTS,
    }
    actions = {
        "x-cap.jerry-liubb.object_info.v1": Action(
            name="object_info",
            verb="read",
            description="Request one object's pose from the Gazebo object-info service",
            input={
                "name": Field(
                    "string",
                    description="Gazebo model name to look up in the operator's world",
                ),
            },
            output={
                "success": Field("boolean", description="True when the model was found"),
                "error_code": Field("integer", description="ObjectInfo error code; 0 is NO_ERROR"),
                **_POSE_FIELDS,
            },
        ),
        "x-cap.jerry-liubb.objects.v1": Action(
            name="read_object",
            verb="read",
            description="Read one object_msgs/Object sample from /gazebo_objects",
            output=_POSE_FIELDS,
        ),
    }
