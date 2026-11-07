# Facts and tags for gh.jackvice/roboterrain

Every fact cites the pinned clone at commit `e56a6642b21746f1c5897b9515ef7ac7d258a550`: `upstream_code` is a
line of the clone and `vendor_doc` is a text file of the clone. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The repository integrates ROS 2 Humble, Gazebo Fortress, PyTorch and Stable Baselines3 with a Gymnasium interface, and simulates the Rover Zero, Clearpath Husky and Leo Rover platforms. | vendor_doc | README.md:14 |
| The README launches the Rover Zero simulation with ros2 launch roverrobotics_gazebo 4wd_rover_gazebo.launch.py. | vendor_doc | README.md:82-83 |
| RoverEnv is a gym.Env subclass documented as a custom environment that follows the Gymnasium interface. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:68-69 |
| The RoverEnv constructor defaults length to 2000, scan_topic to /scan, imu_topic to /imu/data, cmd_vel_topic to /cmd_vel, world_n to inspect, lidar_points to 32 and max_lidar_range to 12.0; these are constructor defaults, not device limits. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:71-73 |
| RoverEnv publishes geometry_msgs/Twist on cmd_vel and subscribes to LaserScan on scan_topic, Imu on imu_topic, PoseArray on /rover/pose_array and Odometry on /odometry/wheels. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:262-299 |
| The action space is a Box with low [-1.0, -pi] and high [1.0, pi], one speed and one relative heading value. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:215-219 |
| The observation space is a Dict of lidar (32 values from 0 to 12.0), pose (3 values), imu (3 angle values from -pi to pi), target (distance 0 to 100 and angle) and velocities (2 values). | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:226-255 |
| step reads action[0] as speed and action[1] as a relative heading command, adds it to current_yaw, passes the result through heading_controller, and publishes linear.x = speed and angular.z = the controller output. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:393-406 |
| heading_controller clamps its control output to max_angular_velocity, which the constructor sets to 7.0. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:128 |
| heading_controller returns np.clip(control, -self.max_angular_velocity, self.max_angular_velocity). | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:330 |
| step increments _step, sets done when _step >= _length, and returns (observation, reward, done, False, info). | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:412-443 |
| get_observation returns the lidar data, rover position, pitch/roll/yaw, target distance and relative angle, and linear/angular velocities. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:446-455 |
| reset calls super().reset(seed=seed), draws the start position and target with the module-level numpy random generator, sends an ign service set_pose command through subprocess, spins the node 100 times, sleeps for 1.0 s and returns (observation, {}). | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:599-683 |
| close destroys the ROS node and shuts down rclpy. | upstream_code | ros2_ws/src/sb3/environments/rover_env.py:691-694 |

## Helper choice

The card's static scan chose the ROS family and `RosDriver`, but the card's entry symbols are Gymnasium
environments. `RoverEnv` is a `gym.Env` subclass (`rover_env.py:68`) that creates an `rclpy` node
(`rover_env.py:78-80`), publishes and subscribes to ROS topics (`rover_env.py:262-299`) and steps a Gazebo
Fortress simulation. There is no rosbridge endpoint in the class, so a `RosDriver` cannot express its
reset/step interface. The package therefore uses `GymnasiumDriver` and records `DEVIATION FROM THE CARD` in
`RESULT.json`. The package serves `RoverEnv` only; the card's other entry symbols are separate environments.

## Scope and limits

The package declares no `Limit` of its own. The only action bound is the environment's action space, which the
Gymnasium bridge derives from the fake's `Box`; because the fake copies the upstream space, `action_space_ref`
cites `rover_env.py:215-219` and the derived limits are `upstream_code`. `ticks` is bounded by the bridge's
`max_ticks` default (1 to 10000), not by a device limit. The constructor values at `rover_env.py:71-73` are
recorded as facts, not reused as limits: they can be configured differently. The device risk is R2
(REVIEW.md item 12): `RoverEnv` publishes `geometry_msgs/Twist` on `/cmd_vel` (`rover_env.py:257-265`,
`393-406`), the connection check only waits for a `LaserScan` (`rover_env.py:808-816`), and
`README.md:14` models the Rover Zero, Clearpath Husky and Leo Rover. No fact cites that only the
simulator consumes `/cmd_vel`. The package still declares no `Limit` of its own, no e-stop physical
reference and no site-limits overlay.

## Fidelity contract

`driver.py` describes the deployed fake, not the upstream Gazebo defaults: engine
`analytic:ROS-free kinematic stand-in for Gazebo Fortress`, level F0, determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 0, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps disclose the absent ROS 2 graph, Gazebo physics, sensor callbacks, `ign service` reset,
wall-clock waits, upstream reward logic and calibrated dynamics.

## Safety

The device risk is R2, a mobile base. There is no hardware backend and no native stop. The runtime latches an
e-stop in software; after it, `cap.world.step.v1` and `cap.world.reset.v1` are refused until an operator's
`mhs.safety.reset` clears the latch. The last observation remains readable. The latch does not publish a zero
Twist on `/cmd_vel` and does not stop a mobile base subscribed to that topic. The fake makes no
hardware-safety claim.

## Tags

`ros2`, `gazebo`, `rover`, `point-navigation`, `reinforcement-learning`, `simulation`, `gymnasium`

## Deployment boundary after source review

Only the declared fake backend is accepted as a contract test. There is no
package simulator factory; installing dependencies does not create one. Native
ROS process ownership, independent interruption/pause, seed behavior and fresh
response checks remain deployment work. The fake's software latch does not
prove that a real ROS/Gazebo world has stopped. No live backend was executed.
