# Facts and tags for gh.linorobot/linorobot2

Facts about the package's own surface cite the pinned clone at commit `f6b0bd0350c4a9d6b815ef4bb5c701a1e5129711` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gz_sim` (gh.gazebosim/gz-sim, fetched under work/companions as `gazebosim__gz-sim@gz-sim8_8.15.0` at `446a44335a45b704b4d36dabcc5508ee34eeb3d8`), `ros_gz` (gh.gazebosim/ros_gz, fetched under work/companions as `gazebosim__ros_gz@1.0.25` at `b87d7523400a695a10d47ca7b8cb5fa86d5b8d9d`) and `gz_transport` (gh.gazebosim/gz-transport, fetched under work/companions as `gazebosim__gz-transport@gz-transport13_13.6.0` at `35fef7ea10c2e133498e9010bd2e397a0ce0c3bf`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, the LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The Gazebo launch bridges /clock (rosgraph_msgs/Clock), /cmd_vel (geometry_msgs/Twist), /odom/unfiltered (nav_msgs/Odometry), /imu/data (sensor_msgs/Imu), /joint_states (sensor_msgs/JointState) and /scan (sensor_msgs/LaserScan) between ROS 2 and Gazebo. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:140-145 |
| diff_drive.urdf.xacro uses the gz-sim DiffDrive system with command topic cmd_vel and odometry topic odom/unfiltered. | upstream_code | linorobot2_description/urdf/controllers/diff_drive.urdf.xacro:4-10 |
| skid_steer.urdf.xacro also uses the gz-sim DiffDrive system with command topic cmd_vel and odometry topic odom/unfiltered. | upstream_code | linorobot2_description/urdf/controllers/skid_steer.urdf.xacro:4-10 |
| omni_drive.urdf.xacro uses the gz-sim MecanumDrive system with command topic cmd_vel and odometry topic odom/unfiltered. | upstream_code | linorobot2_description/urdf/controllers/omni_drive.urdf.xacro:4-10 |
| The DiffDrive plugin is configured with an odom_publish_frequency of 50 Hz. | upstream_code | linorobot2_description/urdf/controllers/diff_drive.urdf.xacro:16 |
| The command_timeout node creates a geometry_msgs/Twist publisher and subscription on the relative cmd_vel topic and a 0.2 s timer. | upstream_code | linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:21-35 |
| When at least 2e8 ns have passed since prev_cmd_time_ and zero_cmd_sent_ is false, the command_timeout brake timer sets zero_cmd_sent_ and publishes one Twist with linear.x, linear.y and angular.z set to 0.0. | upstream_code | linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:37-48 |
| The command_timeout twist callback ignores an all-zero command and otherwise refreshes prev_cmd_time_ and clears zero_cmd_sent_. | upstream_code | linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:50-55 |
| The command_timeout node creates a publisher, a subscription and a timer only; it creates no ROS service or action server. | upstream_code | linorobot2_gazebo/linorobot2_gazebo/command_timeout.py:21-35 |
| The ros_gz_bridge parameter_bridge argument list contains topic bridges only; it declares no service or action bridge. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:136-157 |
| The Gazebo launch starts the command_timeout node unconditionally and passes it no parameters. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:159-163 |
| The EKF consumes odom/unfiltered and imu/data and runs at 50 Hz. | upstream_code | linorobot2_base/config/ekf.yaml:3-24 |
| The generic laser publishes 360 rays at 10 Hz with a 0.08 m to 12.0 m range on the scan topic. | upstream_code | linorobot2_description/urdf/sensors/generic_laser.urdf.xacro:6-14 |
| The laser sensor writes the configured topic_name and update_rate into the Gazebo sensor topic and update_rate. | upstream_code | linorobot2_description/urdf/sensors/laser.urdf.xacro:47-53 |
| The simulated IMU publishes on imu/data at 50 Hz. | upstream_code | linorobot2_description/urdf/sensors/imu.urdf.xacro:16-22 |
| The RGBD camera sensor is a 640x480 R8G8B8 rgbd_camera publishing on the camera topic at 30 Hz. | upstream_code | linorobot2_description/urdf/sensors/depth_sensor.urdf.xacro:56-69 |
| The camera bridge entries declare sensor_msgs/Image for the color and depth topics and remap them to /camera/color/image_raw and /camera/depth/image_rect_raw. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:146-156 |
| The documentation states that all firmware for the base microcontroller is maintained in the linorobot2_hardware repository. | vendor_doc | docs/base_controller.md:35 |
| The documentation states that the Gazebo plugins replace the microcontroller so the rest of the stack sees the same interface. | vendor_doc | docs/base_controller.md:85-87 |
| The Gazebo launch declares the world_name argument with the default turtlebot3_world. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:66-69 |
| turtlebot3_world.sdf names its world turtlebot3_world. | upstream_code | linorobot2_gazebo/worlds/turtlebot3_world.sdf:11 |
| playground.sdf names its world playground. | upstream_code | linorobot2_gazebo/worlds/playground.sdf:11 |
| The docker gazebo service launches the world named by WORLD, playground by default. | vendor_doc | docs/docker.md:322 |
| The Gazebo launch starts the gz-sim server with -r and -s, and a separate GUI client when gui is true. | upstream_code | linorobot2_gazebo/launch/gazebo.launch.py:107-120 |
| The Nav2 collision monitor publishes its output on cmd_vel. | upstream_code | linorobot2_navigation/config/navigation.yaml:302-303 |
| The README lists a Jazzy and a Lyrical branch. | vendor_doc | README.md:8-9 |
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
| DiffDrive's PreUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:451-453 |
| DiffDrive's PostUpdate returns early while paused. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:501-503 |
| DiffDrive's cmd_vel callback stores the received Twist as its target velocity while enabled. | upstream_code | companion:gz_sim/src/systems/diff_drive/DiffDrive.cc:637-644 |
| MecanumDrive's cmd_vel callback stores the received Twist as its target velocity. | upstream_code | companion:gz_sim/src/systems/mecanum_drive/MecanumDrive.cc:672-676 |
| The IMU system updates and publishes only when not paused. | upstream_code | companion:gz_sim/src/systems/imu/Imu.cc:145-146 |
| The bridge maps ros_gz_interfaces/srv/ControlWorld to a gz.msgs.WorldControl request with a gz.msgs.Boolean reply. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:42-52 |
| The ControlWorld response's success is the gz Boolean reply's data. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:134-141 |
| For a failed gz request the ControlWorld response's success is false. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factories/ros_gz_interfaces.cpp:170-178 |
| The service bridge converts each ROS request and sends it with gz Request and a callback that sends the ROS response. | upstream_code | companion:ros_gz/ros_gz_bridge/src/service_factory.hpp:56-86 |
| Node::Request with a callback requests a service using a non-blocking call. | upstream_code | companion:gz_transport/include/gz/transport/Node.hh:662-677 |
| The WorldStatistics conversion copies the gz header into the ROS header and copies paused. | upstream_code | companion:ros_gz/ros_gz_bridge/src/convert/ros_gz_interfaces.cpp:840-844 |
| ros_gz_interfaces WorldStatistics carries a header, sim_time, pause_time, real_time and the paused flag. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldStatistics.msg:1-14 |
| ControlWorld takes a WorldControl request and answers bool success. | upstream_code | companion:ros_gz/ros_gz_interfaces/srv/ControlWorld.srv:1-3 |
| WorldControl's fields include pause, step and multi_step. | upstream_code | companion:ros_gz/ros_gz_interfaces/msg/WorldControl.msg:1-3 |
| The bridge README maps ros_gz_interfaces/msg/WorldStatistics to gz.msgs.WorldStatistics. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:52 |
| The bridge README maps the ros_gz_interfaces/srv/ControlWorld service to gz.msgs.WorldControl and gz.msgs.Boolean. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:86 |
| The bridge README's service example starts parameter_bridge with a /world/<name>/control ControlWorld argument. | vendor_doc | companion:ros_gz/ros_gz_bridge/README.md:261-265 |
| Without a configured QoS profile the bridge's publisher QoS is KeepLast with the publisher queue size. | upstream_code | companion:ros_gz/ros_gz_bridge/src/bridge_config.cpp:274-279 |
| The bridge's publisher allows its deadline, depth, durability, history, liveliness and reliability QoS to be overridden. | upstream_code | companion:ros_gz/ros_gz_bridge/src/factory.hpp:61-82 |

## Scope

The package is a configuration-only ROS 2 `RosDriver` over the topic graph the pinned launch and robot description
create in Gazebo. It declares the simulated mobile-base velocity publication on `/cmd_vel` (`geometry_msgs/msg/Twist`)
and the explicit reads of raw wheel odometry on `/odom/unfiltered`, the simulation clock on `/clock`, the IMU on
`/imu/data` and the default lidar on `/scan`. These declarations cite the ros_gz_bridge argument list, the pinned text
that names the absolute ROS endpoints and their ROS 2 message types. The device resource reads no topic (see Safety).

The gz-sim DiffDrive/MecanumDrive plugins are the simulated base controllers. The physical microcontroller firmware is
in a different repository and is not bound here. The camera image and point-cloud topics are described in the clone's
launch but are **NOT COVERED** by this package. The endpoints name the launch's default world `turtlebot3_world`; the
docker `gazebo` service defaults to the `playground` world, and with any other world the declared endpoints do not
exist and the e-stop fails closed (a run-time world name, E5, is not implemented).

## Limits

The clone states no numeric bound for the `Twist.linear.x` or `Twist.angular.z` accepted by the drive plugins. The
joystick scales in `joy.yaml` and the Nav2 velocity-smoother limits in `navigation.yaml` are client/navigation
settings, not the plugin's accepted range, so both inputs are `Limit.operator_required`. `site-limits.example.json` is
an explicitly illustrative operator overlay for the fake run; it is not a device fact and is not an installed robot
limit.

## Safety

The e-stop is the world pause of the simulator's own repository, a reviewed companion fetched at a pinned commit:
a WorldControl request with `pause` true on `/world/turtlebot3_world/control` (gz-sim 8.15.0, Harmonic; `OnWorldControl` forwards it to
`OnWorldControlState`, which queues it and answers true, and `ProcessWorldControl` calls `SetPaused` in the step
loop), bridged by ros_gz 1.0.25 (Jazzy) as `ros_gz_interfaces/srv/ControlWorld` (its `success` is the Boolean reply, and
false for a failed request). The reply is true for any request the simulator queued, so it confirms nothing. The stop
is confirmed by a fresh-sample topic read-back (E2): after the request returned, a new subscription to `/world/turtlebot3_world/stats`
discards its first sample and needs two samples in a row, each arriving at least 40 ms after the one before it, whose
`paused` is true, within 600 ms (`PublishStats` copies `currentInfo.paused` into `WorldStatistics`, and the statistics
are throttled to 10 per second). A request that is not answered, a reply `success` false, a world that keeps running
(another client), no statistics (no bridge) or a burst of samples (a history replayed on subscribe) leaves the e-stop
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry. While paused the simulator does not
advance its simulation time or step the physics, and DiffDrive (and MecanumDrive) returns early from its updates.

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

The declared re-enable `x-cap.linorobot.resume.v1` (CORE-086) publishes a zero Twist on `/cmd_vel` and then sends a
WorldControl request with `pause` false. DiffDrive stores the last Twist it received and applies it as soon as the
world runs, and the bridge forwards `/cmd_vel` while the world is paused, so the zero replaces a command stored before
or during the pause (the orchestrator's SAFE-042 condition). It is an unacknowledged publication, so a stored command
can still act for a few world steps; the clone's `command_timeout` node also publishes one zero Twist 0.2 s after the
last nonzero command, on the wall clock (it is launched without `use_sim_time`). Nav2's collision monitor and the
joystick teleop may publish new commands. The world resumes from the state it paused in, body velocities included.
The reset only releases the latch; the world stays paused until the resume.

While paused, DiffDrive does not publish `/odom/unfiltered` and the IMU system does not publish `/imu/data`, and the
sensors update on simulation time, which a paused world does not advance; their reads fail `NOT_READY` after their
timeouts. They left the device resource, which reads no topic, so a reset device stays readable and commands do not
wait for them; the cmd_vel receipt reports the two values it sent (TCAP-003). `/clock` keeps the frozen time.

`/cmd_vel` is also the physical robot's command topic: `linorobot2_bringup` starts `micro_ros_agent` on
`/dev/ttyACM0` by default and can start a joystick teleop, and the documentation says Gazebo preserves the
microcontroller's interface (`docs/base_controller.md:85-87`). On a hardware graph no world exists and the e-stop
fails closed; the R2 risk reflects that path. `driver.lock.json` keeps `reviewed_by: null`; no physical emergency stop,
hardware run or human review is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free contract fake (no Gazebo physics)`, level F0,
determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake answers
canned observations and echoes the last commanded twist in raw odometry as a placeholder; it runs no physics, plugin,
EKF or sensor. It keeps a paused flag that the world control request sets after its next statistics sample, publishes
the world statistics every 100 ms (placeholder) while subscribed, and silences the odometry, IMU and scan while
paused. The real LaserScan has 360 rays; the fake returns a reduced placeholder array.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `mobile-base`, `cmd-vel`, `odometry`
