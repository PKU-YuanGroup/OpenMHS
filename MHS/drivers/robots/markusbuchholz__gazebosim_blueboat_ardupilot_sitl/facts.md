# Facts and tags for gh.markusbuchholz/gazebosim_blueboat_ardupilot_sitl

Every fact cites the pinned clone at commit `96b01666d9f8e7ec19b25df3f8709c2aed2e1363`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); `reference.json` is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| BlueboatROSInterface is an rclpy Node that subscribes to /blueboat/cmd_vel (geometry_msgs/Twist) and to the uuv_name-prefixed send_port_motor_0_100_thrust and send_stbd_motor_0_100_thrust topics (std_msgs/Float32), and publishes /blueboat/servo_outputs (std_msgs/Int32MultiArray), /compass (std_msgs/Float32), /imu (sensor_msgs/Imu) and the three Euler-angle Float32 topics. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:86-170 |
| The node declares uuv_name with default 'blueboat'. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:42 |
| The port and starboard motor callbacks cast the Float32 data to int and call send_motor_thrust with hard-coded motor numbers 3 and 4. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:376-386 |
| send_motor_thrust sends MAV_CMD_DO_MOTOR_TEST with thrust_type 0 (percent) and duration 1.0 s; its docstring states thrust_value is 0-100 for percent. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:388-408 |
| arm_vehicle sends MAV_CMD_COMPONENT_ARM_DISARM with param1 1; disarm_vehicle sends the same command with param1 0. Both methods only call command_long_send and do not read a heartbeat acknowledgement. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:263-285 |
| send_motor_thrust wraps command_long_send in a try/except whose handler only logs the error. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:397-411 |
| The constructor initialises self.data to an empty dictionary and starts a daemon MAVLink listener thread. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:173-177 |
| mavlink_listener stores each received MAVLink message as a dict under its message type in self.data while rclpy.ok() is true. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:285-297 |
| The node declares mavlink_connection with default udpin:0.0.0.0:14550. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:39 |
| The constructor opens the MAVLink connection and calls wait_heartbeat. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:35-52 |
| The constructor calls set_stabilize_mode_and_arm. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:35-71 |
| set_stabilize_mode_and_arm sends MAV_CMD_COMPONENT_ARM_DISARM with param1 1. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:232-250 |
| publish_compass reads the VFR_HUD heading, normalises it with heading % 360 and publishes it as a Float32 on /compass. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:413-429 |
| _publish_servo_outputs reads servo1_raw through servo8_raw from the SERVO_OUTPUT_RAW snapshot, with 0 for a missing field, and publishes them as an Int32MultiArray. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:299-322 |
| publish_imu reads ATTITUDE roll, pitch and yaw in radians and RAW_IMU linear acceleration, publishes normalised Euler angles as Float32 degrees and builds a sensor_msgs/Imu message. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:431-490 |
| set_stabilize_mode_and_arm waits for HEARTBEAT messages and checks base_mode & MAV_MODE_FLAG_SAFETY_ARMED; it raises when the vehicle did not arm. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:252-261 |
| JoystickNode publishes axis 4 and axis 1 times 100 times 0.5 as port and starboard thrust and calls arm_vehicle for button 7 and disarm_vehicle for button 6. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:559-584 |
| main starts 'ros2 run joy joy_node' with subprocess.Popen before creating the nodes. | upstream_code | gz_ws/extras_interface/ros2_blueboat_interface.py:589-602 |
| changing_modes.py constructs BoatController on udpin:0.0.0.0:14550 and keeps a commented udpin:192.168.2.1:14550 alternative. | upstream_code | gz_ws/src/extras_boat/changing_modes.py:119-120 |

## Scope and shape

The selected upstream entry is the concrete Python ROS 2 node class
`gz_ws/extras_interface/ros2_blueboat_interface.py:34 BlueboatROSInterface`. The node itself is a
topic bridge: it subscribes to two `std_msgs/Float32` motor-thrust topics and to
`/blueboat/cmd_vel`, and publishes `SERVO_OUTPUT_RAW`, compass, IMU and Euler-angle topics. It
creates no ROS service or action server and exposes no ROS disarm or stop service. The separate
`move_blueboat` launch bridges the Gazebo joint-thrust, odometry, navsat, camera and laser-scan
topics; the driver does not claim that second surface.

DEVIATION FROM THE CARD: the card names the `RosDriver` helper. A configuration-only `RosDriver`
can publish to the thrust topics but cannot declare a native stop, because the clone has no
stop service or action; its only stop-shaped path is the node's `send_motor_thrust(..., 0)` and
`disarm_vehicle()` methods. This package therefore binds the concrete Python node class with a
direct `Driver` and an `@estop` method. Those methods only transmit MAVLink commands, so the
model review of 2026-11-05 found that they are not an acknowledged stop either (see Safety). It does not import or run the upstream node in the gate:
the fake backend is a Python stand-in, and no ROS, MAVLink, ArduPilot or Gazebo process is
started.

The driver exposes the node's shared MAVLink snapshots as read-only state: `base_mode` from
`HEARTBEAT`, `heading_deg` from `VFR_HUD`, `roll_rad`, `pitch_rad` and `yaw_rad` from `ATTITUDE`,
and the eight `SERVO_OUTPUT_RAW` PWM values (a missing `servoN_raw` field is refused, not replaced by
0). Each read returns the node's last stored message of that type, with no age check. It exposes
extension actions for the two motor percentages, arm, disarm and a transmission-only
zero-thrust-and-disarm request. The motor percentage limit 0-100 comes from the
`send_motor_thrust` docstring at line 392. The node hard-codes MAVLink motor numbers 3 (port) and
4 (starboard); the driver preserves those numbers and does not remap them.

The two thrust actions use the node's one-second `MAV_CMD_DO_MOTOR_TEST` path, not a continuous
velocity setpoint. A single command is a test pulse of the configured duration; the driver reports
the transmitted percentage, not a measured thrust, speed, distance or heading.

## Safety

The device is a simulated mobile base at R2. The clone offers no acknowledged stop: the node
creates no ROS service or action, and its `send_motor_thrust` and `disarm_vehicle` methods only
call `command_long_send` (`MAV_CMD_DO_MOTOR_TEST` and `MAV_CMD_COMPONENT_ARM_DISARM`); a failed
motor-test send is only logged, and nothing reads a `COMMAND_ACK`, a heartbeat or the motor
outputs back. The `@estop` still sends `send_motor_thrust(3, 0)`, `send_motor_thrust(4, 0)` and
`disarm_vehicle()`, then raises `MHS.SAFETY.SAFE_STATE_UNREACHED`, so the e-stop fails with the
latch held and the server's background retry resends the commands. The zero-thrust-and-disarm
action (`x-cap.markusbuchholz.stop.v1`) is an ordinary transmission-only command, not a safe-state
action. ArduPilot SITL and Gazebo keep running after an e-stop, and the module's own joystick node
or any MAVLink client can re-arm the vehicle.

The same MAVLink surface drives a real BlueBoat: the node listens on `udpin:0.0.0.0:14550`, waits
for a heartbeat without a timeout and arms the vehicle in its constructor, and
`changing_modes.py` keeps a commented `udpin:192.168.2.1:14550` endpoint. The package declares
only the fake backend; no physical e-stop, ROS graph observation or hardware run is claimed, and
`driver.lock.json` keeps `reviewed_by: null`. The package is blocked (HELPER_MISSING) until an
acknowledged stop exists.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:Python fake of BlueboatROSInterface (no
ROS, MAVLink or physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, and no snapshot/restore. The fake records motor, arm and disarm calls and keeps
placeholder MAVLink-shaped dictionaries; its arm and disarm flip the stored `base_mode` at once,
whereas upstream only transmits the command. It runs no ROS node, node timers, MAVLink connection,
ArduPilot SITL, Gazebo world, thruster, hydrodynamics or sensor. The observation values are
placeholders, not captured traffic. The ROS topic wiring, QoS, launch files and the
`ros_ign_bridge` topics are not exercised.

## Tags

`ros`, `ros2`, `simulation`, `gazebo`, `blueboat`, `usv`, `mavlink`, `thruster`
