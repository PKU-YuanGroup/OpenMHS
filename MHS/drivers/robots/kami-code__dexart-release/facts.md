# Facts and tags for gh.kami-code/dexart-release

Every fact cites its source at commit `d6ab75e1a0b81384d1ac918cbfd4d97b1f230149`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DexArt is a benchmark for dexterous manipulation of articulated objects, and the repository contains the simulated environment and training code | vendor_doc | README.md:12-13 |
| create_env fixes robot_name to allegro_hand_xarm6_wrist_mounted_face_front | upstream_code | dexart/env/create_env.py:16 |
| create_env dispatches the task names faucet, bucket, laptop and toilet to the four RL environment classes and raises NotImplementedError for any other name | upstream_code | dexart/env/create_env.py:32-41 |
| create_env defaults index to -1 | upstream_code | dexart/env/create_env.py:13-15 |
| The robot info for allegro_hand_xarm6_wrist_mounted_face_front declares hand_dof 16 and arm_dof 6 | upstream_code | dexart/utils/common_robot_utils.py:53-56 |
| BaseRLEnv.action_dim returns self.robot.dof | upstream_code | dexart/env/rl_env/base.py:90-92 |
| action_space is a Box from -1 to 1 with action_dim elements | upstream_code | dexart/env/rl_env/base.py:597-599 |
| observation_space is a Box bounded by -inf and inf with obs_dim elements | upstream_code | dexart/env/rl_env/base.py:601-606 |
| The laptop oracle observation concatenates the robot joint positions, the palm linear velocity (3), the palm angular velocity (3), the palm position (3) and the progress fraction (1) | upstream_code | dexart/env/rl_env/laptop_env.py:71-75 |
| LaptopRLEnv.reset accepts seed, return_info and options but its body never reads them, and it returns only the observation | upstream_code | dexart/env/rl_env/laptop_env.py:104-123 |
| BaseRLEnv.step returns the four-value (obs, reward, done, info) tuple; reaching the horizon sets done True and records TimeLimit.truncated as not done | upstream_code | dexart/env/rl_env/base.py:216-229 |
| The laptop environment reports a horizon of 250 steps | upstream_code | dexart/env/rl_env/laptop_env.py:146-148 |
| The laptop simulation scene sets its physics timestep to 0.004 s | upstream_code | dexart/env/sim_env/laptop_env.py:25 |
| create_env defaults frame_skip to 10 | upstream_code | dexart/env/create_env.py:13-15 |
| BaseRLEnv computes control_time_step as the scene timestep times frame_skip | upstream_code | dexart/env/rl_env/base.py:123-125 |
| The laptop simulation sets change_instance_when_reset when index is -1 | upstream_code | dexart/env/sim_env/laptop_env.py:44-47 |
| The laptop simulation reset_env draws the articulated-object instance with the global random module's randint when change_instance_when_reset is set | upstream_code | dexart/env/sim_env/laptop_env.py:120-125 |
| The install requirements are transforms3d, gym 0.25.2, sapien 2.2.1, numpy and open3d 0.14.1 | upstream_code | setup.py:16-18 |
| The README instructs downloading the assets separately and placing the asset directory at the project root | vendor_doc | README.md:35-37 |

## Limits

The driver declares no `Limit` and no `Limit.operator_required`. The only numeric bounds are the environment's own
spaces: the action space is a 22-element Box from -1 to 1 (`base.py:597-599`), which the Gymnasium bridge derives and
enforces as `action.values` per-element limits before any native call, and the bridge's `ticks` input is 1 to 10000.
The card's `safety.risk_floor` is R0, the capabilities are R0 simulation classes, and there is no hardware backend,
so no operator bound is needed and no `site-limits.example.json` is provided.

## Fidelity contract

`driver.py` publishes the complete fidelity contract: engine `analytic:dexart-laptop`, level F0 (kinematic), timestep
40 ms (the control period: `frame_skip` 10 from `create_env.py:14` times the 0.004 s physics step from
`sim_env/laptop_env.py:25`, with `control_time_step` computed at `base.py:125`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. Determinism is `seeded` with `seed_control` `parameter` for the
fake only: the upstream `reset` accepts a seed but does not read it (`laptop_env.py:104-123`) and chooses the
articulated object with the global random module (`sim_env/laptop_env.py:120-125`). The gaps say that the fake does
not model the upstream Sapien dynamics, that the upstream model would be F1, that the observation values are a
stand-in, and that no upstream run was made.

NOT COVERED: the visual observation Dict (camera RGB, depth, segmentation and point-cloud arrays, `base.py:601-646`);
this package models the state observation path only. The state observation is the real laptop layout and length (22
joint positions plus 10 palm and progress values); its values come from the fake.

The fake's numbers are test data marked `# placeholder` in `fake.py`; none of them is copied into a Fact, a Limit or
the reference.

## Safety

The device is simulated at R0. There is no hardware backend and no native stop method in a simulated environment;
the e-stop is the runtime's software latch, after which step, reset and seed are refused until `mhs.safety.reset`
clears it, and the last world state stays readable. No physical protection is claimed.

Tags: dexart, sapien, dexterous-manipulation, articulated-objects, reinforcement-learning, simulation, gym
