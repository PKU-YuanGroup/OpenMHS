OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.anurye/gym-turtlebot

Every fact cites the pinned clone at commit `c1e8b72a1081b92821dc14320fc7105b10423c54`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name a text file of the
clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The package registers Gymnasium environment Turtlebot4Env-v0 with entry point tb4_drl_navigation.envs.diffdrive.turtlebot4:Turtlebot4Env and max_episode_steps=500. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/__init__.py:3-7 |
| Turtlebot4Env defines a two-element float32 Box action space with low [0.0, -1.0] and high [1.0, 1.0]. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:187-191 |
| Turtlebot4Env defines a Dict observation space with min_ranges and min_ranges_angle shaped by num_bins and bounded by the scan range and angle, dist_to_goal bounded 0.0 to 100.0, orient_to_goal bounded -pi to pi, and the last action copied from the action space. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:219-234 |
| step stores the action, converts action[0] to the linear.x twist component and action[1] to angular.z, publishes the twist through Publisher, and propagates the state for time_delta seconds. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:331-346 |
| Sensors creates a sensor_msgs/LaserScan subscription on /scan and a nav_msgs/Odometry subscription on /odometry/filtered. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:57-70 |
| Publisher creates a TwistStamped publisher on /cmd_vel with queue depth 10. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:135-139 |
| pub_cmd_vel stamps the TwistStamped with the node clock and the configured base frame and publishes it. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:160-165 |
| reset passes seed to Gymnasium's super().reset(seed=seed), calls SimulationControl.reset_world(), zeroes the last action and republishes it, and reads start_pos/goal_pos from options. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:375-394 |
| SimulationControl creates a ControlWorld service client on /world/<world_name>/control. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:400-403 |
| SimulationControl.reset_world requests a ControlWorld reset with model_only=True, and pause_unpause sets world_control.pause to the requested value. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/utils/ros_gz.py:423-441 |
| _propagate_state unpauses the world, spins the executor until time_delta elapses, pauses the world, and then reads the observation from the sensors. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:446-456 |
| ScenarioGenerator is constructed with seed=None. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:178-185 |
| When reset options omit start_pos and goal_pos, the start and goal yaws are drawn from np.random.uniform(-pi, pi), not from the seeded Gymnasium RNG. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:392-404 |
| The environment terminates when dist_to_goal < goal_threshold or min(min_ranges) < collision_threshold. | upstream_code | src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:495-503 |
| README states that Gazebo Sim does not support model reset and that the robot's odometry and pose are reset with the SetPose and SetEntityPose services. | vendor_doc | README.md:89-91 |
| The tutorial says num_bins creates 30 bins by default and can be as high as len(ranges). | vendor_doc | docs/Tutorial.md:42-43 |

## Scope

The upstream entry is a Gymnasium environment, not a ROS transport: `step` publishes a
Twist through its own ROS 2 publisher and then spins its own executor while Gazebo
advances, and `reset` calls its own Gazebo and robot_localization service clients. The
package therefore serves `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1` through `GymnasiumDriver`; it does not expose `/cmd_vel`, `/scan` or
`/odometry/filtered` as separate ROS capabilities.

The action space is copied from the upstream environment so the bridge derives the same
`cap.world.step.v1` bounds; `action_space_ref` cites `turtlebot4.py:187-191`. No numeric
constructor default is used as a device limit. The fake's 30-bin observation is a
placeholder: the tutorial gives 30 as the default `num_bins`, and upstream clamps it to
the live scan length (`turtlebot4.py:260`).

## Fidelity and fake

The package backend is the ROS-free analytic fake in `fake.py`, served as mode
`simulated` with F0 evidence only. The fake creates no ROS 2 node and never contacts
Gazebo or the simulator topics. Its observation values, rewards and flags are
placeholders; it runs no physics, no `time_delta` propagation and no `max_episode_steps`
TimeLimit. The upstream `ScenarioGenerator` is unseeded (`seed=None`) and the yaw draws
use the global `np.random`, so even the real environment's Gymnasium seed does not fully
control the scenario; the fake's seed only selects its placeholder distance. Rendering,
observation images, TF, snapshots and the full `LaserScan` array are NOT COVERED.

## Safety

The device risk is R2 (REVIEW.md item 12). `Turtlebot4Env.step` publishes
`geometry_msgs/TwistStamped` on `/cmd_vel` (`ros_gz.py:135-139`, `160-165`;
`turtlebot4.py:331-346`), and the tutorial says a differential-drive robot can be used
directly when its topics are `scan`, `odom` and `cmd_vel` (`docs/Tutorial.md:34`). No
fact cites that only the simulator consumes `/cmd_vel`. The runtime latch refuses every
`cap.world.*` command after an e-stop until an operator reset; in `simulated` mode the
receipt reports a software-only stop, not a physical emergency stop. The package has no
`@estop` method. The latch does not publish a zero Twist and does not stop a mobile base
subscribed to `/cmd_vel`. Safe-state evidence is the runtime's refusal of further steps.

## Tags

`gymnasium`, `simulation`, `ros2`, `gazebo`, `turtlebot4`, `navigation`, `reinforcement-learning`

## Deployment boundary after source review

Only the declared fake backend is accepted as a contract test. There is no
package simulator factory; installing dependencies does not create one. Native
ROS process ownership, independent interruption/pause, seed behavior and fresh
response checks remain deployment work. The fake's software latch does not
prove that a real ROS/Gazebo world has stopped. No live backend was executed.
