# Facts and tags for gh.ubi-coro/magbotsim

Every fact cites its source at commit `694e8582164de71fe58c7ef36c68fd4f2b57e054`: `upstream_code` is a code or
comment line of the clone (`path/in/clone:LINE`), and `vendor_doc` would be documentation text. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| StateBasedPushBoxEnv-v0 is registered with max_episode_steps=25 | upstream_code | magbotsim/__init__.py:58-62 |
| The observation space is a Dict with the keys observation, achieved_goal and desired_goal | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:272-286 |
| With learn_jerk and learn_mover_c_rotation false, the observation array is num_movers*4 values: the (x,y) position and (x,y) velocity of each mover | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:1157-1158 |
| When learn_pose is false, achieved_goal is the object's (x,y) position (2 values) and desired_goal the desired (x,y) position (2 values) | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:1162-1175 |
| The action space is a Box of num_movers*2 values bounded by -a_max_xy and a_max_xy | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:288-298 |
| a_max_xy defaults to 10.0 | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:129 |
| max_position_err defaults to 0.05 m and is the position threshold for goal achievement | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:142 |
| The per-step penalty is -0.01, the collision penalty -10.0 and the at-goal reward 1.0 | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:144-146 |
| compute_reward applies the per-step penalty, replaces it with the collision penalty on a collision, and with the at-goal reward when the goal is reached without a collision | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:1134-1142 |
| The episode terminates on a mover collision or a wall collision (or early termination when configured) | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:953 |
| The environment's compute_truncated always returns False: the time limit is the Gymnasium TimeLimit wrapper | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:955-974 |
| The default layout is a 4x3 grid of tiles when layout_tiles is None | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:155-157 |
| The default number of control cycles applied per step is 40 | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:124 |
| The default MuJoCo option sets timestep=0.001 s | upstream_code | magbotsim/basic_magbot_env.py:1340 |
| The environment takes cycle_time from model.opt.timestep | upstream_code | magbotsim/basic_magbot_env.py:297 |
| reset(seed) seeds the gymnasium RNG and rng_noise, and passes options to _reset_callback | upstream_code | magbotsim/rl_envs/basic_single_agent_env.py:134-140 |
| The reset options mover_xy_start_pos, object_xy_start_pos and object_xy_goal_pos override the sampled positions | upstream_code | magbotsim/rl_envs/object_manipulation/pushing/state_based_global_pushing_env.py:690-700 |

Limits: the driver declares none. The only bounds are derived by the bridge from the environment's action space
(`Box` of `num_movers*2` values bounded by `a_max_xy`; the fake publishes the same shape) and from `ticks`
(1 to the bridge's `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is
`operator_required` and no site overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `magbotsim:StateBasedPushBoxEnv-v0`, level F1 (a
kinematic stand-in, no MuJoCo contact or actuator model), determinism `seeded` with `seed_control` `parameter`,
timestep 40 ms (40 control cycles of the 0.001 s default MuJoCo timestep), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what is not modelled and that this package's fake was not
compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: magbotsim, magnetic-robotics, reinforcement-learning, simulation, gymnasium, push-box
