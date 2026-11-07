# Facts and tags for gh.hsp-iit/pybullet-robot-envs

Every fact cites its source at commit `8fb3f9ba1f1a0dec4cd1e96e26556afbd89cbd59`, from `upstream_code` (a file and line
of the clone).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| iCubReach-v0 is registered with entry point pybullet_robot_envs.envs:iCubReachGymEnv, max_episode_steps=1000, IK position control of the left arm (use_IK=1, control_orientation=0) and rendering on by default | upstream_code | pybullet_robot_envs/__init__.py:7-17 |
| The observation concatenates the robot observation, the world observation and the object pose in the hand frame as position and Euler angles | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:151-180 |
| The robot observation is the end-effector position, Euler orientation, Cartesian linear velocity and the positions of the controlled joints | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_env.py:202-249 |
| The world observation is the object position and its Euler orientation, or its quaternion when control_eu_or_quat is 1 | upstream_code | pybullet_robot_envs/envs/world_envs/world_env.py:109-126 |
| The controlled joints are the three torso joints plus the seven joints of the selected arm | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_env.py:42-50 |
| With use_IK set and control_orientation 0 the action dimension is 3: position x, y and z | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_env.py:187-197 |
| The action space is a Box whose every element is bounded by -1 and 1 | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:103-107 |
| In IK position mode a raw action element is multiplied by 0.005 and added to the hand position, then the position is clamped to the workspace | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:204-229 |
| The workspace limits are [0.1, 0.45] on x, [-0.3, 0.3] on y and [0.5, 1.0] on z before the table height adjusts the z minimum | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_env.py:62 |
| Observations and actions are rescaled between the Box bounds and -1..1 by scale_gym_data | upstream_code | pybullet_robot_envs/envs/utils.py:78-92 |
| The physics timestep is 1/240 s | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:37 |
| The gravity used by the simulation is -9.8 m/s^2 on z | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:130 |
| A reset reloads the robot and the world, steps the simulation 100 times after each reload and clears the step counter | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:121-149 |
| The reach task's target distance threshold is 0.03 m | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:52 |
| The episode ends when the hand-to-object distance is at most the target distance, when the terminated flag is set, or when the step counter exceeds max_steps | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:301-317 |
| The reward is minus the hand-to-object distance, plus 1000 and (100 - distance * 80) when the distance is at most the target distance | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:319-330 |
| step returns the four-tuple observation, reward, done, info of the legacy Gym API | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:248-259 |
| seed sets the numpy generator and the world and robot seeds and returns the seed in a list | upstream_code | pybullet_robot_envs/envs/icub_envs/icub_reach_gym_env.py:261-265 |

Limits: the driver declares none.  The only bound is the action space, derived by the bridge from the environment
(`Box` with every element at -1 and 1, no source, ref `action_space of the fake backend .fake:FakeiCubReachEnv`), and
`ticks` (1 to `max_ticks`, 10000 by default).  The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:iCubReach-v0`, level F1 (rigid-body dynamics with
contacts), determinism `seeded` with `seed_control` `parameter`, timestep 4.1667 ms (1/240 s), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say what is not modelled and that the fake was not
compared with the upstream environment.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: icub, reach, manipulation, pybullet, reinforcement-learning, simulation, gym
