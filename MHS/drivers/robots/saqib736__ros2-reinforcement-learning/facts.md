# Facts and tags for gh.saqib736/ros2-reinforcement-learning

Every fact cites its source at commit `c17f9055076f72d91be6a628a2a5db084dacd7d1`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| This project demonstrates reinforcement learning for robotic tasks using ROS 2 Humble, Gazebo, Stable-Baselines3 and Gymnasium | vendor_doc | README.md:3 |
| start_learning registers RacingBotEnv-v0 with entry point rl_racing.gazebo_env:GazeboEnv and max_episode_steps=1000 | upstream_code | rl_racing/rl_racing/start_learning.py:36-40 |
| GazeboEnv subclasses GazeboConnection (from rl_racing.gazebo_connections) and gymnasium's Env | upstream_code | rl_racing/rl_racing/gazebo_env.py:5-11 |
| GazeboConnection subclasses rclpy's Node, and its constructor creates the node gazebo_connection | upstream_code | rl_racing/rl_racing/gazebo_connections.py:6-32 |
| The action space is Box(low=[-1, -1], high=[1, 1], dtype=float32) | upstream_code | rl_racing/rl_racing/gazebo_env.py:25-27 |
| The observation space is Box(low=0, high=1, shape=(60,), dtype=float32) | upstream_code | rl_racing/rl_racing/gazebo_env.py:29 |
| The environment sets max_linear_vel=1.0, min_linear_vel=0.0, angular_vel=1.0 and min_obstacle_dist=0.2 | upstream_code | rl_racing/rl_racing/gazebo_env.py:20-23 |
| seed() creates a generator with gymnasium.utils.seeding.np_random and returns [seed] | upstream_code | rl_racing/rl_racing/gazebo_env.py:34-36 |
| spin() clears done_laser_ and done_odom_ and calls rclpy.spin_once(self) in a loop, with no deadline, until both flags are set | upstream_code | rl_racing/rl_racing/gazebo_env.py:38-42 |
| step() applies the action, spins, reads the observation, evaluates done, computes the reward and returns (obs, reward, done, False, {}) | upstream_code | rl_racing/rl_racing/gazebo_env.py:44-60 |
| reset() optionally seeds, calls resetSim(), updates the episode, spins, reads the observation, clears last_action and returns (obs, {}) | upstream_code | rl_racing/rl_racing/gazebo_env.py:62-81 |
| _set_action computes the linear velocity (max_linear_vel * (action[0] + 1) + min_linear_vel * (1 - action[0])) / 2 and the angular velocity (angular_vel * (action[1] + 1) - angular_vel * (1 - action[1])) / 2, then calls publish_velocity | upstream_code | rl_racing/rl_racing/gazebo_env.py:95-103 |
| _get_obs returns the laser scan divided by 10 | upstream_code | rl_racing/rl_racing/gazebo_env.py:105-110 |
| _is_done is true when any laser distance is below min_obstacle_dist | upstream_code | rl_racing/rl_racing/gazebo_env.py:112-119 |
| The reward is 5 * get_current_linear_vel(), plus -(min_obstacle_dist - min(obs)) when the minimum of the scaled observation is below min_obstacle_dist, minus 20 when done, plus 0.1, and minus 2 when the action equals last_action | upstream_code | rl_racing/rl_racing/gazebo_env.py:121-145 |
| GazeboConnection publishes geometry_msgs/Twist on /cmd_vel and subscribes to nav_msgs/Odometry on /odom and sensor_msgs/LaserScan on /front_laser/scan | upstream_code | rl_racing/rl_racing/gazebo_connections.py:36-39 |
| publish_velocity puts velocity[0] in linear.x and velocity[1] in angular.z | upstream_code | rl_racing/rl_racing/gazebo_connections.py:47-51 |
| laser_callback copies msg.ranges into a numpy array and replaces infinite readings with 10 | upstream_code | rl_racing/rl_racing/gazebo_connections.py:53-56 |
| odom_callback stores msg.twist.twist.linear.x as the current linear velocity | upstream_code | rl_racing/rl_racing/gazebo_connections.py:61-66 |
| resetSim repeats wait_for_service(max_retry_) until /reset_simulation is available, sends an Empty request, waits with rclpy.spin_until_future_complete without a timeout and sets resetSim_done_ when the future has a result | upstream_code | rl_racing/rl_racing/gazebo_connections.py:68-88 |
| The GazeboConnection docstring lists /reset_simulation, /reset_world, /pause_physics and /unpause_physics under 'Services not used' | upstream_code | rl_racing/rl_racing/gazebo_connections.py:24-28 |
| The documented simulation launch is ros2 launch sim_package start_simulation.launch.py | vendor_doc | README.md:78 |
| The documented training launch is ros2 launch rl_racing start_training.launch.py | vendor_doc | README.md:88 |
| The package declares rclpy, geometry_msgs, sensor_msgs, nav_msgs, std_srvs, gymnasium, numpy and stable_baselines3 dependencies | upstream_code | rl_racing/package.xml:10-25 |
| The URDF attaches a front_laser link to the chassis at x=0.125, z=0.25 | upstream_code | sim_package/urdf/td_robot.urdf:383-388 |
| The racing_track world includes model://td_robot at pose 0 5 0.01 | upstream_code | sim_package/worlds/racing_track.world:31-35 |
| The td_robot model's laser sensor has 60 horizontal samples from -1.5708 to 1.5708, a range of 0.1 to 10 and an update rate of 100, and its libgazebo_ros_ray_sensor plugin remaps its output to /front_laser/scan as sensor_msgs/LaserScan | upstream_code | sim_package/models/td_robot/td_robot.sdf:340-366 |
| The td_robot model's libgazebo_ros_diff_drive plugin uses command_topic cmd_vel and odometry_topic odom with max_wheel_torque 20, max_wheel_acceleration 1.8 and update_rate 50 | upstream_code | sim_package/models/td_robot/td_robot.sdf:727-750 |

Limits: the driver declares no numeric limit of its own. The only bound is the action space, which the bridge derives
from the environment (`Box([-1, -1], [1, 1])`: `action.values` from -1 to 1 per element, with the source
`upstream_code` and the ref `rl_racing/rl_racing/gazebo_env.py:25-27`), and `ticks` (1 to `max_ticks`, 10000 by
default). The device risk is R2 (REVIEW.md item 12): `step` publishes `geometry_msgs/Twist` on
`/cmd_vel` (`gazebo_env.py:95-103`, `gazebo_connections.py:36-39`, `47-51`). The package still declares
no `Limit` of its own, so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:kinematic scan stand-in (no Gazebo physics)`,
level F0, determinism `seeded` with `seed_control` `parameter`, timestep 0 ms (the fake has no physical timestep),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps state that the fake models no
Gazebo physics, contacts, rays, odometry or rendering and returns immediately instead of waiting for ROS messages;
that the laser publishing `/front_laser/scan` (60 samples, range 0.1 to 10) and the diff-drive plugin on `cmd_vel`
and `odom` are in the model SDF (`sim_package/models/td_robot/td_robot.sdf:340-366, 727-750`), not in the URDF; that
the upstream is free-running and its step, spin and reset wait without a deadline; that constructing it needs a prior
global `rclpy.init()`, that the environment is registered only inside `start_learning.main` with a 1000-step limit
the fake does not apply; that the fake's progress reward uses the commanded instead of the odometry velocity; and
that the upstream safety penalty compares the scaled observation with the unscaled crash distance.

Safety: device risk R2, a mobile base. The e-stop is the runtime's software latch (there is no hardware backend); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch, and the fake's state stays readable. Nothing is
sent to the environment: a live Gazebo is free-running and would keep simulating with the last `/cmd_vel` Twist in
place, because the upstream publishes velocity only from `step` and calls no pause service. The latch does not
publish a zero Twist, so a physical base subscribed to `/cmd_vel` is not stopped. The upstream ROS topics
are internal to the environment and are not separately exposed; they are the generic root `/cmd_vel`, `/odom` and
`/front_laser/scan`, so a live environment in a ROS graph with a real base on `/cmd_vel` would command that base.

Tags: ros2, gazebo, reinforcement-learning, gymnasium, racing, simulation, laser, pioneer3dx
