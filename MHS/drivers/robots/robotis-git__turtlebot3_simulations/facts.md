# Facts and tags for gh.robotis-git/turtlebot3_simulations

Every fact cites its source at commit `9be186fb03d84ed4f293e5c0db71d8c05bbc91f3`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same entries are in `facts = [...]` in `driver.py`; the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The turtlebot3_fake_node package is a ROS 2 ament_cmake package that depends on rclcpp. | upstream_code | turtlebot3_fake_node/package.xml:19-29 |
| The package description says the node supports simple tests without a robot. | vendor_doc | turtlebot3_fake_node/package.xml:6-8 |
| The constructor names the node turtlebot3_fake_node. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:24-25 |
| The constructor creates an odom publisher, a joint_states publisher and a tf publisher on relative names, then one cmd_vel subscription, then a 10 ms wall timer; it creates no ROS service or action server. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-59 |
| The odom publisher is nav_msgs::msg::Odometry. | upstream_code | turtlebot3_fake_node/include/turtlebot3_fake_node/turtlebot3_fake_node.hpp:49 |
| The joint_states publisher is sensor_msgs::msg::JointState. | upstream_code | turtlebot3_fake_node/include/turtlebot3_fake_node/turtlebot3_fake_node.hpp:50 |
| The cmd_vel subscription is geometry_msgs::msg::Twist on the relative name cmd_vel. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:48-50 |
| The wall timer is created with a 10 ms period and calls update_callback. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:59 |
| command_velocity_callback records the command time, copies cmd_vel.linear.x and cmd_vel.angular.z to goal velocities and computes the two wheel-speed setpoints from the wheel separation; it returns void and publishes no acknowledgement. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:135-146 |
| init_variables sets cmd_vel_timeout_ to 1.0 s. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:99 |
| update_callback's stale-command watchdog zeroes both wheel-speed setpoints when the last cmd_vel sample is older than cmd_vel_timeout_; its comment reads 'stop the robot if no cmd_vel'. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:157-161 |
| update_callback publishes odometry, joint states and tf on every timer tick. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:151-178 |
| update_odometry comments label the translational velocity [m/s] and the rotational velocity [rad/s]. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:191-192 |
| init_variables names the two wheel joints wheel_left_joint and wheel_right_joint and sizes position, velocity and effort to two entries. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:122-126 |
| update_joint_state copies last_position_ into position and last_velocity_ into velocity for the left and right wheels. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:247-253 |
| update_odometry sets each wheel's last_velocity_ to its wheel-speed setpoint divided by wheel_radius_ and adds that rate times the step time to last_position_; its comment labels the wheel rotation value [rad]. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:181-214 |
| The constructor assigns a KeepLast(10) QoS and passes that QoS to the odom publisher. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-43 |
| update_callback assigns odom_.header.stamp from time_now and publishes odom_. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:165-166 |
| update_odometry assigns odom_.pose.pose.position.x and y from odom_pose_ and sets z to 0. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:228-230 |
| update_odometry builds a quaternion with setRPY of odom_pose_[2] and assigns it to odom_.pose.pose.orientation. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:232-238 |
| update_odometry adds delta_s and delta_theta, computed from wheel_l and wheel_r, to odom_pose_. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:215-221 |
| init_parameters reads wheels.separation into wheel_seperation_ and wheels.radius into wheel_radius_, and the default of each get_parameter_or call is 0.0. | upstream_code | turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:88-89 |
| The burger parameter file sets wheels.separation to 0.160 and wheels.radius to 0.033. | upstream_code | turtlebot3_fake_node/param/burger.yaml:3-5 |
| The fake-node launch includes rviz2.launch.py and starts the turtlebot3_fake_node and robot_state_publisher executables. | upstream_code | turtlebot3_fake_node/launch/turtlebot3_fake_node.launch.py:60-75 |
| turtlebot3_drive creates a geometry_msgs::msg::Twist publisher on the relative name cmd_vel. | upstream_code | turtlebot3_gazebo/src/turtlebot3_drive.cpp:42 |
| turtlebot3_drive's update_cmd_vel assigns linear.x and angular.z and publishes that Twist. | upstream_code | turtlebot3_gazebo/src/turtlebot3_drive.cpp:98-104 |

## Scope notes

The driver targets the `turtlebot3_fake_node` package. The repository's Gazebo packages (`turtlebot3_gazebo`), the
`ros_gz_bridge` topic surface, `/scan`, `/imu`, `/camera/image_raw` and `/tf` are outside the commanded surface.
`turtlebot3_drive` in `turtlebot3_gazebo` publishes `cmd_vel` (see the facts above); no launch file in the pinned
clone starts that executable. The fake node creates no ROS service or action server. The e-stop is a
sensed-confirmation stop: one all-zero Twist on `/cmd_vel`, achieved only while the `/odom` pose stays within the
operator's bounds for five fresh stamped samples. The 1 s stale-command branch is a watchdog, and the confirmation
does not rely on it. `init_parameters` defaults `wheels.separation` and `wheels.radius` to 0.0. cpp:194 divides
each wheel speed by `wheel_radius_`. cpp:204-210 replace a NaN wheel increment with 0. cpp:216 multiplies by
`wheel_radius_` and divides by `wheel_seperation_`. Both defaults still 0 and a zero command make the pose
non-finite. Radius 0 with a non-zero separation and a zero command leaves a finite pose and NaN wheel velocities.
A non-zero command with radius 0 makes `delta_s` non-finite. The pose-only confirmation does not validate wheel
geometry. The operator loads a parameter file such as `burger.yaml`. `/cmd_vel` is also a physical TurtleBot3
command topic.
