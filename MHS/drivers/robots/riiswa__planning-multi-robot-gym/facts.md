# Facts and tags for gh.riiswa/planning-multi-robot-gym

Every fact cites its source at commit `dbb4eb5ab82e4143d1d567095eacae7bdb390b0b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment simulates the movements of multiple robots in an environment with barriers and a target, and the goal is to navigate the robots to the target while avoiding collisions | vendor_doc | README.md:5 |
| The action space is a Dict of two Box arrays named vR and vL, each with one value per robot and each element bounded by -max_velocity and +max_velocity | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:85-90 |
| The observation is a Dict with vR, vL and theta (one value per robot), robot_positions (n_robots x 2), future_target_position (2) and future_obstacle_positions ((n_barriers - 1) x 2) | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:92-113 |
| The play field corners are x from -4.0 to 4.0 and y from -3.0 to 3.0 | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:80 |
| A reset draws each barrier position uniformly between the play-field bounds and each barrier velocity from a normal distribution with standard deviation barrier_velocity_range | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:154-162 |
| A reset draws the target index uniformly from 0 to n_barriers - 1 | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:164 |
| A reset places robot i at x = left play-field corner - 0.5, y = -2.0 + 0.8 * i, with theta 0.0 | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:166 |
| Barriers move by their velocity times dt on every step, and a velocity component is reversed when the barrier passes the matching play-field edge | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:170-181 |
| The wheel spacing of the differential-drive model is twice robot_radius | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:68 |
| The pose model moves straight when the wheel speeds are equal, rotates in place when they are opposite, and follows an arc otherwise | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:183-212 |
| A step limits each wheel's speed change to max_acceleration * dt, then integrates the pose over dt | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:222-238 |
| The future obstacle and target positions are predicted by advancing a copy of the barriers steps_ahead_to_plan steps without moving the simulation state | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:129-144 |
| A robot closer than barrier_radius + robot_radius to the target barrier earns reach_target_reward and a new target is drawn; the same distance to another barrier or another robot earns collision_penalty | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:250-264 |
| An episode is terminated only when reset_when_target_reached is true and a robot reached the target; truncated is always false | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:269 |
| The info dictionary reports n_robots, max_acceleration, max_velocity, barrier_radius, robot_radius, dt and tau | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:115-124 |
| The environment is registered as PlanningMultiRobot-v0 with entry point planning_multi_robot_gym:PlanningMultiRobotEnv | upstream_code | planning_multi_robot_gym/__init__.py:5-8 |
| The environment metadata declares the render modes rgb_array and human with render_fps 30 | upstream_code | planning_multi_robot_gym/planning_multi_robot_env.py:24 |

Limits: the driver declares none. The only action bounds are the two Box spaces of the environment, which the bridge
derives from the environment instance (`vR` and `vL`: one bound per robot, no source, ref
`action_space of the fake backend .fake:FakePlanningMultiRobotEnv`), plus `ticks` bounded by the bridge (1 to
`max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required` and there is no
site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:PlanningMultiRobot-v0`, level F1 (planar
differential-drive kinematics with circle distance tests, no contacts, wheel slip, actuator, sensor or noise model),
determinism `seeded` with `seed_control` `parameter`, timestep 100 ms (the upstream default `dt` of 0.1 s,
`planning_multi_robot_env.py:37`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say what is not modelled, that the fake was not compared with the upstream environment, that the `info` member
`predict_position` is a callable dropped from JSON, and that no frame is rendered.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: multi-robot, planning, obstacle-avoidance, reinforcement-learning, simulation, gymnasium
