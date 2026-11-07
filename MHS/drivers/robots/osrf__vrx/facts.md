OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.osrf/vrx

Facts about the package's own surface cite the pinned clone at commit `7609d1bd90ce7edb29d040a082f949e8b089c864` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gz_sim` (gh.gazebosim/gz-sim, fetched under work/companions as `gazebosim__gz-sim@gz-sim8_8.15.0` at `446a44335a45b704b4d36dabcc5508ee34eeb3d8`), `ros_gz` (gh.gazebosim/ros_gz, fetched under work/companions as `gazebosim__ros_gz@1.0.25` at `b87d7523400a695a10d47ca7b8cb5fa86d5b8d9d`) and `gz_transport` (gh.gazebosim/gz-transport, fetched under work/companions as `gazebosim__gz-transport@gz-transport13_13.6.0` at `35fef7ea10c2e133498e9010bd2e397a0ce0c3bf`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, the LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README.md states that the repository is ported to Gazebo Harmonic and ROS 2 Jazzy. | upstream_code | README.md:14-16 |
| competition_bridges always includes the clock and task_info bridges in its bridge list. | upstream_code | vrx_gz/src/vrx_gz/launch.py:255-259 |
| competition_bridges constructs one ros_gz_bridge parameter_bridge Node with the arguments and remappings of its bridge list. | upstream_code | vrx_gz/src/vrx_gz/launch.py:311-318 |
| bridges.clock maps Gazebo /clock to ROS /clock as rosgraph_msgs/msg/Clock with the GZ_TO_ROS direction. | upstream_code | vrx_gz/src/vrx_gz/bridges.py:88-94 |
| bridges.task_info maps Gazebo /vrx/task/info to ROS /vrx/task/info as ros_gz_interfaces/msg/ParamVec with the GZ_TO_ROS direction. | upstream_code | vrx_gz/src/vrx_gz/bridges.py:96-102 |
| ScoringPlugin defaults its task-info topic to /vrx/task/info. | upstream_code | vrx_gz/src/ScoringPlugin.cc:80 |
| ScoringPlugin advertises a Gazebo msgs::Param publisher on the task-info topic. | upstream_code | vrx_gz/src/ScoringPlugin.cc:441-442 |
| ScoringPlugin::UpdateTaskMessage sets state, elapsed_time, remaining_time, timed_out, num_collisions and score, and PublishStats publishes them at 1 Hz. | upstream_code | vrx_gz/src/ScoringPlugin.cc:314-336 |
| Model.is_UAV recognizes vrx_hexrotor and vrx_quadrotor, while Model.is_USV recognizes usv and wam-v. | upstream_code | vrx_gz/src/vrx_gz/model.py:36-44 |
| Model.is_UAV returns whether the model type is in UAVS and is_USV whether it is in USVS. | upstream_code | vrx_gz/src/vrx_gz/model.py:60-64 |
| Model.bridges appends cmd_vel only inside the is_UAV branch; the is_USV branch performs no command bridge. | upstream_code | vrx_gz/src/vrx_gz/model.py:81-93 |
| launch.spawn places the bridge and helper nodes in a PushRosNamespace(model.model_name) group. | upstream_code | vrx_gz/src/vrx_gz/launch.py:384-387 |
| competition.launch.py defaults the spawned robot name to wamv and its model type to wam-v. | upstream_code | vrx_gz/launch/competition.launch.py:112-119 |
| launch.simulation starts ros_gz_sim's gz_sim launch and passes -r unless the launch was given paused; the paused flag is a launch argument, not a ROS service. | upstream_code | vrx_gz/src/vrx_gz/launch.py:214-230 |
| Model.payload_from_sdf records each gz::sim::systems::Thruster and JointPositionController plugin as a thruster_thrust_<name> or thruster_rotate_<name> payload entry. | upstream_code | vrx_gz/src/vrx_gz/model.py:296-313 |
| payload_bridges dispatches thruster_thrust_* entries to thrust() and thruster_rotate_* entries to thrust_joint_pos(). | upstream_code | vrx_gz/src/vrx_gz/payload_bridges.py:229-236 |
| payload_bridges.thrust maps ROS thrusters/<side>/thrust to Gazebo <model>/thrusters/<side>/thrust as std_msgs/msg/Float64 with the ROS_TO_GZ direction. | upstream_code | vrx_gz/src/vrx_gz/payload_bridges.py:152-158 |
| payload_bridges.thrust_joint_pos maps ROS thrusters/<side>/pos to Gazebo <model>/thrusters/<side>/pos as std_msgs/msg/Float64 with the ROS_TO_GZ direction. | upstream_code | vrx_gz/src/vrx_gz/payload_bridges.py:160-172 |
| The shipped wamv.yaml teleop configuration names /wamv/thrusters/left/thrust with std_msgs/msg/Float64. | upstream_code | vrx_gz/config/wamv.yaml:80-81 |
| The shipped wamv.yaml teleop configuration names /wamv/thrusters/right/thrust with std_msgs/msg/Float64. | upstream_code | vrx_gz/config/wamv.yaml:91-92 |
| The shipped wamv.yaml teleop configuration names /wamv/thrusters/left/pos with std_msgs/msg/Float64. | upstream_code | vrx_gz/config/wamv.yaml:102-103 |
| The shipped wamv.yaml teleop configuration names /wamv/thrusters/right/pos with std_msgs/msg/Float64. | upstream_code | vrx_gz/config/wamv.yaml:113-114 |
| The WAM-V thruster macro configures gz-sim-thruster-system on topic thrusters/<name>/thrust with velocity_control true. | upstream_code | vrx_urdf/wamv_gazebo/urdf/thruster_layouts/wamv_gazebo_thruster_config.xacro:10-24 |
| The WAM-V thruster macro configures gz-sim-joint-position-controller-system on topic <namespace>/thrusters/<name>/pos. | upstream_code | vrx_urdf/wamv_gazebo/urdf/thruster_layouts/wamv_gazebo_thruster_config.xacro:26-34 |
| competition.launch.py declares the world argument with the default sydney_regatta. | upstream_code | vrx_gz/launch/competition.launch.py:68-71 |
| sydney_regatta.sdf names its world sydney_regatta. | upstream_code | vrx_gz/worlds/sydney_regatta.sdf:4 |
| navigation_task.sdf also names its world sydney_regatta. | upstream_code | vrx_gz/worlds/navigation_task.sdf:4 |
| The sydney_regatta GUI configuration loads the WorldControl plugin with play/pause and step enabled. | upstream_code | vrx_gz/worlds/sydney_regatta.sdf:115-134 |
| ScoringPlugin's PreUpdate updates the time from the simulation time, updates the task state and calls PublishStats. | upstream_code | vrx_gz/src/ScoringPlugin.cc:463-478 |
| ScoringPlugin's PublishStats publishes the task message once per second of the plugin's current time. | upstream_code | vrx_gz/src/ScoringPlugin.cc:327-337 |
| The README names a humble branch for users who continue with Gazebo Garden and ROS 2 Humble. | vendor_doc | README.md:18 |
| SimulationRunner composes its transport namespace as /world/ followed by the world name. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:249 |
| SimulationRunner advertises the control service with OnWorldControl as its callback. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:325 |
| OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1321-1328 |
| OnWorldControlState appends the control to worldControls and sets the Boolean reply to true. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1375-1377 |
| ProcessWorldControl calls SetPaused with the pause flag of each queued control. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1440-1443 |
| A queued control with multi_step on a paused world adds the steps and unpauses the world so that stepping can occur. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1445-1452 |
| SetPaused stores the pause state in currentInfo.paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1290-1291 |
| Step publishes the world statistics. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1023-1024 |
| Step processes the world control messages. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1063-1064 |
| The Run loop calls Step on every iteration and counts a processed iteration only while not paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:896-911 |
| The statistics publisher on the stats topic is limited to 10 messages per second. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:806-808 |
| PublishStats copies currentInfo.paused into the WorldStatistics message. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:534 |
| UpdateCurrentInfo advances the simulation time and the iteration count only while not paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:423-429 |
| The Physics system steps the physics only when not paused. | upstream_code | companion:gz_sim/src/systems/physics/Physics.cc:1047-1051 |
| The Thruster system's thrust callback stores the clamped thrust command. | upstream_code | companion:gz_sim/src/systems/thruster/Thruster.cc:517-526 |
| The Thruster system's PreUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/thruster/Thruster.cc:634-639 |
| The joint position controller's position callback stores the commanded position. | upstream_code | companion:gz_sim/src/systems/joint_position_controller/JointPositionController.cc:489-492 |
| The joint position controller's PreUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/joint_position_controller/JointPositionController.cc:395-397 |
| The bridge maps ros_gz_interfaces/srv/ControlWorld to a gz.msgs.WorldControl request with a gz.msgs.Boolean reply. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:42-52 |
| The ControlWorld response's success is the gz Boolean reply's data. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:134-141 |
| For a failed gz request the ControlWorld response's success is false. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:170-178 |
| The service bridge converts each ROS request and sends it with gz Request and a callback that sends the ROS response. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factory.hpp:56-86 |
| Node::Request with a callback requests a service using a non-blocking call. | upstream_code | companion:gz_transport/include/gz/transport/Node.hh:662-677 |
| The WorldStatistics conversion copies the gz header into the ROS header and copies paused. | upstream_code | companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp:840-844 |
| ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldStatistics.msg:1-14 |
| ControlWorld takes a WorldControl request and answers bool success. | upstream_code | companion:ros_gz/ros_gz_interfaces/srv/ControlWorld.srv:1-3 |
| WorldControl's fields include pause, step and multi_step. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldControl.msg:1-3 |
| ros_gz_interfaces ParamVec carries a header and rcl_interfaces Parameter entries. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/ParamVec.msg:3-7 |
| The bridge README maps ros_gz_interfaces/msg/WorldStatistics to gz.msgs.WorldStatistics. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:52 |
| The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to gz.msgs.WorldControl and gz.msgs.Boolean. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:86 |
| The bridge README's service example starts parameter_bridge with a /world/<name>/control ControlWorld argument. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:261-265 |
| Without a configured QoS profile the bridge's publisher QoS is KeepLast with the publisher queue size. | upstream_code | companion:ros_gz/ros_gz_bridge/src/bridge_config.cpp:274-279 |
| The bridge's publisher allows its deadline, depth, durability, history, liveliness and reliability QoS to be overridden. | upstream_code | companion:ros_gz/ros_gz_bridge/src/factory.hpp:61-82 |

## Scope

The package is a configuration-only ROS 2 `RosDriver` over the competition bridge that
`vrx_gz.launch.competition_bridges` always starts: the simulated clock (`/clock`) and the scoring plugin's task
information (`/vrx/task/info`, `ros_gz_interfaces/msg/ParamVec`). It also declares the ROS command surface that the
shipped WAM-V launch creates for the two aft thrusters and their joint position controllers
(`/wamv/thrusters/{left,right}/{thrust,pos}`, `std_msgs/msg/Float64`, bridged ROS to Gazebo). Each command's receipt
reports the value it handed to rosbridge; the device resource reads no topic (the earlier command-echo reads
subscribed to command topics that nothing publishes on a schedule). The `/wamv` namespace assumes the default model
name. The endpoints of the stop name the default world `sydney_regatta` (navigation_task.sdf reuses the name); the
other task worlds carry their own names, and with them the declared endpoints do not exist and the e-stop fails
closed (a run-time world name, E5, is not implemented). The clock read reports the ROS 2 `builtin_interfaces/Time`
fields `sec` and `nanosec`.

## Limits

The pinned clone states no numeric range or unit for the Float64 thruster or joint-position commands, so all four
inputs are `Limit.operator_required`; `site-limits.example.json` is example operator data, not a device fact.

## Safety

The e-stop is the world pause of the simulator's own repository, a reviewed companion fetched at a pinned commit:
a WorldControl request with `pause` true on `/world/sydney_regatta/control` (gz-sim 8.15.0, Harmonic; `OnWorldControl` forwards it to
`OnWorldControlState`, which queues it and answers true, and `ProcessWorldControl` calls `SetPaused` in the step
loop), bridged by ros_gz 1.0.25 (Jazzy) as `ros_gz_interfaces/srv/ControlWorld` (its `success` is the Boolean reply, and
false for a failed request). The reply is true for any request the simulator queued, so it confirms nothing. The stop
is confirmed by a fresh-sample topic read-back (E2): after the request returned, a new subscription to `/world/sydney_regatta/stats`
discards its first sample and needs two samples in a row, each arriving at least 40 ms after the one before it, whose
`paused` is true, within 600 ms (`PublishStats` copies `currentInfo.paused` into `WorldStatistics`, and the statistics
are throttled to 10 per second). A request that is not answered, a reply `success` false, a world that keeps running
(another client), no statistics (no bridge) or a burst of samples (a history replayed on subscribe) leaves the e-stop
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry. While paused the simulator does not
advance its simulation time or step the physics, and the Thruster system returns early from its updates.

Freshness is the arrival time only: the bridged `WorldStatistics` header is the simulator's header, which
`PublishStats` does not stamp, so no producer stamp shows when a sample was made. By default the bridge's publisher
QoS sets only KeepLast with its queue size, so its durability stays rclcpp's default, volatile, which replays no
history to a late subscriber; the first sample is discarded and a sample that arrives less than 40 ms after
the previous one restarts the count (a live stream arrives at most 10 per second); a QoS override of the stats
publisher to a deeper transient-local history is not covered beyond that burst rule. It is the paused flag in that
window, not a measured standstill: the GUI, a WorldControl `multi_step` (which unpauses a paused world to step it) or
any client of the control service can unpause or step the world, and MHS does not watch the flag after the e-stop.

Neither endpoint exists unless the operator runs ros_gz's `parameter_bridge` with the two arguments of
`operator_bridges` (`REFERENCE.md`, "Operator must run"); the clone's own bridge carries topics only. Without them the
control call is not answered and the read-back sees no sample, so the e-stop fails closed. The control call (400 ms)
and the read-back bound (600 ms) add up to the default 1000 ms budget and leave no margin for the bridge, so the
package declares `estop_latency_ms = 1500` (gate G3 checks the arithmetic). The deployment's simulator and ros_gz must be the pinned
releases; rosbridge cannot read their versions.

No unpause is offered, neither as a re-enable nor as an ordinary command (the orchestrator's SAFE-042 condition). The
Thruster system stores the last thrust command (`Thruster.cc:517-526`) and each joint position controller the last
angle target (`JointPositionController.cc:489-492`), and buoyancy, waves and wind act on the hull as soon as the world
steps. A zero thrust on both sides would replace the stored thrust only unacknowledged, and a stored angle target
cannot be cleared without a joint reading this package does not have. After `mhs.safety.reset` the world stays paused
and commands sent then are stored for the next unpause. The operator recovers outside MHS: publish zero thrust on both
sides (and the wanted angles), stop the joystick teleop if it runs (it publishes on the same four topics,
`wamv.yaml:75-119`), then unpause with the GUI's play button or a ControlWorld request with `pause` false.

While paused, the scoring plugin publishes no task information (it publishes once per second of simulation time), so
the task-info read fails `NOT_READY`; `/clock` keeps the frozen time. `driver.lock.json` keeps `reviewed_by: null`;
no hardware run or human review is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake answers the clock and task
information subscriptions (with the rcl_interfaces parameter types: string 4, bool 1, integer 2, double 3) and records
the four thruster publications; it runs no physics, thruster system, buoyancy, waves or wind. It keeps a paused flag
that the world control request sets after its next statistics sample, publishes the world statistics every 100 ms
(placeholder) while subscribed, and silences the task information while paused.

## Tags

`ros`, `ros2`, `simulation`, `gazebo`, `vrx`, `usv`, `clock`, `task-info`, `thrusters`
