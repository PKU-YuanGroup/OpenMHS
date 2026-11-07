# Facts and tags for gh.clvrai/furniture

Every fact cites its source at commit `ed4a905e7beb1daf3af7717d979e0ba93421077a`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FurnitureGym builds the concrete environment with make_env(name, config) and copies its observation_space and action_space | upstream_code | furniture/env/furniture_gym.py:16-33 |
| FurnitureGym.reset returns the wrapped observation only; step returns the wrapped (observation, reward, done, info) tuple | upstream_code | furniture/env/furniture_gym.py:52-65 |
| IKEASawyer-v0 is registered with entry_point furniture.env.furniture_gym:FurnitureGym and kwargs id IKEASawyer-v0, name FurnitureSawyerEnv, furniture_name swivel_chair_0700, background Industrial and port 1050 | upstream_code | furniture/env/__init__.py:32-43 |
| The action space is a Dict with one member default, a Box of shape (dof,) bounded by low -1 and high 1 per element | upstream_code | furniture/env/furniture.py:294-310 |
| For control_type ik the Sawyer dof is 3 + 3 + 1 + 1 for move, rotate, select and connect | upstream_code | furniture/env/furniture_sawyer.py:60-64 |
| object_ob is a Box of shape (3 + 4) * n_objects: position 3 and quaternion 4 per object | upstream_code | furniture/env/furniture.py:230-237 |
| The Sawyer ik observation space adds a robot_ob Box of shape 3 + 4 + 3 + 3 + 2 for pos, quat, velp, velr and gripper | upstream_code | furniture/env/furniture_sawyer.py:44-48 |
| object_ob, object_ob_all and robot_ob default to True | upstream_code | furniture/config/furniture.py:230-246 |
| swivel_chair_0700 declares three bodies: 1_chair_base, 2_chair_column and 3_chair_seat | upstream_code | furniture/env/models/assets/objects/swivel_chair_0700.xml:19-47 |
| The furniture part count is len(self.mujoco_objects), the children of the loaded furniture XML | upstream_code | furniture/env/furniture.py:2001-2002 |
| _get_obs concatenates each object's position and quaternion into object_ob | upstream_code | furniture/env/furniture.py:1362-1379 |
| The Sawyer _get_obs builds robot_ob from gripper_qpos, eef_pos, eef_quat, eef_velp and eef_velr for a non-qpos observation | upstream_code | furniture/env/furniture_sawyer.py:103-153 |
| max_episode_steps defaults to 2000 | upstream_code | furniture/config/furniture.py:164-168 |
| _after_step marks the episode terminal when the episode length reaches max_episode_steps or the episode failed; _step also marks success when all required parts are connected | upstream_code | furniture/env/furniture.py:440-480 |
| The reward is success_reward + touch_reward + pick_reward + ctrl_penalty, and ctrl_penalty is -ctrl_penalty_coef times the sum of the squared actions | upstream_code | furniture/env/furniture.py:524-550 |
| ctrl_penalty_coef defaults to 1e-3 | upstream_code | furniture/config/furniture.py:290-295 |
| control_freq defaults to 10 | upstream_code | furniture/config/furniture.py:72 |
| _do_simulation takes _model_timestep from sim.model.opt.timestep and _control_timestep from 1.0 / control_freq, then runs int(control_timestep / model_timestep) physics steps per environment step | upstream_code | furniture/env/furniture.py:2849-2881 |
| The environment seeds its numpy RandomState with config.seed at construction, and reset draws the furniture placement randomness from it | upstream_code | furniture/env/furniture.py:72 |
| config.seed defaults to 123 | upstream_code | furniture/config/furniture.py:324 |
| When config.unity is set the environment creates a UnityInterface for rendering | upstream_code | furniture/env/furniture.py:174-182 |
| The prerequisites are Python 3.7, MuJoCo 2.0 and Unity 2018.4.23f1 | vendor_doc | docs/installation.md:3-7 |
| setup.py install_requires lists gym, mujoco-py, numpy, scipy and the other upstream dependencies | upstream_code | setup.py:11-31 |

Limits: the driver declares none. The only bound is the environment's action space, which the bridge derives from
the live fake environment (`Dict.default`: eight elements from -1 to 1, source `upstream_code`, ref
`furniture/env/furniture.py:298-310`), plus the bridge's own `ticks` bound (1 to `max_ticks`, 10000 by default) and
the non-negative `seed` of the reset and seed classes. The device is simulated (R0), so no limit is
`operator_required`; there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:IKEASawyer-v0`, level F0 (the package's kinematic
fake, not MuJoCo), determinism `seeded` with `seed_control` `none` because `FurnitureGym.reset` takes no seed and the
clone seeds its numpy RandomState only at construction (`furniture.py:72`, default 123 at
`config/furniture.py:324`), timestep 100 ms (one environment step is one control period, 1 / control_freq with
`control_freq` 10 at `config/furniture.py:72` and `furniture.py:2855`; the MuJoCo physics timestep is not stated in
the clone and `base.xml:4` sets only `impratio` and `cone`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware was attached
and no hardware run is claimed.

Tags: ikea, furniture-assembly, sawyer, gym, mujoco, manipulation, reinforcement-learning, simulation
