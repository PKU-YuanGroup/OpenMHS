# Facts and tags for gh.erlerobot/gym-gazebo

Every fact cites the pinned clone at commit `ade82b627839f816c1f4be6cea77b56eb21abc81`:
`vendor_doc` for a text file of the clone and `upstream_code` for a `path/in/clone.py:LINE`
reference. The same facts are written into `driver.py` (`facts = [...]`); `reference.json`
and `REFERENCE.md` are generated from the driver, not from this page.

## Scope

This package serves one of the card's five entry symbols,
`gym_gazebo.envs.turtlebot:GazeboCircuitTurtlebotLidarEnv`, through the SDK's
configuration-only `GymnasiumDriver`. The card names `RosDriver`, but the confirmed entry
is a legacy `gym.Env` whose primary interface is `reset()` and `step(action)`; its ROS
publisher and Gazebo service proxies are internals created by the constructor, not a
rosbridge surface (see the DEVIATION FROM THE CARD note in `driver.py` and
`RESULT.json`). The other four entry symbols are separate environments and are not covered.

The package exposes:

- `cap.world.reset.v1` (`{seed, options}`): reset the environment and return the
  discretized initial observation;
- `cap.world.step.v1` (`{ticks, action}`): advance the environment by `ticks` transitions
  with `action.index` in 0..2, derived from the upstream `spaces.Discrete(3)`;
- `cap.world.seed.v1` (`{seed}`): store the seed used by the next reset.

No catalogue `Limit` is declared. `cap.world.step.v1` derives `action.index` 0..2 from
`gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:26`
(`self.action_space = spaces.Discrete(3) #F,L,R`), cited by `action_space_ref`. The
`ticks` 1..10000 bound is the family bridge's own contract, not a device fact. No bound is
`operator_required` and no `site-limits.example.json` is needed.

## Facts

| fact | source | ref |
|---|---|---|
| The project is an extension of the initial OpenAI gym for robotics using ROS and Gazebo. | vendor_doc | README.md:10 |
| The README marks the repository as deprecated in favour of gym-gazebo2. | vendor_doc | README.md:4 |
| GazeboCircuitTurtlebotLidar-v0 is registered with entry point gym_gazebo.envs.turtlebot:GazeboCircuitTurtlebotLidarEnv. | upstream_code | gym_gazebo/__init__.py:15-19 |
| The documented example constructs the environment with gym.make('GazeboCircuitTurtlebotLidar-v0'). | upstream_code | examples/turtlebot/circuit_turtlebot_lidar_qlearn.py:24 |
| GazeboEnv derives from gym.Env and is the superclass of the environment. | upstream_code | gym_gazebo/envs/gazebo_env.py:13 |
| GazeboEnv chooses a random ROS master port and a Gazebo master port one higher. | upstream_code | gym_gazebo/envs/gazebo_env.py:21-25 |
| GazeboEnv launches the roslaunch process for the environment's launch file. | upstream_code | gym_gazebo/envs/gazebo_env.py:53 |
| GazeboEnv writes ROS_MASTER_URI and GAZEBO_MASTER_URI into os.environ and prints both URIs. | upstream_code | gym_gazebo/envs/gazebo_env.py:27-33 |
| GazeboEnv calls rospy.init_node('gym', anonymous=True) after starting roslaunch. | upstream_code | gym_gazebo/envs/gazebo_env.py:59 |
| GazeboEnv._close counts gzclient, gzserver, roscore and rosmaster in ps -Af and runs killall -9 on each that appears. | upstream_code | gym_gazebo/envs/gazebo_env.py:119-138 |
| The environment's launch file takes its world from the GYM_GAZEBO_WORLD_CIRCUIT environment variable and includes the turtlebot_gazebo base launch (kobuki unless TURTLEBOT_BASE is set). | upstream_code | gym_gazebo/envs/assets/launch/GazeboCircuitTurtlebotLidar_v0.launch:1-23 |
| GazeboCircuitTurtlebotLidarEnv derives from gazebo_env.GazeboEnv. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:16 |
| The constructor creates a rospy Publisher on /mobile_base/commands/velocity and service proxies for /gazebo/unpause_physics, /gazebo/pause_physics and /gazebo/reset_simulation. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:21-24 |
| The action space is spaces.Discrete(3), commented #F,L,R. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:26 |
| discretize_observation samples every len(ranges)/new_ranges beam, maps infinity to 6, NaN to 0 and any other range to int(range), and sets done when a range is greater than 0 and below 0.2. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:31-46 |
| Action 0 commands linear.x 0.3 and angular.z 0.0, action 1 linear.x 0.05 and angular.z 0.3, and action 2 linear.x 0.05 and angular.z -0.3. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:60-74 |
| A step first calls /gazebo/unpause_physics; a rospy.ServiceException is printed and the step continues. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:54-58 |
| A step retries rospy.wait_for_message('/scan', LaserScan, timeout=5) inside a bare except until a message arrives, with no limit on the number of attempts. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:76-81 |
| A step calls the /gazebo/pause_physics service after reading the scan; a rospy.ServiceException is printed and the step continues. | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:83-88 |
| step discretizes the scan into five ranges; a non-terminal step rewards 5 for action 0 and 1 otherwise, a terminal one rewards -200, and it returns (state, reward, done, {}). | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:90-100 |
| reset calls the /gazebo/reset_simulation and /gazebo/unpause_physics services, waits for a scan, calls /gazebo/pause_physics, and returns the result of discretize_observation(data, 5). | upstream_code | gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:102-137 |
| setup.py declares only gym>=0.2.3 as a runtime dependency. | upstream_code | setup.py:10 |
| The installation guide requires ROS Melodic and Gazebo 9.0.0. | vendor_doc | INSTALL.md:13-15 |
| The README describes GazeboCircuitTurtlebotLidar-v0 as a more complex maze with high-contrast floor and walls, in which lidar is the input that trains the robot's navigation. | vendor_doc | README.md:41 |

## Fidelity contract

`driver.py` describes the deployed fake, not the upstream Gazebo simulator: engine
`analytic:gym-gazebo GazeboCircuitTurtlebotLidar-v0 fake (no Gazebo)`, level F0,
determinism `seeded` with `seed_control` `parameter`, timestep 0 ms, `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot/restore. The fake accepts and stores
`reset(seed=...)` but its start state and its per-tick update do not use the seed; the
upstream `reset()` takes no seed. The `gaps` in `driver.py` disclose the absent ROS/Gazebo
physics, the placeholder five-sector distances, the fact that the fake checks only the
five sampled sectors while upstream checks every beam, the missing Twist/scan/pose model,
the fake-only seed extension, the absent live/sim backend, and the unexposed rendering and
ROS services. `NOT COVERED: the upstream Gazebo simulator and the raw LaserScan stream.`
Model review (2026-11-05) added three gaps: the live-construction hazards of this fake-only
contract (the server process's environment rewritten, standard output written, roslaunch and
`rospy.init_node` in the server process, `GYM_GAZEBO_WORLD_CIRCUIT` required, and the legacy
`_close` that runs `killall -9` on every Gazebo and ROS master process of the host); the
service waits without a timeout, the unbounded `/scan` retries and the printed-only unpause and pause failures; and the `done` flag
of the upstream reset, which the bridge drops.

## Safety

The device risk is R2 (REVIEW.md item 12). `step` publishes `geometry_msgs/Twist` on
`/mobile_base/commands/velocity` (`gazebo_circuit_turtlebot_lidar.py:21`, `60-74`), and the
launch file defaults the base to kobuki and names create and roomba
(`GazeboCircuitTurtlebotLidar_v0.launch:3`, `19-23`). No fact cites that only the simulator
consumes that topic. There is no hardware backend. The latch does not publish a zero Twist
and does not stop a physical base on that topic. The runtime's software e-stop latch refuses further
`cap.world.step.v1` and `cap.world.reset.v1` calls after an e-stop until
`mhs.safety.reset` is accepted; the last observation stays readable, and the latch sends
nothing to a simulator. In the upstream environment each completed step or reset ends with an
unchecked `/gazebo/pause_physics` call (`gazebo_circuit_turtlebot_lidar.py:83-88, 128-133`), so
Gazebo is normally left paused with the last Twist still commanded; a failed pause call is only
printed, and any client that unpauses Gazebo lets the simulated TurtleBot drive on with the last
Twist. `safe_state` states this (model review, 2026-11-05: it previously said the simulation
stops advancing). This is not a safety certification or a safety-rated channel.

## Tags

`gym`, `gazebo`, `ros`, `ros1`, `turtlebot`, `lidar`, `simulation`, `reinforcement-learning`
