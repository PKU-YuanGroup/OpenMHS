# Facts and tags for gh.ian-chuang/homestri-ur5e-rl

Every fact cites its source at commit `89b7e23cc5acbd9a164222fa548cb0113684523e`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a MuJoCo Gymnasium environment for manipulating flexible objects with a UR5e robot arm and a Robotiq 2F-85 gripper | vendor_doc | README.md:3 |
| The repository combines a MuJoCo simulation of the arm, gripper and flexible cable with Gymnasium integration and a graphical environment view | vendor_doc | README.md:11-13 |
| The repository declares the dependencies gymnasium-robotics, mujoco, gymnasium and pynput | upstream_code | setup.py:7-12 |
| The package registers the environment id BaseRobot-v0 with entry point homestri_ur5e_rl.envs.base_robot:BaseRobot | upstream_code | homestri_ur5e_rl/__init__.py:3-6 |
| BaseRobot is a subclass of the repository's MujocoEnv | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:24 |
| The BaseRobot constructor defaults are model_path ../assets/base_robot/scene.xml and frame_skip=40 | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:34-40 |
| The observation space is a Box with low=-inf, high=inf, shape=(28,) and dtype float64 | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:46 |
| The action space is a Box with low=-1.0, high=1.0, shape=(7,) and dtype float64 | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:65 |
| The MuJoCo model uses the implicitfast integrator, angles in radians and a timestep of 0.002 s | upstream_code | homestri_ur5e_rl/envs/assets/base_robot/scene.xml:2-6 |
| The initial joint configuration sets shoulder_lift, elbow and wrist_1 to -pi/2 and wrist_2 to pi/2 | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:216-223 |
| Each step runs the operational-space controller with action[:6], writes action[6] to the seventh control channel and calls do_simulation(ctrl, n_frames=1) once per frame_skip iteration | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:275-296 |
| step returns the observation with reward 0.0, terminated=False, truncated=False and an empty info dictionary | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:301-303 |
| The observation concatenates the robot qpos and qvel returned by robot_get_obs | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:305-311 |
| reset_model restores init_qpos and init_qvel with set_state and returns the observation | upstream_code | homestri_ur5e_rl/envs/base_robot/base_robot_env.py:313-319 |
| The README states that the repository is not actively maintained and is experimental | vendor_doc | README.md:27 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`action.values` with seven elements between -1.0 and 1.0, no source, ref
`action_space of the fake backend .fake:FakeBaseRobot`), and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:BaseRobot-v0`, level F0 for the checked fake
backend (kinematic, no MuJoCo dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 80 ms
(frame_skip 40 at base_robot_env.py:37 times 0.002 s at scene.xml:6), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say that the fake is not MuJoCo, that the controller, gripper and cable are
not modelled, that there is no wall-clock pacing, that the fake was not compared with upstream, and that no physical
UR5e was modelled or validated.

Safety: simulated R0 device. The e-stop is the runtime's software latch; after it no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the state stays readable. No hardware backend exists.

Tags: homestri, ur5e, robotiq-2f85, mujoco, gymnasium, simulation, reinforcement-learning
