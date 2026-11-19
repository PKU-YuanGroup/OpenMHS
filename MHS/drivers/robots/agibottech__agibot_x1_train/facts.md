# Facts and limits for gh.agibottech/agibot_x1_train

Every fact below cites the clone at `e6651b9ab843fd1b1be70c087bfb7e8b28e44ccd`. The table matches driver.py; generated references come from that driver.

| fact | source | ref |
|---|---|---|
| X1DHStandEnv is a LeggedRobot subclass | upstream_code | humanoid/envs/x1/x1_dh_stand_env.py:79 |
| X1DHStandEnv.step adds the reference action when cfg.env.use_ref_actions is set, then calls LeggedRobot.step | upstream_code | humanoid/envs/x1/x1_dh_stand_env.py:353-356 |
| LeggedRobot.step clips actions to +-cfg.normalization.clip_actions, simulates cfg.control.decimation physics substeps and returns (obs_buf, privileged_obs_buf, rew_buf, reset_buf, extras) | upstream_code | humanoid/envs/base/legged_robot.py:111-155 |
| LeggedRobot.reset takes no arguments, resets every environment, steps zero actions and returns (obs, privileged_obs) | upstream_code | humanoid/envs/base/legged_robot.py:157-162 |
| LeggedRobot.check_termination combines termination contacts, the episode time-out and the roll and pitch cutoffs of 1.5 rad into one reset flag | upstream_code | humanoid/envs/base/legged_robot.py:206-217 |
| X1DHStandCfg.env sets frame_stack=66, num_single_obs=47 and num_observations=3102 | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:41-45 |
| X1DHStandCfg.env sets c_frame_stack=3, single_num_privileged_obs=73 and num_privileged_obs=219 | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:43-48 |
| X1DHStandCfg.env sets num_actions=12 | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:49 |
| X1DHStandCfg.env sets num_envs=4096 for training | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:50 |
| X1DHStandCfg.control sets action_scale=0.5 and decimation=10, and X1DHStandCfg.sim sets dt=0.001 s | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:153-158 |
| X1DHStandCfg.init_state lists the 12 default joint angles in radians | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:128-141 |
| X1DHStandCfg.asset selects the MuJoCo scene resources/robots/x1/mjcf/xyber_x1_flat.xml | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:64 |
| X1DHStandCfg.normalization sets clip_actions=100 and clip_observations=100 | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:366-367 |
| X1DHStandCfgPPO sets the PPO training seed to 5 | upstream_code | humanoid/envs/x1/x1_dh_stand_config.py:370-371 |
| The environment imports isaacgym and torch | upstream_code | humanoid/envs/x1/x1_dh_stand_env.py:35-40 |
| setup.py install_requires lists isaacgym, mujoco==2.3.6 and mujoco-python-viewer | upstream_code | setup.py:44-50 |
| The README says the repository is the reinforcement-learning training code for AgiBot X1, used with separate inference software for real-robot and simulated walking | vendor_doc | README.md:5 |
| The README documents MuJoCo sim2sim validation with scripts/sim2sim.py --task=x1_dh_stand | vendor_doc | README.md:60-64 |
| The environment is registered as x1_dh_stand through the in-tree task_registry, not gym.register | upstream_code | humanoid/envs/__init__.py:39-43 |

## Fake-only contract and limits

The package exposes cap.world.step.v1 and cap.world.reset.v1 for one fake world. Step accepts a 12-value action and repeats it for ticks; the catalogue bounds ticks to 1..10000. The wrapper checks cancellation before each further tick and caches every completed native tick, including a partially cancelled batch. Non-finite native scalars are refused before conversion to boolean terminal flags. Reset accepts only empty options, reports the required seed field as the documented placeholder zero, and makes no RNG-seeding claim. cap.world.seed.v1 is omitted.

The source configuration states clip_actions=100, while the symmetric clip is implemented in legged_robot.py:117-118. The former single-line bound citation cannot support both endpoints for the gate, so action.values is operator_required. site-limits.example.json supplies illustrative fake-scale bounds only. This is not a joint angle or torque envelope.

The fake returns arrays of upstream-configured sizes (3102 and 219), with placeholder layouts and dynamics, and preserves a terminal step's reward across its placeholder auto-reset. It is neither Isaac Gym nor the MJCF/MuJoCo policy loop. Those MJCF assets are alternative sim2sim inputs, not the served engine.

## Live-route gaps and safety

No live backend is enabled. LeggedRobot.step requires a torch.Tensor on the simulator device, whereas this fake-only adapter passes Python lists. A live factory needs tensor conversion and single-environment configuration. Construction acquires Isaac Gym, changes process-wide torch JIT flags and creates a simulator and optional viewer (base_task.py:44-110); the viewer close/QUIT path calls sys.exit and rendering may block in fetch_results or sync_frame_time (155-177). These hazards are not validated by the fake.

The fake world advances only through calls. The latch refuses new step/reset actions and cancellation is checked between ticks; cached state remains readable. The served scope is simulated R0 and controls no physical X1. The cited Python sources state BSD-3-Clause. Evidence is contract_checked only; reviewed_by remains null.
