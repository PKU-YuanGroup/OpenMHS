# Facts and scope for gh.toppers/hakoniwa-digital-twin

Every fact cites the pinned clone at commit `1a2c15b8aade01696a81207c8f28a77013497384`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans adjacent
lines. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

The selected device is the concrete ROS 2 `infra_sensor_urg` node `lidar_subscriber`, not the repository's
Unity/Hakoniwa demo as a whole. The driver observes the node's published position estimate; it does not start
the node, feed its LiDAR/IMU inputs or step its estimator.

## Facts

| fact | source | ref |
|---|---|---|
| LIDARSubscriber is an rclpy Node constructed with the name 'lidar_subscriber'. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:62-64 |
| The constructor declares the ROS 2 parameter 'act_mode' with the default string 'sim' and reads it once through get_parameter. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:66-73 |
| With act_mode == 'sim' the node subscribes to '/LiDARSensor2D_scan' and '/TB3RoboModel_imu'; otherwise it subscribes to '/scan' and '/tb3_imu'. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:66-92 |
| The constructor initialises the node's scan_mode flag to False. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:63-103 |
| The node imports geometry_msgs.msg.Twist. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:5 |
| The node creates a publisher for Twist on the absolute topic '/TB3RoboAvatar_cmd_pos' with queue size 10. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:78 |
| The LaserScan and Imu subscriptions use one QoS profile with depth 10, BEST_EFFORT reliability and VOLATILE durability. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:80-92 |
| listener_callback runs the estimator while the estimator reports scan mode or the node's scan_mode flag is set, each time with scan_count_max=lidar_param_scan_count_max and value_threshold=lidar_param_segment_threshold; otherwise it sets x and y to 0.0. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:121-133 |
| listener_callback then fills Twist linear.x and linear.y with x and y, linear.z with 0.0 and angular.x, angular.y and angular.z with the stored angle_x, angle_y and angle_z, and publishes the message at the end of every call. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:121-142 |
| listener_imu stores the roll, pitch and yaw that euler_from_quaternion computes from the Imu orientation as angle_x, angle_y and angle_z. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:105-116 |
| euler_from_quaternion computes roll and yaw with np.arctan2 and pitch with np.arcsin. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:20-38 |
| The pinned lidar_params literals are lidar_param_scan_count_max = 50 and lidar_param_segment_threshold = 0.05. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_params.py:4-5 |
| write_pos adds 0.075 to the filtered x average when a non-None result is supplied; with no result it returns the stored average without the offset. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:121-141 |
| The estimator constructor initialises average_x, average_y and average_r to 0.0. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:65 |
| is_scan_mode returns True until scan() sets finalized, which scan() does only after it has collected scan_count_max scans. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:227-242 |
| run returns write_pos(None) while scan() reports that the environment scan has not finished. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/pos_estimator.py:249-252 |
| KeyboardMonitor maps the keyboard input 's' to True and 'p' to False. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:148-157 |
| main connects the keyboard monitor's mode_changed signal to LIDARSubscriber.set_scan_mode. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:173-176 |
| set_scan_mode only assigns self.scan_mode under the node lock; it does not create a ROS service or action endpoint. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/infra_sensor_urg/lidar_subscriber.py:144-146 |
| The README starts the node with 'ros2 run infra_sensor_urg lidar_subscriber --ros-args -p act_mode:=real' and says to pass act_mode:=sim for tests. | vendor_doc | README.md:417-420 |
| The README says the robot-position estimate is delivered on RobotAvator_cmd_pos and shows a ros2 topic echo of /TB3RoboAvatar_cmd_pos with linear and angular components. | vendor_doc | README.md:451-465 |
| The README asks the operator to wait about 30 seconds for the environment scan, then place the robot and enter s at the node's terminal. | vendor_doc | README.md:434-443 |
| The infra_sensor_tg15 node also creates a Twist publisher on '/TB3RoboAvatar_cmd_pos'. | upstream_code | real/sensors/workspace/src/infra_sensor_tg15/infra_sensor_tg15/lidar_subscriber.py:18 |
| tb3_controller_node subscribes to TB3RoboAvatar_cmd_pos with sensor_callback_pos. | upstream_code | real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:92-94 |
| sensor_callback_pos takes linear.x as the robot position and, in the MOVE state between 0.5 and 0.8, stops the motor unless the signal state is blue. | upstream_code | real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:164-194 |
| tb3_controller_node publishes its Twist on /TB3RoboModel_cmd_vel when act_mode is 'sim' and on /tb3_cmd_vel otherwise. | upstream_code | real/robot/workspace/src/tb3_controller/src/tb3_controller.cpp:57-76 |
| The README starts tb3_controller_node with act_mode:=real. | vendor_doc | README.md:476 |
| The infra_sensor_urg package manifest declares the licence TOPPERS. | upstream_code | real/sensors/workspace/src/infra_sensor_urg/package.xml:3-8 |

## Scope

The package binds one ROS 2 topic observation: a fresh `geometry_msgs/msg/Twist` subscribed on the absolute
`/TB3RoboAvatar_cmd_pos` topic and served as `cap.sensing.read.v1`. The `values` object exposes `x`, `y` and
`z` in metres and `roll`, `pitch` and `yaw` in radians. The optional `fields` input selects a subset of those
six channel names; an unrecognised name is ignored. The observation is stamped with the driver's local receive
time because `geometry_msgs/msg/Twist` has no header.

The node's input topics are not bound. `act_mode` is a startup parameter read once in the constructor; the
pinned source creates no ROS service, action or runtime parameter callback that changes the topic choice.
`set_scan_mode` is reached only through the interactive PyQt keyboard monitor (`s`/`p`), so this package
exposes no `cap.device.configure.v1` action and does not send keyboard input. Without that input the bound
estimate is not one: x and y are 0.0 while the estimator collects its 50 environment scans and, after the
message that completes the scan, 0.0 again until an operator enters `s` (`p` returns to 0.0); z is always 0.0.
The clone's `infra_sensor_tg15` node publishes on the same topic, and `tb3_controller_node`, which the README
starts with `act_mode:=real` against a TurtleBot3, subscribes to it as its position input. This package
only subscribes. `cap.sensing.read.v1` is the
catalogue class that fits this read-only sensor; the registry also lists `cap.device.configure.v1`, but no
source-backed runtime configure endpoint exists at this pin.

The node publishes only when it receives a scan; a deployment that starts the node under another namespace or
with `act_mode:=real` must expose the corresponding resolved topic to rosbridge. The package does not infer a
ROS graph, QoS match, remapping or publisher liveness from the declaration.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS 2 /TB3RoboAvatar_cmd_pos transcript (no estimator,
LiDAR or physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven canned responses with no
estimator or physics step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The fake
answers the declared subscription with placeholder Twist messages and runs no `infra_sensor_urg` node, LiDAR
filter, circle fit, PyQt plotter or ROS graph. Its pose values are test data and do not establish estimator
accuracy, tracking or a physical position. The upstream Unity/Hakoniwa simulator is outside the clone and was
not started; no ROS graph or hardware was contacted.

## Safety

The selected node is a passive position publisher. This package binds only its published estimate and declares
no actuation, motion command, native stop, reset or safe-state action. The stock e-stop therefore latches in
software and reports no native stop (`native: null`); this is not a physical emergency stop and no safe-state
achievement is claimed. A catalogue-confirmed read class remains available during the software latch. RosDriver
refuses every hardware backend without a human hardware review; this package was exercised only with the fake
backend.

## Tags

`ros`, `ros2`, `lidar`, `position`, `sensor`, `hakoniwa`, `simulation`
