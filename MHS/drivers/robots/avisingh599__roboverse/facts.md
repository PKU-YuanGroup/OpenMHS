OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.avisingh599/roboverse

Every fact cites its source at commit `a443f79af67529158ba409889fd7b8006b1d3f88`. The upstream clone is a legacy
Gym 0.12.1 / PyBullet simulation of a WidowX 250 arm; it has no vendor manual, so the README statements are
`vendor_doc` and every other fact is `upstream_code`. The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| roboverse is a set of environments that use PyBullet to simulate robotic manipulation tasks | vendor_doc | README.md:2 |
| The documented use is `env = roboverse.make('Widow250DoubleDrawerOpenNeutral-v0', gui=True)`, then `env.reset()` and `env.step(env.action_space.sample())` | vendor_doc | README.md:7-11 |
| The requirements pin gym 0.12.1 (the legacy Gym API) and pybullet 2.7.9 | upstream_code | requirements.txt:1-2 |
| `roboverse.make` is `gym.make` and the environments are registered with `gym.register` | upstream_code | roboverse/envs/registration.py:1024-1037 |
| Widow250Grasp-v0 is registered with entry_point `roboverse.envs.widow250:Widow250Env` and `control_mode` `discrete_gripper` | upstream_code | roboverse/envs/registration.py:8-16 |
| The action vector is eight-dimensional: `ACTION_DIM = 8` | upstream_code | roboverse/envs/widow250.py:27 |
| The action space is a `gym.spaces.Box` with one bound per action dimension, built from `act_bound` 1 (so every entry is in -1..1) | upstream_code | roboverse/envs/widow250.py:331-335 |
| `step` reads `action[:3]` as an end-effector position action, `action[3:6]` as an orientation action, `action[6]` as the gripper action and `action[7]` as the neutral action | upstream_code | roboverse/envs/widow250.py:203-206 |
| `xyz_action_scale` defaults to 0.2 and `abc_action_scale` to 20.0 | upstream_code | roboverse/envs/widow250.py:57-59 |
| The target end-effector position is the current position plus `xyz_action_scale` times the xyz action, and the target orientation adds `abc_action_scale` times the abc action | upstream_code | roboverse/envs/widow250.py:214-217 |
| `ee_pos_low` defaults to (0.4, -0.2, -0.34) and `ee_pos_high` to (0.8, 0.4, -0.1) | upstream_code | roboverse/envs/widow250.py:61-62 |
| The target end-effector position is clipped between `ee_pos_low` and `ee_pos_high` before the action is applied | upstream_code | roboverse/envs/widow250.py:244-245 |
| `num_sim_steps` defaults to 10, `num_sim_steps_reset` to 50 and `num_sim_steps_discrete_action` to 75 | upstream_code | roboverse/envs/widow250.py:46-48 |
| The default grasp thresholds are object height -0.25 and object-gripper distance 0.1 | upstream_code | roboverse/envs/widow250.py:50-52 |
| `check_grasp` succeeds only when the object height is above the height threshold and the distance from the end effector to the object is below the distance threshold | upstream_code | roboverse/bullet/object_utils.py:46-56 |
| `get_observation` returns a dictionary with the keys `object_position`, `object_orientation`, `state` and `image`; `state` concatenates the end-effector position (3), quaternion (4), gripper joints (2) and the gripper-open flag (1) | upstream_code | roboverse/envs/widow250.py:277-297 |
| The image observation is the rendered image flattened and divided by 255 into float32 values | upstream_code | roboverse/envs/widow250.py:284-286 |
| `observation_img_dim` defaults to 48 | upstream_code | roboverse/envs/widow250.py:35 |
| The `observation_space` declares an image whose length is `observation_img_dim ** 2 * 3` and a 10-entry state bounded by +/-100 | upstream_code | roboverse/envs/widow250.py:337-347 |
| `reset()` resets the simulation, loads the meshes, resets the robot joints and returns `get_observation()` | upstream_code | roboverse/envs/widow250.py:182-192 |
| `step` returns `(observation, reward, done, info)` and `done` is always `False`, so the environment never terminates on its own | upstream_code | roboverse/envs/widow250.py:272-275 |
| The reward for `reward_type` `grasping` is the target object's grasp-success flag as a float | upstream_code | roboverse/envs/widow250.py:299-304 |
| The physics step is 1/240 s with 150 solver iterations and gravity -10 | upstream_code | roboverse/bullet/core.py:30-35 |
| `connect_headless` calls `p.connect(p.DIRECT)` when `gui` is false | upstream_code | roboverse/bullet/core.py:5-11 |
| `Widow250Env` connects to PyBullet in its constructor through `bullet.connect_headless(self.gui)` | upstream_code | roboverse/envs/widow250.py:102 |
| The WidowX 250 URDF `wx250s.urdf` is loaded at base position [0.6, 0, -0.4] | upstream_code | roboverse/envs/objects.py:34-41 |

Limits: The checked fake keeps eight normalized action values in -1..1. The Gymnasium bridge derives these unchanged action bounds with source `upstream_code` and ref `roboverse/envs/widow250.py:332-335`, where the same-span ones assignment and Box construction state the bounds. The selected environment and width were source-reviewed separately; symbolic shapes alone do not prove a width. `ticks` remains the SDK bridge budget (1 to max_ticks, 10000 by default), not a device limit. This simulated R0 package declares no operator-required hardware limit.

## Fidelity contract

`driver.py` (`fidelity = {...}`) describes the model as deployed in the checked package, the kinematic fake: engine
`pybullet:Widow250Grasp-v0 (roboverse)`, level F0 (no rigid-body dynamics or contacts), determinism `seeded` with
`seed_control` `parameter`, one tick = 41.6667 ms (10 PyBullet steps of 1/240 s, `roboverse/bullet/core.py:30-35`;
a discrete gripper toggle advances 75 steps, `roboverse/envs/widow250.py:46-48`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: no dynamics, contacts, inverse
kinematics, PyBullet, camera or tray; the observation image is reduced from the real 48x48x3 values (6912,
`roboverse/envs/widow250.py:339-341`) to 12 test values; and the fake was not compared with the upstream environment.

## Safety

Simulated R0 device: there is no hardware backend and no physical effect. The e-stop is the runtime's software latch;
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

## Tags

roboverse, widow250, widowx-250, pybullet, gym, reinforcement-learning, simulation
