# Facts and tags for gh.nus-advanced-robotics-centre/me5413_final_project

Facts about the package's own surface cite the pinned clone at commit `9fd6ce2643f7dc9ed6e074ea559d3af29ef4968b` (`path/in/clone:LINE`). Facts about the stop cite the two reviewed companion sources that `task.json` declares (user decision of 2026-11-05) at their corpus pins, written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs at `cd9cc952402375be5f274f39b29399c4087aa839`, gazebo_ros 2.9.3 for ROS 1 Noetic) and `gazebo_classic` (gh.gazebosim/gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`, Gazebo 11.15.1). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ObjectSpawner::Load creates the /gazebo/delete_model DeleteModel service client, a 0.1 s timer, the Gazebo factory publisher, the /rviz_panel/respawn_objects and /cmd_unblock subscriptions, the /box_cmd_vel publisher, the /box_odom subscription and the /gazebo/ground_truth/box_markers publisher. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:35-42 |
| The plugin include object_spawner_gz_plugin.hpp includes std_msgs/Int16.h, std_msgs/Bool.h, visualization_msgs/MarkerArray.h, geometry_msgs/Twist.h, nav_msgs/Odometry.h and gazebo_msgs/DeleteModel.h. | upstream_code | src/me5413_world/include/me5413_world/object_spawner_gz_plugin.hpp:19-32 |
| ObjectSpawner::deleteObject fills gazebo_msgs::DeleteModel request.model_name, calls clt_delete_objects_ and logs success only when response.success is true. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:207-216 |
| The RViz control panel advertises a std_msgs/Int16 publisher on the absolute topic /rviz_panel/respawn_objects with queue size 1. | upstream_code | src/interactive_tools/src/rviz_panel.cpp:25 |
| The panel's regenerate button publishes data 1 and its clear button publishes data 0 on the respawn topic. | upstream_code | src/interactive_tools/src/rviz_panel.cpp:117-130 |
| The world plugin subscribes to the absolute /cmd_unblock topic. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:39 |
| Load creates a 0.1 s timer whose callback publishes box_markers_msg_ as visualization_msgs/MarkerArray on the absolute /gazebo/ground_truth/box_markers topic. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:36-53 |
| The plugin subscribes to the absolute /box_odom topic. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:41 |
| The red obstacle is spawned by gazebo_ros spawn_model as the model named planar_box at x 6.0, y 0.0, z 3.5 from planar_box.urdf.xacro. | upstream_code | src/me5413_world/launch/world.launch:19-27 |
| respawnCmdCallback executes deleteCone, deleteRandomCone and deleteBoxes with common::Time::MSleep(500) between them for command 0, and repeats that sequence then spawnRandomCone, spawnCone and spawnRandomBoxes for command 1; the callback has no cancellation check. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:309-345 |
| openBridgeCallback deletes the cone, calls common::Time::Sleep(10) and respawns the cone inside the same subscriber callback; this blocking ten-second path has no cancellation check. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:347-370 |
| boxOdomCallback reads pose.pose.position.y and, for every /box_odom message, publishes a geometry_msgs/Twist with linear.y plus or minus the SPEED constant 2.0 on /box_cmd_vel. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:372-388 |
| planar_box.urdf.xacro loads libgazebo_ros_planar_move.so with commandTopic box_cmd_vel, odometryTopic box_odom and odometryRate 20.0. | upstream_code | src/me5413_world/launch/include/planar_box.urdf.xacro:36-42 |
| world.launch includes launch/include/spawn_jackal.launch to add the Jackal robot. | upstream_code | src/me5413_world/launch/world.launch:15-16 |
| spawn_jackal.launch includes jackal_control's control.launch and teleop.launch and spawns the model jackal with gazebo_ros spawn_model. | upstream_code | src/me5413_world/launch/include/spawn_jackal.launch:23-30 |
| world.launch sets /use_sim_time true and launches gazebo_ros empty_world.launch with paused=false, use_sim_time=true and the me5413_project_2526.world file. | upstream_code | src/me5413_world/launch/world.launch:1-13 |
| The README tells students to unblock the lower-level exit by publishing a true std_msgs/Bool message to /cmd_unblock and states that the unblock lasts 10 s. | vendor_doc | README.md:180-181 |
| The README asks students not to use ground truth topics such as /gazebo/ground_truth/state or /box_odom. | vendor_doc | README.md:188 |
| Load creates the marker timer with a 0.1 s ros::Duration on the plugin's node handle. | upstream_code | src/me5413_world/src/object_spawner_gz_plugin.cpp:36 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:125-126 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:145 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:492-498 |
| The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:501-507 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:383-389 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:257-264 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1731-1735 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1489 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1496-1528 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:219-222 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-854 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:824-827 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1585-1593 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1579-1582 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:920-929 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-863 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1630-1640 |
| GazeboRosPlanarMove connects UpdateChild to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_planar_move.cpp:174-177 |
| UpdateChild sets the model's linear and angular velocity from the stored x_, y_ and rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_planar_move.cpp:198-208 |
| cmdVelCallback stores linear.x, linear.y and angular.z of the received Twist in x_, y_ and rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_planar_move.cpp:242-250 |
| The API plugin advertises the delete_model service on gazebo_queue_, the queue the pause uses. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:293-299 |
| deleteModel publishes an entity_delete request, then loops, sleeping 1 ms per round, until the model is gone or ROS time passes its 60 s timeout. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:851-878 |

## Scope notes

- The primary control surface of the pinned 2526 world is the object spawner's two publication topics. Both are
  fire-and-forget publications with no acknowledgement and their callbacks run blocking `common::Time::MSleep`/`Sleep`
  sequences with no cancellation check. The driver exposes them honestly as transmission-only actions and does not
  claim completion or quiescence.
- The clone's only acknowledged upstream ROS endpoint is the `/gazebo/delete_model` service client (its server is
  gazebo_ros). Deleting `planar_box`, the moving obstacle, through it is an ordinary one-shot command, not a stop. The
  clone declares no respawn for `planar_box`; the fake answers a repeat delete of the absent model with
  `success=false`, as gazebo_ros does. `delete_model` accepts any model name, including `jackal`.
- The clone exposes no ROS service or action that pauses, steps or resets Gazebo. The e-stop is the Gazebo world pause
  of the companion gazebo_ros (user decision of 2026-11-05), which gazebo_ros's `gzserver` wrapper loads into the
  server that `world.launch` starts through `empty_world.launch`: `/gazebo/pause_physics` (`pausePhysics` calls
  `World::SetPaused(true)`), confirmed only when `/gazebo/get_physics_properties` reads `pause` true back; a failed
  pause, a failed read-back (a non-ODE engine) or `pause` false gives `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch
  held and a background retry. No re-enable and no ordinary unpause are offered. `mhs.safety.reset` only releases the
  latch and the world stays paused. The earlier `x-cap.nus-advanced-robotics-centre.resume.v1` was removed (SAFE-042).
- While paused, no model update runs: `planar_box` moves only through gazebo_ros_planar_move's world-update hook and
  the Jackal through its controller's, so both stop, and `/box_odom` is silent (and so is the marker topic while its
  simulated-time timer waits). It is the paused flag, not a measured standstill. A paused world still processes delete
  and spawn requests, and the plugin's respawn and unblock callbacks sleep on the wall clock, so a callback already
  running completes its bounded world edits during the pause; the latch refuses this driver's publications until the
  reset. The pause shares gazebo_ros's callback queue with the delete service (which loops until the deleted model is gone),
  so a pending delete can push it past its 500 ms timeout; the e-stop then stays unconfirmed and retries. Any client or
  the Gazebo GUI can unpause or step the world; MHS does not watch the flag after the e-stop. No unpause is offered.
  `boxOdomCallback` publishes `linear.y` of plus or minus 2.0 on `/box_cmd_vel` (`object_spawner_gz_plugin.cpp:372-387`)
  and `gazebo_ros_planar_move` stores that twist (`gazebo_ros_planar_move.cpp:242-249`) and applies it on the world
  update (`198-208`). `planar_box.urdf.xacro:36-42` sets no `cmdTimeout`, and the plugin default `cmd_timeout_` is
  -1 (`gazebo_ros_planar_move.cpp:117`), so the update does not zero that velocity. This package does not publish `/box_cmd_vel`. `spawn_jackal.launch` includes `jackal_control`'s
  control and teleop launches (`spawn_jackal.launch:23-26`), which are not in this clone, so the Jackal controller's
  command cannot be cleared here either. After the reset the operator deletes `planar_box` (the remove command still
  applies while paused, or the GUI does it) and stops those Jackal nodes outside MHS, then unpauses with the Gazebo
  GUI (`world.launch:9`, `gui` true) or `rosservice call /gazebo/unpause_physics`. The deployment's gazebo_ros and
  Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases; rosbridge cannot read their versions.
- The 2526 plugin clears `box_markers_msg_` and its marker construction is commented out, so the published marker array
  is empty in this revision.
- NOT COVERED: `/gazebo/ground_truth/state` and `/box_odom` are ground-truth topics the README asks students not to use
  for the task; the driver exposes `/box_odom` only as an explicit observation, not as an automatic resource snapshot.
- The fake is a ROS-free canned transport, not a recording of captured traffic. It keeps a paused flag that the
  pause service sets and the read-back reports. It does not serve `/gazebo/unpause_physics`. While the flag is set
  it publishes no `/box_odom` or markers and still applies a delete. Its GetPhysicsProperties numbers are
  placeholders. No ROS graph, Gazebo process or hardware was run; `driver.lock.json` keeps `reviewed_by: null`.

Tags: `ros`, `ros1`, `gazebo`, `simulation`, `course-world`, `object-spawner`, `world-sim`.
