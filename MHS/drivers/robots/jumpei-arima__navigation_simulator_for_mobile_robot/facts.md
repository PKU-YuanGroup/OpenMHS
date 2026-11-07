# Facts and tags for gh.jumpei-arima/navigation_simulator_for_mobile_robot

Every fact cites its source at commit `4727fa696f363e88d757c0896f1c3f0dacc83af3` with
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Nsmr-v1 is registered with entry_point nsmr.envs.NsmrGymEnv:NsmrGymEnv and max_episode_steps=500 | upstream_code | nsmr/envs/__init__.py:7-11 |
| The observation space is a Dict of a lidar Box with num_range elements from min_range to max_range and a target Box with bounds [0.0, -1.0, -1.0] to [100.0, 1.0, 1.0] | upstream_code | nsmr/envs/NsmrGymEnv.py:119-127 |
| The action space is a Box of two values, linear velocity between min_linear_velocity and max_linear_velocity and angular velocity between min_angular_velocity and max_angular_velocity, both read from the robot configuration | upstream_code | nsmr/envs/NsmrGymEnv.py:128-134 |
| The bundled robot configuration sets radius 0.3, linear velocity limits 0.0 and 1.0, and angular velocity limits -1.0 and 1.0 | upstream_code | nsmr/robots/robot.json:2-6 |
| The bundled robot configuration sets linear acceleration 0.5 and angular acceleration 1.0 | upstream_code | nsmr/robots/robot.json:7-8 |
| The bundled lidar configuration has 720 rays, range 0.1 to 30.0, max_angle 1.5707963267948966 and angle_increment 0.004363323129985824 | upstream_code | nsmr/robots/robot.json:17-22 |
| NsmrGymEnv constructs NSMR with only robot and layout | upstream_code | nsmr/envs/NsmrGymEnv.py:25 |
| NSMR's constructor default timestep is dt=0.1 s and it is stored as the simulator's DT | upstream_code | nsmr/envs/nsmr.py:12-18 |
| NSMR.update runs add_bias, stuck, check_action, state_transition and add_noise in that order | upstream_code | nsmr/envs/nsmr.py:71-77 |
| check_action limits the change of each velocity by max_linear_acceleration*DT or max_angular_acceleration*DT and then clamps both to the robot's velocity limits | upstream_code | nsmr/envs/nsmr.py:79-86 |
| state_transition integrates the unicycle pose in closed form and normalizes the heading | upstream_code | nsmr/envs/nsmr.py:88-98 |
| reset_pose draws a random pose until it is collision free and a random target | upstream_code | nsmr/envs/nsmr.py:48-59 |
| reset_noise_param draws the noise parameters from numpy's global random module | upstream_code | nsmr/envs/nsmr.py:61-69 |
| get_lidar returns num_range readings from the Raycasting map, with oversight and range noise | upstream_code | nsmr/envs/nsmr.py:139-152 |
| get_relative_target_position returns [distance, sin(theta), cos(theta)] | upstream_code | nsmr/envs/nsmr.py:154-162 |
| The reward is goal_reward when the distance is below the robot radius, -collision_penalty on a collision and otherwise alpha times the distance change; a stop_penalty is subtracted when there is no progress, and beta/(2*pi)*abs(theta) for the heading error | upstream_code | nsmr/envs/NsmrGymEnv.py:83-98 |
| is_done is true at max_steps, on a collision or after the goal | upstream_code | nsmr/envs/NsmrGymEnv.py:100-108 |
| reset returns only the observation and step returns the legacy 4-tuple (observation, reward, done, info) | upstream_code | nsmr/envs/NsmrGymEnv.py:53-72 |
| NsmrGymEnv.seed assigns self.np_random and returns [seed] | upstream_code | nsmr/envs/NsmrGymEnv.py:113-115 |

Limits: the driver declares none. The only bound is the environment's Box action space, which the bridge derives from
the environment (`action.values` per element: linear velocity 0.0 to 1.0 and angular velocity -1.0 to 1.0 with the
bundled robot configuration, `nsmr/robots/robot.json:3-6`; source `upstream_code`, ref `nsmr/robots/robot.json:3-6`)
plus `ticks` (1 to 10000, bridge bound). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `nsmr:2d-raycasting`, level F0 (kinematic 2D unicycle,
no rigid-body dynamics or contacts), determinism `seeded` with `seed_control` `parameter` (the fake draws its start
pose and target from `random.Random(seed)`; the upstream seed does not reach NSMR's global numpy draws), timestep
100 ms (`dt = 0.1` s, `nsmr/envs/nsmr.py:15,18`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled, that the fake's 720 lidar readings are placeholders at max range, that
there is no rendering or noise model, and that nothing was compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Honest limits of this package: the upstream environment was never installed or run (it needs legacy gym, numpy and the
Cython raycasting extension), so the fake was not compared with it; the fake's lidar is a constant placeholder array,
not a raycast; the fake never reports a collision and its reward is therefore simpler than the upstream's; the fake's
reset positions differ from numpy's stream even for the same seed. The gate checks the package on the fake backend only.

Tags: navigation, mobile-robot, lidar, reinforcement-learning, simulation, gym
