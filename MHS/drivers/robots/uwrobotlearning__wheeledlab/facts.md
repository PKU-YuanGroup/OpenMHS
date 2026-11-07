# Facts and tags for gh.uwrobotlearning/wheeledlab

Every fact cites its source at commit `a5017ce0696032805190448b2addb8077e458387`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The drift task is registered as Isaac-MushrDriftRL-v0 with entry point isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point MushrDriftRLEnvCfg | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/__init__.py:14-21 |
| MushrDriftRLEnvCfg extends ManagerBasedRLEnvCfg and sets seed 42, num_envs 1024 and env_spacing 0 | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:369-373 |
| The drift configuration sets sim.dt = 0.005 s (200 Hz) and decimation = 4 (50 Hz), so one environment step applies one action over four physics steps of 20 ms | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:393-394 |
| The drift episode length is 5 simulated seconds | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:396 |
| The MuSHR action group is an RCCarRWDActionCfg with scale (3.0, 0.488), base length 0.325, base width 0.2, wheel radius 0.05, no_reverse True and bounding strategy clip | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/common/actions.py:8-23 |
| The Ackermann action term reports action_dim 2: target velocity and target steering angle | upstream_code | source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py:103-105 |
| apply_actions passes component 0 of the processed action as the target velocity and component 1 as the target steering angle | upstream_code | source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py:136-140 |
| process_actions clips every action component to [-1.0, 1.0] before scaling, and with no_reverse set it clamps the velocity component to at least 0 | upstream_code | source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py:119-133 |
| The policy observation group concatenates root_pos_w, root_euler_xyz, base_lin_vel, base_ang_vel and last_action; last_action is clipped to (-1, 1) and the first four terms carry Gaussian noise | upstream_code | source/wheeledlab_tasks/wheeledlab_tasks/common/observations.py:23-54 |
| The project targets Isaac Lab 2.0.2 and Isaac Sim 4.5.0 on Linux 64-bit | upstream_code | README.md:7-10 |
| Real-robot deployments are maintained in the separate RealLab repository, not in this clone | upstream_code | README.md:173-175 |
| The upstream test starts Isaac Sim through AppLauncher and instantiates the task with gym.make(task_name, cfg=env_cfg) | upstream_code | source/wheeledlab_tasks/test/create_and_step_env.py:13-28 |

The card lists four entry symbols. This package implements the first, the drift configuration above. The other three
are not implemented here (one device class per package): `MushrVisualRLEnvCfg`
(`source/wheeledlab_tasks/wheeledlab_tasks/visual/mushr_visual_env_cfg.py:412`), `MushrElevationRLEnvCfg`
(`source/wheeledlab_tasks/wheeledlab_tasks/elevation/mushr_elevation_env_cfg.py:438`) and `F1TenthDriftRLEnvCfg`
(`source/wheeledlab_tasks/wheeledlab_tasks/drifting/f1tenth_drift_env_cfg.py:132`).

Limits: the driver declares none itself. The step action envelope is derived from the fake environment's action space,
which is the two-component clip range [-1, 1] of the upstream action term
(`source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py:123-124`); the bridge publishes it as the limit of
`cap.world.step.v1` `action.values` and derives the `ticks` bound from its own `max_ticks` (10000). The device is
simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:ManagerBasedRLEnv (Isaac-MushrDriftRL-v0)`, level
F0 (the fake is kinematic: no rigid-body dynamics, contacts, actuator, sensor or noise model), determinism `seeded`
with `seed_control` `parameter`, physics timestep 5 ms (`sim.dt = 0.005`, `mushr_drift_env_cfg.py:393`; one step is
`decimation` 4 physics steps, a 20 ms control period, `:394`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say that the upstream Isaac Sim task was not run, that the upstream task is vectorized
while the fake models one environment, and that the fake never terminates and pays a constant reward.

Safety: simulated R0 device and no hardware backend. The e-stop is the runtime's software latch (the fake has no native
stop); after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays
readable.

Tags: wheeledlab, isaac-lab, isaac-sim, mushr, drifting, reinforcement-learning, simulation, gymnasium
