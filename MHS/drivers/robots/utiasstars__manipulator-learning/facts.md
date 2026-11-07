# Facts and tags for gh.utiasstars/manipulator-learning

Every fact cites `upstream_code` at commit `d887bdcfc92d2238532e6b5a27491f1aeaca47b4`, a path from the clone root.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The README loads environments with `getattr(manipulator_learning.sim.envs, name)`; its example instantiates `PandaPlayInsertTrayXYZState`, calls `reset()` and unpacks the four-value `step()` result | upstream_code | `README.md:67-74` |
| Environment generation compatible with `gym.make` is an unchecked roadmap item, so the class has no registered Gymnasium id | upstream_code | `README.md:172` |
| `PandaPlayInsertTrayXYZState` documents a 59-value observation space and a 4-value action space | upstream_code | `manipulator_learning/sim/envs/panda_play.py:419` |
| The observation layout is pos 0:3, vel 3:6, grip_pos 6:8, prev_grip_pos 8:12, obj_pos 12:26, obj_vel 26:38, obj_rel_pos 38:53 and force_torque 53:59 | upstream_code | `manipulator_learning/sim/envs/panda_play.py:420-428` |
| The class defaults are `max_real_time` 18 s, `n_substeps` 5, `action_multiplier` 0.002 and the insert task, with `state_data` pos, vel, grip_pos, prev_grip_pos, obj_pos, obj_rot, obj_vel, obj_rot_vel and force_torque | upstream_code | `manipulator_learning/sim/envs/panda_play.py:430-433` |
| A full-magnitude action moves the desired position by 2 mm per substep over five substeps, 1 cm per environment step | upstream_code | `manipulator_learning/sim/envs/panda_play.py:429` |
| `PandaPlayGeneric` passes `grip_in_action=True`, so the last action value is always the gripper command | upstream_code | `manipulator_learning/sim/envs/panda_play.py:90-91` |
| The insert-tray class uses `valid_t_dofs=(1, 1, 1)` and `valid_r_dofs=(0, 0, 0)` with `control_method` `'dp'` | upstream_code | `manipulator_learning/sim/envs/panda_play.py:442` |
| The insert-tray workspace bounds are x 0.85 to 1.15, y -0.35 to -0.05 and z 0.665 to 0.8 in world coordinates | upstream_code | `manipulator_learning/sim/envs/panda_play.py:443` |
| The class defaults `force_pb_direct=True` | upstream_code | `manipulator_learning/sim/envs/panda_play.py:431` |
| `ManipulatorEnv` derives `num_actions` from the translation DOFs, the rotation DOFs and `grip_in_action` and builds the action space as `Box(-1, 1, (num_actions,))` | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:141-142` |
| The observation space is a `Box` from -inf to +inf with `num_obs` elements | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:159` |
| The `PBEnv` default simulation time step is 0.01 s | upstream_code | `manipulator_learning/sim/envs/pb_env.py:69` |
| `ManipulatorEnv` computes `real_t_per_ts` as `time_step * n_substeps` and `_max_episode_steps` as `round(max_real_time / real_t_per_ts)` | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:88-89` |
| A step returns the legacy four-tuple `(observation, reward, done, info)` and sets `done` when `ep_timesteps` reaches `_max_episode_steps` | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:229-238` |
| `reset` takes `mb_base_angle` and `reset_dict`, returns only the observation and has no `seed` parameter | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:550-573` |
| The separate `seed(seed=None)` method delegates to the `PBEnv` seed and copies `np_random` | upstream_code | `manipulator_learning/sim/envs/manipulator_env_generic.py:166-169` |
| `PBEnv.seed` uses `gym.utils.seeding.np_random` and returns `[seed]` | upstream_code | `manipulator_learning/sim/envs/pb_env.py:390-393` |
| `PBEnv` creates an in-process `BulletClient` in `pybullet.DIRECT` mode when `force_pb_direct` is set | upstream_code | `manipulator_learning/sim/envs/pb_env.py:221-222` |

## Limits

The driver declares no `Limit`. The only bound the bridge enforces is the environment's action space, which it
derives from the fake's `Box(-1, 1, (4,))`: `action.values` from -1 to 1 per element, with no source and the bridge's
derived reference `action_space of the fake backend .fake:FakePandaPlayInsertTrayXYZState`. `ticks` is bounded by
`GymnasiumDriver.max_ticks` (10000 by default). The workspace bounds at `panda_play.py:443` are limits of the
simulated controller, not of this interface, so they are a Fact and not a Limit. The device is simulated (R1), so no
limit is `operator_required` and there is no operator overlay (`site-limits.example.json`).

## Risk

The device is `mode = "simulated"` and `risk = "R1"`. The package has no hardware backend and never starts a PyBullet
client or a robot. The R1 classification follows MHS-004 section 2.1, which lists simulation stepping as a low-energy
bounded action; the card's `safety.risk_floor` is R0 and is not exceeded downward. Because the driver is simulated,
no independent physical stop exists and none is claimed: an e-stop is the runtime's software latch, after which no
step or reset is accepted until `mhs.safety.reset` clears the latch, and the last state stays readable. The e-stop is
not a hardware safety function and nothing here was tested on hardware.

## Fidelity

`fidelity` declares the model as deployed: engine `analytic:manipulator_learning/PandaPlayInsertTrayXYZState`, level
F0 (kinematic, no dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 50.0 (the 5
substeps of 0.01 s that make one environment step), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot/restore. The gaps state that the upstream environment is a PyBullet rigid-body simulation (F1), that the
fake is a kinematic stand-in with no PyBullet dynamics, IK, contacts or sensors, that only four parts of the
59-value observation are modelled, that the reward is a placeholder, that its `random.Random` stream differs from
upstream's numpy generator, that the legacy `done` flag is reported as terminated rather than truncation, and that
the `sim` backend was not run because the class has no `gym.make` registration.

## Other entry symbols

The card lists five environment classes. This package implements the first, `PandaPlayInsertTrayXYZState`; the other
four are not implemented (one device per package):

| symbol | class file:line |
|---|---|
| `ThingDoorMultiview` | `manipulator_learning/sim/envs/thing_door.py:111` |
| `ThingInsertMultiview` | `manipulator_learning/sim/envs/thing_insert.py:94` |
| `ThingPickAndInsertSucDoneMultiview` | `manipulator_learning/sim/envs/thing_insert.py:117` |
| `ThingLiftXYZStateMultiview` | `manipulator_learning/sim/envs/thing_pick_and_place.py:380` |

The other four classes are not modelled. `ThingDoorMultiview`, `ThingInsertMultiview` and
`ThingPickAndInsertSucDoneMultiview` return `Dict` observations with RGB and depth arrays
(`thing_door.py:98-102`, `thing_insert.py:82-86`, `thing_insert.py:105-109`); `ThingLiftXYZStateMultiview` returns a
14-value state `Box` (`thing_pick_and_place.py:382-383`). None of those observations is covered by this package: the
camera, depth and multiview arrays are NOT COVERED.

## Tags

`pybullet`, `panda`, `insert`, `manipulation`, `reinforcement-learning`, `simulation`, `gymnasium`
