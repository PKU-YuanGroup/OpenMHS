# Facts and tags for gh.albusgive/wheel_legged_genesis

Every fact cites its source at commit `d34f4a13cf74216063df276a77efda5b784ecdbf`: `upstream_code` is a file and
line of the clone, `vendor_doc` is text of the clone. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| WheelLeggedEnv is the concrete Genesis environment class of the repository | upstream_code | locomotion/wheel_legged_env.py:15 |
| The environment imports genesis as gs | upstream_code | locomotion/wheel_legged_env.py:3 |
| The constructor takes num_envs, the env, observation, reward, command, curriculum, domain randomization and terrain configurations, robot_morphs, show_viewer, num_view, device and train_mode | upstream_code | locomotion/wheel_legged_env.py:16-17 |
| The control period is 0.01 s, 100 Hz | upstream_code | locomotion/wheel_legged_env.py:35 |
| The Genesis scene uses the control period and five physics substeps | upstream_code | locomotion/wheel_legged_env.py:48-51 |
| The training configuration sets num_actions to 8 | upstream_code | locomotion/wheel_legged_train.py:62 |
| The training configuration lists the left and right hip, thigh, calf and wheel joints | upstream_code | locomotion/wheel_legged_train.py:86-106 |
| The training configuration sets num_obs to 286, num_slice_obs to 28 and history_length to 9 | upstream_code | locomotion/wheel_legged_train.py:166-168 |
| The training configuration sets num_commands to 6 | upstream_code | locomotion/wheel_legged_train.py:217 |
| The observation row concatenates the history buffer, the current slice and the scaled commands | upstream_code | locomotion/wheel_legged_env.py:511-517 |
| step clips every action to the configured clip_actions range | upstream_code | locomotion/wheel_legged_env.py:391-392 |
| The training configuration sets clip_actions to 100.0 | upstream_code | locomotion/wheel_legged_train.py:160 |
| step advances the Genesis scene once with scene.step() | upstream_code | locomotion/wheel_legged_env.py:403 |
| step returns the observation, None for the privileged observation, the reward buffer, the reset flag buffer and the extras | upstream_code | locomotion/wheel_legged_env.py:519 |
| reset sets reset_buf, calls reset_idx for every environment and returns the existing obs_buf and None | upstream_code | locomotion/wheel_legged_env.py:602-605 |
| reset_idx resets the DOF and base state and the episode buffers but does not recompute the observation buffers | upstream_code | locomotion/wheel_legged_env.py:527-600 |
| The episode timeout is marked in extras['time_outs'] for every environment whose episode_length_buf exceeds max_episode_length | upstream_code | locomotion/wheel_legged_env.py:472-474 |
| check_termination sets reset_buf from the episode length, the roll and pitch limits and contact with the listed links | upstream_code | locomotion/wheel_legged_env.py:607-618 |
| When train_mode is true, step calls reset_idx for every environment whose reset_buf is set before it computes the reward and observation | upstream_code | locomotion/wheel_legged_env.py:475-478 |
| The training configuration sets episode_length_s to 20.0 | upstream_code | locomotion/wheel_legged_train.py:155 |
| The training script initializes Genesis with the GPU backend | upstream_code | locomotion/wheel_legged_train.py:281 |
| The training script defaults num_envs to 8192 | upstream_code | locomotion/wheel_legged_train.py:277 |
| The training configuration carries a runner seed of 1 | upstream_code | locomotion/wheel_legged_train.py:54 |
| The install dependencies are genesis-world, tensorboard, pygame, torch and the in-tree rsl-rl | upstream_code | pyproject.toml:8-14 |
| The README states that the repository is reinforcement learning of wheel-legged robots based on Genesis and that sim2sim in MuJoCo is supported | vendor_doc | README.md:1-4 |
| The README says Genesis 0.2.1 cannot be installed from pip and must be a local installation of the main branch because of an API update | vendor_doc | README.md:11-13 |

## Limits

The step action carries one limit. The action values are the normalized joint and wheel action, one value per
joint, and `WheelLeggedEnv.step` clips them to `env_cfg["clip_actions"]`
(`locomotion/wheel_legged_env.py:392`). The training configuration states `clip_actions=100.0`
(`locomotion/wheel_legged_train.py:160`), while the signed clip is on another file's line. The driver therefore
declares `action.values` as `operator_required` rather than accepting the provenance warning. Without an overlay,
steps are refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` fills -100.0..100.0 for fake checks
only; a deployment supplies its own bounds. `ticks` retains the catalogue class's 1..10000 range.

`cap.world.seed.v1` is not bound because `WheelLeggedEnv` defines no seed method; only `set_commands`, `step`,
`get_observations`, `reset_idx` and `reset` are defined (`locomotion/wheel_legged_env.py:388-605`). The reset
action accepts a seed and seeds the process generators (Python random, NumPy and Torch) before calling the native
reset; the training script only carries a runner seed of 1 (`locomotion/wheel_legged_train.py:54`).

## Fidelity

The model as deployed on the checked fake backend is analytic, level F0, seeded (seed control is the reset
parameter), 10 ms per tick, lockstep, full reset, no snapshot and restore. The gaps in `driver.py` state that the
fake is a pure Python stand-in with no Genesis engine, that the real environment needs a source build of Genesis
from its main branch, that the upstream reset can return a stale observation, that the upstream step auto-resets
when `train_mode` is true, that only one environment instance and the default training configuration are modelled,
and that no physical device or upstream simulator was run. A pure native timeout is reported as truncation, not
termination; the native reset flag also covers roll, pitch and contact termination. Missing or nonfinite native
rewards and flags are refused instead of being converted to zero or a boolean.

## Safety

The device is simulated (R0); steps need an operator action interval. The e-stop is the runtime's software latch;
after it no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the last observation and tick stay readable. The running step checks
`self.check_cancelled()` between ticks so an e-stop does not wait for the loop. There is no `@estop` method and no
`@reset` hook; the upstream simulation has no native stop for a machine.

Tags: wheel-legged, robot, genesis, simulation, reinforcement-learning, cj-003
