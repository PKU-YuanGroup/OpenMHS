# Facts and contract for gh.ad-sdl/digitaltwin

Every fact below is copied into `facts = [Fact(...)]` in `driver.py` with the source and reference shown. The pinned
commit is `c8dfbd5998462d6fd0c1afb197f66b5a52c2d126`; paths are relative to the clone root.

## Facts

| fact | source | ref |
|---|---|---|
| The registered gym id Isaac-Centrifuge-Bimanual-OpenArm-IK-Abs-Mimic-v0 uses entry point rpl_centrifuge.openarm.mimic_env:CentrifugeBimanualOpenArmIKAbsMimicEnv and env cfg rpl_centrifuge.openarm.ik_abs_mimic_env_cfg:CentrifugeBimanualIkAbsMimicEnvCfg | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/__init__.py:75-84 |
| The action tensor is 16-dimensional: [0:3] is the left arm position, [3:7] the left quaternion (qx, qy, qz, qw), [7:8] the left gripper, [8:11] the right arm position, [11:15] the right quaternion and [15:16] the right gripper, with positions in the robot root frame | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/mimic_env.py:13-21 |
| Both gripper channels are scalars in [0, 1], consumed by the binary joint-position action | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/mimic_env.py:18-21 |
| The arm actions are absolute target poses: both terms use command_type pose with use_relative_mode=False and differential IK with the dls method | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/ik_abs_env_cfg.py:260-279 |
| The binary gripper actions drive the finger joints to 0.044 for open and 0.0 for close | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/ik_abs_env_cfg.py:281-293 |
| The environment runs sim.dt=0.01 s (100 Hz) with decimation 5, so one environment step spans five physics steps | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:398-402 |
| episode_length_s is 30.0 s | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:400 |
| The termination terms are time_out at the episode length, tube_dropped when the tube root is below _SURFACE_Z - 0.30 m, and success once the tube has stayed inside the bucket for 3.0 s | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:319-331 |
| No reward manager is configured: rewards, commands and curriculum are None | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:393-396 |
| Observations are grouped into policy, an empty rgb_camera group and subtask_terms; the policy group holds joint positions and velocities, last action, left/right end-effector poses and tube/bucket poses | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:243-316 |
| A reset randomizes the pickup station in x/y by (-0.03, 0.03) m and yaw by (-0.15, 0.15) rad, drops the tube into one of four rack wells from 0.15 m above the rack, and shifts the bucket in x/y by (-0.03, 0.03) m | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/env_cfg.py:335-375 |
| The Mimic wrapper adds get_robot_eef_pose, target_eef_pose_to_action, action_to_target_eef_pose, actions_to_gripper_actions and get_subtask_term_signals to the ManagerBasedRLMimicEnv base | upstream_code | tasks/centrifuge/tasks/src/rpl_centrifuge/openarm/mimic_env.py:44-192 |
| The package is an external Isaac Lab 3.0.0 task extension that bundles USD assets and registers its gym ids on import | vendor_doc | tasks/centrifuge/tasks/README.md:3-11 |
| The prerequisites are Ubuntu 22.04+ with a recent NVIDIA driver and Isaac Sim 6.0.0 or 6.0.1 | vendor_doc | docs/01_install_isaaclab_release-3.0.0-beta2.md:9-12 |
| The upstream README calls the scene geometry (robot mount and prop positions) and the XR anchor and retargeter offsets starting points that need in-sim tuning and cannot be validated without the GUI or a headset | vendor_doc | tasks/centrifuge/tasks/README.md:32-34 |
| The task pack also contains SO101 physical leader-arm-over-USB variants and a GR1T2 variant | vendor_doc | tasks/centrifuge/tasks/README.md:5-9 |
| The rendering script launches an Isaac application before importing rpl_centrifuge and supplies parse_env_cfg's result as cfg to gym.make | upstream_code | tasks/centrifuge/tasks/scripts/render_images_from_demos.py:63-83 |

## Action and observation contract

`cap.world.step.v1` carries the 16-element action in the order of `mimic_env.py:13-21`: left arm position, left
quaternion (x, y, z, w), left gripper, right arm position, right quaternion, right gripper. The two gripper channels
are in [0, 1] (`mimic_env.py:18-21`). The arm position and quaternion bounds are not written in the clone: the
differential-IK action terms configure the controller but Isaac Lab's action manager builds the Box. The driver
therefore leaves `action_space_ref` unset, and the reference marks the fake's per-element bounds as the fake
backend's, without a source. The arm bounds in `fake.py` are placeholders.

`cap.world.reset.v1` maps to the environment reset; `cap.world.seed.v1` sets the seed used by the next reset. The
native reset also randomizes the USD scene (station, rack well, bucket), which the fake does not model.

The upstream observation is a Dict of `policy`, `rgb_camera` and `subtask_terms` groups. The fake observation is a
16-element echo of the last action and is not the upstream observation.

## Timing and fidelity

The environment runs `sim.dt = 0.01` s at 100 Hz with `decimation = 5`, so one control step is 0.05 s and the
30.0 s episode is 600 control steps. The supplied fake backend is F0 (analytic, no dynamics) with seeded placeholder resets. The Isaac Lab engine metadata
is descriptive only: no live adapter, seeded engine replay or PhysX run is supplied or validated.

## Stops and risk

This is a simulated world (R0): its capabilities change simulated state only. There is no hardware backend, no
physical e-stop and no operator-required limit. The runtime's software e-stop latches `cap.world.step.v1`,
`cap.world.reset.v1` and `cap.world.seed.v1`; the last world state stays readable. The safe-state text is restricted to the fake. `open_native()` refuses every other backend before native construction,
so the inherited live `gymnasium.make` fallback cannot run through this package. The upstream rendering script launches
an Isaac application, then imports the task pack and supplies a resolved cfg to `gym.make`
(`tasks/centrifuge/tasks/scripts/render_images_from_demos.py:63-83`); that lifecycle and the tensor/batch conversion
are absent here. A latch on this fake makes no assertion about an independently running Isaac application.

Only the bimanual OpenArm fake is served. The task pack's SO101 physical leader-arm-over-USB variants and GR1T2 task
(`tasks/centrifuge/tasks/README.md:5-9`) are outside this package. Publication review remains required by the card:
packaging metadata says BSD-3-Clause (`tasks/centrifuge/tasks/pyproject.toml:14`), while the pinned lock retains
NOASSERTION/unknown.

## Tags

`centrifuge`, `bimanual`, `openarm`, `imitation-learning`, `isaac-lab`, `simulation`, `gymnasium`
