# Source facts for gh.robotis-git/turtlebot3

Pinned commit: `fc817ce3073af1d6032397c64504134882af5e9a`. Source declarations and controlled fake evidence do not prove native execution.

| Fact | Source | Reference |
|---|---|---|
| The turtlebot3_node package is a ROS 2 ament_cmake package that depends on rclcpp. | upstream_code | `turtlebot3_node/package.xml:18-23` |
| The bringup launch selects param/humble/<model>.yaml on Humble and param/<model>.yaml otherwise. | upstream_code | `turtlebot3_bringup/launch/robot.launch.py:42-55` |
| The Humble Burger parameter file disables stamped cmd_vel. | upstream_code | `turtlebot3_bringup/param/humble/burger.yaml:5` |
| The Humble Waffle parameter file disables stamped cmd_vel. | upstream_code | `turtlebot3_bringup/param/humble/waffle.yaml:5` |
| The Humble Waffle Pi parameter file disables stamped cmd_vel. | upstream_code | `turtlebot3_bringup/param/humble/waffle_pi.yaml:5` |
| The Burger bringup parameter file sets enable_stamped_cmd_vel to true. | upstream_code | `turtlebot3_bringup/param/burger.yaml:5` |
| The Waffle bringup parameter file sets enable_stamped_cmd_vel to true. | upstream_code | `turtlebot3_bringup/param/waffle.yaml:5` |
| The Waffle Pi bringup parameter file sets enable_stamped_cmd_vel to true. | upstream_code | `turtlebot3_bringup/param/waffle_pi.yaml:5` |
| TwistSubscriber declares enable_stamped_cmd_vel false when the parameter is absent, then reads it and subscribes geometry_msgs::msg::TwistStamped when true or geometry_msgs::msg::Twist otherwise. | upstream_code | `turtlebot3_node/include/turtlebot3_node/twist_subscriber.hpp:86-99` |
| TurtleBot3::cmd_vel_callback constructs TwistSubscriber with the relative topic name "cmd_vel". | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:334-336` |
| The TwistStamped callback uses only twist.linear.x and twist.angular.z, multiplies each by 100, casts to int32, writes the six-register velocity block to the OpenCR, and returns void after a debug log; it publishes no motion acknowledgement or stop timer. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:370-405` |
| TurtleBot3::add_devices registers the relative "motor_power" service. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:213-214` |
| MotorPower's constructor creates a std_srvs::srv::SetBool service on the supplied server name. | upstream_code | `turtlebot3_node/src/devices/motor_power.cpp:31-38` |
| MotorPower::command writes request.data to the motor_torque_enable control-table address and returns the Dynamixel SDK write's success/message; it does not write a velocity setpoint or wait for the wheels to stop. | upstream_code | `turtlebot3_node/src/devices/motor_power.cpp:42-51` |
| TurtleBot3::add_sensors constructs the relative "battery_state" publisher. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:179-182` |
| The battery_state publisher is sensor_msgs::msg::BatteryState. | upstream_code | `turtlebot3_node/src/sensors/battery_state.cpp:30` |
| BatteryState::publish sets design_capacity 1.8, voltage as 0.01 times the battery_voltage register, percentage as 0.01 times the battery_percentage register, and present false when voltage is at most 7.0. | upstream_code | `turtlebot3_node/src/sensors/battery_state.cpp:43-53` |
| TurtleBot3::add_sensors constructs the relative "sensor_state" publisher. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:191-194` |
| The sensor_state publisher is turtlebot3_msgs::msg::SensorState. | upstream_code | `turtlebot3_node/src/sensors/sensor_state.cpp:40` |
| SensorState::publish reads the motor_torque_enable register into msg->torque. | upstream_code | `turtlebot3_node/src/sensors/sensor_state.cpp:117-119` |
| TurtleBot3::add_sensors constructs the relative "joint_states" publisher. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:202-206` |
| The joint_states publisher is sensor_msgs::msg::JointState. | upstream_code | `turtlebot3_node/src/sensors/joint_state.cpp:37` |
| JointState::publish pushes two wheel velocities converted by RPM_TO_MS. | upstream_code | `turtlebot3_node/src/sensors/joint_state.cpp:98-99` |
| The diff_drive_controller node publishes nav_msgs::msg::Odometry on the relative name "odom". | upstream_code | `turtlebot3_node/src/odometry.cpp:81` |
| The node registers the relative "reset" service. | upstream_code | `turtlebot3_node/src/turtlebot3.cpp:215-216` |
| Reset::command writes an IMU recalibration, sleeps five seconds, sets success=true, and then only logs the asynchronous reset_odometry reply. | upstream_code | `turtlebot3_node/src/devices/reset.cpp:51-78` |
| The teleoperation script caps Burger at 0.22 m/s and 2.84 rad/s and Waffle/Waffle Pi at 0.26 m/s and 1.82 rad/s; these are teleoperation caps, not measured hardware limits. | upstream_code | `turtlebot3_teleop/turtlebot3_teleop/script/teleop_keyboard.py:50-54` |

## Scope, limits and safety

This is an explicit TwistStamped profile preserving velocity publication, motor-power/torque requests, battery, odometry, wheel and torque observations. Top-level model YAMLs enable stamped cmd_vel, but robot.launch.py:42-55 selects param/humble/<model>.yaml on Humble; all three Humble files set enable_stamped_cmd_vel=false. The shipped Humble/default Twist configuration cannot use this fixed stamped declaration. There is no automatic type guessing.

The positive teleoperation caps at teleop_keyboard.py:50-54 do not literally establish the negative lower endpoints formerly attributed to that citation. Both signed velocity envelopes are now operator-required. The example overlay is fake-only illustrative data (linear -0.1..0.1 m/s; yaw -0.5..0.5 rad/s), not an upstream range, physical recommendation or installed model claim. Without an overlay stock commands are refused; both lower and upper limits are tested.

The existing SetBool(false) motor-power binding retains its precise source-supported torque-register-write acknowledgement. MotorPower::command checks the Dynamixel write response at motor_power.cpp:42-51. This is not a brake, sensed zero wheel velocity, external-publisher stop or physical e-stop. Ordinary torque-enable never runs automatically on reset. The upstream IMU/odometry reset remains unexposed.
