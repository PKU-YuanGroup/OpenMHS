# Facts and tags for gh.clvrai/furniture-bench

Every fact cites its source at commit `a87960a2490a7a19c86ea16a5ef371718b2baa70`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FurnitureSim-v0 is registered with entry point furniture_bench.envs.furniture_sim_env:FurnitureSimEnv | upstream_code | furniture_bench/__init__.py:33-36 |
| FurnitureSimEnv is the gym.Env subclass of the simulator | upstream_code | furniture_bench/envs/furniture_sim_env.py:48 |
| The default visual observation lists ee_pos, ee_quat, ee_pos_vel, ee_ori_vel, gripper_width, color_image1 and color_image2 | upstream_code | furniture_bench/envs/observation.py:19-27 |
| For the quat rotation representation the action is an end-effector delta of 8 numbers [x, y, z, qx, qy, qz, qw, gripper]; rot_6d uses 10 numbers and axis uses 7 | upstream_code | furniture_bench/envs/furniture_sim_env.py:707-714 |
| The action space is a Box with every element from -1 to 1 and shape (num_envs, pose_dim + 1) | upstream_code | furniture_bench/envs/furniture_sim_env.py:660-666 |
| pose_dim is 7 for quat, 9 for rot_6d and 6 for axis | upstream_code | furniture_bench/envs/furniture_sim_env.py:653-658 |
| step clips the action to the bounds of the action space before applying it | upstream_code | furniture_bench/envs/furniture_sim_env.py:720-723 |
| The default maximum number of environment steps is 3000 | upstream_code | furniture_bench/envs/furniture_sim_env.py:70 |
| An environment is done when its step count exceeds the furniture's max_env_steps | upstream_code | furniture_bench/envs/furniture_sim_env.py:1009-1016 |
| The observation space is a Dict with a nested robot_state Dict (unless concat_robot_state is True) and one Box per colour image | upstream_code | furniture_bench/envs/furniture_sim_env.py:673-703 |
| The robot-state dimensions are ee_pos 3, ee_quat 4, ee_pos_vel 3, ee_ori_vel 3, joint_positions 7, joint_velocities 7, joint_torques 7 and gripper_width 1 | upstream_code | furniture_bench/robot/robot_state.py:17-26 |
| The resized camera image is (224, 224) pixels | upstream_code | furniture_bench/config.py:79 |
| The full-resolution camera image is (1280, 720) pixels | upstream_code | furniture_bench/config.py:77 |
| step returns a four-tuple (observation, reward, done, info) | upstream_code | furniture_bench/envs/furniture_sim_env.py:822-827 |
| reset returns the observation | upstream_code | furniture_bench/envs/furniture_sim_env.py:1152-1175 |
| The reward is computed from the furniture assembly state | upstream_code | furniture_bench/envs/furniture_sim_env.py:829-846 |
| The robot control frequency is 10 Hz | upstream_code | furniture_bench/config.py:21 |
| The Isaac Gym simulation timestep is 1/60 s with 2 substeps | upstream_code | furniture_bench/sim_config.py:23-24 |
| step derives the number of simulator refreshes from the control frequency, the timestep and the substeps | upstream_code | furniture_bench/envs/furniture_sim_env.py:725-731 |
| A positive gripper action closes the gripper and a negative one opens it to max_gripper_width | upstream_code | furniture_bench/envs/furniture_sim_env.py:762-774 |
| max_gripper_width is 0.065 for the square_table furniture | upstream_code | furniture_bench/config.py:35-36 |
| squeeze_batch_dim defaults to False, so observations keep the leading environment dimension | upstream_code | furniture_bench/envs/furniture_sim_env.py:184-185 |

Limits: the driver declares none of its own. The action bound is the environment's action space, which the
bridge derives: `cap.world.step.v1` takes `action.values` with 8 elements, each between -1 and 1, with source
`upstream_code` and ref `furniture_bench/envs/furniture_sim_env.py:660-666`. `ticks` is bounded by the driver's
`max_ticks` (10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `furniture_bench:FurnitureSim-v0 (fake kinematic stand-in)`,
level F0 (kinematic; no rigid-body dynamics, contacts, actuators or sensors), determinism `seeded` with
`seed_control` `parameter`, timestep 100 ms (one environment step at the 10 Hz control frequency), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps state that the fake is not the upstream Isaac Gym
PhysX simulator (which would be F1), that the image observations are 2 x 2 x 3 placeholders while the configured real
sizes are 224 x 224 or 1280 x 720, that rotation and the assembly reward are not modelled, that one environment is
modelled, and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (a simulator has no native stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: furniture-assembly, manipulation, isaac-gym, reinforcement-learning, simulation, gymnasium
