# Facts and tags for gh.ipa320/cob_simulation

Facts about the package's own surface cite the pinned clone at commit `907144342c0351c9427ddd960ef4dfe013847113` (`path/in/clone:LINE`). Facts about the stop cite the two reviewed companion sources that `task.json` declares (user decision of 2026-11-05) at their corpus pins, written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs at `cd9cc952402375be5f274f39b29399c4087aa839`, gazebo_ros 2.9.3 for ROS 1 Noetic) and `gazebo_classic` (gh.gazebosim/gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`, Gazebo 11.15.1). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | ref |
|---|---|
| The cob_simulation metapackage describes itself as packages to work with the Care-O-bot within simulation environments such as Gazebo. | cob_simulation/package.xml:3-4 |
| The cob_simulation metapackage depends on cob_bringup_sim, cob_gazebo, cob_gazebo_objects, cob_gazebo_tools and cob_gazebo_worlds. | cob_simulation/package.xml:13-18 |
| The world launch includes gazebo_ros/empty_world.launch with the world_name, paused, use_sim_time and gui arguments. | cob_gazebo_worlds/launch/world.launch:26-34 |
| The robot launch runs the gazebo_ros spawn_model node with -urdf -param robot_description and -model robot. | cob_gazebo/launch/robot.launch:17 |
| spawn_object.py waits for /gazebo/get_world_properties and creates a GetWorldProperties ServiceProxy on that absolute name. | cob_gazebo_tools/scripts/spawn_object.py:123-128 |
| spawn_object.py reads world_properties.model_names only when world_properties.success is true, and otherwise uses an empty model list. | cob_gazebo_tools/scripts/spawn_object.py:135-138 |
| move_object.py creates a GetModelState ServiceProxy on /gazebo/get_model_state and a SetModelState ServiceProxy and ModelState publisher on /gazebo/set_model_state. | cob_gazebo_tools/scripts/move_object.py:50-54 |
| move_object.py's get_model_state sends a request with only model_name set and returns the GetModelState response. | cob_gazebo_tools/scripts/move_object.py:78-86 |
| move_object.py's start-up loop calls get_model_state for its model and keeps waiting while the response's success is false. | cob_gazebo_tools/scripts/move_object.py:61-65 |
| move_object.py builds a ModelState with model_name, a Pose whose position is x/y and whose orientation is a yaw quaternion, and reference_frame 'world', then publishes it. | cob_gazebo_tools/scripts/move_object.py:127-143 |
| move_object.py sets reference_frame to 'world' for its ModelState messages. | cob_gazebo_tools/scripts/move_object.py:140 |
| move_object.py documents polygon points as forming a polygon in [m] and the initialpose argument as a Cartesian Pose. | cob_gazebo_tools/scripts/move_object.py:280-290 |
| remove_object.py creates a gazebo/delete_model ServiceProxy, waits for the absolute /gazebo/delete_model service, and calls it with the model name. | cob_gazebo_tools/scripts/remove_object.py:118-124 |
| spawn_object.py assembles its spawn endpoint at runtime as '/gazebo/spawn_' + model_type + '_model'; the clone has no fixed spawn endpoint literal. | cob_gazebo_tools/scripts/spawn_object.py:205-211 |
| The clone's CI workflow builds for the single ROS distro noetic. | .github/workflows/main.yml:26-29 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:125-126 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:145 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:492-498 |
| The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:501-507 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:383-389 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:257-264 |
| pausePhysics calls world_->SetPaused(true) and returns true. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1731-1735 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1489 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1496-1528 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:219-222 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | companion:gazebo_classic/gazebo/physics/World.cc:835-854 |
| World::Step holds worldUpdateMutex while it steps the world. | companion:gazebo_classic/gazebo/physics/World.cc:824-827 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | companion:gazebo_classic/gazebo/physics/World.cc:1585-1593 |
| World::IsPaused returns the stored paused flag. | companion:gazebo_classic/gazebo/physics/World.cc:1579-1582 |
| World::Update fires the worldUpdateBegin event and then updates every model. | companion:gazebo_classic/gazebo/physics/World.cc:920-929 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | companion:gazebo_classic/gazebo/physics/World.cc:835-863 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | companion:gazebo_classic/gazebo/physics/World.cc:1630-1640 |
| The API plugin advertises the set_model_state service on gazebo_queue_, the queue the pause uses. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:439-445 |
| The API plugin subscribes to the set_model_state topic on gazebo_queue_ with updateModelState as the callback. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:483-489 |
| updateModelState passes the received ModelState to setModelState. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1663-1669 |
| setModelState records whether the world is paused, pauses it, sets the model pose, then restores the recorded paused state. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1642-1645 |
| deleteModel publishes an entity_delete request, then loops, sleeping 1 ms per round, until the model is gone or ROS time passes its 60 s timeout. | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:851-878 |

## Scope

The ROS 1 Gazebo object tools that the clone calls at runtime (world properties, the robot's pose, model deletion and
the ModelState publication); the package launches neither Gazebo nor the upstream scripts. The clone's CI builds for
ROS Noetic (`.github/workflows/main.yml:26-29`); the README's distro table names only older releases, and the package
serves the Noetic profile only. The two service reads answer while the world is paused (gazebo_ros serves them on its
own callback queue), so the device resource stays readable after an e-stop and a reset.

## Stop and read-back

The clone registers no stop service. The stop is the Gazebo world pause served by the companion gazebo_ros API
plugin, which gazebo_ros's `gzserver` wrapper loads into the server that `cob_gazebo_worlds/launch/world.launch`
starts through `empty_world.launch`:

- e-stop: `/gazebo/pause_physics` (`std_srvs/Empty`): `pausePhysics` calls `World::SetPaused(true)`;
- read-back (`safety_bindings.safe_state`): `/gazebo/get_physics_properties`; the e-stop is confirmed only when its
  `pause` field is true. A failed pause, a failed read-back (a non-ODE engine) or a read-back with `pause` false gives
  `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry;
- no re-enable and no ordinary unpause. `mhs.safety.reset` only releases the latch; the world stays paused. The
  earlier `x-cap.ipa320.resume.v1` was removed (SAFE-042).

While paused, `World::Step` runs no world update, so no model and no controller moves, the robot's included. It is
the paused flag, not a measured standstill. A paused world still applies world edits: `setModelState` records the
paused state, pauses, sets the pose and restores the recorded state (the world stays paused), and delete requests are
processed on every step. The latch refuses this driver's edits until the reset; other clients and the Gazebo GUI can
edit, step or unpause the world at any time, and MHS does not watch the flag after the e-stop. The pause shares
gazebo_ros's callback queue with every other world service, one request at a time: a spawn or a delete that still
waits for its world edit (`deleteModel` loops until the model is gone) delays it beyond its 500 ms timeout, and the e-stop then
stays unconfirmed with the latch held and retries. No unpause is offered. This package publishes no controller
command. `robot.launch` includes `cob_bringup`, an exec_depend that is not in this clone
(`cob_gazebo/package.xml:18`, `robot.launch:12`), and the component test addresses `JointTrajectory` topics
`/<component>_controller/command` (`component_test.py:78-81`). The world launches spawn controllers this package
does not command: position controllers in `ipa-apartment.xml:13-14` and velocity controllers in
`ipa-kitchen.xml:14` and `automotive-assembly-line.xml:15`. `elevator.py:64-66` publishes `Float64` 0, the close
position, after the open position 0.87 (lines 51-55); that close publish moves the door, so it cannot clear a stored command. Those commands
act again when the world runs. After the reset the operator
stops those controller nodes outside MHS, then unpauses with the Gazebo GUI (`world.launch:14`, `gui` defaults to
true) or `rosservice call /gazebo/unpause_physics`. The deployment's gazebo_ros and Gazebo must be the pinned 2.9.3
(Noetic) and 11 releases; rosbridge cannot read their versions. The fake answers a delete of an absent model with
success, while gazebo_ros 2.9.3 answers success false (`DeleteModel: model does not exist`), so a live delete of an
absent model is a failed receipt.

Tags: `ros1`, `gazebo`, `simulation`, `care-o-bot`, `world`, `models`,
`object-tools`.
