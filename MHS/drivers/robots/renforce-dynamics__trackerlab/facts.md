# Facts and tags for gh.renforce-dynamics/trackerlab

Every fact cites a line of the upstream clone at commit `1e5ccc062b445712a0aa7308cfb99edd7296cc88`: `upstream_code`
(code or a comment of the clone) or `vendor_doc` (documentation text of the clone). The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TrackerLab-Tracking-Unitree-G1-23D-Walk is registered with entry point trackerLab.tracker_env:ManagerBasedTrackerEnv and the training config g1_23d_tracking_env_cfg:G1TrackingWalk | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/__init__.py:3-12 |
| ManagerBasedTrackerEnv extends ManagerBasedRLEnv and its constructor takes cfg, an optional render_mode and keyword arguments | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env.py:3-12 |
| step(action) calls the parent step, updates the motion manager and returns the observation, reward, terminated, timeout and extras buffers | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env.py:35-39 |
| reset(seed, env_ids, options) forwards to the parent reset and returns the observation buffer and extras | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env.py:41-49 |
| The action configuration is a joint-position action over all robot joints with scale 0.5, the default joint offset and a configured clip of -6.0 to 6.0 | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env_cfg/configs.py:154-159 |
| The G1 23-DoF tracking task selects the 23-joint motion alignment, sets the action scale to 0.5, enables a 5-step policy observation history and sets the episode length to 20.0 s | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/g1_23d_tracking_env_cfg.py:166-186 |
| G1_23D_MOTION_ALIGN_CFG lists 23 gym joint names for the G1 23-DoF tracking task | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/motion_align_cfg.py:1-16 |
| The policy observation group is the dof-position command, root-velocity command, base linear velocity, base angular velocity, projected gravity, relative joint position, relative joint velocity and last action | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env_cfg/configs.py:171-188 |
| set_no_scanner removes the height scanner and the height_scan policy observation | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env_cfg/tracking_env_base.py:75-78 |
| The G1 23-DoF tracking task calls set_no_scanner | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/g1_23d_tracking_env_cfg.py:167 |
| The base configuration uses 4 physics steps of 0.005 s per environment step | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env_cfg/tracking_env_base.py:40-43 |
| The G1 23-DoF tracking task sets the episode length to 20.0 s and disables the base-contact termination | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/g1_23d_tracking_env_cfg.py:185-186 |
| The termination terms are a base height below 0.2 m and a bad orientation beyond 0.8 rad | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/tracking_humanoid_env_cfg.py:20-21 |
| The reset events sample base pose x and y in -2.5 to 2.5, yaw in -3.14 to 3.14, base velocity x, y and z in -1.0 to 1.0, roll, pitch and yaw in -0.5 to 0.5 and the joint velocity scale in -1.0 to 1.0 | upstream_code | source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/g1_23d_tracking_env_cfg.py:126-149 |
| The environment config sets sim.physx.gpu_max_rigid_patch_count to 10 * 2**15 | upstream_code | source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env_cfg/tracking_env_base.py:46 |
| TrackerLab extends IsaacLab and requires IsaacLab and its dependencies to be installed | vendor_doc | README.md:58-59 |
| The setup guide includes Isaac Sim installation and Python environment setup | vendor_doc | docs/tutorial_en.md:17 |

## Limits

The fake's action Box is unbounded because the raw action space is built by Isaac Lab outside the clone and was
not observed here. `action.values` is `Limit.operator_required`: without a deployment envelope, every raw action is
refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` supplies illustrative fake bounds only; they are
operator data and make no upstream or physical-bound claim. The configured target clip (-6.0 to 6.0) and scale
0.5 (`manager_based_tracker_env_cfg/configs.py:154-159`) do not establish a raw action-space envelope. The
catalogued schema also bounds `ticks` (1 to the bridge's `max_ticks`, 10000) and `seed` to a non-negative integer.
The package-local `adapter.py` uses the public bridge schema hook to keep `action` required and describe both
inputs when declaring that envelope. A missing action is rejected before dispatch, rather than failing in the fake.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `analytic:trackerlab-g1-23d-walk-stand-in (Isaac Lab target)`,
determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 20.0 (one environment control step: 4 physics
steps of 0.005 s, `tracking_env_base.py:40-43`), `realtime_factor` 0, clock `lockstep`, reset `full`,
`snapshot_restore` false. The gaps in `driver.py` state what is not modelled, including the analytic 104-value policy
observation without the upstream 5-step history, the unbounded fake action Box, the missing termination and reward
terms, the single-environment reduction of the 4096-environment upstream, and the fact that the Isaac Lab stack was
never run here.
The fake now applies the task's angular-velocity observation scale 0.25 and joint-velocity scale 0.05
(`g1_23d_tracking_env_cfg.py:174-179`). Its zero-offset target approximation, independent initial joint-velocity
samples and 1000-step episode budget are fake-only reductions; default joint offsets and native in-step episode
resets are not modelled.

## Safety

Simulated R0 fake-only contract. While latched, no step or world reset is accepted; the analytic fake's cached
observation, target, tick and episode stay readable. Safety reset releases only the latch and advances no ticks.
No external Isaac Sim application is paused or stopped. Only `fake` is declared; the inherited generic
`gymnasium.make` fallback is not a supported live adapter. Native construction requires cfg
(`manager_based_tracker_env.py:11`), and the shipped training script bootstraps AppLauncher, imports task
registrations and supplies cfg before `gym.make` (`scripts/rls/base/train.py:29-33, 51-62`). Torch/batch conversion,
application lifecycle integration and the native observation/history layout remain outside this package. No
physical stop or hardware execution is claimed.

Tags: trackerlab, isaac-lab, humanoid, unitree-g1, motion-tracking, reinforcement-learning, simulation, gymnasium
