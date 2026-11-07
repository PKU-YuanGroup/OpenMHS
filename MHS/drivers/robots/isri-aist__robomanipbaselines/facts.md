# Facts and tags for gh.isri-aist/robomanipbaselines

Every fact cites its source at commit `8535948420f8f9bc979fdb31ed049d1c82b906b2`: `upstream_code` is a code, XML
model or comment line of the clone.  The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MujocoUR5eCableEnv is registered as robo_manip_baselines/MujocoUR5eCableEnv-v0 with entry point robo_manip_baselines.envs.mujoco:MujocoUR5eCableEnv | upstream_code | robo_manip_baselines/envs/__init__.py:5-8 |
| The class subclasses MujocoUR5eEnvBase and passes the scene env_ur5e_cable.xml and the init qpos [pi, -pi/2, -0.75*pi, -0.25*pi, pi/2, pi/2] followed by eight zeros | upstream_code | robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eCableEnv.py:9-32 |
| MujocoEnvBase subclasses gymnasium.envs.mujoco:MujocoEnv and calls it with the model path, frame_skip 8, the observation space, 640x480 rendering and the default camera config | upstream_code | robo_manip_baselines/envs/mujoco/MujocoEnvBase.py:11-38 |
| The scene sets the MuJoCo timestep to 0.004 s | upstream_code | robo_manip_baselines/envs/assets/mujoco/envs/ur5e/env_ur5e_common.xml:3 |
| MujocoEnvBase sets sim_timestep to 0.004 s and frame_skip to 8, so one environment step advances 0.032 s | upstream_code | robo_manip_baselines/envs/mujoco/MujocoEnvBase.py:12-13 |
| The observation space is a Dict of three Box spaces: joint_pos (7), joint_vel (7) and wrench (6), each unbounded (-inf, inf) | upstream_code | robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eEnvBase.py:25-31 |
| The observation concatenates six arm joint positions and velocities with one normalized gripper value (rad2deg of the mean gripper qpos, divided by 45 and multiplied by 255), a three-axis force and a three-axis torque | upstream_code | robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eEnvBase.py:84-125 |
| step runs do_simulation(action, frame_skip) and returns (observation, reward, terminated=False, truncated=False, info); a TimeLimit wrapper would be the only truncation | upstream_code | robo_manip_baselines/envs/mujoco/MujocoEnvBase.py:82-97 |
| reset_model restores init_qpos and init_qvel and returns the observation, so the environment reset has a fixed start pose and does not draw a random one | upstream_code | robo_manip_baselines/envs/mujoco/MujocoEnvBase.py:163-165 |
| The cable reward is 1 only when the cable stays below the pole tops, its end is past the second pole and the cable crosses the two poles; otherwise it is 0 | upstream_code | robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eCableEnv.py:48-105 |
| The UR5e model defines six arm joint actuators and one gripper tendon actuator | upstream_code | robo_manip_baselines/envs/assets/mujoco/robots/ur5e/ur5e_integrated_specific_config.xml:4-14 |
| The arm actuator ctrlrange is -6.2831 to 6.2831 and the limited elbow ctrlrange is -3.1415 to 3.1415 | upstream_code | robo_manip_baselines/envs/assets/mujoco/robots/ur5e/ur5e_integrated_shared_config.xml:6-11 |
| The gripper actuator ctrlrange is 0 to 255 | upstream_code | robo_manip_baselines/envs/assets/mujoco/robots/ur5e/ur5e_integrated_specific_config.xml:13 |
| The scene includes the UR5e shared and specific configurations and the cable configuration | upstream_code | robo_manip_baselines/envs/assets/mujoco/envs/ur5e/env_ur5e_cable.xml:9-12 |
| The upstream pins gymnasium 1.0.0 and mujoco 3.1.6 | upstream_code | pyproject.toml:33-34 |

Limits: the driver declares none.  The step action bounds are derived by the bridge from the fake environment's
`action_space`, which reproduces the seven actuator `ctrlrange` values above; `cap.world.seed.v1` and the reset seed
have the catalogue's integer schema bounds.  The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:robo_manip_baselines/MujocoUR5eCableEnv-v0`,
level F0 (the fake is kinematic: no contacts, cable, actuator or sensor model), determinism `seeded` with
`seed_control` `parameter`, timestep 32 ms (`sim_timestep` 0.004 s x `frame_skip` 8), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore.  The gaps say what is not modelled, including NOT COVERED: the
three 640x480 camera RGB/depth images and tactile maps in the upstream info dictionary.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: ur5e, cable, manipulation, mujoco, reinforcement-learning, simulation, gymnasium
