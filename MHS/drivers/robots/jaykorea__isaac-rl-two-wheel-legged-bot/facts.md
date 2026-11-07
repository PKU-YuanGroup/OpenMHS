# Facts and tags for gh.jaykorea/isaac-rl-two-wheel-legged-bot

Every fact cites its source at commit `d922cce9e07a8877c37e12b2cb39dfdcf34b9d40`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The package is
model-authored and unreviewed: it is checked on the fake backend only and no simulator or hardware run is claimed.

| fact | source | ref |
|---|---|---|
| Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint is registered with entry point lab.flamingo.isaaclab.isaaclab.envs:ManagerBasedConstraintRLEnv and the FlamingoFlatEnvCfg configuration | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/__init__.py:22-30 |
| The environment class is a Gymnasium Env for a vectorized manager-based workflow: ManagerBasedConstraintRLEnv(ManagerBasedEnv, gym.Env) | upstream_code | lab/flamingo/isaaclab/isaaclab/envs/manager_based_constraint_rl_env.py:29-35 |
| The default action terms are six joint-position targets for the left/right hip, shoulder and leg joints with scale 2.0 and two wheel-velocity targets for the left/right wheel joints with scale 20.0, so the action has eight values | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/flat_env/stand_drive/flat_env_stand_drive_cfg.py:36-52 |
| The action space is Box(low=-inf, high=inf) with shape (action_dim,) and the observation space is a Dict of Box(low=-inf, high=inf) groups, both batched over num_envs | upstream_code | lab/flamingo/isaaclab/isaaclab/envs/manager_based_constraint_rl_env.py:327-348 |
| The flat velocity config defaults to 4096 parallel environments | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/velocity_env_cfg.py:419 |
| The flat velocity config sets decimation 4 and sim.dt 0.005 s, so one environment step advances 20 ms of simulated time | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/velocity_env_cfg.py:433-436 |
| The Flamingo velocity flat task sets episode_length_s to 20.0 s | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/flat_env/stand_drive/flat_env_stand_drive_cfg.py:247-251 |
| max_episode_length is ceil(episode_length_s / step_dt), 1000 steps for 20 s at 20 ms per step | upstream_code | lab/flamingo/isaaclab/isaaclab/envs/manager_based_constraint_rl_env.py:97-105 |
| The time_out constraint truncates the episode when episode_length_buf reaches max_episode_length | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/mdp/constraints.py:59-61 |
| The base_contact constraint terminates on a contact force above 1.0 on base_link, hip, shoulder or leg bodies | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/flat_env/stand_drive/flat_env_stand_drive_cfg.py:67-72 |
| The stack_policy observation group concatenates joint_pos, joint_vel, base_ang_vel, base_euler and actions terms in that order | upstream_code | lab/flamingo/tasks/constraint_based/locomotion/velocity/velocity_env_cfg.py:240-250 |
| step processes the action, runs the simulation for cfg.decimation steps, computes the constraint and reward buffers, resets terminated environments, computes observations and returns observations, rewards, reset_delta, reset_time_outs and extras | upstream_code | lab/flamingo/isaaclab/isaaclab/envs/manager_based_constraint_rl_env.py:165-245 |
| The README targets Isaac Sim 4.5, Isaac Lab 2.0.0, Python 3.10 and Linux | vendor_doc | README.md:3-6 |
| The package is installed with pip install -e . from the repository root | vendor_doc | README.md:68-73 |
| The USD assets are not uploaded by git and must be unzipped manually under the assets folder | vendor_doc | README.md:74-78 |
| The training script creates the task with gym.make(task, cfg=env_cfg, render_mode=...) | upstream_code | scripts/co_rl/train.py:117 |
| The training script seeds the environment with env.seed(agent_cfg.seed) | upstream_code | scripts/co_rl/train.py:162 |

Limits: the driver declares none. The action space is `Box(low=-inf, high=inf)` with eight values
(`manager_based_constraint_rl_env.py:342-344`, `flat_env_stand_drive_cfg.py:36-52`), so the bridge derives no finite
action bound and there is no catalogue limit to narrow. `ticks` is bounded by the bridge (1 to 10000 by default).
The device is simulated (R0), so no limit is `operator_required` and no site-limits overlay is provided.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
`isaaclab:Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint`, level F0 because only the interface stand-in is shipped
(no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (decimation 4 x sim.dt 0.005 s,
`velocity_env_cfg.py:433-436`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say that the fake models no physics, that only one environment and the 28-value stack_policy observation are
represented, and that the upstream Isaac Sim environment was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: flamingo, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium, two-wheel-legged-bot
