# Facts and tags for gh.robo-eval/roboeval (LiftPotPosition)

Every fact cites the clone at commit `7199e5c4851bbf8eaf185d486735cbcb233f608a`; the same facts are written in
`driver.py` (`facts = [...]`) and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| `reset` takes keyword-only `seed` and `options` and returns `(observation, info)` | upstream_code | roboeval/roboeval_env.py:560-577 |
| `step` takes an optional action vector and `fast` flag and returns `(observation, reward, terminated, truncated, info)` | upstream_code | roboeval/roboeval_env.py:603-616 |
| the physics timestep `PHYSICS_DT` is 0.002 s | upstream_code | roboeval/roboeval_env.py:36 |
| the control frequency must be between 20 and 500 Hz | upstream_code | roboeval/roboeval_env.py:33-34 |
| one control step is `round(500/control_frequency)` physics steps | upstream_code | roboeval/roboeval_env.py:112-113 |
| the Mojo physics wrapper is created with `timestep=PHYSICS_DT` | upstream_code | roboeval/roboeval_env.py:141 |
| a reset calls `np.random.seed` with the current episode seed | upstream_code | roboeval/roboeval_env.py:558 |
| `get_observation` returns the enabled observation components: proprioception by default | upstream_code | roboeval/roboeval_env.py:449-462 |
| the default `ObservationConfig` enables proprioception and no cameras | upstream_code | roboeval/utils/observation_config.py:53-54 |
| proprioception concatenates robot `qpos` and `qvel` and adds gripper and floating-base fields | upstream_code | roboeval/roboeval_env.py:490-504 |
| `get_info` adds `task_success` as a float of the current success flag | upstream_code | roboeval/roboeval_env.py:480-482 |
| `LiftPotPosition` clears and samples the `workspace` spawn boundary with `min_distance=0.1` on reset | upstream_code | roboeval/envs/lift_pot.py:125-132 |
| `INITIAL_HEIGHT` is 0.996 m and `SUCCESS_HEIGHT` is 0.1 m above it | upstream_code | roboeval/envs/lift_pot.py:14-16 |
| the success rotation tolerance `SUCCESS_ROT` is 20 degrees | upstream_code | roboeval/envs/lift_pot.py:15 |
| the base `LiftPot` reset places the pot at x=0.7, y=0.0 and z=`INITIAL_HEIGHT` | upstream_code | roboeval/envs/lift_pot.py:45 |
| `close` closes the environment's renderers | upstream_code | roboeval/roboeval_env.py:719-721 |

## Limits

The driver declares no limit of its own. The only numeric bounds on its inputs come from the catalogue classes:

- `cap.world.step.v1` bounds `ticks` to 1..10000 (catalogue class; the runtime enforces it, not the driver);
- `cap.world.reset.v1` bounds `seed` to a non-negative integer (catalogue class);
- the action vector has no statically known shape or bound: it is the environment's action space, built from the
  `ActionMode` and robot configuration supplied to `RoboEvalEnv.__init__` (roboeval/roboeval_env.py:73-113 and
  roboeval/action_modes.py:236-260). Those are constructor options, so no catalogue `Limit` is declared for them.

The device is simulated R0, so no limit is `operator_required` and there is no `site-limits.example.json`.

## Fidelity

The driver publishes F0: the upstream environment is a MuJoCo rigid-body simulation, but the backend this package
can run is the package's kinematic fake (MuJoCo is not installed, the upstream package is never installed, and the
clone is never imported). The gaps in `driver.py` state that no dynamics, contacts, actuators, sensors or noise are
modelled by the fake, that the observation is a placeholder, and that the control period
(`round(500/control_frequency)` physics steps) is a constructor option.

## Safety

Simulated R0 device. There is no hardware backend and no native stop; an e-stop is the runtime's software latch,
after which no step or reset is accepted until `mhs.safety.reset` clears it, and the observation stays readable.

Tags: roboeval, mujoco, manipulation, lift-pot, simulation, bimanual
