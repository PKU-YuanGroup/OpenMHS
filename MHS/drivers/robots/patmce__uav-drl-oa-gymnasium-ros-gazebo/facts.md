OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.patmce/uav-drl-oa-gymnasium-ros-gazebo

Every fact cites the pinned clone at commit `7e72584e02545c782bc15f3a73480a228a9498af`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name a text file of the clone.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

## Shape

The card named a `RosDriver` family `ros` package. The entry symbols the card lists are Gymnasium
environment classes (`DroneGymGazeboEnv(gymnasium.Env)` at `step1/new_drone_gym_gazebo_env.py:33`
and `step2/eval_drone_gym_gazebo_env.py:33`), and the environment, not a ROS topic or service, is
the primary control interface. A Gymnasium environment does not become a ROS transport driver
because the repository also contains ROS launch files, so this package is a configuration-only
`GymnasiumDriver` over the step1 copy. This is a deliberate deviation from the card's helper.

The step2 copy registers the same `DroneGymGazeboEnv-v0` id, but changes the reset y selection
from `np.random.choice` to a counter and the goal epsilon from 0.5 to 0.7
(`step2/eval_drone_gym_gazebo_env.py:120-126`, `:312`). One package serves one concrete
environment; this package serves step1, whose registration line the action space cites.

## Facts

| fact | source | ref |
|---|---|---|
| The repository is connected to the paper 'Towards Latency Efficient DRL Inference: Improving UAV Obstacle Avoidance at the Edge Through Model Compression' | vendor_doc | README.md:3 |
| The setup clones the external decargroup/ifo_gazebo Gazebo model and PX4-Autopilot workspace | vendor_doc | README.md:20-24 |
| The setup clones the external troiwill/mavros-px4-vehicle package, which communicates with the PX4 autopilot through MAVROS | vendor_doc | README.md:79-83 |
| The README instructs copying six Python scripts by hand into the mavros-px4-vehicle catkin package's scripts directory | vendor_doc | README.md:103-109 |
| The environment imports rospy, sensor_msgs, geometry_msgs, std_srvs, cv_bridge and cv2, and imports PX4_MODE_OFFBOARD, SetPositionWithYawCmdBuilder and PX4Vehicle from mavros_px4_vehicle | upstream_code | step1/new_drone_gym_gazebo_env.py:5-24 |
| The constructor creates PX4Vehicle(auto_connect=True) | upstream_code | step1/new_drone_gym_gazebo_env.py:36 |
| The constructor creates the /gazebo pause and unpause service proxies and subscribes to /camera/depth/image_raw and /mavros/local_position/pose | upstream_code | step1/new_drone_gym_gazebo_env.py:73-80 |
| The environment registers DroneGymGazeboEnv-v0 with entry point new_drone_gym_gazebo_env:DroneGymGazeboEnv and max_episode_steps 225 | upstream_code | step1/new_drone_gym_gazebo_env.py:26-31 |
| DroneGymGazeboEnv derives from gymnasium.Env | upstream_code | step1/new_drone_gym_gazebo_env.py:33 |
| The action space is spaces.Discrete(3), commented as three actions forward/left/right | upstream_code | step1/new_drone_gym_gazebo_env.py:39 |
| The observation space is spaces.Box(low=-1.0, high=8.0, shape=(3, 80, 106), dtype=np.float32) | upstream_code | step1/new_drone_gym_gazebo_env.py:41-45 |
| The start point is (0.0, 0.0, 1.5) and the desired point is (7.0, start.y, 1.5) | upstream_code | step1/new_drone_gym_gazebo_env.py:47-55 |
| The workspace bounds are x in (-0.5, 7.5], y in (-1.7, 1.7] relative to start_point.y and z in (0.5, 3.2] | upstream_code | step1/new_drone_gym_gazebo_env.py:57-63 |
| The goal reward is 100, speed is 0.5 m/s, action_duration is 0.5 s and the candidate y start/desired points are 0.0, -5.0, -10.0 and -15.0 | upstream_code | step1/new_drone_gym_gazebo_env.py:66-69 |
| step unpauses Gazebo, applies the action, pauses Gazebo and returns (observation, reward, terminated, False, {}) | upstream_code | step1/new_drone_gym_gazebo_env.py:83-92 |
| reset takes options then seed and calls random.seed(seed) when a seed is given | upstream_code | step1/new_drone_gym_gazebo_env.py:94-104 |
| When the drone is not armed (commented as the first call of reset) reset unpauses Gazebo, arms the drone, goes to takeoff height and sets offboard mode; otherwise it draws the start y with np.random.choice(self.possible_y_start_desired_points) | upstream_code | step1/new_drone_gym_gazebo_env.py:106-121 |
| The other reset branch unpauses Gazebo, sends the drone to x-0.5, then up to work_space_z_max + 1.0, then to the start point x and y at that height, with rospy.sleep waits of 8, 4 and 8 s, goes to takeoff height and pauses Gazebo | upstream_code | step1/new_drone_gym_gazebo_env.py:128-150 |
| reset ends by calling reset_dist_to_desired_point_and_observations and returning _get_obs() | upstream_code | step1/new_drone_gym_gazebo_env.py:152-153 |
| forward and left_or_right read the current pose and send a set_pose2d setpoint offset by round(self.speed, 2) in x, or by direction * speed in y, at start_point.z | upstream_code | step1/new_drone_gym_gazebo_env.py:233-251 |
| unpause_sim and pause_sim wait for the Gazebo service with rospy.wait_for_service and only print a failed call | upstream_code | step1/new_drone_gym_gazebo_env.py:166-178 |
| The constructor's readiness checks retry rospy.wait_for_message with a 5 s timeout until a depth image and a pose arrive or ROS shuts down | upstream_code | step1/new_drone_gym_gazebo_env.py:180-200 |
| _set_action maps 0 to forward, 1 to left_or_right(1) and 2 to left_or_right(-1), holding each action for action_duration seconds | upstream_code | step1/new_drone_gym_gazebo_env.py:253-273 |
| _get_obs writes desired.x - x and desired.y - y into the position channel and concatenates the current depth image, the previous depth image and that position map | upstream_code | step1/new_drone_gym_gazebo_env.py:294-305 |
| is_in_desired_position defaults epsilon to 0.5 and tests x and y against desired +/- epsilon | upstream_code | step1/new_drone_gym_gazebo_env.py:307-327 |
| is_inside_workspace tests the absolute x and z bounds and the y bounds offset by start_point.y | upstream_code | step1/new_drone_gym_gazebo_env.py:337-348 |
| drone_has_collided treats roll outside (-0.2, 0.2], pitch outside (-0.2, 0.2] or yaw outside (-0.05, 0.05] as a collision | upstream_code | step1/new_drone_gym_gazebo_env.py:350-369 |
| _is_done terminates when the drone leaves the workspace, collides or reaches the desired position | upstream_code | step1/new_drone_gym_gazebo_env.py:371-386 |
| _compute_reward returns -1 plus the reduction in distance while the episode runs, goal_reward when it ends at the desired position and -goal_reward otherwise | upstream_code | step1/new_drone_gym_gazebo_env.py:388-410 |
| close shuts down the ROS node with rospy.signal_shutdown | upstream_code | step1/new_drone_gym_gazebo_env.py:162-164 |
| The step2 copy registers the same DroneGymGazeboEnv-v0 id with entry point eval_drone_gym_gazebo_env:DroneGymGazeboEnv | upstream_code | step2/eval_drone_gym_gazebo_env.py:26-31 |
| The step2 reset selects the start y with a counter that cycles through the four candidate points | upstream_code | step2/eval_drone_gym_gazebo_env.py:120-126 |
| The step2 goal test defaults epsilon to 0.7 | upstream_code | step2/eval_drone_gym_gazebo_env.py:312 |

## Limits

The driver declares no `Limit`. The only bound of the served contract is the environment's own
action space, which the bridge derives from the fake's `Discrete(3)`; `action_space_ref` cites
`step1/new_drone_gym_gazebo_env.py:39`, so the derived `action.index` bound 0..2 is
`upstream_code`. The fake copies that space. `cap.world.step.v1` `ticks` and the reset/seed
inputs are bounded by their catalogue classes. The device risk is R2 (REVIEW.md item 12): `forward`
and `left_or_right` send a pose setpoint through `PX4Vehicle.set_pose2d`
(`step1/new_drone_gym_gazebo_env.py:233-249`), and `README.md:79-83` says that package talks to
the PX4 autopilot through MAVROS. The package still declares no `Limit` of its own, so no bound is
`operator_required` and no site-limits overlay is needed.

## Fidelity contract

`driver.py` `fidelity` describes the fake as deployed: engine
`analytic:DroneGymGazeboEnv-v0 kinematic setpoint stand-in`, level F0 (no dynamics; no
contacts, actuator, sensor or noise model), determinism `seeded` with `seed_control`
`parameter`, `timestep_ms` 0 (one step is a discrete setpoint transition, not a physics
timestep), `realtime_factor` 0 (no wall-clock pacing), clock `lockstep`, reset `full`, no
snapshot and restore. The gaps name the missing ROS/Gazebo/PX4/MAVROS stack, the smaller
3 x 8 x 8 placeholder observation (the real one is 3 x 80 x 106), the absent depth image,
collision and attitude model, the missing 0.5 s action interval, the step1/step2 differences,
the directly implemented 225-step truncation, and the absence of a live backend.

## Safety

Device risk R2, a vehicle in flight. There is no hardware backend. The e-stop is the runtime's
software latch. After an e-stop every step, reset and seed call is refused until
`mhs.safety.reset` clears the latch, and the last observation and tick stay readable. The latch
does not disarm the vehicle and does not clear the pose setpoint sent through
`PX4Vehicle.set_pose2d`, so a physical PX4 behind that MAVROS link is not stopped. The runtime
never treats the simulated observation as a physical safe state.

Model review (2026-11-05): the upstream environment itself ends every completed step and reset
with `/gazebo/pause_physics` (step1:86, :118, :150), but a failed pause is only printed
(step1:173-178), a running step (a 0.5 s busy-wait) or reset (rospy.sleep waits with physics
unpaused) is not interrupted, and the drone stays armed (OFFBOARD after the first reset). The
original `safe_state` ("the simulation stops advancing") was replaced by that description. A
live backend would also inherit the construction hazards listed in the fidelity gaps: no
`rospy.init_node` in the class, unbounded waits for the Gazebo services, a depth image and a
pose, arming and OFFBOARD in `reset`, `rospy.signal_shutdown` in `close`, and stdout prints.
The fake's later resets now start the drone in the chosen lane (step1:144-149); before the
review they left it at y=0, so every non-zero lane terminated on its first step.

## Tags

uav, drone, gazebo, px4, mavros, reinforcement-learning, simulation, gymnasium
