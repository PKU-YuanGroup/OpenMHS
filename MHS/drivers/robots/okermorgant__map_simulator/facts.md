# Facts and tags for gh.okermorgant/map_simulator

Every fact cites the pinned clone at commit `537a06464d7fcaa2cba4f4fea9532f0556854440`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The package provides a 2-D simulator for mobile robots in ROS 2; robots move through a cmd_vel topic and may publish a laser scan. | vendor_doc | README.md:3 |
| The Simulation node advertises a service to spawn robots in, wrapped by the spawn executable. | vendor_doc | README.md:22 |
| The spawn node is run in the same namespace as the robot_description topic, and that namespace is used to publish the robot topics. | vendor_doc | README.md:26 |
| Spawning a robot twice resets only its pose; other parameters are changed by removing and re-spawning the robot. | vendor_doc | README.md:43 |
| The cmd_vel topic is subscribed by the simulator for each robot according to its namespace, and by default the scan topic is used unless a Gazebo plugin names another topic. | vendor_doc | README.md:51-53 |
| Spawn.srv defines SHAPE_SQUARE=0, SHAPE_CIRCLE=1 and SHAPE_RECTANGLE=2, followed by the request members and an empty response after the separator. | upstream_code | srv/Spawn.srv:1-19 |
| SimulatorNode registers the absolute /simulator/spawn service whose callback calls addRobot, and the /simulator/add_anchor service. | upstream_code | src/simulator.cpp:42-50 |
| The SimulatorNode class declares two ROS service members, spawn_srv and anchor_srv, and no other service member. | upstream_code | include/map_simulator/simulator.h:17-44 |
| SimulatorNode::addRobot appends a trailing slash to the requested namespace and, for an existing robot, calls resetTo with the requested pose instead of creating a new robot. | upstream_code | src/simulator.cpp:53-65 |
| Robot::resetTo assigns the requested pose, writes it to initial_pose when that transform has a child frame, and clears odom.pose.pose and odom.twist.twist. | upstream_code | include/map_simulator/robot.h:135-143 |
| Robot::loadModel assigns odom_pub from create_publisher<nav_msgs::msg::Odometry>(robot_namespace + "odom", 10). | upstream_code | src/robot.cpp:214 |
| Robot::loadModel creates a geometry_msgs/Twist subscription on <robot_namespace>cmd_vel; the callback copies only linear.x, linear.y and angular.z into odom.twist.twist. | upstream_code | src/robot.cpp:219-226 |
| parseLaser defaults to 100 samples and the relative scan topic. | upstream_code | src/robot.cpp:131-132 |
| Without a Gazebo ray plugin and with force_scanner true, loadModel sets angle_max=49*M_PI/50, angle_min=-angle_max, range_min=0.1, range_max=5, resizes the ranges array to the sample count and creates the LaserScan publisher. | upstream_code | src/robot.cpp:194-211 |
| SimulatorNode computes dt=1/declare_parameter("rate", 20) and drives refresh from a wall timer. | upstream_code | src/simulator.cpp:17-40 |
| SimulatorNode::refresh calls robot.move(dt) only for connected robots, then recomputes the laser scans and publishes each connected robot. | upstream_code | src/simulator.cpp:114-136 |
| Robot::initFromURDF waits 500 ms and subscribes to <robot_namespace>robot_description with transient-local QoS; the callback calls loadModel with the received description text. | upstream_code | src/robot.cpp:113-126 |
| Robot::move integrates the pose from the stored odom.twist.twist velocities, each passed through withNoise, on every call. | upstream_code | src/robot.cpp:282-293 |
| Robot::publish assigns odom.header.stamp and transform.header.stamp from its now argument and then publishes odom. | upstream_code | src/robot.cpp:74-77 |
| Pose2D::writeTo(geometry_msgs::msg::Pose) assigns pose.position.x, pose.position.y, pose.orientation.w and pose.orientation.z. | upstream_code | include/map_simulator/robot.h:62-67 |
| Robot::move constructs a Pose2D from odom.pose.pose, calls updateFrom and then writeTo(odom.pose.pose). | upstream_code | src/robot.cpp:313-315 |
| withNoise returns val * (1 + std * unit_noise(random_engine)), where unit_noise is a static std::normal_distribution<double>(0, 1). | upstream_code | src/robot.cpp:54-58 |
| SimulatorNode::addRobot reads spec.robot_namespace.back() without checking for an empty namespace. | upstream_code | src/simulator.cpp:53-57 |
| With the display enabled, a double click in the OpenCV window calls removeRobotAt, which removes the robots at that pixel. | upstream_code | src/simulator.cpp:28-36 |
| The README says a robot is unspawned by double-clicking it, which cannot be done with display false. | vendor_doc | README.md:45-47 |
| The TurtleBot3 example spawns its robot in the namespace given by the name argument, default turtlebot1, and starts slider_publisher with cmd_vel.yaml in that namespace. | upstream_code | example/turtlebot3/turtlebot3_world_launch.py:8-36 |
| The multi-robot example starts slider_publisher with cmd_vel_multi.yaml and spawns robots in the namespaces r2d2, r2d3 and r2d4. | upstream_code | example/multirobot/multi_launch.py:21-46 |
| Robot.__init__, when cmd_type is not None, reads declare_parameter('pub_cmd', True).value and, when that value is true, creates a Twist publisher on the relative topic 'cmd_vel' with queue size 5. | upstream_code | src/kinematics.py:101-103 |
| Robot.publish publishes self.cmd_vel on self.cmd_vel_pub when self.cmd_vel_pub is not None. | upstream_code | src/kinematics.py:121-122 |

## Scope

The package is a configuration-only ROS 2 `RosDriver` over rosbridge. It serves one
configured robot namespace, `/robot1`, and declares these extension capabilities:

- `x-cap.okermorgant.spawn.v1`: call the absolute `/simulator/spawn` service with
  the namespace, pose, radius, shape and rectangle size. The Spawn response is
  empty, so the receipt confirms only that the callback returned.
- `x-cap.okermorgant.twist.v1`: publish a `geometry_msgs/Twist` on
  `/robot1/cmd_vel`. The simulator copies `linear.x`, `linear.y` and `angular.z`
  into `odom.twist.twist`.
- `x-cap.okermorgant.odometry.v1`: subscribe to one `nav_msgs/Odometry` sample on
  `/robot1/odom`.
- `x-cap.okermorgant.scan.v1`: subscribe to one `sensor_msgs/LaserScan` sample on
  `/robot1/scan`.

The resource state (`odom_pose`, `odom_twist`) is read from `/robot1/odom`; it is
an automatic snapshot for this driver, not the scan. The odom and scan endpoints
use relative upstream names in `source_name`; a deployment that starts the robot in
another namespace must expose the matching resolved endpoints. Multi-robot
deployments, `/simulator/add_anchor`, `/tf`, `/joint_states`, `/ranges`, the
map_server lifecycle and world step/reset are NOT COVERED. `kinematics.py` is
not a command of this package. When its `pub_cmd` parameter is true it publishes
`cmd_vel` (`src/kinematics.py:101-103`, `121-122`), so a deployment that runs it
in `/robot1` is a competing publisher and the sensed stop fails closed.

`/robot1` is this package's deployment choice: no shipped launch spawns it. The
examples spawn `/turtlebot1` (`example/turtlebot3/turtlebot3_world_launch.py:8-36`) or
`/r2d2`, `/r2d3` and `/r2d4` (`example/multirobot/multi_launch.py:21-46`) and also start
`slider_publisher`, a competing `cmd_vel` publisher. Until a robot is spawned in `/robot1`
and its `robot_description` arrives, `/robot1/odom` and `/robot1/scan` do not exist: the
resource read fails `NOT_READY`, and every command, the first spawn included, waits the
2 s read timeout before completing (reviewer probe on the fake). The simulator keeps
integrating the last `cmd_vel` command on every refresh until another command or a
duplicate spawn arrives (`src/robot.cpp:219-226`, `282-293`), and robots can be removed
only by a double click in the OpenCV window (`src/simulator.cpp:28-36`). An empty
`robot_namespace` reaches `std::string::back()` in `addRobot` (`src/simulator.cpp:55-57`).

## Safety

The simulator registers no ROS stop, pause or removal service. The package stop
is a sensed confirmation for this simulated card only (SAFE-049). The e-stop
publishes one all-zero `geometry_msgs/Twist` on `/robot1/cmd_vel`. That
publication is transmission only. The stop is achieved only when `/robot1/odom`
shows position x and y and orientation z and w within the operator span, and
linear.x, linear.y and angular.z within the operator absolute bound, for three
consecutive fresh stamped samples inside the confirmation bound. The thresholds
are `operator_required`; the fixture numbers are placeholders for the fake.
`Robot::publish` stamps `odom.header.stamp` from `now` (`src/robot.cpp:74`).
`Pose2D::writeTo` assigns the pose fields (`include/map_simulator/robot.h:62-67`)
and `Robot::move` writes that pose onto `odom.pose.pose` (`src/robot.cpp:313-315`).
The twist terms are the callback's stored command (`src/robot.cpp:223-225`).
`withNoise` multiplies by `(1 + std * unit_noise)` (`src/robot.cpp:54-58`), so a
zero command stays zero. The odom publisher is
`create_publisher<nav_msgs::msg::Odometry>(robot_namespace + "odom", 10)`
(`src/robot.cpp:214`); the history citation is that closed call with the literal
depth 10. The line does not say volatile.

The stop covers `/robot1` only, and nothing after the window. `slider_publisher`
in the examples and `kinematics.py` when `pub_cmd` is true are other `cmd_vel`
publishers; if one keeps publishing, confirmation fails closed. A duplicate spawn
calls `resetTo` and is an ordinary command, not a reset binding and not a stop
(SAFE-042). Removing a robot is a GUI double click. Until `robot_description`
arrives, `/robot1/odom` does not exist and the confirmation fails closed. The
client bounds are not source facts. Device risk is R2 because `cmd_vel` is a
topic a physical mobile robot also consumes (REVIEW.md item 12). The device kind
stays `world.sim`. Spawn stays R1. No `estop_physical_ref` is declared. No
hardware stop is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven responses with no
physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The fake starts with a placeholder `/robot1` robot; it does not
model the real `robot_description` handshake, the occupancy-grid ray cast, noisy
`Robot::move` integration, URDF scan geometry or scan-topic remapping. Its odom
and scan values are placeholders, not facts. An odom subscription is a short
stamped burst: the first sample is the stored twist and later samples snap to
the last cmd_vel. A non-zero cmd_vel steps the stored pose by a placeholder
and does not replace the stored twist; a zero command stores a still pose and
a zero twist. The real simulator's default scan is
100 samples with `angle_max=49*M_PI/50` and range 0.1..5, all configurable by the
URDF. The fake is a canned stand-in, not a recording, and not the upstream
simulator.

## Tags

`ros`, `ros2`, `simulation`, `map`, `mobile-base`, `laser-scan`, `cmd-vel`
