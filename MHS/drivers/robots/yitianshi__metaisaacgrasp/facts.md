# Facts and tags for gh.yitianshi/metaisaacgrasp

Every fact cites the clone at commit `2acd0808ba799f14bcd8450e8443a581586ab543`: `upstream_code` is a code or comment
line of the clone, `vendor_doc` is documentation text of the clone. The same facts are declared in
`driver.py`; the reference is generated from the driver, not from this page.

## Scope

This package models the `AIR-v0-Data` environment, whose entry class is `isaac_env.air_env_data:AIREnvData`
(air_env_data/__init__.py:25-28). The other registered environments (`AIR-v0-Grasp`, `AIR-v0-Tele`, `AIR-v0-SB3`,
`AIR-v0-RL`, `AIR-v0-SKRL`, `AIR-v0-Targo`) are other configurations or devices and are not covered. In particular,
the grasp package binds localhost:8081 and waits for a remote agent at import (air_env_grasp/element_cfg.py:11-25),
the teleoperation environment creates a `Se3Keyboard` device (air_env_tele/env.py:27, :56), and the SB3 and Tele
registrations name modules that do not define the named class (air_env_sb3/__init__.py:28,
air_env_tele/__init__.py:28). The `sim` backend (`gymnasium.make("AIR-v0-Data")`) was not run: it needs Isaac Sim 4.5
and Isaac Lab 2.0 and a GPU.

## Facts

| fact | source | ref |
|---|---|---|
| AIREnvData extends AIREnvBase | upstream_code | isaac_env/air_env_data/env.py:37 |
| AIREnvBase extends Isaac Lab's ManagerBasedRLEnv | upstream_code | isaac_env/air_env_base/env.py:44 |
| AIR-v0-Data is registered with entry point isaac_env.air_env_data:AIREnvData | upstream_code | isaac_env/air_env_data/__init__.py:25-28 |
| The project supports IsaacLab 2.0 and IsaacSim 4.5.0 | vendor_doc | README.md:1 |
| The installation instructions require Isaac-Sim and then Isaac Lab | vendor_doc | README.md:55-57 |
| The action configuration has a joint-position term over the arm joints and a binary gripper term | upstream_code | isaac_env/air_env_data/env_cfg.py:127-137 |
| ARM_JOINT defines six joints: shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2 and wrist_3 | upstream_code | isaac_env/air_env_base/element_cfg.py:182-189 |
| AIREnvBase.step takes a grasp pose and an optional policy inference criteria tensor | upstream_code | isaac_env/air_env_base/env.py:276 |
| The simulation advances at 1/120 s per physics step with decimation 2, so one environment step is 1/60 s | upstream_code | isaac_env/air_env_data/env_cfg.py:287-292 |
| The configured episode length is 5 s | upstream_code | isaac_env/air_env_data/env_cfg.py:288 |
| STEP_TOTAL is 30 steps, the per-episode step total the timeout checks | upstream_code | isaac_env/air_env_base/element_cfg.py:43 |
| The configured camera resolution is 480 x 640 and one camera is used | upstream_code | isaac_env/air_env_base/element_cfg.py:60-63 |
| The observation groups are cam_pos and policy; the policy group holds rgb, normals, instance_segmentation_fast, distance_to_image_plane, pcd and gripper_pose | upstream_code | isaac_env/air_env_data/env_cfg.py:144-173 |
| The reward is 1 when an object is lifted above LIFT_HEIGHT * 0.8 while the state machine is in lift | upstream_code | isaac_env/air_env_base/env_cfg.py:421-426 |

## Limits

No `Limit` is declared. The clone states no numeric bound for the action values: the arm's joint-position action term
is configured with `scale=1.0` and no range (air_env_data/env_cfg.py:130-132), and the gripper's binary action term
maps the command to the open/close expressions (env_cfg.py:133-137). The family bridge therefore publishes the action
Box without finite bounds and the conformance suite cannot probe SAFE-014. No operator-required limit is needed
because nothing in the contract is a settable state field.

## The checked fake

The fake backend is the package's pure Python kinematic stand-in. It implements only the Gymnasium surface the bridge
calls: `action_space` (seven values: six arm joints plus the binary gripper), `observation_space` (two seven-value
poses), `reset`, `step` and `close`. It is not a recording and not the upstream environment.

- The action values are applied as small joint-target increments with a placeholder gain; no physics, contacts,
  friction, gravity, actuator, sensor or noise model exists.
- The observation is reduced to the camera pose and the end-effector pose (seven values each). **NOT COVERED:** the
  policy group's `rgb`, `normals`, `instance_segmentation_fast`, `distance_to_image_plane` and `pcd` arrays; the
  configured size is 480 x 640 per camera (element_cfg.py:63).
- The fake truncates at the 30-step episode total (element_cfg.py:43) and never terminates on a grasp; its reward is
  a fixed placeholder 0.0.
- Every start position, increment, orientation and reward that is not taken from the clone is marked `# placeholder`
  in fake.py and was not copied into a Fact, a Limit or the reference.

Tags: `isaac-lab`, `isaac-sim`, `grasp`, `robot-arm`, `reinforcement-learning`, `simulation`, `gymnasium`.
