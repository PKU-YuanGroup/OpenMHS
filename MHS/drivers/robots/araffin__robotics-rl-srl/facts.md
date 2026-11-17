# Facts and tags for gh.araffin/robotics-rl-srl

Every fact cites its source at commit `eae7c1ab310c79662f6e68c0d255e08641037ffa`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| OmnirobotEnv-v0 is registered to the OmniRobotEnv class | upstream_code | environments/registry.py:52 |
| The registry builds the entry point from env_class.__module__ + ':' + env_class.__name__ | upstream_code | environments/registry.py:66-72 |
| USING_OMNIROBOT_SIMULATOR defaults to True | upstream_code | real_robots/constants.py:14 |
| When USING_OMNIROBOT_SIMULATOR is true the environment constructs OmniRobotSimulatorSocket with output_size [RENDER_WIDTH, RENDER_HEIGHT] and random_target; otherwise it connects a ZMQ PAIR socket to HOSTNAME:self.server_port | upstream_code | environments/omnirobot_gym/omnirobot_env.py:130-138 |
| The separate ROS server creates publishers for /position_commands, /stop, /wheel_speeds_commands and /velocity_commands | upstream_code | real_robots/omnirobot_server.py:71-83 |
| The separate ROS server publishes True to both position and velocity controller switches during construction | upstream_code | real_robots/omnirobot_server.py:88-92 |
| is_discrete defaults to True | upstream_code | environments/omnirobot_gym/omnirobot_env.py:73-75 |
| The default action space is spaces.Discrete(N_DISCRETE_ACTIONS) | upstream_code | environments/omnirobot_gym/omnirobot_env.py:105-106 |
| N_DISCRETE_ACTIONS is 4 | upstream_code | environments/omnirobot_gym/omnirobot_env.py:35 |
| The discrete action values are FORWARD 0, BACKWARD 1, LEFT 2, RIGHT 3 and STOP 4 | upstream_code | real_robots/constants.py:114-119 |
| A step sends the action to the simulator socket, reads the state, receives and resizes the camera frame, and returns a 4-tuple (observation, reward, done, {}) | upstream_code | environments/omnirobot_gym/omnirobot_env.py:193-214 |
| A reset clears the episode flag and the step and contact counters, sends the reset command, reads the state and observation, and returns the observation without an info dictionary | upstream_code | environments/omnirobot_gym/omnirobot_env.py:267-288 |
| The native reset signature takes no arguments besides self | upstream_code | environments/omnirobot_gym/omnirobot_env.py:267 |
| RENDER_WIDTH and RENDER_HEIGHT are 224 | upstream_code | environments/omnirobot_gym/omnirobot_env.py:29-30 |
| The observation space is Box(0, 255, shape=(RENDER_WIDTH, RENDER_HEIGHT, 3), dtype=np.uint8) | upstream_code | environments/omnirobot_gym/omnirobot_env.py:120-122 |
| The simulator samples the robot's initial x and y with numpy's random_sample from the INIT_MIN/MAX bounds | upstream_code | real_robots/omnirobot_utils/omnirobot_manager_base.py:88-89 |
| INIT_MIN_X = -0.7, INIT_MAX_X = 0.7, INIT_MIN_Y = -0.7 and INIT_MAX_Y = 0.7 | upstream_code | real_robots/constants.py:96-97 |
| On a reset the simulator draws a target in x and y with numpy's random_sample from the TARGET_MIN/MAX bounds when random_target is true or on the first episode | upstream_code | real_robots/omnirobot_simulator_server.py:413-419 |
| TARGET_MIN_X = -0.7, TARGET_MAX_X = 0.7, TARGET_MIN_Y = -0.7 and TARGET_MAX_Y = 0.7 | upstream_code | real_robots/constants.py:100-101 |
| MIN_X = -0.85, MAX_X = 0.85, MIN_Y = -0.85 and MAX_Y = 0.85 | upstream_code | real_robots/constants.py:92-93 |
| STEP_DISTANCE is 0.1 m | upstream_code | real_robots/constants.py:121 |
| A forward move is refused when robot_pos[0] + STEP_DISTANCE is not below MAX_X and the manager reports a bump; backward, left and right use MIN_X, MAX_Y and MIN_Y analogously | upstream_code | real_robots/omnirobot_utils/omnirobot_manager_base.py:27-68 |
| The reward is REWARD_TARGET_REACH when the robot-target distance is below DIST_TO_TARGET_THRESHOLD, REWARD_BUMP_WALL for a wall bump and REWARD_NOTHING otherwise | upstream_code | real_robots/omnirobot_utils/omnirobot_manager_base.py:152-158 |
| REWARD_TARGET_REACH is 1, REWARD_NOTHING is 0 and REWARD_BUMP_WALL is -1 | upstream_code | real_robots/constants.py:81-83 |
| DIST_TO_TARGET_THRESHOLD is 0.2 m | upstream_code | real_robots/constants.py:110 |
| MAX_STEPS is 250 | upstream_code | real_robots/constants.py:90 |
| _hasEpisodeTerminated returns True when episode_terminated is set or the step counter is greater than MAX_STEPS | upstream_code | environments/omnirobot_gym/omnirobot_env.py:290-301 |
| SRLGymEnv.seed sets np_random and returns [seed] | upstream_code | environments/srl_env.py:71-78 |
| The simulator samples positions with numpy's random_sample() | upstream_code | real_robots/omnirobot_utils/omnirobot_manager_base.py:88-89 |

Limits: `action.index` is derived from the fake's `Discrete(4)` and remains 0 through 3. The generated bound
identifies the fake backend and claims no upstream source. The matching native space is separately documented by
`Discrete(N_DISCRETE_ACTIONS)` at `environments/omnirobot_gym/omnirobot_env.py:105-106`, the cardinality 4 at `:35`,
and movement codes 0..3 at `real_robots/constants.py:114-118`; STOP=4 is outside the space. An insufficient
`action_space_ref` was removed rather than accepted as a sourced-bound warning. `ticks` is the bridge's step
budget (1 to `max_ticks`, 10000 by default). No limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:OmnirobotEnv-v0 (analytic fake of the
in-process simulator)`, level F0, determinism `seeded` with `seed_control` `parameter` for the fake (the fake's
legacy `seed()` controls its own generator; upstream `SRLGymEnv.seed` only sets `np_random`, as the facts above
say), `timestep_ms` 0 (a step is one 0.1 m discrete command, not an integration interval), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: no rendering (the fake
returns a 16 x 16 x 3 placeholder marker image while the device returns 224 x 224 x 3), no noise, no PyBullet, Gazebo
or ROS path, no seeded control of the upstream simulator's global numpy draws, reset options that the family
advertises but the native reset does not take, and no comparison with the upstream simulator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware backend is declared.

Scope: only the package fake and the pinned default in-process simulator are described as R0. The separate ROS
server publishes position, wheel-speed and velocity commands and enables both controllers during construction
(`real_robots/omnirobot_server.py:71-92`). Changing `USING_OMNIROBOT_SIMULATOR` can select a ZMQ route to that
server; the software latch does not stop a real robot, and that route is outside this contract.

Tags: omnirobot, robotics, reinforcement-learning, simulation, gymnasium
