# Facts and tags for gh.mees/calvin_env

Every fact cites its source at commit `797142c588c21e76717268b7b430958dbd13bf48`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PlayTableSimEnv is a gym.Env subclass | upstream_code | calvin_env/envs/play_table_env.py:27 |
| The constructor takes bullet_time_step and control_freq (default 30) and sets action_repeat to int(bullet_time_step // control_freq) | upstream_code | calvin_env/envs/play_table_env.py:28-53 |
| The play_table_env configuration sets bullet_time_step 240.0 and control_freq 30 | upstream_code | conf/env/play_table_env.yaml:5-12 |
| initialize_bullet sets the physics timestep to 1.0 / bullet_time_step | upstream_code | calvin_env/envs/play_table_env.py:126 |
| reset(scene_obs, robot_obs) resets the scene and robot, advances one physics step and returns get_obs() | upstream_code | calvin_env/envs/play_table_env.py:170-174 |
| seed(seed) sets np_random with gym.utils.seeding.np_random and returns [seed] | upstream_code | calvin_env/envs/play_table_env.py:176-179 |
| step(action) applies robot.apply_action(action), advances physics action_repeat times, steps the scene and returns obs, 0, False, info | upstream_code | calvin_env/envs/play_table_env.py:222-243 |
| get_camera_obs renders every camera to an rgb and a depth array | upstream_code | calvin_env/envs/play_table_env.py:181-189 |
| get_obs returns the camera observations and the robot and scene state observations | upstream_code | calvin_env/envs/play_table_env.py:191-196 |
| get_state_obs returns robot_obs from Robot.get_observation() and scene_obs from PlayTableScene.get_obs() | upstream_code | calvin_env/envs/play_table_env.py:198-213 |
| get_info returns robot_info and, when use_scene_info is set, scene_info | upstream_code | calvin_env/envs/play_table_env.py:215-220 |
| Robot.get_observation returns the tcp position, the tcp orientation, the gripper opening width, the seven arm joint states and the gripper action | upstream_code | calvin_env/robot/robot.py:181-212 |
| Robot.apply_action accepts the dict types joint_rel, joint_abs, cartesian_rel and cartesian_abs, plus a raw relative action array | upstream_code | calvin_env/robot/robot.py:245-291 |
| The relative action scales default to max_rel_pos 0.02 and max_rel_orn 0.05 | upstream_code | calvin_env/robot/robot.py:33-34 |
| relative_to_absolute multiplies the relative position by max_rel_pos and the relative orientation by max_rel_orn | upstream_code | calvin_env/robot/robot.py:228-237 |
| The gripper action must be -1 or 1 | upstream_code | calvin_env/robot/robot.py:293-295 |
| The configured gripper joint limits are 0 to 0.04 | upstream_code | conf/robot/panda.yaml:12 |
| The panda configuration sets euler_obs true, so the tcp orientation is three Euler angles | upstream_code | conf/robot/panda.yaml:22 |
| The static camera is configured at 200 by 200 pixels | upstream_code | conf/cameras/cameras/static.yaml:7-8 |
| The gripper camera is configured at 84 by 84 pixels | upstream_code | conf/cameras/cameras/gripper.yaml:7-8 |
| The tactile camera is configured at 120 by 160 pixels | upstream_code | conf/cameras/cameras/tactile.yaml:3-4 |
| PlayTableScene.get_obs concatenates door, button, switch, light and movable-object states | upstream_code | calvin_env/scene/play_table_scene.py:152-160 |
| get_env loads the dataset's merged Hydra configuration and instantiates the environment | upstream_code | calvin_env/envs/play_table_env.py:267-286 |

Limits: the driver declares none. `cap.world.step.v1` derives `ticks` (1 to 10000) and the open `action` object from the
bridge, and `cap.world.seed.v1` derives a non-negative seed; the environment itself defines no action space or
observation space. The device is simulated (R0), so no limit is `operator_required`.

Reset: the upstream `reset(scene_obs, robot_obs)` takes initial observations, not a seed or options. The bridge's
legacy path can apply a seed through `seed()`; the package advertises only that reset input and refuses anything else
rather than dropping it. The initial scene and robot observations are therefore not exposed by this driver.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:PlayTableSimEnv`, level F1, determinism `seeded`
with seed control `parameter`, timestep 33.33 ms (one control step: 8 physics ticks of 1/240 s from
`conf/env/play_table_env.yaml:5-12`, `play_table_env.py:53` and `:126`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, that the camera arrays are 4x4 placeholders while the
configured cameras are 200x200 and 84x84 (`conf/cameras/cameras/static.yaml:7-8`, `gripper.yaml:7-8`), and that the fake
was never compared with a pybullet run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: calvin, simulation, pybullet, gym, manipulation, reinforcement-learning, world
