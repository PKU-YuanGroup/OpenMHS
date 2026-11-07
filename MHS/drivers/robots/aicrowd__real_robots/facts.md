# Facts and tags for gh.aicrowd/real_robots

Every fact cites its source at commit `6dd5b70bad14426483e2d3ee29b3d8708d34e1ba`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. Two facts are
`vendor_doc` (README.md and environment.md); the rest are `upstream_code`.

| fact | source | ref |
|---|---|---|
| The REALRobot environment is a standard gym environment with a 7DoF Kuka arm, a 2DoF gripper and a table with 3 objects | vendor_doc | README.md:104-105 |
| The action is a vector of 9 joint positions in radians; the two gripper joints range from 0 to +pi/2 and are coupled so the second is at most twice the first | vendor_doc | environment.md:8-10 |
| The environment registers 18 REALRobot2020 ids and creates them through real_robots.envs:REALRobotEnv with additional_obs, objects and action_type keyword arguments | upstream_code | real_robots/__init__.py:16-28 |
| REALRobotEnv defaults to render=False, objects=3, action_type='joints' and additional_obs=True | upstream_code | real_robots/envs/env.py:36-37 |
| With action_type='joints' the action space is a Dict with 'joint_command' (the 9-joint Box) and 'render' (MultiBinary(1)) | upstream_code | real_robots/envs/env.py:57-61 |
| Kuka builds a 9-element Box action space from min_joints and max_joints; the two gripper joints are limited to 0 and pi/2 | upstream_code | real_robots/envs/robot.py:58-71 |
| Each step clamps the change of a joint to at most 0.2 rad for joints 1 to 5, 0.3 rad for joints 6 and 7 and 0.1 rad for the two gripper joints | upstream_code | real_robots/envs/env.py:314-321 |
| step_joints applies the joint command, advances the Bullet scene and returns (observation, reward, done, info) | upstream_code | real_robots/envs/env.py:326-356 |
| The default reward function returns 0 for every observation | upstream_code | real_robots/envs/env.py:11-12 |
| The intrinsic phase ends after 15e6 steps and an extrinsic trial after 10e3 steps | upstream_code | real_robots/envs/env.py:32-34 |
| step_joints sets done when the timestep reaches intrinsic_timesteps or extrinsic_timesteps | upstream_code | real_robots/envs/env.py:345-352 |
| The observation dictionary carries joint_positions, touch_sensors, retina and goal, and the extended form adds depth, mask, object_positions, goal_mask and goal_positions | upstream_code | real_robots/envs/env.py:277-310 |
| The top camera image and the goal image are 240x320x3 arrays | vendor_doc | environment.md:39-40 |
| Kuka has 9 joints, 4 touch sensors and a 320 by 240 eye camera | upstream_code | real_robots/envs/robot.py:26-31 |
| The observation space declares joint_positions, touch_sensors, retina, depth, goal and, with additional_obs, mask, object_positions, goal_mask and goal_positions with the Kuka dimensions | upstream_code | real_robots/envs/robot.py:81-99 |
| The Bullet scene uses gravity 9.81, a timestep of 0.005 s and frame_skip 1 | upstream_code | real_robots/envs/env.py:202-204 |
| reset resets the simulation, sets gravity to (0, 0, -9.81), resets the timestep to 0 and returns the observation | upstream_code | real_robots/envs/env.py:206-219 |
| The installation requires gym, pybullet and numpy (plus Click, tqdm, aicrowd-api, pillow and pyinterval); it declares no serial, VISA or socket dependency | upstream_code | setup.py:24-31 |

## Limits

The driver declares no `Limit` of its own. The numeric bounds of `cap.world.step.v1` are derived by the Gymnasium
bridge from the environment's own action space: `action.joint_command` is the 9-element Box built from Kuka
`min_joints`/`max_joints` (`robot.py:58-71`, no source, with the derived ref
`action_space of the fake backend .fake:FakeREALRobotEnv`), and `action.render` is MultiBinary(1), so 0 or 1
(`env.py:57-61`). These are the environment's declared bounds, not operator-required limits. The device is simulated
(R0), and the runtime's software latch is the only stop.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `pybullet:REALRobot2020`, level F0 (the fake is kinematic: it has no
rigid-body dynamics or contacts), determinism `seeded` with `seed_control` `parameter`, timestep 5 ms
(`env.py:202-204` states 0.005 s), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.
The gaps say that the fake is not the PyBullet simulation, that the arrays are a 24x32 stand-in for the device's
240x320x3 / 240x320 arrays (`robot.py:30-31,86-95`), that only the fake honours a reset seed (the upstream
`reset()` at `env.py:206` takes none), that `goal_mask`/`goal_positions` are zero arrays where the upstream extended
observation has None until a goal is set (`env.py:97-98,307-309`), that the simulation is not wall-clock paced, that
snapshots are absent, and that nothing was validated against a device.

## Safety

Simulated R0 device. There is no hardware stop: the runtime's software latch refuses every step and reset after an
e-stop until `mhs.safety.reset` clears it, and the last observation stays readable. No hardware backend is declared
and no hardware was attached.

## Mock path

The card's preferred mock is `upstream-sim`, but gym and pybullet are not installed where the gate runs and package
code never imports or installs the clone, so `backends = {"fake": ".fake:FakeREALRobotEnv"}` is used. The fake
implements only `reset` and `step`, the two public methods of `REALRobotEnv` (gate G7), plus private helpers. The
upstream `gym.make(env_id)` path of `GymnasiumDriver` was not run.

Tags: kuka, iiwa, manipulation, pybullet, reinforcement-learning, simulation, gym
