# Facts and tags for gh.tuojingai/softvtbench

Every fact cites its source at commit `58056111f01e05bf1a4ae1dee75db4e3d9e7c5be`: `upstream_code` for code and
comments of the clone, `vendor_doc` for documentation text of the clone. The same facts are written into `facts = [...]`
in `driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment Isaac-Libero-Franka-IK-v0 is registered with entry_point isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point IKLiberoCameraEnvCfg | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/__init__.py:32-39 |
| IKLiberoCameraEnvCfg is defined in franka_libero_env_cfg.py and extends JointPositionLiberoCameraEnvCfg | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:1065-1066 |
| The IK arm action is a differential-inverse-kinematics pose command with ik_method dls and scale 1.0 | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:1075-1086 |
| The default gripper action is a binary joint-position action whose open command is 0.04 and close command is 0.0 for the panda_finger joints | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:496-501 |
| The policy observation group contains the last action, the end-effector pose in the robot base frame, the gripper position and the 7D Franka arm joint positions, with concatenate_terms False | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:335-347 |
| The subtask observation group adds one grasp flag for every object of interest | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:350-375 |
| The simulation advances 1/60 s of physics per simulation step with decimation 3, so one environment step is 0.05 s (20 Hz), and the libero_10 episode length is 16.0 s | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:905-909 |
| Policy observations are synchronized at 20 Hz | vendor_doc | README.md:67 |
| The commands, rewards and curriculum managers are None, so the configured environment has no reward function of its own | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:411-417 |
| The terminations are time_out, one object_dropped term per object of interest below -0.05 m and the task goal success term | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:382-401 |
| The eye-in-hand and agentview cameras are 512 by 512 with rgb and distance_to_image_plane data | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:955-975 |
| The task JSON is selected by TASK_SUITE (default libero_10) and TASK_ID (default 0) under benchmarks/datasets/libero/config, and the USD assets come from LIBERO_ASSETS_DATA_DIR | upstream_code | SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py:96-123 |
| The closed-loop policy client creates the environment with gym.make(env_name, cfg=env_cfg).unwrapped | upstream_code | SoftVTBench/benchmarks/common/closedloop_policy_inference.py:97 |
| The released softvtbench-eval environment contains Isaac Sim 4.5, Isaac Lab 2.1.1 and Python 3.10 | vendor_doc | README.md:255-267 |
| The simulator setup installs Isaac Lab 2.1.1 from a separate checkout and then the local tac_manip extension | vendor_doc | README.md:280-291 |
| The evaluation scene and USD assets are hosted in the external eval-assets bundle | vendor_doc | README.md:122 |
| The tactile runtime assets are downloaded outside the repository and symlinked into tac_manip/assets/data | vendor_doc | README.md:196-197 |
| The tac_manip install_requires list contains only debugpy, psutil, nvidia-ml-py and pre-commit, with no simulator or device transport package | upstream_code | SoftVTBench/source/tac_manip/setup.py:14-19 |

## Limits

The driver declares none. The family bridge derives the action contract from the environment's action space, which
Isaac Lab builds as an unbounded `Box` (no file of the clone states a numeric action bound, so the fake invents none),
and bounds `ticks` from 1 to `max_ticks` (10000 by default). The device is simulated (R0), so no limit is
`operator_required` and there is no site-limits overlay.

## Fidelity

`driver.py` publishes `engine = "isaaclab:Isaac-Libero-Franka-IK-v0"`, `fidelity_level = "F0"` (the fake is
kinematic/analytic), determinism `seeded` with `seed_control` `parameter`, `timestep_ms = 50.0` (1/60 s physics times
decimation 3, README.md:67 states 20 Hz), `realtime_factor = 0`, clock `lockstep`, reset `full`, and no snapshot and
restore. The gaps say that the model has no Isaac Sim contacts, no FEM deformables, no camera or tactile arrays, no IK
solver and no validation against the upstream simulator. The real environment (backend `sim`) was not installed or
run; only the fake backend was checked.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or reset is
accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state stays
readable. No hardware is attached and no hardware run was made.

## Tags

softvtbench, isaac-lab, libero, franka, deformable, reinforcement-learning, simulation, gymnasium
