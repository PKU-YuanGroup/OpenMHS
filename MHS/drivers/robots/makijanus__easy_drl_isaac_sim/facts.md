# Facts and tags for gh.makijanus/easy_drl_isaac_sim

Every fact cites its source at commit `aa7fcf6d8a8c707ca3d94a8db7dad0de13a45245`: `vendor_doc` (a text file of the
clone such as `README.md`) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README requires Isaac Sim 2021.2.1 and installs the library by copying DRL_Isaac_lib into the Isaac Sim package directory | vendor_doc | README.md:70-74 |
| Isaac_envs is a gym.Env whose metadata declares render.modes human | upstream_code | DRL_Isaac_lib/env.py:15-16 |
| The constructor defaults are skip_frame 1, physics_dt 1/60 s, rendering_dt 1/60 s, max_episode_length 3000, seed 0 and headless True | upstream_code | DRL_Isaac_lib/env.py:18-25 |
| The step interval is stored as physics_dt * skip_frame and the reset offset as int(rendering_dt / physics_dt) | upstream_code | DRL_Isaac_lib/env.py:31-34 |
| The constructor hardcodes env_name random_walk, robot_name jetbot and action_type discrete | upstream_code | DRL_Isaac_lib/env.py:40-42 |
| For random_walk the constructor builds the fixed vertical path map with random=False, then draws a random robot pose and target | upstream_code | DRL_Isaac_lib/env.py:53-57 |
| get_action_space returns spaces.Discrete(3) for the discrete action type | upstream_code | DRL_Isaac_lib/isaac_robots.py:312-313 |
| The observation space is a Dict of three Boxes: IR_raleted shape (1,12) in [0,1], pos_raleted shape (2,) low [0,-pi] high [8,pi], and vel_raleted shape (2,) low [0,-pi/4] high [10,pi/4] | upstream_code | DRL_Isaac_lib/env.py:96-120 |
| The Jetbot's three discrete movements are [15, 0.785], [25, 0] and [15, -0.785], each a [linear, yaw] pair | upstream_code | DRL_Isaac_lib/isaac_robots.py:317-320 |
| The differential controller uses wheel radius 3.25 and wheel base 11.25 for the Jetbot and computes the two wheel joint velocities from the [linear, yaw] command | upstream_code | DRL_Isaac_lib/isaac_robots.py:142-163 |
| step applies the selected movement for each skip frame, calls differential_controller for a differential robot, advances the world with world.step(render=False), and returns (observations, reward, done, info) | upstream_code | DRL_Isaac_lib/env.py:126-193 |
| The observation is the lidar ranges, the goal distance and angular difference, and the base linear and angular velocity | upstream_code | DRL_Isaac_lib/env.py:220-237 |
| The lidar interface resizes its depth array to (1, number_lasers) | upstream_code | DRL_Isaac_lib/isaac_envs.py:235-243 |
| distance_to measures the 3D Euclidean distance and angular_difference_to computes theta from the quaternion components and returns a wrapped theta-alpha angle | upstream_code | DRL_Isaac_lib/isaac_robots.py:222-260 |
| The episode ends when current_time_step_index - steps_after_reset reaches max_episode_length, when the minimum lidar range is <= 0.155, or when the goal distance is <= 0.5 | upstream_code | DRL_Isaac_lib/env.py:157-189 |
| The reward starts as distance_reward = -distance/100 and is scaled by 1 - index/max_episode_length only when distance_reward is positive, minus 10*(0.6 - minimum_lidar) on a lidar collision, and plus 10 + 90*(1 - index/max_episode_length) at the goal | upstream_code | DRL_Isaac_lib/env.py:168-189 |
| reset calls world.reset() and, for random_walk, randomizes the goal position and then the robot pose; it returns only the observation | upstream_code | DRL_Isaac_lib/env.py:195-213 |
| The seed method uses gym.utils.seeding.np_random(seed), calls np.random.seed(seed) and returns [seed] | upstream_code | DRL_Isaac_lib/env.py:249-252 |
| The lidar is created with 12 lasers, a 360-degree horizontal FOV, a 30-degree vertical FOV, 360/number_lasers horizontal resolution, rotation_rate 0 and yaw_offset 0 | upstream_code | DRL_Isaac_lib/isaac_envs.py:157-219 |
| For the Jetbot the lidar min_range is 0.15 and max_range is 1 | upstream_code | DRL_Isaac_lib/isaac_envs.py:166-171 |
| The random_walk map uses map_dist_unit 0.5 and height 0.2 for the Jetbot, a 5x5 grid, four outer walls and one cube for every grid cell | upstream_code | DRL_Isaac_lib/isaac_envs.py:248-321 |
| The fixed map array is rotated counter-clockwise with np.rot90, and a cell is visible when its rotated value is 1 | upstream_code | DRL_Isaac_lib/isaac_envs.py:365-387 |
| The random reset draws the robot x as map_dist_unit * randint(map_dimension), its y as -1.5*map_dist_unit and its orientation quaternion as [0, 0, sin(a), cos(a)] with a = rand()*pi; the goal x is drawn the same way with y = 5.5*map_dist_unit and z = 0.25 | upstream_code | DRL_Isaac_lib/isaac_envs.py:409-430 |
| get_observations acquires depth camera data but does not use it; the returned dictionary contains only IR_raleted, pos_raleted and vel_raleted | upstream_code | DRL_Isaac_lib/env.py:215-240 |
| render returns without drawing and close closes the SimulationApp | upstream_code | DRL_Isaac_lib/env.py:242-247 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(3)`: `action.index` from 0 to 2, with the source `upstream_code` and the ref
`DRL_Isaac_lib/isaac_robots.py:313`, where `spaces.Discrete(3)` shows the largest action 2), and `ticks` (1 to
`max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaac-sim-2021.2.1 (analytic fake)`, level F0 (the fake
integrates commanded velocity directly; no dynamics, contacts, actuator or sensor model), determinism `seeded` with
`seed_control` `parameter`, timestep 1000/60 ms (the default `physics_dt * skip_frame`, 1/60 s), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake uses
`random.Random` rather than upstream's numpy generator, that the camera arrays are not covered, and that the fake was
never compared with Isaac Sim.

The fake's linear command gain of 0.01 is a placeholder, not a verified unit conversion: the cited wheel-controller
code states no linear command unit. The goal-angle calculation preserves the pinned quaternion expression
(`DRL_Isaac_lib/isaac_robots.py:245-259`); for the fake's planar quaternion its theta is pi rather than yaw. The
simulator's quaternion convention was not validated.

A live wrapper would need separate lifecycle and output handling: the constructor starts `SimulationApp` and uses
flat module imports (`DRL_Isaac_lib/env.py:27-37`), reset and the goal branch print to stdout (`:207-210`, `:185-189`),
and `close` closes the app (`:245-247`). Only the fake backend is served, and its latch controls no external timeline.

Safety: simulated R0 fake. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No physical stop, no hardware backend and no operator-required bound is declared.

Tags: isaac-sim, jetbot, reinforcement-learning, simulation, gymnasium, random-walk
