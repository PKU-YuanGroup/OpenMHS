# Facts and tags for gh.rigbetellabs/tortoisebot

Facts about the package's own surface cite the pinned clone at commit `eae9f74a17213adb4dcc8552d65236d5549ebf62` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gz_sim` (gh.gazebosim/gz-sim, fetched under work/companions as `gazebosim__gz-sim@ignition-gazebo6_6.18.0` at `b90cd2c41a193102d6951857c2d83e13f59bb64b`) and `ros_gz` (gh.gazebosim/ros_gz, fetched under work/companions as `gazebosim__ros_gz@0.244.27` at `856e319ee4da713609b3f6e58c74ac8db7662482`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, the LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The ros_gz_bridge parameter_bridge declares /cmd_vel as geometry_msgs/msg/Twist in the ROS to Ignition direction, /odom as nav_msgs/msg/Odometry and /clock as rosgraph_msgs/msg/Clock in the Ignition to ROS direction. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:74-76 |
| The launch script binds the scan endpoint name /scan. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:34 |
| The ros_gz_bridge declares the scan bridge as sensor_msgs/msg/LaserScan. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:78 |
| The Ignition DiffDrive system plugin takes its commands from the /cmd_vel topic and names /odom as its odometry topic. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:24-35 |
| The Ignition DiffDrive system names frame_id odom and child_frame_id base_link. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:49-50 |
| The DiffDrive system declares max_linear_velocity 0.23 and min_linear_velocity -0.23 m/s. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:37-38 |
| The DiffDrive system declares max_angular_velocity 1.5 and min_angular_velocity -1.5 rad/s. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:39-40 |
| The DiffDrive system configures wheel_separation 0.17186 m and wheel_radius 0.0325 m. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:31-32 |
| The DiffDrive system publishes odometry at 50 Hz. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:51 |
| The gpu_lidar sensor ydlidar has update_rate 10.0 and topic /scan. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:86-90 |
| The gpu_lidar sensor publishes 360 horizontal samples between -3.14159 and 3.14159 rad with a 0.3 to 12.0 m range and 0.01 m resolution. | upstream_code | tortoisebot_gazebo/gazebo/tortoisebot_ignition.gazebo:85-113 |
| The README states that TortoiseBot uses Ignition Fortress as its simulation backend. | vendor_doc | README.md:38 |
| The real-robot firmware script differential.py imports RPi.GPIO and defines the motor enable and direction pins. | upstream_code | tortoisebot_firmware/scripts/differential.py:6-16 |
| The Differential node subscribes Twist on cmd_vel and publishes lpwm, rpwm, ldir and rdir. | upstream_code | tortoisebot_firmware/scripts/differential.py:102-111 |
| The Differential callback computes the wheel velocities from linear.x and angular.z and calls stop when both are zero, otherwise wheel_vel_executer. | upstream_code | tortoisebot_firmware/scripts/differential.py:113-130 |
| autobringup.launch.py starts tortoisebot_firmware's differential.py as node differential unless use_sim_time is set. | upstream_code | tortoisebot_bringup/launch/autobringup.launch.py:76-82 |
| The Ignition launch's default world is worlds/nav2_test_world.sdf. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:22 |
| nav2_test_world.sdf names its world default. | upstream_code | tortoisebot_gazebo/worlds/nav2_test_world.sdf:4 |
| room2.sdf names its world default. | upstream_code | tortoisebot_gazebo/worlds/room2.sdf:2 |
| The launch's joint-state bridge reads /world/default/model/tortoisebot/joint_state. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:99-102 |
| The launch runs ign gazebo -r with the GUI when gui is true and with -s when it is false. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:111-121 |
| The launch's main bridge sets QoS overrides for its /tf_static, /scan and /odom publishers. | upstream_code | tortoisebot_gazebo/launch/ignition_sim.launch.py:86-91 |
| The README names ROS 2 Humble. | vendor_doc | README.md:1 |
| SimulationRunner composes its transport namespace as /world/ followed by the world name. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:122 |
| SimulationRunner advertises the control service with OnWorldControl as its callback. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:214 |
| OnWorldControl copies the WorldControl request into a WorldControlState and calls OnWorldControlState. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1120-1127 |
| OnWorldControlState appends the control to worldControls and sets the Boolean reply to true. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1174-1176 |
| ProcessWorldControl calls SetPaused with the pause flag of each queued control. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1239-1242 |
| A queued control with multi_step on a paused world adds the steps and unpauses the world so that stepping can occur. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1244-1251 |
| SetPaused stores the pause state in currentInfo.paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:1088-1089 |
| Step publishes the world statistics. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:826-827 |
| Step processes the world control messages. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:867-868 |
| The Run loop calls Step on every iteration and counts a processed iteration only while not paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:732-746 |
| The statistics publisher on the stats topic is limited to 10 messages per second. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:649-651 |
| PublishStats copies currentInfo.paused into the WorldStatistics message. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:430 |
| UpdateCurrentInfo advances the simulation time and the iteration count only while not paused. | upstream_code | companion:gz_sim/src/SimulationRunner.cc:345-350 |
| The Physics system steps the physics only when not paused. | upstream_code | companion:gz_sim/src/systems/physics/Physics.cc:855-859 |
| DiffDrive's PreUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:450-452 |
| DiffDrive's PostUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:518-520 |
| DiffDrive's cmd_vel callback stores the received Twist as its target velocity while enabled. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:654-661 |
| The bridge maps ros_gz_interfaces/srv/ControlWorld to an ignition.msgs.WorldControl request with an ignition.msgs.Boolean reply. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:42-52 |
| The ControlWorld response's success is the Boolean reply's data. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:134-141 |
| For a failed request the ControlWorld response's success is false. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:170-178 |
| The service bridge converts each ROS request and sends it with Request and a callback that sends the ROS response. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factory.hpp:56-86 |
| The WorldStatistics conversion copies the Ignition header into the ROS header and copies paused. | upstream_code | companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp:823-827 |
| ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldStatistics.msg:1-14 |
| ControlWorld takes a WorldControl request and answers bool success. | upstream_code | companion:ros_gz/ros_gz_interfaces/srv/ControlWorld.srv:1-3 |
| WorldControl's fields include pause, step and multi_step. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldControl.msg:1-3 |
| The bridge README maps ros_gz_interfaces/msg/WorldStatistics to ignition.msgs.WorldStatistics. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:55 |
| The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to ignition.msgs.WorldControl and ignition.msgs.Boolean. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:78 |
| The bridge README's service example starts parameter_bridge with a /world/<name>/control ControlWorld argument. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:241-245 |
| The bridge's publisher QoS is KeepLast with the queue size, and its depth, durability, history and reliability may be overridden. | upstream_code | companion:ros_gz/ros_gz_bridge/src/factory.hpp:60-80 |

## Scope

The package is a configuration-only ROS 2 `RosDriver` over the Ignition Gazebo topic graph of the pinned clone: the
velocity publication on `/cmd_vel` (`geometry_msgs/msg/Twist`, bridged ROS to Ignition, capped by the DiffDrive
system's declared limits) and the explicit reads of `/odom`, `/clock` and `/scan`. The device resource reads no topic
(see Safety). The camera stream, the TF tree, Nav2, AMCL and Cartographer are **NOT COVERED**. The endpoints of the
stop name the world `default`, the name of both shipped worlds, which the clone itself composes into
`/world/default/model/tortoisebot/joint_state`.

## Limits

The DiffDrive system declares `max_linear_velocity 0.23`, `min_linear_velocity -0.23`, `max_angular_velocity 1.5` and
`min_angular_velocity -1.5` (`tortoisebot_ignition.gazebo:37-40`); the velocity inputs carry these as sourced
limits.

## Safety

The e-stop is the world pause of the simulator's own repository, a reviewed companion fetched at a pinned commit:
a WorldControl request with `pause` true on `/world/default/control` (ignition-gazebo 6.18.0, Fortress; `OnWorldControl` forwards it to
`OnWorldControlState`, which queues it and answers true, and `ProcessWorldControl` calls `SetPaused` in the step
loop), bridged by ros_gz 0.244.27 (Humble) as `ros_gz_interfaces/srv/ControlWorld` (its `success` is the Boolean reply, and
false for a failed request). The reply is true for any request the simulator queued, so it confirms nothing. The stop
is confirmed by a fresh-sample topic read-back (E2): after the request returned, a new subscription to `/world/default/stats`
discards its first sample and needs two samples in a row, each arriving at least 40 ms after the one before it, whose
`paused` is true, within 600 ms (`PublishStats` copies `currentInfo.paused` into `WorldStatistics`, and the statistics
are throttled to 10 per second). A request that is not answered, a reply `success` false, a world that keeps running
(another client), no statistics (no bridge) or a burst of samples (a history replayed on subscribe) leaves the e-stop
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry. While paused the simulator does not
advance its simulation time or step the physics, and DiffDrive returns early from its updates.

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

The declared re-enable `x-cap.rigbetellabs.resume.v1` (CORE-086) publishes a zero Twist on `/cmd_vel` and then sends
a WorldControl request with `pause` false. DiffDrive stores the last Twist it received and applies it as soon as the
world runs, and the bridge forwards `/cmd_vel` while the world is paused, so the zero replaces a command stored before
or during the pause (the orchestrator's SAFE-042 condition). It is an unacknowledged publication, so a stored command
can still act for a few world steps; the simulation launch has no command timeout, and the teleop keyboard and
`firmware/scripts/1ms.py` also publish `cmd_vel`. The world resumes from the state it paused in, body velocities
included. The reset only releases the latch; the world stays paused until the
resume.

While paused, DiffDrive does not publish `/odom` and the lidar updates on simulation time, which a paused world does
not advance; their reads fail `NOT_READY` after their timeouts. The odometry left the device resource, which reads no
topic, so a reset device stays readable and commands do not wait for it; the velocity receipt reports the two values
it sent. `/clock` keeps the frozen time.

The binding cannot tell the simulation from the real robot: `autobringup.launch.py:76-82` starts `differential.py`,
which drives the Raspberry Pi GPIO motors from the same `cmd_vel` topic, so R2 is right; on the real robot no world
exists and the e-stop fails closed. The card requires an owner's publication decision (`publish_review: required`).
`driver.lock.json` keeps `reviewed_by: null`; no hardware run or human review is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free rosbridge contract fake (no physics)`, level F0,
determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake answers one
fresh subscription per observation with placeholders (an 8-element scan while the sensor declares 360 samples) and
records the velocity publication. It keeps a paused flag that the world control request sets after its next
statistics sample, publishes the world statistics every 100 ms (placeholder) while subscribed, and silences `/odom`
and `/scan` while paused.

## Tags

`ros`, `ros2`, `ignition`, `gazebo`, `simulation`, `tortoisebot`, `cmd-vel`, `odometry`, `clock`, `scan`
