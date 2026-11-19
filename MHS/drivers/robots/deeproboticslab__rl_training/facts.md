# Facts and tags for gh.deeproboticslab/rl_training

Every fact cites its source at commit `3d05d3b97f7a2390f003547f23a02b3b42eea195`: `upstream_code` (code of the
clone) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The package serves one task of this training library, `Amp-Flat-Deeprobotics-DR02-v0`, whose entry point is
`rl_training.envs:AmpLocomotionEnv` and whose env config is `DR02AmpFlatEnvCfg`. The other robots and tasks in the
README table are separate cards and are not modelled.

| fact | source | ref |
|---|---|---|
| The DR02 AMP task is registered as Amp-Flat-Deeprobotics-DR02-v0 with entry point rl_training.envs:AmpLocomotionEnv and env config DR02AmpFlatEnvCfg | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/config/humanoid/dr02/__init__.py:8-15 |
| AmpLocomotionEnv extends Isaac Lab's ManagerBasedRLEnv | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:63 |
| AmpLocomotionEnv.step applies the action through the action manager, then steps the simulation cfg.decimation times | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:106-122 |
| AmpLocomotionEnv.step returns obs_buf, reward_buf, reset_terminated, reset_time_outs and extras | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:175 |
| AmpLocomotionEnv.reset forwards to the base reset, resets the AMP helper and returns obs_buf with extras | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:206-209 |
| The AmpLocomotionEnvCfg field only_positive_rewards defaults to True | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:59-60 |
| AmpLocomotionEnv.step clips the total reward to a minimum of 0 when only_positive_rewards is true | upstream_code | source/rl_training/rl_training/envs/amp_locomotion_env.py:139-141 |
| The DR02 AMP config sets the joint-position action joint_names from DR02_DOF_ORDER and the per-joint action scale | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/config/humanoid/dr02/flat_env_cfg.py:66-67 |
| DR02_DOF_ORDER lists the DR02 joint names in action order: left leg, right leg, waist, left arm and right arm | upstream_code | source/rl_training/rl_training/assets/deeprobotics.py:287-295 |
| The AMP action config is a JointPositionActionCfg with use_default_offset, the clip (-10.0, 10.0), and preserve_order enabled | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py:135-141 |
| The observation groups are policy (73 dims), critic (121 dims), amp_obs_history (305 dims), obs_future (69 dims) and vel (3 dims) | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py:149-156 |
| The policy observation is [ang_vel(3), proj_grav(3), cmd(3), cmd_flag(1), dof_pos(21), dof_vel(21), actions(21)] | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py:150-151 |
| The AMP environment config sets decimation 4, episode_length_s 20.0 and sim.dt 0.005 s, with the comment naming 0.02 / decimation | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py:675-680 |
| The default scene config creates 4096 environments, so the upstream environment is vectorized | upstream_code | source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py:701 |
| The README says rl_training is an IsaacLab-based RL training library and lists Amp-Flat-Deeprobotics-DR02-v0 as the DR02 environment | vendor_doc | README.md:16-23 |
| The README requires Isaac Sim 5.1.0, Isaac Lab 2.3.2 and Python 3.11 on Linux | vendor_doc | README.md:33 |
| The README tells users to deploy policies in MuJoCo or on real robots through a separate Deep Robotics deploy repository | vendor_doc | README.md:26-27 |
| The package install requirements list no serial, USB, VISA or ROS client library | upstream_code | source/rl_training/setup.py:20-33 |

## Limits

The fake backend's action Box is unbounded because the upstream Gymnasium input space is constructed outside the
clone. The endpoint therefore declares `action.values` as `Limit.operator_required`; without an operator envelope,
steps carrying an action are refused with `MHS.SAFETY.LIMITS_UNSET`. R0 does not waive this envelope.
`site-limits.example.json` uses -100..100 as fake-scale test data only, with no physical unit or upstream provenance.
The config's internal clip (-10.0, 10.0) does not establish the raw input Box. The fake's clipping is placeholder
processing and does not reproduce the per-joint scales, default offsets or external manager's processing order.
The catalogue/bridge also bounds ticks and non-negative seeds.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `analytic`, determinism
`seeded` with `seed_control` `parameter`, `timestep_ms` 20.0 (decimation 4 x sim.dt 0.005 s), `realtime_factor` 0,
clock `lockstep`, reset `full`, `snapshot_restore` false. The gaps in `driver.py` state what is not modelled, including
the absence of Isaac Sim physics and of the upstream reward/termination terms, the vectorized-to-single-environment
reduction, the operator-required input envelope, and that the upstream stack was never run here. Only the analytic
fake stops advancing under the software latch. No live backend is declared; it would need the Isaac application
lifecycle, configured assets and `deep_robotics_model` submodule. The card's Lite3 rough-task config is not served.

The fake's joint start offsets, kinematic gain, zero observations, reward and terminal flags are placeholders and are
not Facts or Limits. The action width (21), the observation group sizes (73, 121, 305, 69, 3), the clip and the 20 ms
control step are taken from the cited configuration.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, the fake is not advanced, and the state stays readable. No physical stop exists
and none is claimed.

Tags: deep-robotics, dr02, humanoid, locomotion, amp, isaac-lab, reinforcement-learning, simulation, gymnasium

Installation metadata follows README.md:33,48: upstream needs Linux and installs the extension from
`source/rl_training`, rather than the repository root. No installation was performed. The analytic fake
needs no Isaac application, GPU or model assets. The asset submodule has its own BSD-3-Clause LICENSE.txt.
