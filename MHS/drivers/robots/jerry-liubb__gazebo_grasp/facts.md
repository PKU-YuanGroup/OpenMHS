# Facts and tags for gh.jerry-liubb/gazebo_grasp

Every fact cites the pinned clone at commit
`0bd506d52c7e0a1791a0488afab5c31fc34e2347`. `upstream_code` refs name
`path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| GazeboObjectInfo is a Gazebo world plugin registered with GZ_REGISTER_WORLD_PLUGIN. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:24 |
| GazeboObjectInfo::Load creates a ros::NodeHandle named /gazebo_state_plugins. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:32 |
| The plugin defaults are publish_world_objects false, world_objects_topic world/objects, request_object_service world/request_object and objects_frame_id world. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:11-14 |
| GazeboObjectInfo::Load reads the publish_world_objects, world_objects_topic, request_object_service and objects_frame_id parameters. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:34-44 |
| GazeboObjectInfo::Load connects the world-update callback and advertises the WORLD_OBJECTS_TOPIC publisher only when publish_world_objects is true. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:48-51 |
| GazeboObjectInfo::Load advertises the REQUEST_OBJECTS_TOPIC service with the GazeboObjectInfo::requestObject callback. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:56 |
| The object_msgs/ObjectInfo type is included from object_msgs/ObjectInfo.h. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/include/gazebo_state_plugins/GazeboObjectInfo.h:9 |
| The object_msgs/Object type is included from object_msgs/Object.h. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/include/gazebo_state_plugins/GazeboObjectInfo.h:8 |
| requestObject returns success=false with OBJECT_NOT_FOUND for a missing model, and otherwise success=true, NO_ERROR and an object built by createBoundingBoxObject. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:59-75 |
| createBoundingBoxObject sets the object name, header stamp and frame, one primitive pose per collision (collision pose plus link world pose), primitive_origin ORIGIN_AVERAGE, mesh_origin ORIGIN_UNDEFINED and content SHAPE or POSE; it assigns origin for every collision because origin_init is never set to true, so origin holds the last collision's pose. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:177-250 |
| advertEvent publishes every generated object and onWorldUpdate generates one object per world model; both return early while the objects topic has no subscriber. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/src/GazeboObjectInfo.cpp:78-105 |
| The shipped GazeboObjectInfo.yaml sets publish_world_objects false. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:4 |
| The shipped GazeboObjectInfo.yaml names the object topic /gazebo_objects. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:8 |
| The shipped GazeboObjectInfo.yaml names the object-info service /gazebo_objects/get_info. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:12 |
| The shipped GazeboObjectInfo.yaml sets objects_frame_id to world. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/config/GazeboObjectInfo.yaml:16 |
| ObjectInfo.srv declares name and get_geometry in the request and success, object and error_code in the response; get_geometry=false returns only pose fields. | upstream_code | general-message-pkgs-master/object_msgs/srv/ObjectInfo.srv:1-23 |
| Object.msg carries a Header, name, object type, primitive, mesh and plane arrays with their poses, primitive_origin, mesh_origin, origin, content and the content and origin-mode constants. | upstream_code | general-message-pkgs-master/object_msgs/msg/Object.msg:1-75 |
| The FakeObjectRecognizer configuration names the recognize_object service /gazebo_test_tools/recognize_object. | upstream_code | gazebo-pkgs-noetic/gazebo_test_tools/config/FakeObjectRecognizer.yaml:3 |
| The FakeObjectRecognizer configuration publishes object_msgs/Object information on /gazebo_objects after an object has been recognized. | upstream_code | gazebo-pkgs-noetic/gazebo_test_tools/config/FakeObjectRecognizer.yaml:5-7 |
| FakeObjectRecognizer's timer republishes only the objects added through its recognize_object service with republish set, and only while its objects topic has a subscriber. | upstream_code | gazebo-pkgs-noetic/gazebo_test_tools/src/FakeObjectRecognizer.cpp:46-92 |
| gazebo_fake_object_recognition.launch includes plugin_loader.launch and fake_object_recognizer.launch with the default FakeObjectRecognizer.yaml. | upstream_code | gazebo-pkgs-noetic/gazebo_test_tools/launch/gazebo_fake_object_recognition.launch:6-14 |
| plugin_loader.launch loads WorldPlugins.yaml, GazeboObjectInfo.yaml and GazeboMapPublisher.yaml into the gazebo_state_plugins namespace. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/launch/plugin_loader.launch:2-4 |
| WorldPlugins.yaml lists gazebo_object_info with file libgazebo_object_info.so as the world plugin to load. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/config/WorldPlugins.yaml:10-12 |
| GazeboPluginLoader is a system plugin that has to be loaded together with Gazebo, for example gzserver -s libgazebo_world_plugin_loader.so. | upstream_code | gazebo-pkgs-noetic/gazebo_world_plugin_loader/include/gazebo_world_plugin_loader/GazeboPluginLoader.h:31-34 |
| GazeboPluginLoader::onWorldCreate reads world_name and the world_plugins list from the /gazebo_state_plugins parameter namespace. | upstream_code | gazebo-pkgs-noetic/gazebo_world_plugin_loader/src/GazeboPluginLoader.cpp:19-38 |
| The README runs roslaunch lora_moveit_config demo_gazebo.launch and then python demo.py. | vendor_doc | README.md:19-29 |
| gazebo.launch starts Gazebo through gazebo_ros empty_world.launch with pass_all_args and paused true; its arguments are gazebo_gui, paused, world_name, world_pose and initial_joint_positions. | upstream_code | lora_moveit_config/launch/gazebo.launch:3-13 |
| ros_controllers.yaml declares arm_controller as a position_controllers/JointTrajectoryController. | upstream_code | lora_moveit_config/config/ros_controllers.yaml:1-2 |
| ros_controllers.yaml declares hand_controller as a position_controllers/JointTrajectoryController. | upstream_code | lora_moveit_config/config/ros_controllers.yaml:41-42 |
| simple_moveit_controllers.yaml names arm_controller with action_ns follow_joint_trajectory and plugin type FollowJointTrajectory. | upstream_code | lora_moveit_config/config/simple_moveit_controllers.yaml:2-4 |
| simple_moveit_controllers.yaml names hand_controller with action_ns follow_joint_trajectory and plugin type FollowJointTrajectory. | upstream_code | lora_moveit_config/config/simple_moveit_controllers.yaml:13-15 |
| demo.py constructs MoveGroupCommander objects for the arm and hand groups. | upstream_code | demo.py:13-14 |
| The demo world declares a 0.001 s maximum physics step, real-time factor 1 and 1000 Hz real-time update rate. | upstream_code | inspire_hand_description/worlds/demo_world.world:72-76 |
| The vendored gazebo-pkgs-noetic directory carries a BSD 3-Clause License file. | vendor_doc | gazebo-pkgs-noetic/LICENSE:1-3 |
| The gazebo_state_plugins package.xml declares the licence GPLv3. | upstream_code | gazebo-pkgs-noetic/gazebo_state_plugins/package.xml:15 |
| The vendored general-message-pkgs-master directory carries a BSD 3-Clause License file. | vendor_doc | general-message-pkgs-master/LICENSE:1-3 |
| The object_msgs package.xml declares the licence string LPGv3. | upstream_code | general-message-pkgs-master/object_msgs/package.xml:20 |

## Scope

The selected device is the source-backed Gazebo object-state sensor of the
vendored gazebo-pkgs, not the robot-arm motion stack. The package binds the
`object_msgs/ObjectInfo` service on `/gazebo_objects/get_info` and the
`object_msgs/Object` topic on `/gazebo_objects`. The service is the primary
observation because the shipped `GazeboObjectInfo.yaml` sets
`publish_world_objects: false`; the topic is silent unless the operator enables
the state plugin's publisher (then one message per world model every 0.2 s) or a
client registers an object through the `FakeObjectRecognizer`'s
`/gazebo_test_tools/recognize_object` service. The service fixes
`get_geometry: false`, so only the object name, frame and origin are carried;
the plugin sets `origin` for every collision because `origin_init` is never set,
so it is the world pose of the model's last collision element. The full
primitive, mesh and plane arrays are NOT COVERED.

The repository's README demo (`roslaunch lora_moveit_config demo_gazebo.launch`)
starts Gazebo through `gazebo.launch` without the
`libgazebo_world_plugin_loader.so` system plugin and loads no
`gazebo_state_plugins` parameters, so neither endpoint exists there; the operator
must start gzserver with the loader and load `plugin_loader.launch` (or
`gazebo_fake_object_recognition.launch`) first.

The arm and hand controllers are external MoveIt/ros_control nodes. The clone
names the controllers, their action namespace `follow_joint_trajectory` and the
short type `FollowJointTrajectory`, but no fully qualified ROS action type, and
it declares no acknowledged ROS stop. The package therefore does not bind the
arm or hand motion and makes no robot-arm safety claim. `demo.py` constructs
MoveGroupCommander clients for the arm and hand groups.

Licences: the repository has no root licence; the vendored `gazebo-pkgs-noetic`
and `general-message-pkgs-master` directories carry BSD 3-Clause LICENSE files
while `gazebo_state_plugins/package.xml` declares GPLv3 and
`object_msgs/package.xml` declares `LPGv3`. The owner decides publication.

## Safety

The device is a simulated sensor at R0. The package has no actuation commands,
so there is no native stop to reach: the server's software latch refuses
further extension observations and no motion is commanded. The safe-state
description says this explicitly. No hardware, ROS graph, Gazebo world or
object plugin was run, and `driver.lock.json` keeps `reviewed_by: null`.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS recording fake
(no Gazebo physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake answers
the declared service and topic with placeholder objects; it runs no Gazebo
physics, object dynamics, state plugin or recognizer. The upstream world's
0.001 s physics step is a source fact, not the fake's timing.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `object-state`, `object-info`, `grasp`
