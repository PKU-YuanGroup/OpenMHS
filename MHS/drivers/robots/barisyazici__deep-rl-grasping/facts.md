# Facts and tags for gh.barisyazici/deep-rl-grasping

Every fact cites its source at commit `fd2214e42a77e80fa986f04e27e043e0133b4d51`: `upstream_code` is code or a
comment of the clone (`path/in/clone.py:LINE`). The clone's README.md is a usage guide and states no numeric device
bound, so every fact below is `upstream_code`. Copy each fact into `facts = [Fact(text, source=..., ref=...)]` in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered as gripper-env-v0 with entry point manipulation_main.gripperEnv.robot:RobotEnv | upstream_code | manipulation_main/__init__.py:3-6 |
| RobotEnv requires a config argument; a path is loaded as YAML before World is constructed | upstream_code | manipulation_main/gripperEnv/robot.py:46-50 |
| The continuous, non-simplified action space is Box(-1, 1, shape=(5,)) | upstream_code | manipulation_main/gripperEnv/actuator.py:71-73 |
| The five action components are translation xyz, yaw rotation and the gripper open/close signal | upstream_code | manipulation_main/gripperEnv/actuator.py:101-105 |
| The full action clips the translation norm to max_translation and the yaw to max_yaw_rotation, both taken from the config | upstream_code | manipulation_main/gripperEnv/actuator.py:91-98 |
| A positive fifth action value opens the gripper when it is closed, a negative one closes it when it is open, and otherwise the robot moves | upstream_code | manipulation_main/gripperEnv/actuator.py:116-124 |
| In non-simplified depth mode _observe stacks the depth image with a zero pad whose [0][0] carries the actuator state | upstream_code | manipulation_main/gripperEnv/robot.py:199-205 |
| The non-simplified depth observation space is Box(0, 255, shape=(height, width, 2)) | upstream_code | manipulation_main/gripperEnv/robot.py:226-228 |
| The upstream tests expect Box(-1, 1, shape=(5,)) for the continuous case and a (64, 64, 2) observation for the non-simplified depth case | upstream_code | tests_gripper/test_sim.py:30-40 |
| step returns (obs, reward, done, info) and reports done when episode_step equals time_horizon - 1 | upstream_code | manipulation_main/gripperEnv/robot.py:152-171 |
| World advances the physics by 1/240 s in every step_sim call | upstream_code | manipulation_main/simulation/simulation.py:37 |
| World.seed seeds the random generator with gym.utils.seeding.np_random and evaluate mode fixes RandomState(1) | upstream_code | manipulation_main/simulation/simulation.py:91-100 |
| RobotEnv.reset() takes no arguments | upstream_code | manipulation_main/gripperEnv/robot.py:115 |
| World.close disconnects the physics client | upstream_code | manipulation_main/simulation/simulation.py:88-89 |
| The gripper width is measured from 0.05 per finger, so a fully open gripper is 0.1 wide | upstream_code | manipulation_main/gripperEnv/robot.py:288-293 |
| The upstream dependencies include gym 0.19.0, pybullet 3.2.5, tensorflow 1.14.0 and numpy 1.18 | upstream_code | setup.py:6-24 |

Limits: the driver declares no device Limit. The only bounds are derived by the Gymnasium bridge from the fake's
action space: `action.values` is each of the five values -1 to 1 (the upstream `Box(-1, 1, shape=(5,))`,
`actuator.py:72-73`), and `ticks` is 1 to the bridge's `max_ticks` (10000). Neither is an operator-required bound, and
the simulated device has no hardware write. The values of `max_translation`, `max_yaw_rotation`, `time_horizon` and
`num_actions_pad` are constructor/config values of the upstream environment, not device limits, so none is declared as
a Limit.

Fidelity contract (`driver.py`, `fidelity`): engine `analytic`, level F0 (kinematic stand-in, no dynamics), determinism
`seeded` with `seed_control` `parameter`, timestep 1/240 s = 4.1667 ms (`simulation.py:37`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore, with gaps for the absent pybullet scene, camera, encoder,
reward, scene reset and wall-clock pacing. The fake returns an 8 x 8 x 2 observation stand-in; the real space is
64 x 64 x 2 (`tests_gripper/test_sim.py:39-40`). The upstream package was never installed or imported, and the fake was
never compared with it.

Safety: simulated R0 device. There is no hardware backend and no hardware e-stop path. The runtime's software latch
stops the simulation: after an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
state stays readable. OpenMHS is not a safety certification and not a safety-rated channel.

Tags: grasping, robot, reinforcement-learning, simulation, gym, pybullet
