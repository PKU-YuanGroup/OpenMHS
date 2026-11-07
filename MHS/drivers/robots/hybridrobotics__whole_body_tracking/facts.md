# Facts and tags for gh.hybridrobotics/whole_body_tracking

Every fact cites its source at commit `cd65172032893724b445448818c34165846d847d`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the registered Gymnasium task `Tracking-Flat-G1-v0`. The clone does not define the environment
class: it registers `isaaclab.envs:ManagerBasedRLEnv` and supplies the `G1FlatEnvCfg` configuration, which is the
card's entry symbol and the driver's `native`.

| fact | source | ref |
|---|---|---|
| Tracking-Flat-G1-v0 is registered with entry point isaaclab.envs:ManagerBasedRLEnv, env_cfg_entry_point flat_env_cfg.G1FlatEnvCfg and rsl_rl_cfg_entry_point G1FlatPPORunnerCfg, with the environment checker disabled | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/config/g1/__init__.py:9-17 |
| The repository targets Isaac Sim 4.5.0, Isaac Lab 2.1.0, Python 3.10 and Linux | vendor_doc | README.md:3-6 |
| G1FlatEnvCfg subclasses TrackingEnvCfg and sets the G1 cylinder robot, the G1 joint action scale, the torso_link motion anchor and 14 tracked body names from pelvis to the wrists and ankles | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/config/g1/flat_env_cfg.py:8-31 |
| TrackingEnvCfg is a ManagerBasedRLEnvCfg that groups the scene, observations, actions, commands, rewards, terminations, events and curriculum configuration | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:293-307 |
| The environment uses decimation 4 over a 0.005 s simulation step and an episode length of 10.0 s, so one control step is 0.02 s and the time-out is 500 control steps | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:309-316 |
| The sole action term is a joint-position action over every joint of the robot with the default joint positions as offset | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:102-106 |
| G1_ACTION_SCALE maps every actuator joint expression to 0.25 * effort_limit_sim / stiffness | upstream_code | source/whole_body_tracking/whole_body_tracking/robots/g1.py:184-195 |
| The policy observation group concatenates command, motion anchor position, motion anchor orientation, base linear velocity, base angular velocity, joint position, joint velocity and the last action, in that order, with corruption enabled | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:113-133 |
| The motion command is the concatenation of the reference joint positions and joint velocities loaded from the motion file | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/mdp/commands.py:100-110 |
| MotionLoader asserts that the motion file exists and loads fps, joint_pos, joint_vel and body pose, quaternion and velocity arrays from a numpy NPZ file | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/mdp/commands.py:30-42 |
| MotionCommandCfg.motion_file is MISSING, so a reset cannot run until a motion file is supplied to the command term by the caller | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/mdp/commands.py:357-361 |
| The termination terms cut an episode when the anchor-z error exceeds 0.25, the projected-gravity error of the anchor exceeds 0.8, or a tracked end-effector body's z error exceeds 0.25, and time_out ends it at the episode length | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:257-278 |
| The command configuration sets the reset pose ranges, the velocity range and a joint position range of -0.1 to 0.1 | upstream_code | source/whole_body_tracking/whole_body_tracking/tasks/tracking/tracking_env_cfg.py:85-99 |
| The robot description is not part of the clone: the README downloads unitree_description.tar.gz from GCS into the package assets directory before the G1 URDF can be spawned | vendor_doc | README.md:46-55 |
| Reference motions are stored in and loaded from the WandB registry, and the reference motion must be retargeted to the robot and use generalized coordinates | vendor_doc | README.md:67-69 |
| The training script creates the environment with gym.make(task, cfg=env_cfg), so the registered environment is driven through the Gymnasium make/step/reset interface | upstream_code | scripts/rsl_rl/train.py:113-114 |

Limits: the driver declares none. The clone states no bound on the action: the action term is a joint-position action
whose unitless values are scaled to a joint target by `G1_ACTION_SCALE = 0.25 * effort_limit_sim / stiffness`
(`robots/g1.py:184-195`), so the bridge derives an unbounded action space (29 array elements, no per-element bound)
and refuses a wrong length as `MHS.CAPABILITY.INPUT_INVALID`. `ticks` is bounded by the bridge (1 to 10000 by
default). The device is simulated (R0), so no limit is `operator_required`. The action vector's 29 elements follow the
joint expressions of `robots/g1.py:63-134`; the URDF that fixes the real joint set is downloaded from GCS and is not
in the clone.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Tracking-Flat-G1-v0`, level F1 (Isaac
Sim/PhysX rigid-body dynamics with contacts, as configured by the terrain and articulation settings), determinism
`seeded` with `seed_control` `parameter`, timestep 20 ms (one control step: `sim.dt` 0.005 s times `decimation` 4,
`tracking_env_cfg.py:312-315`; the 5 ms physics step is named in the gaps), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what the fake does not model, that the G1 URDF and motion NPZ are
not in the clone, and that neither the upstream environment nor the fake was compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No physical robot is commanded: deployment is delegated to a separate repository (README.md:23-24).

Tags: beyondmimic, g1, humanoid, motion-tracking, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium
