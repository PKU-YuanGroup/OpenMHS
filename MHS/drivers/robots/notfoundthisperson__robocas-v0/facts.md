# Facts and tags for gh.notfoundthisperson/robocas-v0

Every fact cites its source at commit `b7844e975df7b54963b299d2f59ab3283523d708`: `vendor_doc` (a text file of the
clone such as README.md or requirements.txt) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The ManiSkill2
submodule (`3rd_party/ManiSkill`, pinned at 493be36121a9dd06071a57172274babe617b789f) is a gitlink in the parent
commit, so no fact cites a file below it: the gate's provenance reader can only read the parent tree.

| fact | source | ref |
|---|---|---|
| RoboCAS is a benchmark for robotic manipulation in complex object arrangement scenarios, run in a physical simulation environment | vendor_doc | README.md:1-7 |
| The benchmark needs the PartNet-Mobility and GraspNet-1Billion assets in the assets directory | vendor_doc | README.md:24 |
| TaskBaseEnv imports BaseEnv from mani_skill2.envs.sapien_env | upstream_code | robot_sim/envs/basic_env.py:11 |
| The entry class TaskBaseEnv subclasses BaseEnv and supports the simulated mobile Franka Panda robot | upstream_code | robot_sim/envs/basic_env.py:22-23 |
| TaskBaseEnv fixes robot_uid to mobile_franka_panda | upstream_code | robot_sim/envs/basic_env.py:49 |
| TaskBaseEnv's default control mode is base_pd_pos_arm_pd_ee_abs_pose_wrt_arm_base | upstream_code | robot_sim/envs/basic_env.py:28 |
| TaskBaseEnv defaults to sim_freq 240 and control_freq 10 | upstream_code | robot_sim/envs/basic_env.py:30-31 |
| The benchmark configuration sets obs_mode image and control_freq 5 | vendor_doc | robot_sim/config/env/common.yaml:20-22 |
| The arm controller for the default mode is the absolute end-effector pose controller relative to the arm base | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:235-245 |
| The base joint-position controller takes its limits from the model | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:88-96 |
| The absolute end-effector pose controller uses position bounds [-1, -1, 0] to [1, 1, 1.5] | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:58-59 |
| The rotation bound of the absolute end-effector pose controller is pi | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:239 |
| The gripper controller bounds each finger joint from -0.01 to 0.04 | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:288-297 |
| controller_configs composes each control mode from a base, an arm and a gripper controller | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:300-307 |
| The base, gripper and static cameras are configured at 640 x 480 | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:372-408 |
| The mobile base joint limits are x -0.2 to 0.8, y -0.8 to 0.8 and rotation z -3.1415926 to 1.5707 | upstream_code | assets/urdf/mobile_franka_panda.urdf:35-58 |
| The gripper finger joints are limited 0 to 0.04 in the URDF | upstream_code | assets/urdf/mobile_franka_panda.urdf:350-363 |
| TaskBaseEnv.reset delegates to its superclass reset | upstream_code | robot_sim/envs/basic_env.py:264-270 |
| TaskBaseEnv.evaluate is marked Not Implemented and returns {'success': True} | upstream_code | robot_sim/envs/basic_env.py:322-324 |
| TaskBaseEnv.compute_normalized_dense_reward returns 0 | upstream_code | robot_sim/envs/basic_env.py:326-328 |
| TaskBaseEnv.set_main_rng ignores its seed argument and draws a random seed | upstream_code | robot_sim/envs/basic_env.py:69-70 |
| The upstream dependencies include gymnasium>=0.28.1, sapien==2.2.2 and mplib==0.1.0 | vendor_doc | requirements.txt:3-5 |
| TaskBaseEnv.get_images converts the camera colours, positions and segmentations for all cameras | upstream_code | robot_sim/envs/basic_env.py:379-390 |
| The agent's initial joint positions are the 12 values in init_qpos | upstream_code | robot_sim/agents/configs/mobile_franka_panda/defaults.py:69 |

Limits: the driver declares none. The only bounds are the environment's action space, which the Gymnasium bridge
derives from the fake's `Box` at `cap.world.step.v1` (`action.values`, one bound per element, no source, ref
`action_space of the fake backend .fake:FakeTaskBaseEnv`, which G4 skips as a simulator-derived limit). The action
layout is the default control mode's flat 11-element Box: base joint positions (3), absolute end-effector position and
rotation vector in the arm-base frame (6), and gripper finger positions (2). The bounds are the mobile base URDF limits
(assets/urdf/mobile_franka_panda.urdf:41, :49, :57), the end-effector position and rotation limits
(robot_sim/agents/configs/mobile_franka_panda/defaults.py:58-59 and :239) and the gripper controller limits
(robot_sim/agents/configs/mobile_franka_panda/defaults.py:291-292). The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:RoboCAS-v0 fake`, level F0 (the deployed fake
is kinematic; the upstream class would build a SAPIEN rigid-body scene), determinism `seeded` with `seed_control`
`parameter`, timestep 100 ms (one control step at the TaskBaseEnv default `control_freq` 10,
`robot_sim/envs/basic_env.py:31`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps name the missing physics, the 22-float observation surrogate against the upstream state vector and the
640 x 480 x 3 image observation of the benchmark configuration, the always-terminating `evaluate` stub, the partial
upstream seeding, and the unrun sim backend.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: robocas, manipulation, benchmark, sapien, maniskill, mobile-franka, simulation, gymnasium
