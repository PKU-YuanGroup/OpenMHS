OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a
reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.rodriguesrenato/warehouse_robot_simulation

Package facts cite the pinned clone at commit `c8fe89a8501bfbcd97ffb0a0a4bef26e1abffc75`.
Companion facts cite the lock clones `ros-simulation/gazebo_ros_pkgs` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`
(alias `gazebo_ros_pkgs`) and `gazebosim/gazebo-classic` at `e4400ae7e04e4859eec392ac67b813402703bab0`
(alias `gazebo_classic`). `upstream_code` refs name `path/in/clone:LINE`, or
`companion:<alias>/path/in/companion:LINE`. A bounded range is used where the statement spans adjacent
lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| WarehouseSimulation.cpp includes std_msgs/String.h for the order callback. | upstream_code | src/WarehouseSimulation.cpp:13 |
| The WarehouseSimulation node subscribes to the relative topic warehouse/order/add with queue size 10 and registers OrderController::AddOrder as its callback. | upstream_code | src/WarehouseSimulation.cpp:272 |
| The README states that the only way to interact externally with the simulation is to publish an Order message via ROS topic /warehouse/order/add. | vendor_doc | README.md:92 |
| The README defines an Order as a one-line plain string with the pattern target_dispatch_model_name product product_quantity product_n product_n_quantity. | vendor_doc | README.md:94 |
| The README states the project was built and was run on Ubuntu 18.04.5 LTS. | vendor_doc | README.md:11 |
| The README lists ROS Melodic among the required dependencies. | vendor_doc | README.md:16 |
| The README lists Gazebo 9.17.0 among the required dependencies. | vendor_doc | README.md:17 |
| The README says to adjust the following apt-get commands to the ROS version, and the example commands name ros-noetic packages. | vendor_doc | README.md:40-49 |
| OrderController::AddOrder parses the string, skips products with non-positive quantities, discards the whole order on any parse error, and otherwise appends the order to its queue when GetProductList().bucket_count() is greater than zero; it returns nothing to the sender. | upstream_code | src/OrderController.cpp:30-79 |
| Robot::Move builds a move_base_msgs::MoveBaseGoal, sends it through an actionlib SimpleActionClient and calls waitForResult() without a timeout. | upstream_code | src/Robot.cpp:102-132 |
| WarehouseSimulation constructs the Robot with robot name amr and action name move_base. | upstream_code | src/WarehouseSimulation.cpp:255 |
| The shipped amcl.launch starts map_server, amcl and move_base, loads the navigation parameter files, and remaps odom and scan. | upstream_code | launch/amcl.launch:4-59 |
| The custom SIGINT handler sets the global isShutdown flag. | upstream_code | src/WarehouseSimulation.cpp:35-42 |
| main calls ros::init with the node name WarehouseSimulation and ros::init_options::NoSigintHandler. | upstream_code | src/WarehouseSimulation.cpp:223 |
| main calls signal(SIGINT, SigintHandler). | upstream_code | src/WarehouseSimulation.cpp:274-275 |
| After the main loop ends, main deletes the spawned storages and dispatches and the products in the robots' cargo bins, sleeps 1 s and calls ros::shutdown. | upstream_code | src/WarehouseSimulation.cpp:283-310 |
| The main loop calls ros::spinOnce and loop_rate.sleep() while ros::ok() is true and isShutdown is false, with ros::Rate(10). | upstream_code | src/WarehouseSimulation.cpp:278-282 |
| The package builds one executable, WarehouseSimulation, from the listed C++ sources. | upstream_code | CMakeLists.txt:210-211 |
| The README states that the simulation is ended by pressing CTRL+C in the terminal that runs the WarehouseSimulation node. | vendor_doc | README.md:110 |
| world.launch includes $(find gazebo_ros)/launch/empty_world.launch and sets use_sim_time true, debug false, gui true and world_name. | upstream_code | launch/world.launch:9-14 |
| warehouse.world sets the physics element type to ode. | upstream_code | worlds/warehouse.world:67 |
| The delivery robot gazebo file loads the plugin libgazebo_ros_diff_drive.so and sets commandTopic to cmd_vel. | upstream_code | models/urdf/delivery_robot.gazebo:121-130 |
| ModelController::GazeboDelete calls the service gazebo/delete_model. | upstream_code | src/ModelController.cpp:103 |
| package.xml declares buildtool_depend catkin. | upstream_code | package.xml:11 |
| package.xml declares build_depend gazebo_ros. | upstream_code | package.xml:14 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch defaults its paused argument to false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:5 |
| empty_world.launch defaults its use_sim_time argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:6 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:127-128 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:147 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:462-468 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:364-370 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:235-242 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1662-1666 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1668-1672 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1426 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1433-1465 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:224-227 |
| GazeboRosDiffDrive connects UpdateChild to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:174-175 |
| GazeboRosDiffDrive::UpdateChild calls getWheelVelocities. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:240-270 |
| GazeboRosDiffDrive::getWheelVelocities reads x_ and rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:314-319 |
| GazeboRosDiffDrive::cmdVelCallback stores cmd_msg->linear.x in x_ and cmd_msg->angular.z in rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:325-329 |
| GazeboRosDiffDrive::QueueThread calls queue_.callAvailable with ros::WallDuration(timeout). | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:332-338 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-710 |
| While the world is paused and stepInc is greater than zero, World::Step calls Update and then decrements stepInc. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-702 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:683 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1428-1436 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1422-1425 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:776-782 |
| World::Step calls ProcessMessages after the paused or unpaused branch. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-718 |
| A WorldControl message with has_pause calls SetPaused, one with has_step calls OnStep, and one with has_multi_step calls SetPaused(true) and sets stepInc. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1462-1477 |
| World::OnStep sets stepInc to 1. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1364-1366 |

## Scope

The integration is the in-process `WarehouseSimulation` ROS 1 node plus the companion Gazebo world pause.
The node's only external ROS input is the relative `warehouse/order/add` subscription carrying
`std_msgs/String` (`src/WarehouseSimulation.cpp:272`). The order callback parses the plain string and
queues it (`src/OrderController.cpp:30-79`); it does not publish a status, order, queue, robot or
completion topic. The robot thread is a `move_base` action client (`src/Robot.cpp:102-132`). The
delivery robot loads `libgazebo_ros_diff_drive.so` with `commandTopic` `cmd_vel`
(`models/urdf/delivery_robot.gazebo:121-130`). `launch/world.launch` includes gazebo_ros
`empty_world.launch` (`launch/world.launch:9-14`).

The e-stop is `/gazebo/pause_physics` (`std_srvs/Empty`), which calls `World::SetPaused(true)`
(`companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1662-1666`). The safe-state
read-back is `/gazebo/get_physics_properties` with `pause` true (`:1426`). No unpause is declared.

The package declares one capability, `x-cap.rodriguesrenato.order.v1`, which publishes the caller's
string verbatim to `/warehouse/order/add` and reports that string as `sent_order`. It declares no
reads. The main resource snapshot is empty. NOT COVERED: Gazebo physics execution, the order queue
and its execution, `move_base` goals and action feedback, AMCL and `map_server`, TF, `/clock`,
`/scan`, `/odom`, `/cmd_vel` as a driver binding, RViz, ROS parameters, live ROS and hardware.

## Limits

No `Limit` is declared. The only input is the free-form order string, and the clone states no
maximum length, character set, token count, quantity range or dispatch/product enumeration that the
node enforces. The README's pattern (`README.md:94`) is a syntax description, not a numeric bound;
in particular the positive-quantity check at `src/OrderController.cpp:58` applies to the parsed
integer but the node does not state a maximum quantity. The package does not invent one. There is no
numeric input whose value could be bounded by a `Limit`, so `site-limits.example.json` is not
needed. An operator who needs an order-string policy must enforce it before publication; the driver
does not parse or rewrite the string.

## Safety

The declaration is `mode = "simulated"` and `device_kind = "world.sim"`, with `risk = "R2"` because
the order starts an autonomous mobile-base task in the simulated warehouse, above the card's R0
floor. The stop is the paused flag, not a measured standstill. `World::Step` calls `Update` when the world
is not paused, when `stepInc` is greater than zero, or when a reset is due
(`companion:gazebo_classic/gazebo/physics/World.cc:691-702`). While `IsPaused()` stays true and
`stepInc` is greater than zero, that `Update` still runs and then `stepInc` is decremented
(`:701-702`). `World::OnStep` sets `stepInc` to 1 (`:1364-1366`). A `WorldControl` with `has_step`
calls `OnStep`, and one with `has_multi_step` calls `SetPaused(true)` and sets `stepInc`
(`:1467-1476`). That update applies the stored `x_` and `rot_`
(`companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:270` and `:314-319`), so a
single step, a multi-step, or a step already pending runs stored motion without making `pause`
false. MHS does not clear `stepInc`. No unpause and no re-enable are offered. A pending
`move_base` goal (`src/Robot.cpp:119-120`) and the last `cmd_vel` stored in `x_` and `rot_`
(`:325-329`) also resume on an unpause. A zero Twist would not clear the goal, because `move_base`
publishes `cmd_vel` again.

`main` calls `ros::init` with `ros::init_options::NoSigintHandler` (`src/WarehouseSimulation.cpp:223`)
and then `signal(SIGINT, SigintHandler)` (`:274-275`). The handler only sets `isShutdown`
(`:35-42`). The loop (`:278-282`) sleeps on `ros::Rate(10)` while `use_sim_time` is true
(`launch/world.launch:10`), and `publishSimTime` is connected to the world update
(`companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:224-227`). While the world is
paused, the loop does not observe `isShutdown` and does not parse orders until the world steps.
Operator recovery outside MHS is to unpause and then press CTRL+C. Stored motion resumes during
that unpause, and also during a step that leaves `pause` true. `empty_world.launch` defaults
`paused` to false (`:5`) and `gui` to true (`:8`) and starts `gzclient` (`:51-54`); any client can
unpause or step, and MHS does not watch the flag after the e-stop.

`get_physics_properties` returns success false when the engine is not ODE
(`companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1433-1465`).
`worlds/warehouse.world:67` sets physics type `ode`. A read-back other than `pause` true leaves the
e-stop unconfirmed and the latch held. `mhs.safety.reset` releases the latch only; the world stays
paused. The README states Ubuntu 18.04.5, ROS Melodic and Gazebo 9.17.0 (`README.md:11`, `:16`,
`:17`). The companion pin is Gazebo 9.19.0, the same major. The apt examples at `README.md:43-49`
name `ros-noetic` packages after line 40 says to adjust them (`README.md:40-49`). No physical emergency stop exists in
this simulation repository and no hardware run is claimed.

`driver.lock.json` keeps `reviewed_by: null` and the original `authored_by`. This is a model repair
of a model-authored, unreviewed package. The fake is not a recording of captured traffic and claims
F0 only.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `warehouse`, `order`, `mobile-base`
