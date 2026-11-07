# Facts and tags for gh.leekwoon/nav-gym

Every fact cites the pinned clone at commit `92aa9ce66074cc51d5aa598205b52443976d8af7`. The same facts are
written into `driver.py` (`facts = [...]`); the generated reference file is read from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| NavGym-v0 is registered with id 'NavGym-v0' | upstream_code | nav_gym/src/nav_gym_env/__init__.py:5 |
| NavGym-v0's entry point is 'nav_gym_env.env:NavGymEnv' | upstream_code | nav_gym/src/nav_gym_env/__init__.py:39 |
| The registration supplies the constructor kwargs, including time_step 0.2 s, distance_threshold 0.5 m and num_scan_stack 1 | upstream_code | nav_gym/src/nav_gym_env/__init__.py:8-11 |
| The registration sets the linear velocity range to [0, 0.5] and the rotational velocity range to [-0.64, 0.64] | upstream_code | nav_gym/src/nav_gym_env/__init__.py:12-13 |
| The action space is a two-element Box: low [linvel_range[0], rotvel_range[0]] and high [linvel_range[1], rotvel_range[1]], dtype float32 | upstream_code | nav_gym/src/nav_gym_env/env.py:133-137 |
| The observation space is a Dict of the scan-plus-pose observation (num_scan_stack * robot.n_angles + 7), a two-element achieved_goal and a two-element desired_goal; all are unbounded float32 Boxes | upstream_code | nav_gym/src/nav_gym_env/env.py:138-142 |
| KetiRobot reports 512 lidar angles, angle_min -3.141592, angle_max 3.141592, angle_increment 0.0122718463 and range_max 25 m | upstream_code | nav_gym/src/nav_gym_env/keti_robot.py:44-48 |
| KetiRobot.set_vel applies the [linear, rotational] velocity for time_step with a 0.14474 m rotation-centre offset and wraps theta modulo 2*pi | upstream_code | nav_gym/src/nav_gym_env/keti_robot.py:65-93 |
| A step applies the action with robot.set_vel, computes the reward, done and info, and returns (observation, reward, done, info) | upstream_code | nav_gym/src/nav_gym_env/env.py:664-728 |
| step prints a message when the linear or rotational velocity is outside its registered range but applies the action unclipped (the np.clip lines are commented out); the rotational upper-bound check compares action[0] | upstream_code | nav_gym/src/nav_gym_env/env.py:606-613 |
| The terminal flag is the logical OR of success (goal distance below distance_threshold) and crash (any scan range below scan_threshold) | upstream_code | nav_gym/src/nav_gym_env/env.py:508-512 |
| The reward adds the factors reward_success, reward_crash, reward_progress, reward_forward, reward_rotation and reward_discomfort, each scaled by reward_scale | upstream_code | nav_gym/src/nav_gym_env/env.py:557-578 |
| The registration sets reward_scale 15 and the success, crash, progress, forward, rotation and discomfort factors to 1, 1, 0.001, 0.0, 0.005 and 0.01 | upstream_code | nav_gym/src/nav_gym_env/__init__.py:19-25 |
| A reset samples the environment parameters and map, creates the robot and humans, and returns the initial observation without taking a reset argument | upstream_code | nav_gym/src/nav_gym_env/env.py:730-831 |
| The upstream package declares matplotlib, pandas, rospkg, netifaces, gym 0.10.5, opencv-python, PyQt5, torch, pyastar2d, pymap2d, pyrangelibc and pyrvo2 as install requirements | upstream_code | nav_gym/setup.py:13-27 |
| The project is an OpenAI-gym compatible navigation simulator that can be integrated into ROS | vendor_doc | README.md:3 |

## Scope and shape

The selected interface is the registered Gymnasium environment `NavGym-v0`, not the repository's ROS nodes. The
repository contains a separate ROS bridge (`nav_gym/src/nav_gym_ros/`), but an environment does not become a ROS
transport driver merely because the repository also contains ROS nodes. **DEVIATION FROM THE CARD:** the card names
helper `RosDriver` (family `ros`); this package uses `GymnasiumDriver` for the environment's own `reset`/`step`
interface, and `driver.lock.json` records the fake backend.

The card also lists `crowd_sim.envs:CrowdSim`, which is a separate crowd-simulation environment registered as
`CrowdSim-v0` (`nav_gym/src/crowd_sim/__init__.py:3`). It is not covered: its `configure(config)` path must run before
`reset(phase='test', test_case=None, ...)`, and that lifecycle is not the `cap.world.reset.v1` contract this package
serves. A second package would be needed for it. The selected `NavGymEnv` is concrete for the registered default
`robot_type` 'keti'; any other `robot_type` reaches `NotImplementedError` (`nav_gym/src/nav_gym_env/env.py:772-773`),
so this package serves only the registered NavGym-v0 configuration.

## Limits

The driver declares no `Limit` of its own. The only input bounds are the upstream action space, which the bridge
derives from the fake environment and cites with `action_space_ref = nav_gym/src/nav_gym_env/__init__.py:12-13`:
`action.values[0]` is the linear velocity in [0, 0.5] and `action.values[1]` is the rotational velocity in
[-0.64, 0.64]. `cap.world.step.v1` also bounds `ticks` from 1 to `max_ticks` (10000 by default), and the bridge
bounds the reset and seed inputs. The upstream `step` itself does not clip: it prints a message for an out-of-range
velocity and applies the action unclipped (`env.py:606-613`), so the bridge's refusal is stricter than the upstream.
The device is simulated at R0, so no bound is `operator_required` and
`site-limits.example.json` is not needed.

## Fidelity and fake scope

The checked backend is the package's own analytic stand-in (`fake.py`), not the upstream simulator. It preserves
the two-element velocity action, the 512-angle scan observation, the 200 ms step, the four-tuple step return and the
goal-distance success terminal. It has no generated map, crowd, human policy, lidar ray casting, collision,
discomfort or scan noise; its scan is a constant maximum-range return, so the crash terminal is never reached, and
its trajectories were never compared with the upstream environment. The upstream registers `NavGym-v0` with gym
0.10.5 (`__init__.py:1`), not Gymnasium, and its reward indexes with the `np.bool` alias (`env.py:557-565`) that
current NumPy releases no longer define, so a live backend needs the upstream's old dependency set; none was run.
The upstream constructor additionally needs
torch, OpenCV, pyastar2d, range_libc, CMap2D, pose2d and `human_policy.pth`; none of those is available where the
gate runs, and package code never imports or runs the clone.

The fidelity contract is declared in `driver.py`: engine `analytic: open-space kinematic stand-in for NavGym-v0`, level
F0, determinism `seeded` with `seed_control` `none` (the fake is deterministic from a fixed start, and the upstream
`reset()` takes no seed and exposes no `seed()` method, so the bridge-recorded seed does not vary the scene),
timestep 200 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or restore. The gaps list each
missing model and the unvalidated trajectory.

## Safety

Simulated R0 device. There is no native stop method; the e-stop is the runtime's software latch. After it, the
bridge refuses `cap.world.step.v1` and `cap.world.reset.v1` until `mhs.safety.reset` clears the latch, and the world
state stays readable.

## Tags

navigation, reinforcement-learning, simulation, gym, crowd
