OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.ctu-mrs/mrs_uav_flightforge_simulator

Every fact cites the pinned clone at commit `e4715a8c75aac70a9bcd7f75113746b938139117`.
`upstream_code` refs name `path/in/clone:LINE` (a bounded range where the statement spans adjacent
lines). The same facts are written into `driver.py` (`facts = [...]`); `REFERENCE.md` and
`reference.json` are generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The FlightforgeSimulator component passes the node name `mrs_uav_flightforge_simulator` to its `rclcpp::Node` constructor. | upstream_code | src/flightforge_simulator.cpp:663 |
| The shipped launch starts the component in an empty namespace with the node name `flightforge_simulator`. | upstream_code | launch/flightforge_simulator.launch.py:110-111 |
| The node publishes `rosgraph_msgs::msg::Clock` on the private topic `~/clock_out`. | upstream_code | src/flightforge_simulator.cpp:1185 |
| The shipped launch remaps `~/clock_out` to the absolute `/clock` topic. | upstream_code | launch/flightforge_simulator.launch.py:120 |
| `timerMain` advances `sim_time_` by one clock step (`1/clock_rate`) and publishes a `rosgraph_msgs::msg::Clock` message on every main-timer tick. | upstream_code | src/flightforge_simulator.cpp:1320-1333 |
| The shipped config sets `simulation_rate` to 100.0 Hz and `clock_rate` to 400.0 Hz, with a comment that `clock_rate` should be at least `simulation_rate`. | upstream_code | config/flightforge_simulator.yaml:4-7 |
| `timerMain` calls `publishPoses` after stepping every UAV that has not crashed, once at least one simulation step of sim time has passed since the last step. | upstream_code | src/flightforge_simulator.cpp:1361-1377 |
| The node publishes `geometry_msgs::msg::PoseArray` on the private topic `~/uav_poses_out`. | upstream_code | src/flightforge_simulator.cpp:1187 |
| The shipped launch remaps `~/uav_poses_out` to the private topic `~/uav_poses`. | upstream_code | launch/flightforge_simulator.launch.py:121 |
| `publishPoses` writes the current `sim_time_` into the PoseArray header stamp, the configured world frame name into `frame_id`, and one pose per UAV from its position and attitude. | upstream_code | src/flightforge_simulator.cpp:2412-2441 |
| The shipped config names the world frame `simulator_origin`. | upstream_code | config/flightforge_simulator.yaml:268-271 |
| The shipped uav list contains one UAV named `uav1`. | upstream_code | config/uavs.yaml:1-3 |
| The node registers `yaml_prefix + "paused"` through `dynparam_mgr_->register_param` with `&drs_params_.paused`, the literal `false` and `callbackPause`. | upstream_code | src/flightforge_simulator.cpp:740 |
| `timerInit` sets `drs_params_.paused` to false. | upstream_code | src/flightforge_simulator.cpp:864 |
| `callbackPause` cancels `timer_main_` and `timer_status_` when the paused parameter is true, and recreates both timers when it is false. | upstream_code | src/flightforge_simulator.cpp:2111-2129 |
| `timerInit` constructs one `mrs_multirotor_simulator::UavSystemRos` on this node for every name in `uav_names`. | upstream_code | src/flightforge_simulator.cpp:872-888 |
| `timerInit` creates a `GameModeController` for `LOCALHOST` port 8551 and, while `rclcpp::ok()`, retries `Connect()` every second, logging an error about Unreal's game mode controller. | upstream_code | src/flightforge_simulator.cpp:894-905 |
| `timerInit` creates the `~/clock_out` and `~/uav_poses_out` publisher handlers and then the main wall timer with period `1 / (clock_rate * realtime_factor)`. | upstream_code | src/flightforge_simulator.cpp:1183-1196 |
| The hw_api launch remaps the plugin's simulator command outputs (actuators, control group, attitude rate, attitude, acceleration, velocity, position and tracker commands) to `/flightforge_simulator/<uav_name>/` topics. | upstream_code | launch/hw_api.launch.py:110-124 |
| The hw_api plugin's `callbackArming` stores `armed_` and returns success for both an arm and a disarm request. | upstream_code | src/hw_api_plugin.cpp:360-380 |
| The LICENSE file is the GNU General Public License, version 2. | vendor_doc | LICENSE:1-2 |
| `package.xml` declares the licence `BSD 3-Clause`. | upstream_code | package.xml:12 |

## Scope

This is a configuration-only ROS 2 `RosDriver` over rosbridge with no Python native class and no
`native.py`. The launch starts the component in an empty namespace under the node name
`flightforge_simulator` (`launch/flightforge_simulator.launch.py:110-111`), so the package configures
the resolved endpoints `/clock` (the launch's absolute remap) and
`/flightforge_simulator/uav_poses` (the launch's private remap under that node name). The upstream
tokens `"/clock"` and `"~/uav_poses"` are recorded as `source_name`. A deployment that names or
namespaces the component differently must expose these endpoints at the declared absolute names or
change the driver deliberately; the gate does not prove ROS graph resolution.

Only the two observation topics that the node publishes once it has connected to the FlightForge
binary are exposed. The node creates their publishers after `timerInit` has connected to the
binary on localhost port 8551, which it retries every second while `rclcpp::ok()`
(`src/flightforge_simulator.cpp:894-905`, `1183-1196`); without the running binary, or while the
`paused` parameter is true, both topics are silent and both reads time out. The node also publishes
per-UAV rangefinder, lidar and camera topics at absolute `/<uav_name>/...` names through its own
publishers and `image_transport` (`src/flightforge_simulator.cpp:1079-1094`), and its
`UavSystemRos` objects (from `mrs_multirotor_simulator`, outside the clone) provide per-UAV odometry,
IMU and command interfaces that the hw_api plugin reaches under `/flightforge_simulator/<uav_name>/`
(`launch/hw_api.launch.py:110-124`); those are NOT COVERED. The hw_api plugin
(`src/hw_api_plugin.cpp`, whose `callbackArming` only stores a flag and answers success) and the
external FlightForge binary (an Unreal Engine game) are NOT COVERED.

The `paused` dynamic parameter is NOT COVERED as a command. ROS parameter access is not a
rosbridge opcode, and the clone does not declare the parameter-service type, so this package does
not invent a source-cited parameter-service binding. Its callback would cancel the main and status
timers (`src/flightforge_simulator.cpp:2111-2129`), but no ROS service or action exposes it in the
pinned source.

## Safety

The device is simulated at R0: the package only observes simulated clock and pose state and has no
physical effect. The pinned clone creates no ROS service or action server, so the package declares
no e-stop or safe-state binding. The stock e-stop therefore latches the observation profile and
reports the software-only safe state (`software_only`); it makes no claim that the simulator, the
external FlightForge process or any ROS publisher stopped. The extension observation capabilities remain
latched even though their action verb is `read`, because the server does not trust an extension
verb as a latch exemption. No physical emergency stop exists or is claimed.

## Fidelity

The deployed fake is a ROS-free `RecordingRosTransport` with canned placeholder replies, not a
capture of live ROS traffic and not the FlightForge simulator. `driver.py` records engine
`analytic:ROS-free contract fake with canned placeholder replies (no physics)`, level F0,
determinism `none`, `timestep_ms: 0`, `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The shipped 100 Hz simulation and 400 Hz clock rates are source facts about the
upstream node, not claims about the fake. The fake answers one `/clock` sample and one one-pose
`/flightforge_simulator/uav_poses` sample with placeholder values; it runs no FlightForge process,
physics, sensors, renderer, wall-clock loop or ROS graph. A live run must receive the upstream
node's own samples.

## Licence

The card records GPL-2.0 and `publish_review: not_required`, but the clone is inconsistent: the
LICENSE file is the GNU GPL version 2 (`LICENSE:1-2`) while `package.xml` declares `BSD 3-Clause`
(`package.xml:12`). The owner decides before publication.

## Tags

`ros`, `ros2`, `simulation`, `flightforge`, `uav`, `clock`, `pose`
