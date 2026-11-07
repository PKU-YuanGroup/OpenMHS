# Facts and tags for gh.tommasovandermeer/social-navigation-pyenvs

Every fact cites its source at commit `f9cd244d3e529247ca1031364de22954717b9493`: `upstream_code`
(`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SocialGym-v0 is registered with entry point social_gym.social_nav_gym:SocialNavGym | upstream_code | social_gym/__init__.py:3-6 |
| SocialNavGym is both a gymnasium Env and a SocialNavSim | upstream_code | social_gym/social_nav_gym.py:14 |
| The action and observation spaces are dummy Discrete(1) spaces, declared just for registration | upstream_code | social_gym/social_nav_gym.py:55-57 |
| reset raises AttributeError when no robot has been set and accepts only the train, val and test phases | upstream_code | social_gym/social_nav_gym.py:125-126 |
| reset seeds numpy from the phase's case counter, not from a caller-supplied seed | upstream_code | social_gym/social_nav_gym.py:137 |
| reset puts the robot at the configured start pose, resets the simulator and installs both time steps | upstream_code | social_gym/social_nav_gym.py:213-217 |
| One environment step applies the same action for robot_time_step/time_step sub-steps and advances global time by time_step in each | upstream_code | social_gym/social_nav_gym.py:240-245 |
| The robot action is ActionXY(vx, vy) with holonomic kinematics and ActionRot(v, r) with unicycle kinematics | upstream_code | crowd_nav/utils/action.py:3-4 |
| The unicycle update moves by v in the direction yaw+r and then adds r to yaw; the holonomic update moves by (vx, vy) | upstream_code | social_gym/src/robot_agent.py:116-136 |
| The repository's example env.config sets time_limit 50 s, time_step 0.0125 s and robot_time_step 0.25 s | upstream_code | crowd_nav/configs/env.config:2-4 |
| configure reads the time steps and rejects a robot time step that is not a multiple of the time step | upstream_code | social_gym/social_nav_gym.py:61-65 |
| The observation is the list of the humans' observable states, computed by compute_humans_observable_state | upstream_code | social_gym/social_nav_gym.py:100-105 |
| An observable human state carries px, py, vx, vy and radius | upstream_code | crowd_nav/utils/state.py:24-30 |
| The reward is zero and truncated at time_limit-1; a collision pays collision_penalty and terminates; reaching the goal pays success_reward and terminates; a close pass pays a discomfort penalty | upstream_code | social_gym/social_nav_sim.py:1004-1028 |
| The example env.config sets success_reward 1, collision_penalty -0.25, discomfort_dist 0.2 and discomfort_penalty_factor 0.5 | upstream_code | crowd_nav/configs/env.config:11-14 |
| The constructor starts the circular_crossing scenario with the robot inserted | upstream_code | social_gym/social_nav_gym.py:25 |
| The circular crossing generator defaults to 10 actors, a circle radius of 7 and a robot radius of 0.3 | upstream_code | social_gym/social_nav_sim.py:207-209 |

Limits: the driver declares none.  The only bounds are the bridge's `ticks` (1 to `max_ticks`, 10000 by default) and
the shapes of the fake's action and observation boxes; the upstream action magnitude has no stated bound and is left
unbounded.  The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `social_gym:SocialGym-v0`, level F1 (one robot and one
constant-velocity human; no crowd model, walls, rendering or policy), determinism `seeded` with `seed_control`
`parameter` for the fake only (the upstream reset seeds numpy from its phase case counter), timestep 250 ms (one
step applies the action for the example robot_time_step 0.25 s), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore.  The gaps say what is not modelled and that the fake was never compared with the upstream
environment.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation and counters stay readable.

Tags: social-navigation, crowd-simulation, reinforcement-learning, simulation, gymnasium
