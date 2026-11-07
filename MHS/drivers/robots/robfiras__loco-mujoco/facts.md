# Facts and tags for gh.robfiras/loco-mujoco

Every fact cites its source at commit `3921fedbca93876c0595c90c535b24ec08ff623d`.  All sources here are
`upstream_code`; no vendor document in the clone states a bound.  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The gymnasium environment `LocoMujoco` is registered with entry point `loco_mujoco.core.wrappers.gymnasium:GymnasiumWrapper` | upstream_code | loco_mujoco/environments/humanoids/__init__.py:58-60 |
| `GymnasiumWrapper`'s constructor takes `env_name` and builds the wrapped environment with `RLFactory.make(env_name, **kwargs)` | upstream_code | loco_mujoco/core/wrappers/gymnasium.py:19-46 |
| `GymnasiumWrapper.step` calls the wrapped environment and returns its five values unchanged: observation, reward, absorbing, done, info | upstream_code | loco_mujoco/core/wrappers/gymnasium.py:55-73 |
| `GymnasiumWrapper.reset` seeds numpy and jax from the seed when one is given and returns `(observation, {})` | upstream_code | loco_mujoco/core/wrappers/gymnasium.py:75-94 |
| `render_fps` is `1.0 /` the wrapped environment's `dt` | upstream_code | loco_mujoco/core/wrappers/gymnasium.py:48 |
| `GymnasiumWrapper.close` stops the wrapped environment | upstream_code | loco_mujoco/core/wrappers/gymnasium.py:107-112 |
| `LocoEnv`'s constructor defaults are `n_substeps=10` and `timestep=0.001` | upstream_code | loco_mujoco/environments/base.py:51-52 |
| `simulation_dt` is the MuJoCo model's `opt.timestep` | upstream_code | loco_mujoco/core/mujoco_base.py:1297-1304 |
| The effective `dt` is `simulation_dt * n_intermediate_steps * n_substeps` | upstream_code | loco_mujoco/core/mujoco_base.py:1307-1314 |
| The inner environment starts with `n_intermediate_steps` set to 1 | upstream_code | loco_mujoco/core/mujoco_base.py:125 |
| The base control function does not run at the simulation frequency | upstream_code | loco_mujoco/core/control_functions/base.py:96-100 |
| The inner environment advances the MuJoCo model with `mujoco.mj_step` for `n_substeps` | upstream_code | loco_mujoco/core/mujoco_base.py:260-262 |
| `PDControl` normalizes the agent's action space to `[-1, 1]` | upstream_code | loco_mujoco/core/control_functions/pd.py:31-32 |
| `Atlas`'s default action specification is the actuator list from `back_bkz_actuator` through `l_leg_akx_actuator` | upstream_code | loco_mujoco/environments/humanoids/atlas.py:387-394 |
| `RLFactory.make` defaults `goal_type` to `GoalRandomRootVelocity` | upstream_code | loco_mujoco/task_factories/rl_factory.py:15-20 |
| The goal is appended to the observation specification | upstream_code | loco_mujoco/core/mujoco_base.py:138 |
| `GoalRandomRootVelocity` has goal dimension 3 | upstream_code | loco_mujoco/core/observations/goals.py:427-429 |

## Limits

The driver declares no `Limit` of its own.  The only bound is the action space, which the bridge derives from the
environment at run time (`-1..1` per actuator, 27 values for `Atlas`); its source is the environment's own
`action_space`, and the driver never widens or clamps it.  The simulated device is R0, so no limit is
`operator_required` and there is no `site-limits.example.json`.

## Configuration and fidelity

The driver binds `env_id="LocoMujoco"` with `env_kwargs = {"env_name": "Atlas", "timestep": 0.001,
"n_substeps": 10}`.  `Atlas` is registered in `humanoids/__init__.py:26`; the two physics numbers are `LocoEnv`'s
constructor defaults (`environments/base.py:51-52`), pinned explicitly so the contract is not left to a default.
With the default PD controller (`run_with_simulation_frequency` is false,
`core/control_functions/base.py:96-100`) and `n_intermediate_steps=1` (`core/mujoco_base.py:125`), the control step
is `0.001 s * 1 * 10 = 0.01 s`, i.e. 10 ms (`core/mujoco_base.py:1307-1314`).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:loco-mujoco:LocoMujoco`, level F1 (rigid-body
dynamics with contacts; the upstream inner environment runs MuJoCo), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.  The gaps
disclose that the upstream sim path was not run, that the fake has no dynamics, that its 68 observation values and 27
action values are placeholders, that the two use different random generators, and that the 10 ms step depends on the
pinned configuration.

## Safety

Simulated R0 device.  There is no hardware backend and no physical stop path.  The e-stop is the runtime's software
latch (no native stop exists for a family simulator); after it no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the last state stays readable.  The device is served as mode `simulated`,
with a fake view at `<device id>/fake` and evidence `contract_checked`.

## Tags and identity

Device id `loco-mujoco`, kind `world.sim` (from the family driver), vendor `robfiras`, model `LocoMujoco/Atlas`.
Tags: loco-mujoco, humanoid, mujoco, reinforcement-learning, simulation, gymnasium.
