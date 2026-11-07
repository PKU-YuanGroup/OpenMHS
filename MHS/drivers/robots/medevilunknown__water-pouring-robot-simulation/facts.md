# Facts and tags for gh.medevilunknown/water-pouring-robot-simulation

Every fact cites its source at commit `ff33ae12ae58ef9569ff40d75c88635a14c61d27`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The entry class So101PourEnv is a subclass of gym.Env | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:7 |
| So101PourEnv loads a MuJoCo model from the xml_path argument, whose default is scene.xml, and creates MjData from that model | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:13-16 |
| The action space is a continuous Box of six values from -1 to 1: five arm joint targets and one absolute gripper command | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:18-19 |
| The observation space is a Box of eighteen unbounded values: five arm joint positions, five arm joint velocities, one gripper width, three bottle coordinates, three beaker coordinates and one beaker volume | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:21-23 |
| The constructor initializes beaker_ml to 0.0, target_ml to 100.0, max_steps to 500 and current_step to 0 | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:29-32 |
| reset(seed, options) calls gym.Env.reset(seed), restores the MuJoCo data with mj_resetData, zeroes beaker_ml and current_step and returns _get_obs() with an empty info dict | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:34-39 |
| step increments current_step, adds action[:5]*0.05 to ctrl[:5], sets ctrl[5] to action[5] and advances MuJoCo with mj_step | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:41-50 |
| Water flow starts only when the bottle tilt is above 30 degrees and is 25.0 * min(1, (tilt-30)/60) times the model timestep, added to beaker_ml | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:52-56 |
| The episode terminates when beaker_ml reaches 150 or current_step reaches max_steps; truncated is always False | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:60-61 |
| The observation concatenates qpos[:5], qvel[:5], the gripper joint position, the bottle site position, the beaker site position and beaker_ml into a float32 array | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:65-71 |
| The reward is minus the distance between the gripperframe and bottle_grasp sites, plus 10*(1-|beaker_ml-target_ml|/target_ml) while beaker_ml is positive, minus 50 while beaker_ml exceeds 110 | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:73-86 |
| The bottle tilt is the angle between the water_bottle body's z axis and the world z axis, in degrees, computed from the body quaternion | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:88-94 |
| The scene model includes so101_new_calib.xml | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/scene.xml:2 |
| The scene model sets the MuJoCo timestep to 0.002 s with the implicitfast integrator | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/scene.xml:5 |
| The imported model defines six position actuators (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper) with per-actuator ctrlrange bounds | upstream_code | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/so101_new_calib.xml:179-186 |
| The README calls So101PourEnv a standard Gymnasium environment for training low-level control policies | vendor_doc | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/README.md:10 |
| The README says the control layer implements a standard Gymnasium API | vendor_doc | workshop/dev/docker/workspace/src/so101_mujoco/mujoco/README.md:24-25 |

Limits: the driver declares none of its own. The only bound is the environment's action space, which the Gymnasium
bridge derives from the fake's duck-typed `Box` (`action.values` from -1 to 1 per element). The device is simulated
(R0), so no limit is `operator_required` and no site overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): the deployed fake is kinematic (F0), engine
`custom:So101PourEnv kinematic fake (upstream mujoco scene.xml not integrated)`, determinism `seeded` with
`seed_control` `none` because `reset()` restores the MuJoCo model defaults and draws no random initial state, timestep
2 ms from `scene.xml:5`, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or restore. The gaps say what
the fake does not model (MuJoCo rigid bodies, contacts, friction, gravity, actuators, free bodies, rendering) and that it
was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Deviation from the card: the card says `family: mujoco`, `helper: MujocoDriver`, but the entry class is a Gymnasium
environment (`pour_env.py:7`) whose `reset()`/`step()` own the MuJoCo model; a `MujocoDriver` would expose raw
`data.ctrl` and `qpos`/`qvel` instead of the environment action space. This package uses `GymnasiumDriver` (decision
`family-config` unchanged).

Tags: so101, robot-arm, pouring, manipulation, mujoco, gymnasium, reinforcement-learning, simulation
