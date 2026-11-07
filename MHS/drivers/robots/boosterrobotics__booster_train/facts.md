# Facts and tags for gh.boosterrobotics/booster_train

Every fact cites its source at commit `8bb5b53824e0fbcfe69a5cb78a81f4bddb3e2a6e`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the registered Gymnasium task `Booster-T1-MotionTracking-v0`. The clone does not define the
environment class: it registers `isaaclab.envs:ManagerBasedRLEnv` and supplies the `RoughWoStateEstimationEnvCfg`
configuration, which is the card's entry symbol and the driver's `native`.

| fact | source | ref |
|---|---|---|
| Booster-T1-MotionTracking-v0 is registered with entry point isaaclab.envs:ManagerBasedRLEnv, env_cfg_entry_point env_cfg.RoughWoStateEstimationEnvCfg, rsl_rl_cfg_entry_point ppo_cfg.PPORunnerCfg and the environment checker disabled | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/__init__.py:13-21 |
| The registered T1 policy environment is RoughWoStateEstimationEnvCfg, which derives from FlatWoStateEstimationEnvCfg; that parent sets the policy motion_anchor_pos_b and base_lin_vel observation terms to None | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/env_cfg.py:42-50 |
| FlatEnvCfg assigns the T1 robot configuration, the T1 action scale, the motion file t1_dance.npz, the trunk motion anchor and 18 tracked body names from the trunk to the ankles | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/env_cfg.py:10-38 |
| The default T1 motion file is the bare relative name t1_dance.npz, not a path under booster_assets | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/env_cfg.py:17 |
| TrackingEnvCfg is a ManagerBasedRLEnvCfg that groups the scene, observations, actions, commands, rewards, terminations, events and curriculum configuration | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/tracking_env_cfg.py:307-320 |
| The environment uses decimation 4 over a 0.005 s simulation step and an episode length of 10.0 s, so one control step is 0.02 s and the time-out is 500 control steps | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/tracking_env_cfg.py:325-328 |
| The sole action term is a joint-position action over every joint of the robot with the default joint positions as offset | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/tracking_env_cfg.py:107 |
| The policy observation group concatenates the motion command, the motion anchor orientation matrix prefix, base angular velocity, joint position, joint velocity and the last action, in that order, with corruption enabled | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking/tracking_env_cfg.py:119-134 |
| The motion command is the concatenation of the reference joint positions and joint velocities loaded from the motion file | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/mdp/commands.py:137-139 |
| MotionLoader asserts that the motion file exists, loads it with numpy and reads fps, joint positions, joint velocities, body positions, orientations and linear and angular velocities, selecting the tracked bodies and joints by name | upstream_code | source/booster_train/booster_train/tasks/manager_based/beyond_mimic/mdp/commands.py:30-65 |
| The T1 robot configuration spawns T1_23dof.urdf from the external booster_assets directory, so the 23-DoF robot description is not part of this clone | upstream_code | source/booster_train/booster_train/assets/robots/booster_t1.py:22-25 |
| T1_CSV_JOINT_NAMES lists the 23 T1 joints in motion order: two head joints, four joints per arm, the waist yaw joint, four joints per leg and two ankle joints per leg | upstream_code | source/booster_train/booster_train/assets/robots/motion_joint_names.py:28-52 |
| The T1 actuator groups cover the arms, waist, legs, feet and head, which are the joints the joint-position action term drives | upstream_code | source/booster_train/booster_train/assets/robots/booster_t1.py:58-125 |
| The repository targets Isaac Lab 2.3.2 and Isaac Sim 5.1.0 and supports the T2, T1 and K1 platforms | vendor_doc | README.md:5-7 |
| booster_assets must be cloned and installed separately because it holds the Booster robot models and motion data | vendor_doc | README.md:19-21 |
| The package is installed in editable mode with python -m pip install -e source/booster_train | vendor_doc | README.md:27 |
| After training, deployment in MuJoCo or on real Booster robots is done in the separate booster_deploy repository | vendor_doc | README.md:63 |
| The training script launches the Omniverse app through AppLauncher(parser) before the environment is created | upstream_code | scripts/rsl_rl/train.py:49 |
| The training script creates the registered task with gym.make(task, cfg=env_cfg), so the environment is driven through the Gymnasium make/step/reset interface | upstream_code | scripts/rsl_rl/train.py:155 |

Limits: the driver declares none. The clone states no bound on the action: the action term is a joint-position action
whose unitless values are scaled to a joint target by `T1_ACTION_SCALE` (`assets/robots/booster_t1.py:128-168`), and
the actual joint limits are in the external `T1_23dof.urdf` (not in the clone), so the bridge derives an unbounded
action space (23 array elements, no per-element bound) and refuses a wrong length as `MHS.CAPABILITY.INPUT_INVALID`.
`ticks` is bounded by the bridge (1 to 10000 by default). The device is simulated (R0), so no limit is
`operator_required`. The action vector's 23 elements follow the T1 motion joint order
(`assets/robots/motion_joint_names.py:28-52`); the URDF that fixes the real joint set is downloaded with
booster_assets and is not in the clone.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Booster-T1-MotionTracking-v0`, level F1 (Isaac
Sim/PhysX rigid-body dynamics with contacts, as configured by the terrain and articulation settings), determinism
`seeded` with `seed_control` `parameter`, timestep 20 ms (one control step: `sim.dt` 0.005 s times `decimation` 4,
`tracking_env_cfg.py:325-328`; the 5 ms physics step is named in the gaps), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what the fake does not model, that the T1 URDF and motion NPZ
are not in the clone, and that neither the upstream environment nor the fake was compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No physical robot is commanded: deployment is delegated to a separate repository (README.md:63).

Tags: booster, t1, humanoid, motion-tracking, beyondmimic, isaac-lab, isaac-sim, reinforcement-learning, simulation,
gymnasium
