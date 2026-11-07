OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.cambel/ur3

Facts about the package's own surface cite the pinned clone at commit `10f96dc362a7700b14e4a2469c8025134ef3e4f7` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gz_sim` (gh.gazebosim/gz-sim, fetched under work/companions as `gazebosim__gz-sim@gz-sim8_8.15.0` at `446a44335a45b704b4d36dabcc5508ee34eeb3d8`), `ros_gz` (gh.gazebosim/ros_gz, fetched under work/companions as `gazebosim__ros_gz@1.0.25` at `b87d7523400a695a10d47ca7b8cb5fa86d5b8d9d`) and `gz_transport` (gh.gazebosim/gz-transport, fetched under work/companions as `gazebosim__gz-transport@gz-transport13_13.6.0` at `35fef7ea10c2e133498e9010bd2e397a0ce0c3bf`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, the LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README.md states ROS 2 Jazzy on Ubuntu 24.04 with Gazebo Harmonic (gz-sim 8), and points ROS 1 Noetic or Melodic with Gazebo Classic at the noetic-devel branch. | vendor_doc | README.md:6-7 |
| README.md says mimic joints need bullet-featherstone and that both gripper launches pass --physics-engine gz-physics-bullet-featherstone-plugin. | vendor_doc | README.md:196-197 |
| README.md says the Robotiq real-hardware driver (robotiq_control / pymodbus) is deferred. | vendor_doc | README.md:211 |
| LICENSE line 1 is The MIT License (MIT). | vendor_doc | LICENSE:1 |
| ur_gripper_gz/package.xml declares license BSD and build tool ament_cmake. | upstream_code | ur_gripper_gz/package.xml:14-16 |
| ur_gripper_gz/package.xml depends on ros_gz_bridge and ros_gz_sim. | upstream_code | ur_gripper_gz/package.xml:33-34 |
| ur_gz_control.launch.py starts a ros_gz_bridge parameter_bridge with the argument /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:65-68 |
| ur_gz_control.launch.py starts ur_control's active_gripper_publisher with gripper robotiq_hande. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:72-75 |
| ur_gz_control.launch.py builds gz_args containing empty.sdf, -r and gz-physics-bullet-featherstone-plugin, and includes ros_gz_sim's gz_sim.launch.py. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:87-95 |
| ur_gz_control.launch.py spawns the model with -name set to the ur_type launch argument. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:98-102 |
| ur_gz_control.launch.py starts a controller_manager spawner named joint_state_broadcaster. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:106-113 |
| ur_gz_control.launch.py starts a controller_manager spawner named scaled_joint_trajectory_controller. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:129-136 |
| ur_gz_control.launch.py spawns forward_velocity_controller and cartesian_compliance_controller with --inactive. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:137-159 |
| ur_gz_control.launch.py spawns gripper_controller when load_gripper is true. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:161-170 |
| ur_gz_control.launch.py defaults ur_type to ur3e, describes that argument as including ur3, and defaults load_gripper to true. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:174-179 |
| ur_gz_control.launch.py registers OnProcessExit so spawn_entity's exit starts jsb_spawner, jsb_spawner's exit starts fts_spawner and jtc_spawner, and jtc_spawner's exit starts fvc_spawner, compliance_spawner and gripper_spawner. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:186-190 |
| force_torque_sensor_broadcaster is passed with -c and /controller_manager. | upstream_code | ur_gripper_gz/launch/ur_gz_control.launch.py:124 |
| ur_gz_controllers.yaml says the trajectory controller is named scaled_joint_trajectory_controller so ur_control's Arm drives the simulated robot unchanged. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:4-5 |
| ur_gz_controllers.yaml sets controller_manager update_rate 500 and use_sim_time true, and sets joint_state_broadcaster's type to joint_state_broadcaster/JointStateBroadcaster. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:8-12 |
| ur_gz_controllers.yaml sets scaled_joint_trajectory_controller's type to joint_trajectory_controller/JointTrajectoryController. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:17-18 |
| ur_gz_controllers.yaml sets gripper_controller's type to joint_trajectory_controller/JointTrajectoryController. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:29-33 |
| ur_gz_controllers.yaml lists shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint and wrist_3_joint for scaled_joint_trajectory_controller, with command interface position. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:45-55 |
| ur_gz_controllers.yaml sets stopped_velocity_tolerance 0.05 and goal_time 0.6 on scaled_joint_trajectory_controller. | upstream_code | ur_gripper_gz/config/ur_gz_controllers.yaml:60-62 |
| constants.py sets JOINT_POSITION_TRAJECTORY_CONTROLLER and JOINT_VELOCITY_TRAJECTORY_CONTROLLER to scaled_joint_trajectory_controller and JOINT_STATE_SUBSCRIBER to joint_states. | upstream_code | ur_control/ur_control/constants.py:29-32 |
| constants.py names shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint and wrist_3_joint. | upstream_code | ur_control/ur_control/constants.py:38-43 |
| constants.py sets JOINT_ORDER to those six joint names. | upstream_code | ur_control/ur_control/constants.py:49-52 |
| controllers.py imports JointState from sensor_msgs.msg. | upstream_code | ur_control/ur_control/controllers.py:21 |
| JointControllerBase creates a JointState subscription on the relative name joint_states with qos_profile_sensor_data. | upstream_code | ur_control/ur_control/controllers.py:64 |
| If that subscription waits past the timeout, JointControllerBase subscribes again to a topic built as the namespace plus joint_states. | upstream_code | ur_control/ur_control/controllers.py:66-71 |
| JointTrajectoryController defaults publisher_name to scaled_joint_trajectory_controller and builds the command topic as the namespace plus that name plus /joint_trajectory. | upstream_code | ur_control/ur_control/controllers.py:377-382 |
| JointTrajectoryController.stop calls cancel_goal_async on the goal handle when one exists. | upstream_code | ur_control/ur_control/controllers.py:493-498 |
| check_for_real_robot returns True without calling the wrapped function when use_real_robot is false. | upstream_code | ur_control/ur_control/ur_services.py:16-24 |
| URServices sets use_real_robot from the parameter use_real_robot with default False. | upstream_code | ur_control/ur_control/ur_services.py:38 |
| URServices creates a std_srvs.srv.Trigger client named stop on the namespace plus ur_hardware_interface/dashboard/stop. | upstream_code | ur_control/ur_control/ur_services.py:51 |
| ur_2f85_gz_control.launch.py also builds gz_args containing empty.sdf and -r. | upstream_code | ur_gripper_gz/launch/ur_2f85_gz_control.launch.py:71-73 |
| ur_2f85_gz_control.launch.py defaults ur_type to ur5e. | upstream_code | ur_gripper_gz/launch/ur_2f85_gz_control.launch.py:105 |
| SimulationRunner composes its transport namespace as /world/ followed by the world name. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:249 |
| SimulationRunner advertises the control service with OnWorldControl as its callback. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:325 |
| OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1321-1328 |
| OnWorldControlState appends the control to worldControls and sets the Boolean reply data to true. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1375-1377 |
| ProcessWorldControl calls SetPaused with the pause flag of each queued control. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1440-1443 |
| A queued control with multi_step greater than zero while paused adds the steps and calls SetPaused false. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1445-1452 |
| SetPaused stores the pause state in currentInfo.paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1290-1291 |
| UpdateSystems calls PreUpdate on each system from SystemsPreUpdate. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:662-684 |
| UserCommands::PreUpdate takes an unused UpdateInfo, copies pendingCmds and calls Execute on each command. | upstream_code | companion:gz_sim/src/systems/user_commands/UserCommands.cc:669-699 |
| Step calls PublishStats. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1023-1024 |
| Step calls ProcessMessages. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1063-1064 |
| While paused the Run loop does not count a processed iteration; without a network manager it calls Step. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:896-911 |
| The statistics publisher comment says the GUI listens to these messages for confirmation that pause and play GUI requests were processed. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:800-805 |
| The statistics publisher on the stats topic is limited to 10 messages per second. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:806-808 |
| PublishStats copies currentInfo.paused into the WorldStatistics message. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:534 |
| UpdateCurrentInfo advances simTime and the iteration count only in the branch that requires the world not paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:423-429 |
| The Physics system steps the physics only when not paused. | upstream_code | companion:gz_sim/src/systems/physics/Physics.cc:1047-1051 |
| examples/worlds/empty.sdf names its world empty. | upstream_code | companion:gz_sim/examples/worlds/empty.sdf:63 |
| examples/worlds/empty.sdf loads gz-sim-physics-system, gz-sim-user-commands-system, gz-sim-scene-broadcaster-system and gz-sim-contact-system. | upstream_code | companion:gz_sim/examples/worlds/empty.sdf:68-83 |
| examples/worlds/empty.sdf then declares a directional light named sun and a model named ground_plane. | upstream_code | companion:gz_sim/examples/worlds/empty.sdf:85-99 |
| The bridge maps ros_gz_interfaces/srv/ControlWorld to a gz.msgs.WorldControl request with a gz.msgs.Boolean reply. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:43-52 |
| The ControlWorld response's success is the gz Boolean reply's data. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:134-141 |
| For a failed gz request the ControlWorld response's success is false. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:170-178 |
| The service bridge converts each ROS request and sends it with gz Request and a callback that sends the ROS response. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factory.hpp:56-86 |
| Node::Request with a callback requests a service using a non-blocking call. | upstream_code | companion:gz_transport/include/gz/transport/Node.hh:662-677 |
| The WorldStatistics conversion copies the gz header, sim_time, pause_time, real_time and paused into the ROS message. | upstream_code | companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp:840-844 |
| ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldStatistics.msg:1-14 |
| ControlWorld takes a WorldControl request and answers bool success. | upstream_code | companion:ros_gz/ros_gz_interfaces/srv/ControlWorld.srv:1-3 |
| WorldControl's fields include pause, step and multi_step. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldControl.msg:1-3 |
| The bridge README maps ros_gz_interfaces/msg/WorldStatistics to gz.msgs.WorldStatistics. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:52 |
| The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to gz.msgs.WorldControl and gz.msgs.Boolean. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:86 |
| The bridge README's service example starts parameter_bridge with /world/shapes/control@ros_gz_interfaces/srv/ControlWorld. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:261-265 |
| Without a configured QoS profile the bridge's publisher QoS is KeepLast with the publisher queue size. | upstream_code | companion:ros_gz/ros_gz_bridge/src/bridge_config.cpp:274-279 |
| The bridge's publisher allows its deadline, depth, durability, history, liveliness and reliability QoS to be overridden. | upstream_code | companion:ros_gz/ros_gz_bridge/src/factory.hpp:61-82 |
| The gz-sim 8 CMake project is gz-sim8 version 8.15.0. | upstream_code | companion:gz_sim/CMakeLists.txt:6 |
| The gz-sim changelog heading is Gazebo Sim 8.15.0 (2026-08-11). | upstream_code | companion:gz_sim/Changelog.md:3 |
| The gz-sim CMake file finds gz-transport13. | upstream_code | companion:gz_sim/CMakeLists.txt:87 |
| ros_gz_bridge package.xml declares version 1.0.25. | upstream_code | companion:ros_gz/ros_gz_bridge/package.xml:5 |
| ros_gz_bridge CHANGELOG.rst records 1.0.25 (2026-10-13). | upstream_code | companion:ros_gz/ros_gz_bridge/CHANGELOG.rst:5 |
| ros_gz_sim package.xml depends on gz_sim_vendor. | upstream_code | companion:ros_gz/ros_gz_sim/package.xml:32 |
| The gz-transport 13 CMake project is gz-transport13 version 13.6.0. | upstream_code | companion:gz_transport/CMakeLists.txt:6 |
| The gz-transport changelog heading is Gazebo Transport 13.6.0 (2026-08-15). | upstream_code | companion:gz_transport/Changelog.md:3 |

## Scope

The package is a configuration-only ROS 2 `RosDriver` for the simulated Hand-E bringup `ur_gripper_gz/launch/ur_gz_control.launch.py` (ROS 2 Jazzy, Gazebo Harmonic / gz-sim 8). The registry record keeps `modes` hardware first and `simulated` second. The card's `safety.expected_mode` is `simulated` because the reviewed override sets `served_mode` to `simulated`. The hardware path stays on the record: `check_for_real_robot` returns true without calling the wrapped function when `use_real_robot` is false (`ur_services.py:16-24`), that parameter defaults false (`ur_services.py:38`), the dashboard stop client is a `std_srvs.srv.Trigger` on `ur_hardware_interface/dashboard/stop` (`ur_services.py:51`), and `README.md:211` defers the Robotiq real-hardware driver. That path is not served. There is no hardware backend. The `noetic-devel` branch named at `README.md:6-7` is not served.

The one observation is the relative `joint_states` subscription in `JointControllerBase` (`controllers.py:64`, type from the `sensor_msgs.msg.JointState` import at `controllers.py:21`), resolved as `/joint_states`. The launch starts a controller_manager spawner named `joint_state_broadcaster` (`ur_gz_control.launch.py:106-113`) and the yaml sets that controller's type (`ur_gz_controllers.yaml:11-12`). Neither line is a topic literal, so this package does not claim that the broadcaster publishes `/joint_states`. A withheld sample is a timeout. The retry at `controllers.py:71` builds the namespace plus `joint_states`; this package serves the relative name on line 64.

The trajectory command is not served. `JointTrajectoryController` defaults `publisher_name` to `scaled_joint_trajectory_controller` and builds the command topic as the namespace plus that name plus `/joint_trajectory` (`controllers.py:377-382`). That assembled string is not published. The launch still starts `scaled_joint_trajectory_controller` (`ur_gz_control.launch.py:129-136`). The yaml says that name is so `ur_control`'s Arm drives the simulated robot unchanged (`ur_gz_controllers.yaml:4-5`). `forward_velocity_controller` and `cartesian_compliance_controller` spawn with `--inactive` (`ur_gz_control.launch.py:137-159`). `gripper_controller` is a second `JointTrajectoryController` (`ur_gz_controllers.yaml:29-33`) spawned when `load_gripper` is true (`ur_gz_control.launch.py:161-170`); `load_gripper` defaults true (`ur_gz_control.launch.py:178-179`).

The served launch is `ur_gz_control.launch.py` only. Its `gz_args` contain `empty.sdf`, `-r` and `gz-physics-bullet-featherstone-plugin`, and it includes `ros_gz_sim`'s `gz_sim.launch.py` (`ur_gz_control.launch.py:87-95`). The string `empty.sdf` is a file name. The companion world file names the world `empty` (`examples/worlds/empty.sdf:63`). The spawn name is the `ur_type` argument (`ur_gz_control.launch.py:102`), which defaults to `ur3e` (`ur_gz_control.launch.py:174-175`); `ur3` is in the argument description. `ur_2f85_gz_control.launch.py` also passes `empty.sdf` (`ur_2f85_gz_control.launch.py:71-73`) and defaults `ur_type` to `ur5e` (`ur_2f85_gz_control.launch.py:105`) and is not served. A different `ur_type` still uses world name `empty`. A different world name means the declared endpoints do not exist and the e-stop fails closed.

`OnProcessExit` order in the served launch: `spawn_entity`'s exit starts `jsb_spawner`, that spawner's exit starts `fts_spawner` and `jtc_spawner`, and `jtc_spawner`'s exit starts `fvc_spawner`, `compliance_spawner` and `gripper_spawner` (`ur_gz_control.launch.py:186-190`). `force_torque_sensor_broadcaster` is passed with `-c` and `/controller_manager` (line 124). That chain is process order only.

The served launch's only `parameter_bridge` argument is `/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock` (`ur_gz_control.launch.py:65-68`). This package does not subscribe to `/clock` and does not list it in `operator_bridges`.

## Limits

`JointState.name`, `position` and `velocity` are arrays. The clone states no unit on the `joint_states` subscription, and the schema fixes neither a length nor a unit. The fake's six names are the `JOINT_ORDER` strings from `constants.py:49-52` and are placeholders. `stopped_velocity_tolerance` 0.05 (`ur_gz_controllers.yaml:60-62`) is a fact, not a Limit. The catalogue has no class that binds a raw `sensor_msgs/JointState` subscription on `robot.arm`, so the read is `x-cap.cambel.joint-states.v1`.

## Safety

The e-stop is the world pause of gz-sim 8.15.0, a reviewed companion fetched at a pinned commit: a `WorldControl` request with `pause` true on `/world/empty/control`, bridged by ros_gz 1.0.25 as `ros_gz_interfaces/srv/ControlWorld`. `SimulationRunner` advertises `control` (`SimulationRunner.cc:325`). `OnWorldControl` copies the request and calls `OnWorldControlState` (`SimulationRunner.cc:1321-1328`). `OnWorldControlState` appends the control and sets the Boolean reply data to true (`SimulationRunner.cc:1375-1377`). `ProcessWorldControl` calls `SetPaused` with that pause flag (`SimulationRunner.cc:1440-1443`). The reply true means the control was queued. `ControlWorld.srv:3` comments that success means the control was successful; that comment is the ROS reply text. Confirmation is an E2 fresh-sample read-back: after the request returned, a new subscription to `/world/empty/stats` discards its first sample and needs two samples in a row, each arriving at least 40 ms after the one before it, whose `paused` is true, within 600 ms. `PublishStats` copies `currentInfo.paused` (`SimulationRunner.cc:534`). `Step` calls `PublishStats` (`SimulationRunner.cc:1023-1024`) and calls `ProcessMessages` (`SimulationRunner.cc:1063-1064`). The sample that applies a queued pause can still report the previous flag, so the read-back discards the first sample. The statistics publisher is limited to 10 messages per second (`SimulationRunner.cc:806-808`). The fake uses that same queue-then-apply order and a placeholder 100 ms period.

A request that is not answered, a reply `success` false, a world that stays unpaused, or no statistics leaves the e-stop `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held. While paused, `UpdateCurrentInfo` advances simulation time only in the branch that requires the world not paused (`SimulationRunner.cc:423-429`), and the Physics system steps only when not paused (`Physics.cc:1047-1051`). The Run loop does not count a processed iteration while paused; without a network manager it calls `Step` (`SimulationRunner.cc:896-911`).

Freshness is the arrival time. The bridged header is the gz header (`ros_gz_interfaces.cpp:840`). Without a QoS profile the publisher QoS is KeepLast (`bridge_config.cpp:274-279`), so durability stays the default volatile and a late subscriber sees no history. The first sample is discarded and a burst restarts the count. An operator QoS override (`factory.hpp:61-82`) is not covered beyond that rule. It is the paused flag, not a measured standstill.

Neither endpoint exists unless the operator runs ros_gz `parameter_bridge` with the two arguments of `operator_bridges` (`/world/empty/control@ros_gz_interfaces/srv/ControlWorld` and `/world/empty/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics`). The bridge README's service example uses `/world/shapes/control` (`ros_gz_bridge/README.md:261-265`); the example world is `shapes`. The control call (400 ms) and the read-back bound (600 ms) sit inside `estop_latency_ms` 1500. The deployment's gz-sim, ros_gz and gz-transport must be the pinned 8.15.0, 1.0.25 and 13.6.0.

The paused flag holds only for that confirmation window. It is not a lasting measured standstill. No unpause is offered (the orchestrator's SAFE-042 condition). The pause retains trajectory targets: `JointTrajectoryController.stop` calls `cancel_goal_async` and does not wait (`controllers.py:493-498`), and `SetPaused` stores `currentInfo.paused` (`SimulationRunner.cc:1290-1291`) and does not send that cancel. This package cannot show that an unpause clears a trajectory the launch's controller accepted. `mhs.safety.reset` releases the MHS latch and the world stays paused. While the latch is held, `mhs.command` of `x-cap.cambel.joint-states.v1` is refused with `MHS.SAFETY.ESTOP_ENGAGED`, because an extension id is not treated as a read. After reset that read is accepted again and the world stays paused. `UserCommands::PreUpdate` takes an unused `UpdateInfo`, copies `pendingCmds` and calls `Execute` on each command (`UserCommands.cc:669-699`). `UpdateSystems` calls `PreUpdate` (`SimulationRunner.cc:662-684`) from `Step`, which the paused Run loop still calls (`SimulationRunner.cc:896-911`), so a queued world edit is still executed while the world is paused. A queued `multi_step` greater than zero while paused calls `SetPaused` false (`SimulationRunner.cc:1445-1452`). The statistics-publisher comment says the GUI listens for confirmation that pause and play requests were processed (`SimulationRunner.cc:800-805`). Another client's pause-false `ControlWorld` also resumes the world outside this package. `examples/worlds/empty.sdf` loads physics, user-commands, scene-broadcaster and contact (`empty.sdf:68-83`), then a light named sun (`empty.sdf:85`) and a model named `ground_plane` (`empty.sdf:99`). Operator recovery outside MHS, after pending motion is cleared, is the GUI play control or a pause-false `ControlWorld` outside MHS. This package does not offer pause false.

The driver risk is R2. Item 12 would leave a world-pause-only simulator at R0. The served device is a simulated UR arm, and the user item rates the arm R2. The card floor stays the catalogue floor. This package publishes no joint command. `driver.lock.json` keeps `reviewed_by` null. `LICENSE:1` is the MIT License. `ur_gripper_gz/package.xml:14` says BSD. `publish_review` stays `not_required`. No hardware run, simulator run or human review is claimed. Evidence is the fake backend, `contract_checked`.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`, level F0, determinism `none`, `timestep_ms` 0, `realtime_factor` 0, reset `none`, and no snapshot restore. The fake answers the `joint_states` subscription with placeholder zeros and the six `JOINT_ORDER` names, records the world-control service, and publishes `/world/empty/stats` while subscribed. The pause flag is applied after the statistics sample is built. It runs no gz-sim, ros_gz bridge, controller_manager or ROS graph.

## Tags

`ros`, `ros2`, `simulation`, `gazebo`, `ur`, `arm`
