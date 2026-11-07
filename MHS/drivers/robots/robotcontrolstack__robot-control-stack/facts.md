# Facts and tags for gh.robotcontrolstack/robot-control-stack

Every fact cites its source at commit `afb3795ae9f49f9992bb61518eef6e7277b9011f`: `upstream_code` is a line of the
clone at its path from the clone root. The driver class carries the same list as `Fact(text, source=..., ref=...)`;
`reference.json` is generated from the class, not from this page.

## The environment

| fact | source | ref |
|---|---|---|
| The `rcs/fr3` environment is registered with gymnasium as `EmptyWorldFR3()` | upstream_code | `python/rcs/envs/configs.py:628` |
| The FR3 environment controls the arm in Cartesian TQuat mode | upstream_code | `python/rcs/envs/configs.py:86` |
| The FR3 environment configures `SimConfig` with `realtime=True`, `async_control=False`, `frequency=1` Hz and `max_convergence_steps=500` | upstream_code | `python/rcs/envs/configs.py:84` |
| When `async_control` is false, `SimEnv.step_sim` calls `sim.step_until_convergence()` instead of a fixed number of physics steps | upstream_code | `python/rcs/envs/base.py:267-278` |
| The FR3 robot is named `right` (`robot_prefix_template`) | upstream_code | `python/rcs/envs/configs.py:35` |
| `MultiRobotWrapper` builds the action and observation spaces as dicts keyed by the robot name | upstream_code | `python/rcs/envs/base.py:462-465` |
| The environment wraps each robot in `RelativeActionSpace` unless `relative_to` is `RelativeTo.NONE` | upstream_code | `python/rcs/envs/scenes.py:362-365` |

## Action and observation

| fact | source | ref |
|---|---|---|
| A relative Cartesian action defaults to at most 0.5 m of translation (`DEFAULT_MAX_CART_MOV`) | upstream_code | `python/rcs/envs/base.py:725` |
| The relative TQuat action box bounds the three translation elements by `+-max_cart_mov`, the quaternion scalar by -1 and 1, and the three quaternion vector elements by -inf and inf | upstream_code | `python/rcs/envs/base.py:70-79` |
| The gripper action box is one value from 0 (closed) to 1 (open) | upstream_code | `python/rcs/envs/base.py:106-108` |
| `TQuatDictType` is a `tquat` field of 7 values bounded by `[-0.855, -0.855, -1, -1, -inf, -inf, -inf]` and `[0.855, 0.855, 1.188, 1, inf, inf, inf]` | upstream_code | `python/rcs/envs/base.py:59-67` |
| `JointsDictType` bounds the `joints` array element-wise by the robot's joint limits | upstream_code | `python/rcs/envs/base.py:82-90` |
| `TRPYDictType` is an `xyzrpy` field of 6 values bounded by `[-0.855, -0.855, -1, -180, -180, -180]` degrees and `[0.855, 0.855, 1.188, 180, 180, 180]` degrees | upstream_code | `python/rcs/envs/base.py:34-44` |
| `ArmObsType` joins `TQuatDictType`, `JointsDictType` and `TRPYDictType` and adds `tquat_flange` | upstream_code | `python/rcs/envs/base.py:170-178` |
| The gripper wrapper adds one normalized width to the observation | upstream_code | `python/rcs/envs/base.py:1090-1097` |

## Step and reset

| fact | source | ref |
|---|---|---|
| `SimEnv.step` advances the simulation and then returns `(observation, reward, terminated, truncated, info)` | upstream_code | `python/rcs/envs/base.py:257-265` |
| `CoverWrapper.reset` resets the simulator, seeds only the wrapper's `np_random`, then advances the simulator 30 steps to apply the reset state | upstream_code | `python/rcs/envs/base.py:309-322` |

## Limits that are derived, not written

The action bounds are derived by the Gymnasium bridge from the environment's action space and published in
`reference.json`. They are not written by hand in `driver.py`, so no `Limit` object with a source and a line is
attached to them. The upstream translation bound is 0.5 m (`python/rcs/envs/base.py:725`, applied by the relative
action wrapper at `:788-795`). The fake narrows the three quaternion vector elements from the upstream's `-inf` and
`inf` to -1 and 1, so the gate can build an out-of-envelope input for every element; that narrowing is listed in the
fidelity `gaps` and in `RESULT.json`.

## Other environments on the card (not implemented)

The card lists the family's other registered environments. One package implements one device class, so this package
serves only `rcs/fr3`; the others are named here for a follow-up package and are not exposed by this driver:

| environment | entry point | source | ref |
|---|---|---|---|
| `rcs/duo` | `EmptyWorldFR3Duo()` | upstream_code | `python/rcs/envs/configs.py:629` |
| `rcs/droid` | `EmptyWorldDroid()` | upstream_code | `python/rcs/envs/configs.py:630` |
| `rcs/ur5e` | `EmptyWorldUR5e()` | upstream_code | `python/rcs/envs/configs.py:631` |
| `rcs/xarm7` | `EmptyWorldXArm7()` | upstream_code | `python/rcs/envs/configs.py:632` |
| `rcs/so101` | `EmptyWorldSO101()` | upstream_code | `python/rcs/envs/configs.py:633` |
| `rcs/yam` | `EmptyWorldYam()` | upstream_code | `python/rcs/envs/configs.py:634` |

## Not facts

Numbers in `fake.py` (home pose, joint offsets, workspace clamps, coupling, observation bounds) are test data and are
marked `# placeholder`. They are not copied into this page, the driver's `Fact` list or the reference. The fake
returns no camera frames, although the registered environment configures two 1280 x 720 cameras at 30 Hz
(`python/rcs/envs/configs.py:105-120`); this is recorded as NOT COVERED in the driver's fidelity `gaps` and in
`RESULT.json`.

## Tags

`robot-arm`, `fr3`, `franka`, `mujoco`, `reinforcement-learning`, `simulation`, `gymnasium`
