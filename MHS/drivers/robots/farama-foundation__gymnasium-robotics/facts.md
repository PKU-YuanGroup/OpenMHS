# Facts and tags for gh.farama-foundation/gymnasium-robotics

Every fact cites its source at commit `b8da02a89191daf8f004e7f7510ff655f7a90100`; all of them are
`upstream_code` lines of the clone. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FetchSlide-v4 is registered with entry point `gymnasium_robotics.envs.fetch.slide:MujocoFetchSlideEnv` and `max_episode_steps=50` | upstream_code | gymnasium_robotics/__init__.py:33-38 |
| The action space is `Box(-1.0, 1.0, (4,), float32)`: the Cartesian displacement dx, dy, dz of the end effector and a gripper command | upstream_code | gymnasium_robotics/envs/fetch/slide.py:53 |
| The action vector has four entries, created with `n_actions=4` | upstream_code | gymnasium_robotics/envs/fetch/fetch_env.py:69 |
| The position control is scaled by 0.05 before it is applied to the simulation | upstream_code | gymnasium_robotics/envs/fetch/fetch_env.py:92 |
| A control step applies the same action for 20 simulator substeps of 0.002 s, a control frequency of 25 Hz (a 40 ms control step) | upstream_code | gymnasium_robotics/envs/fetch/slide.py:49 |
| On reset the gripper starts at global (x,y,z) = [1, 0.75, 0.41] m and the robot base is fixed at [0.405, 0.48, 0] | upstream_code | gymnasium_robotics/envs/fetch/slide.py:132 |
| The puck has a fixed height z = 0.42 m; its initial x,y offset from the gripper is drawn uniformly from [-0.1, 0.1] m until the 2D Euclidean distance is greater than 0.1 m | upstream_code | gymnasium_robotics/envs/fetch/slide.py:134 |
| The target is drawn by adding an offset uniformly in [-0.3, 0.3] m to the initial gripper x,y and its height is 0.42 m | upstream_code | gymnasium_robotics/envs/fetch/slide.py:137 |
| The constructor sets `target_offset` [0.4, 0, 0], `target_range` 0.3, `obj_range` 0.1 and `distance_threshold` 0.05 | upstream_code | gymnasium_robotics/envs/fetch/slide.py:181-184 |
| The sparse reward is -1 until the puck is within 0.05 m of the target and 0 then; the dense reward is the negative Euclidean distance | upstream_code | gymnasium_robotics/envs/fetch/slide.py:115-117 |
| The episode is truncated at `max_episode_steps` (50 by default) and never terminated: the task is continuing | upstream_code | gymnasium_robotics/envs/fetch/slide.py:142-143 |
| The observation array is 25 values of the gripper and puck state | upstream_code | gymnasium_robotics/envs/fetch/slide.py:67 |
| The desired goal and the achieved goal are each a 3-dimensional array (3,) of the puck position | upstream_code | gymnasium_robotics/envs/fetch/slide.py:97-105 |
| The gripper is locked in a closed configuration because the puck does not need to be grasped | upstream_code | gymnasium_robotics/envs/fetch/slide.py:47 |
| The observation space is a Dict of `desired_goal`, `achieved_goal` and `observation` Boxes whose shapes are copied from the reset observation | upstream_code | gymnasium_robotics/envs/robot_env.py:88-98 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1.0, 1.0, (4,), float32)`: `action.values` per element from -1 to 1, with the source `upstream_code` and the ref
`gymnasium_robotics/envs/robot_env.py:87`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium-robotics:FetchSlide-v4`, level F1 (a kinematic
stand-in, no contacts, friction, actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`,
timestep 40 ms (20 substeps of 0.002 s, `slide.py:49`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled and that this package's fake was not compared with the upstream
environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: fetch, fetch-slide, mujoco, robotics, reinforcement-learning, simulation, gymnasium
