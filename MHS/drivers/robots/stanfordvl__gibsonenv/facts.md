# Facts and tags for gh.stanfordvl/gibsonenv

Every fact cites its source at commit `f474d9efd5b5ef703e3bf630a6f7448b54875d0c`; the same facts are written into
`driver.py` (`facts = [...]`) and the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Gibson is a virtual environment simulator for embodied agents, not a hardware device | vendor_doc | README.md:3 |
| Gibson simulates the agent with the Bullet physics engine | vendor_doc | README.md:11 |
| AntNavigateEnv is a CameraRobotEnv subclass whose constructor takes a configuration path and a GPU index | upstream_code | gibson/envs/ant_env.py:26-34 |
| The documented interface is env.step(action) returning (obs, rew, env_done, info) and env.reset(); obs is a dictionary keyed by the configured output components | vendor_doc | README.md:407-414 |
| The play_ant_nonviz configuration sets is_discrete: true and output: [nonviz_sensor] | upstream_code | examples/configs/play/play_ant_nonviz.yaml:8-24 |
| The play_ant_nonviz configuration sets the simulation timestep to 0.01 s with frameskip 1 | upstream_code | examples/configs/play/play_ant_nonviz.yaml:27-29 |
| With is_discrete true the Ant action space is gym.spaces.Discrete(17) | upstream_code | gibson/core/physics/robot_locomotors.py:266-267 |
| The 17 discrete Ant actions are 8 positive joint torques, 8 negative joint torques and one all-zero action | upstream_code | gibson/core/physics/robot_locomotors.py:270-286 |
| The Ant proprioceptive sensor has 28 values | upstream_code | gibson/core/physics/robot_locomotors.py:259-260 |
| calc_state concatenates eight body features, the joint state and the feet contacts and clips every element to [-5, 5] | upstream_code | gibson/core/physics/robot_locomotors.py:191-204 |
| AntNavigateEnv terminates the episode when nframe > 300 | upstream_code | gibson/envs/ant_env.py:89 |
| BaseRobotEnv._step increments nframe before applying the action and checking termination | upstream_code | gibson/envs/env_modalities.py:182-189 |
| The AntNavigateEnv reward is the change in the robot potential between steps | upstream_code | gibson/envs/ant_env.py:42-82 |
| The potential is -walk_target_dist / scene.dt | upstream_code | gibson/core/physics/robot_locomotors.py:206-213 |
| walk_target_dist is the planar distance from the body to the target | upstream_code | gibson/core/physics/robot_locomotors.py:157-160 |
| A reset restores the configured initial position and orientation and then calls robot_specific_reset | upstream_code | gibson/core/physics/robot_bases.py:122-131 |
| On reset the ant joint angles are drawn uniformly from (-0.1, 0.1) through np_random | upstream_code | gibson/core/physics/robot_locomotors.py:64-66 |
| BaseEnv seeds np_random through gym.utils.seeding.np_random | upstream_code | gibson/envs/env_bases.py:90-92 |
| The environment uses an in-process PyBullet connection: p.connect(p.DIRECT) headless or p.GUI with a display | upstream_code | gibson/envs/env_bases.py:44-51 |
| The gym ids registered in gibson/__init__.py point at realenv.envs.* entry points | upstream_code | gibson/__init__.py:14-34 |
| The scene advances one physics step with frame_skip per environment step | upstream_code | gibson/core/physics/scene_abstract.py:47-52 |

Limits: the driver declares none. The action bound (`action.index` 0 to 16) is derived by the Gymnasium bridge from
the fake's `Discrete(17)` space, whose source is `upstream_code` (`robot_locomotors.py:266-267`), and `ticks` is
bounded 1 to 10000 by the `cap.world.step.v1` class. The device is simulated (R0), so there is no operator-required
bound and no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet`, level F1 (rigid-body simulation with contacts,
README.md:11), determinism `seeded` with `seed_control` `parameter` (the reset takes a seed; the joint draw at
`robot_locomotors.py:64-66` uses the seeded `np_random` of `env_bases.py:90-92`), timestep 10 ms (0.01 s with frameskip
1, `examples/configs/play/play_ant_nonviz.yaml:27-29`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say that the fake has no PyBullet contacts, actuator or sensor model, no camera
modalities and no upstream comparison, and that the sim backend was not run.

Safety: simulated R0 environment. The e-stop is the runtime's software latch (there is no native stop in the clone);
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays
readable. No hardware is attached and no physical safety limit is claimed.

Tags: gibson, ant, navigation, pybullet, reinforcement-learning, simulation, gymnasium
