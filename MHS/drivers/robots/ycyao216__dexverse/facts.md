# Facts and tags for gh.ycyao216/dexverse

Every fact cites its source at commit `30cc673e27684b9f10186fa6bea731aed246bc9f`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Dexverse-GraspKettle-v0 is registered to GraspKettleEnvFloatingDexHandRightCfg | upstream_code | source/dexverse/dexverse/tasks/config/functional/__init__.py:17 |
| The registration entry point is isaaclab.envs:ManagerBasedRLEnv with disable_env_checker=True and the environment configuration passed as env_cfg_entry_point | upstream_code | source/dexverse/dexverse/tasks/utils/registration.py:27-36 |
| GraspKettleEnvFloatingDexHandRightCfg is the functional kettle task: grasp the kettle by the handle, then lift it and pour over a mug | upstream_code | source/dexverse/dexverse/tasks/config/functional/grasp_kettle_cfg.py:65-71 |
| The kettle success thresholds are pour_lift_height 0.15 m, pour_angle_rad 45 degrees about the local +X axis and pour_goal_xy_threshold 0.05 m | upstream_code | source/dexverse/dexverse/tasks/config/functional/grasp_kettle_cfg.py:89-95 |
| The kettle object is configured with mass 0.5 kg, half-height 0.04 m, and static and dynamic friction 2.0 | upstream_code | source/dexverse/dexverse/tasks/config/functional/grasp_kettle_cfg.py:74-80 |
| The kettle resets x in [-0.05, 0.15] m, y in [-0.3, -0.1] m and yaw in [2.84, 3.44] rad | upstream_code | source/dexverse/dexverse/tasks/config/functional/grasp_kettle_cfg.py:85-87 |
| The mug that is the pour goal resets x in [-0.15, 0.15] m and y in [0.05, 0.3] m | upstream_code | source/dexverse/dexverse/tasks/config/functional/grasp_kettle_cfg.py:123-124 |
| The table top is at height 0.6 m | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:36 |
| The floating right Shadow hand is controlled by three joint-position action terms: 3 translation joints, 3 rotation joints in z, y, x order and the 22 Shadow finger joints, all with scale 1.0 | upstream_code | source/dexverse/dexverse/robot_agents/shadow/floating.py:99-113 |
| The relative retargeter layout has 28 output values: wrist translation indices 0-2, wrist rotation indices 3-5 and 22 finger indices 6-27 | upstream_code | source/dexverse/dexverse/robot_agents/shadow/floating.py:116-126 |
| Isaac Lab's JointPositionActionCfg defaults to use_default_offset=True, so a joint target is action * scale + default joint position | upstream_code | source/dexverse/dexverse/devices/wrist_origin.py:15-18 |
| Control runs at 60 Hz: decimation is 2 | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:1252 |
| The simulation timestep is 1/120 s | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:1318 |
| The episode length is 20 s | upstream_code | source/dexverse/dexverse/tasks/config/functional/base_cfg.py:467 |
| A time_out term with time_out=True ends an episode at the time limit | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:1017 |
| The action penalties are action_l2 and action_rate_l2, each with weight -0.005 | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:1011-1012 |
| The action_l2_clamped and action_rate_l2_clamped terms sum squared actions and squared action changes over the action dimension and clamp each sum to [-1000, 1000] | upstream_code | source/dexverse/dexverse/tasks/mdp/rewards.py:44-51 |
| The observation layout is grouped into policy (last action), proprio (joint positions), contact, state (object pose), privileged (velocities), goal, rgb, depth and pointcloud | upstream_code | source/dexverse/dexverse/tasks/dexverse_base_env_cfg.py:728-756 |
| The functional grasping observation layout adds a state group with object position and orientation and a goal group | upstream_code | source/dexverse/dexverse/tasks/config/functional/base_cfg.py:204-238 |
| The zero-action script samples a full action vector as 2 * rand - 1 from the action-space shape before multiplying it by zero | upstream_code | scripts/zero_agent.py:312-313 |
| The package installs with python -m pip install -e source/dexverse | vendor_doc | README.md:123 |
| The supported setup installs Isaac Sim 5.1.0 and Isaac Lab v2.3.2 with CUDA 12.8 PyTorch builds | vendor_doc | README.md:84-101 |
| The robot hand and object/scene assets are not stored in the git repository; they come from the gated dexverse/DexVerse_release Hugging Face dataset and must be downloaded before any environment can run | vendor_doc | README.md:144-146 |

Limits: the driver declares none. The simulator contract has only the action-space bound, which the bridge derives from
the environment: `action.values` per element from -1 to 1 (the range the zero-action script samples, with no source and
the generated ref `action_space of the fake backend .fake:FakeDexVerseGraspKettleEnv`), and `ticks` from 1 to
`max_ticks` (10000 by default). The device is simulated (R0), so no limit is `operator_required` and there is no
site-limits overlay. The action range is the fake's own bound, not a number stated by the clone for Isaac Lab;
`driver.py` `fidelity.gaps` says so.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Dexverse-GraspKettle-v0`, level F0 (the fake is a
contract-level stand-in, not a rigid-body simulator), determinism `seeded` with `seed_control` `parameter`, timestep
`1000/60` ms (decimation 2 at a 1/120 s simulation step, `tasks/dexverse_base_env_cfg.py:1252` and `:1318`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps list the omitted physics,
observation groups, task terminations and the gated assets.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the fake has no native stop); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. There is no hardware
backend and no claim of a hardware run.

Tags: dexverse, isaac-lab, dexterous-manipulation, functional-grasping, pouring, simulation, gymnasium
