# Facts and tags for gh.nvlabs/robolab

Every fact cites its source at commit `ad45d4f974725d020f82c2b0d77d78533aeba2b3`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RoboLab is a task-based evaluation benchmark for robot manipulation policies built on NVIDIA Isaac Lab and run in simulation | vendor_doc | README.md:5 |
| The requirements are Isaac Sim 5.0 or 5.1, Isaac Lab 2.2.0 or 2.3.2.post1, Python 3.11, Linux Ubuntu 22.04+ and an NVIDIA RTX GPU | vendor_doc | README.md:162-174 |
| RobolabEnv extends ManagerBasedRLEnv and is the runtime environment class | upstream_code | robolab/core/environments/env.py:24 |
| RobolabEnv.step zeroes the action of every frozen (terminated) environment and then calls ManagerBasedRLEnv.step with the whole batched action | upstream_code | robolab/core/environments/env.py:65-73 |
| When an environment terminates during stepping, RobolabEnv freezes it instead of resetting it: it records success/failure and the termination step and the environment holds its final state | upstream_code | robolab/core/environments/env.py:76-104 |
| register_generated_env registers the generated task environment with gymnasium under the generated name, entry point robolab.core.environments.env:RobolabEnv and the generated env_cfg_entry_point | upstream_code | robolab/core/environments/config.py:318-325 |
| The built-in DROID registration passes env_prefix and env_postfix as empty strings, so the registered environment name is the task class name | upstream_code | robolab/registrations/droid/auto_env_registrations_jointpos.py:113-121 |
| The documented registered environment name for the BananaInBowlTask example is BananaInBowlTask | vendor_doc | docs/environment_run.md:9-17 |
| The environment name is the concatenation env_prefix + TaskClassName + env_postfix | vendor_doc | docs/environment_registration.md:205-209 |
| DroidJointPositionActionCfg takes 7 arm joint targets plus a binary gripper, 8 action values | vendor_doc | robolab/robots/README.md:26-28 |
| The binary gripper action closes when the action value is greater than 0.5 and opens otherwise | upstream_code | robolab/robots/droid.py:306-320 |
| The built-in DROID observation config has the image_obs, proprio_obs and viewport_cam groups | upstream_code | robolab/registrations/droid/auto_env_registrations_jointpos.py:83-86 |
| The proprioception terms are arm_joint_pos, gripper_pos (noise std 0.05 and clipped to 0-1), ee_pos, ee_quat, eef_pos and eef_quat | upstream_code | robolab/robots/droid.py:433-442 |
| The DROID wrist camera is 720 pixels high, 1280 pixels wide and RGB | upstream_code | robolab/robots/droid.py:42-50 |
| The egocentric mirrored viewport camera is 480 pixels high, 864 pixels wide and RGB | upstream_code | robolab/variations/camera.py:179-186 |
| The DROID registration passes dt = 1/(60*2) s and decimation = 8, so one environment step advances 8 physics steps of 1/120 s = 66.67 ms | upstream_code | robolab/registrations/droid/auto_env_registrations_jointpos.py:129-131 |
| The generated configuration assigns self.decimation and self.sim.dt from those registration arguments | upstream_code | robolab/core/environments/config.py:196-200 |

Limits: the driver declares none. The action and observation bounds are the environment's spaces, which the
Gymnasium bridge derives from the live environment; the clone states the DROID joint-position layout (7 arm
values plus a binary gripper) but no numeric action bound, so this package does not invent one. The fake's action
Box has no finite bounds, and the action Box's shape is the interface, not a safety limit. The device is simulated
(R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:BananaInBowlTask`, level F1 (Isaac Lab
rigid-body simulation with PhysX contacts), determinism `seeded` with `seed_control` `parameter`, timestep 66.67 ms
(dt = 1/120 s and decimation 8, `auto_env_registrations_jointpos.py:129-131`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake is a kinematic stand-in, that no
benchmark task/success detection is modelled, that the fake returns 4x6x3 and 2x3x3 placeholder images while the
deployed cameras are 720x1280 and 480x864 RGB, and that the fake was not compared with an Isaac Lab run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: robolab, robot-manipulation, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium
