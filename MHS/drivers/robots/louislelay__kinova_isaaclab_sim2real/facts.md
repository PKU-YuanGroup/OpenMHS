# Facts and tags for gh.louislelay/kinova_isaaclab_sim2real

Every fact cites its source at commit `d97c80ed8f532de5ab2609366f12e9d4c62e1ea3`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a standalone Isaac Lab extension for training reinforcement-learning agents on the Kinova Gen3 and deploying them in Isaac Sim or on the real robot via ROS2 | vendor_doc | README.md:5-7 |
| Isaac Lab is installed first, and the Python package is installed with python -m pip install -e source/gen3 | vendor_doc | README.md:25-30 |
| The Sim2Real pipeline runs with ROS2 and does not require Isaac Lab or Isaac Sim to be installed | vendor_doc | README.md:10 |
| The task package imports gymnasium and registers Gen3-Reach-v0 with gym.register; its entry point is isaaclab.envs:ManagerBasedRLEnv, its environment configuration is joint_pos_env_cfg:Gen3ReachEnvCfg and the environment checker is disabled | upstream_code | source/gen3/gen3/tasks/manager_based/gen3_reach/__init__.py:6-24 |
| Gen3ReachEnvCfg subclasses ReachEnvCfg and sets the scene robot to KINOVA_GEN3_N7_CFG at the prim path {ENV_REGEX_NS}/Robot | upstream_code | source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py:25-31 |
| The reset event reset_robot_joints uses the position range (0.75, 1.25) | upstream_code | source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py:32-33 |
| The action is a JointPositionActionCfg over joint_names ['.*'] with scale 0.5 and use_default_offset=True | upstream_code | source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py:39-41 |
| The end-effector command targets the body end_effector_link and fixes the pitch range at pi/2 | upstream_code | source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py:43-45 |
| The simulation timestep is 0.016666666666666666 s | upstream_code | pretrained_models/reach/env.yaml:21 |
| The decimation is 2, so one policy step advances two simulation timesteps | upstream_code | pretrained_models/reach/env.yaml:76 |
| The scene robot's initial joint positions are joint_1 0.0, joint_2 0.65, joint_3 0.0, joint_4 1.89, joint_5 0.0, joint_6 0.6 and joint_7 -1.57 | upstream_code | pretrained_models/reach/env.yaml:144-151 |
| The sim2real mapping treats a simulation joint angle as radians and converts it to degrees with np.rad2deg | upstream_code | scripts/sim2real/run_task_reach.py:130-141 |
| The scene robot is the Kinova Gen3 N7, loaded from gen3n7_instanceable.usd | upstream_code | pretrained_models/reach/env.yaml:124 |
| The arm actuators have effort limits of 39.0 for joint_1 to joint_4 and 9.0 for joint_5 to joint_7 and a velocity limit of 100.0 | upstream_code | pretrained_models/reach/env.yaml:157-165 |
| The reset event reset_joints_by_scale scales the default joint positions by a factor from 0.75 to 1.25 and sets the joint velocities from the range 0.0 to 0.0 | upstream_code | pretrained_models/reach/env.yaml:352-360 |
| The policy observation group concatenates the joint_pos_rel, joint_vel_rel, ee_pose command and last_action terms, with corruption enabled | upstream_code | pretrained_models/reach/env.yaml:288-338 |
| The joint position and joint velocity observations add uniform noise from -0.01 to 0.01 | upstream_code | pretrained_models/reach/env.yaml:294-315 |
| The ee_pose command is a UniformPoseCommand for end_effector_link resampled every 4.0 s, with position ranges x 0.35 to 0.65, y -0.2 to 0.2 and z 0.15 to 0.5, roll 0.0, pitch 1.5707963267948966 and yaw -3.14 to 3.14 | upstream_code | pretrained_models/reach/env.yaml:508-535 |
| An episode lasts 12.0 s | upstream_code | pretrained_models/reach/env.yaml:369 |
| The only termination is the time-out term | upstream_code | pretrained_models/reach/env.yaml:490-494 |
| The joint-position action term is not clipped (clip: null) | upstream_code | pretrained_models/reach/env.yaml:344 |
| The recorded environment configuration seeds the run with 42 | upstream_code | pretrained_models/reach/env.yaml:75 |
| The training configuration leaves clip_actions null | upstream_code | pretrained_models/reach/agent.yaml:34 |
| The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as dependencies | upstream_code | source/gen3/config/extension.toml:17-22 |
| The package requires Python 3.10 or newer | upstream_code | source/gen3/setup.py:37 |

Limits: the driver declares none. The action space is the manager-based Isaac Lab joint-position Box; the clone
records the action term and its scale 0.5 (`env.yaml:339-350`) but no numeric action bound, and the fake publishes an
unbounded seven-value Box rather than inventing one. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by
default), and the device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Gen3-Reach-v0`, level F0 (the checked fake is
kinematic; the Isaac Lab engine is F1 but was not run), determinism `seeded` with `seed_control` `parameter` for the
fake only, timestep 33.33 ms (decimation 2 of 0.016666666666666666 s, `env.yaml:21` and `:76`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, including rigid-body
dynamics, the action bounds, the full observation layout, the reward terms and that the fake was not compared with
Isaac Sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation stays readable.

Tags: kinova, gen3, reach, isaac-sim, isaac-lab, reinforcement-learning, simulation, gymnasium
