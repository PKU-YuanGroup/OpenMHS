# Facts and tags for gh.farama-foundation/metaworld

Every fact cites its source at commit `c0dafaf1557f31cad3b96ba2b62462f45638f5a5`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

This package implements one of the card's five entry symbols: `assembly-v3`
(`metaworld.envs.sawyer_assembly_peg_v3:SawyerNutAssemblyEnvV3`). The other four confirmed symbols
(`SawyerBasketballEnvV3`, `SawyerBinPickingEnvV3`, `SawyerBoxCloseEnvV3`,
`SawyerButtonPressTopdownEnvV3`) are separate tasks of the same family and are not implemented by this package
(PLAYBOOK.md section 8, one device class per package). The same driver shape can serve any of them by changing
`env_id`/`env_kwargs` and the fake.

| fact | source | ref |
|---|---|---|
| The action space is a 4-element Box with each element from -1 to +1 | upstream_code | metaworld/sawyer_xyz_env.py:239-243 |
| step() requires a 4-element action, applies its first three elements through set_xyz_action and the last element through do_simulation | upstream_code | metaworld/sawyer_xyz_env.py:580-596 |
| set_xyz_action clips every axis to [-1, 1] and multiplies it by action_scale before moving the mocap body | upstream_code | metaworld/sawyer_xyz_env.py:320-336 |
| action_scale is 1.0 / 100 by default | upstream_code | metaworld/sawyer_xyz_env.py:175-183 |
| The observation is one flat 39-element array that concatenates the current state, the previous state and the goal position | upstream_code | metaworld/sawyer_xyz_env.py:513-527 |
| The 18-element current state is the hand position (3), the gripper distance clipped to 0..1 and 14 padded object values | upstream_code | metaworld/sawyer_xyz_env.py:475-511 |
| step() returns (observation, reward, terminated, truncated, info), terminated is always False and truncated becomes True at curr_path_length == max_path_length | upstream_code | metaworld/sawyer_xyz_env.py:631-642 |
| max_path_length is 500 steps by default | upstream_code | metaworld/sawyer_xyz_env.py:153-154 |
| frame_skip is 5 by default | upstream_code | metaworld/sawyer_xyz_env.py:175-183 |
| step() advances self.frame_skip MuJoCo frames per environment step | upstream_code | metaworld/sawyer_xyz_env.py:591-596 |
| The MuJoCo scene physics timestep is 0.0025 s | upstream_code | metaworld/assets/scene/basic_scene.xml:2 |
| SawyerXYZEnv.reset(seed, options) ignores both arguments and resets curr_path_length to 0 | upstream_code | metaworld/sawyer_xyz_env.py:664-682 |
| seed(seed) seeds np_random and the action, observation and goal spaces | upstream_code | metaworld/sawyer_xyz_env.py:275-290 |
| Meta-World/goal_observable is registered with an entry_point that selects the observable-goal class for env_name and passes seed=seed | upstream_code | metaworld/__init__.py:696-706 |
| assembly-v3 maps to SawyerNutAssemblyEnvV3 | upstream_code | metaworld/env_dict.py:26-27 |
| The goal_observable constructor seeds numpy before construction and calls env.seed(seed) after the first reset when a seed is given | upstream_code | metaworld/env_dict.py:184-199 |
| reward_function_version is v2 by default | upstream_code | metaworld/envs/sawyer_assembly_peg_v3.py:19-24 |
| A successful assembly scores a reward of 10.0 | upstream_code | metaworld/envs/sawyer_assembly_peg_v3.py:196-228 |

Limits: the driver declares none. The only input bound is the action space, which the bridge derives from the
environment (`Box([-1,-1,-1,-1], [1,1,1,1])`: `action.values` from -1 to +1 per element, with the source
`upstream_code` and the ref `metaworld/sawyer_xyz_env.py:239-243`). `ticks` is bounded by the catalogue class and
`max_ticks` (1 to 10000 by default). The device is simulated (R0), so no limit is `operator_required`; there is
nothing for an operator overlay to fill and no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:metaworld/SawyerNutAssemblyEnvV3`, level F1
(rigid-body MuJoCo scene, no validated actuator, sensor or noise model), determinism `seeded` with `seed_control`
`none` because the environment is seeded at construction and `SawyerXYZEnv.reset` ignores its seed argument,
timestep 2.5 ms (the scene physics timestep, `basic_scene.xml:2`) with a 12.5 ms control period (`frame_skip=5`,
`sawyer_xyz_env.py:591-596`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
say what is not modelled and that this package's fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. The package declares no
hardware backend and no physical stop path.

Tags: metaworld, assembly-v3, sawyer, robotics, reinforcement-learning, simulation, gymnasium
