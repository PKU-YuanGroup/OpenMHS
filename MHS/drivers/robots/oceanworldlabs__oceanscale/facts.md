# Facts and tags for gh.oceanworldlabs/oceanscale

The package is the Gymnasium `ROVEnv` station-keeping environment of the OceanScale underwater-robotics simulator.
Every fact cites the clone at commit `84f6cc4ce3dcf7cb4a53e2e9d2e81f541b0c63f2`: `upstream_code` is a code or
comment line of the clone, `vendor_doc` is documentation text of the clone. The path is relative to the clone root
and the number after the colon is the line (a range covers every claim of the fact).

## Tags

`oceanworldlabs`, `oceanscale`, `underwater-robotics`, `rov`, `station-keeping`, `reinforcement-learning`,
`simulation`, `gymnasium`.

## Facts

| Fact | Source | Ref |
|---|---|---|
| The observation is a 26-element flat vector: position error (3), orientation quaternion xyzw (4), linear velocity (3), angular velocity (3), depth error (1), roll and pitch heading error (2), previous action (6) and previous hydro wrench (4). | `upstream_code` | `oceanscale/rov_env.py:62-70` |
| The observation space is an unbounded 26-element Box and the action space is a 6-element Box bounded element-wise by -1.0 and +1.0. | `upstream_code` | `oceanscale/rov_env.py:163-164` |
| The action is a six-degree-of-freedom wrench command (surge, sway, heave, roll, pitch, yaw) in [-1, +1] per DOF, mapped to the thrusters through the T_matrix pseudoinverse. | `upstream_code` | `oceanscale/rov_env.py:72-73` |
| The default integration step is `DEFAULT_DT = 1/240` s. | `upstream_code` | `oceanscale/hydro/tier1.py:43` |
| `ROVEnv`'s `dt` argument defaults to `DEFAULT_DT`. | `upstream_code` | `oceanscale/rov_env.py:89` |
| `init_pos_noise_std` and `init_yaw_noise_std` are uniform half-ranges, not standard deviations. | `upstream_code` | `oceanscale/rov_env.py:75-76` |
| A reset samples a position offset per axis uniformly in `[-init_pos_noise_std, +init_pos_noise_std]` and a yaw offset uniformly in `[-init_yaw_noise_std, +init_yaw_noise_std]` with the environment's `np_random` generator. | `upstream_code` | `oceanscale/rov_env.py:806-812` |
| `reset(seed=...)` seeds the environment's `np_random` generator through gymnasium's `Env.reset`. | `upstream_code` | `oceanscale/rov_env.py:285-293` |
| The default target position is `[0.0, 0.0, -1.5]` m. | `upstream_code` | `oceanscale/rov_env.py:137-139` |
| A reset option `target_position` replaces the target position. | `upstream_code` | `oceanscale/rov_env.py:299-303` |
| The reward is `0.5*exp(-position_error/1.0) + 0.3*exp(-velocity_norm/0.5) + 0.2*exp(-action_norm/1.0)`, always in (0, 1]. | `upstream_code` | `oceanscale/rov_env.py:785-789` |
| The episode truncates when the step count reaches `max_episode_steps`. | `upstream_code` | `oceanscale/rov_env.py:414-416` |
| The episode terminates when the ROV is more than 5.0 m from its target. | `upstream_code` | `oceanscale/rov_env.py:418-421` |
| `step` always returns batched shapes: observation (n_envs, 26) and reward and flags (n_envs,). | `upstream_code` | `oceanscale/rov_env.py:346-347` |
| The environment adds Gaussian noise of `sensor_noise_std` to every observation entry, drawn from `torch.randn_like` rather than the seeded generator. | `upstream_code` | `oceanscale/rov_env.py:768-769` |
| Each environment models one free-body sphere (an ROV proxy) with 6-DOF hydrodynamic forces computed by the Tier-1 kernels. | `upstream_code` | `oceanscale/rov_env.py:59-60` |
| OceanScale is an alpha GPU-native underwater-robotics simulator built on Newton and Warp. | `vendor_doc` | `README.md:7-8` |
| An NVIDIA GPU with CUDA 12.8+ is required and Linux x86_64 is the supported platform. | `vendor_doc` | `README.md:14-20` |
| The install pulls CUDA-enabled wheels of warp-lang, newton and torch. | `upstream_code` | `pyproject.toml:27-30` |

## Limits

The only bounds this driver serves are derived by the Gymnasium bridge from the environment's action space:
`action.values` is a six-element array with minimum -1.0 and maximum +1.0 per element (`oceanscale/rov_env.py:164`).
The driver declares no limit of its own and needs no operator overlay: the action space is the device's complete
command envelope, and no constructor default (number of environments, number of thrusters, `max_episode_steps`) is
treated as a bound.

## The fake backend

The gate cannot import OceanScale: it needs an NVIDIA GPU with CUDA 12.8+ and an install that pulls CUDA-enabled
wheels (~10 GB), `README.md:10-11` and `:20`. `fake.py` therefore re-implements the interface the bridge uses with
pure Python and cites the upstream lines for the observation layout, the action space, the reset noise, the reward,
the out-of-bounds termination and the truncation. Its kinematic acceleration and drag are placeholders and are not
upstream facts; it models one environment and returns flat 26-element observations where upstream returns batched
arrays, and it omits the upstream sensor noise. The fidelity `gaps` in `driver.py` state all of this.

## What was not run

The upstream simulator, its CUDA stack and the `sim` backend were not run. No physical ROV was involved, no hardware
backend exists in this package, and nothing here was reviewed or tested by a human.
