# Facts and tags for gh.unitreerobotics/unitree_sim_isaaclab

Every fact cites its source at commit `e30c25b1dffdf92ada1d6c8c1fe9a47bdde0fecc` as `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The task is registered as the Gymnasium id Isaac-Move-Cylinder-G129-Dex1-Wholebody with the entry point isaaclab.envs:ManagerBasedRLEnv and the local configuration class MoveCylinderG129Dex1WholebodyEnvCfg | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/__init__.py:10-14 |
| The simulator creates the task with gym.make(task, cfg=env_cfg).unwrapped and calls env.seed(seed), so the user-facing interface is a Gymnasium environment | upstream_code | sim_main.py:185-186 |
| The control step is 20 ms: decimation 4 at a physics timestep of 0.005 s, i.e. four physics steps per control step | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:144-147 |
| An episode is configured to last 20.0 s of simulated time, which is 1000 control steps of 20 ms | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:145 |
| The action is a joint-position target applied to every robot joint (joint_names ['.*']) with scale 1.0 relative to the default joint offset | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:58 |
| The policy observation group contains robot_joint_state, robot_gipper_state and camera_image, with corruption disabled and concatenate_terms false | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:74-83 |
| The robot body observation is 87 values: 29 joint positions, 29 joint velocities and 29 joint torques | upstream_code | tasks/common_observations/g1_29dof_state.py:152-156 |
| The gripper observation reads the two joint indices 31 and 29, so the articulation has at least 32 joints | upstream_code | tasks/common_observations/gripper_state.py:104-106 |
| The camera observation placeholder is a (1, 480, 640, 3) tensor | upstream_code | tasks/common_observations/camera_state.py:79-81 |
| The wrist cameras render 480 x 640 RGB frames at a 0.02 s update period | upstream_code | tasks/common_config/camera_configs.py:113-118 |
| The task has no termination terms: TerminationsCfg is empty | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:90-94 |
| A reset samples the object pose with x in [-0.05, 0.05] and y in [0.0, 0.05] and resets the scene to its default state | upstream_code | tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:163-172 |
| The robot is the G1 29-DOF whole-body configuration with a Dex1 hand, loaded from the USD asset named in the articulation configuration | upstream_code | robots/unitree.py:536-538 |

Limits: the driver declares no `Limit`. The action bounds are not stated in the clone text: the task applies
JointPositionActionCfg to every articulation joint (joint_names `['.*']`), and the joint position limits come from the
USD asset named at robots/unitree.py:538, which is fetched separately and is not text in the clone. The fake therefore
publishes an unbounded action space instead of inventing a joint limit. The device is simulated (R0).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
`isaaclab:Isaac-Move-Cylinder-G129-Dex1-Wholebody (kinematic fake)`, level F0, determinism `seeded` with
`seed_control` `parameter`, timestep 20 ms (decimation 4 at sim.dt 0.005 s, hw_env_cfg.py:144-147), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say the fake is kinematic, the action and camera
arrays are reduced stand-ins, and the Isaac Lab application was never launched.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the fake has no native stop); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Scope: the task card lists two entry symbols. This package implements the first,
`MoveCylinderG129Dex1WholebodyEnvCfg`
(tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py:121). The second,
`PickPlaceG129DEX1BaseFixEnvCfg`
(tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex1/pickplace_cylinder_g1_29dof_dex1_joint_env_cfg.py:118), is not
covered: it is a different task configuration. The other Gymnasium ids in the card hints are different tasks over the
same G1 robot and observation code and are not part of this package either.

Tags: unitree, g1, humanoid, mobile-manipulation, isaac-lab, simulation, gymnasium
