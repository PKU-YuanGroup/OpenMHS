# Facts and tags for gh.vimalabs/vimabench

Every fact cites its source at commit `97e0af11e126fd477c9d81eeabfb6c739021c680`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same list is in `facts = [Fact(text, source=..., ref=...)]` in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The public factory is `vima_bench.make`, which returns a `VIMAEnvBase` | upstream_code | `vima_bench/__init__.py:14-42` |
| `VIMAEnvBase` is a `gym.Env` subclass | upstream_code | `vima_bench/env/base.py:25` |
| The README calls the interface Gym-style and shows `make(task_name=...)`, `env.reset()` | vendor_doc | `README.md:30-40` |
| VIMA-Bench is a PyBullet simulation of a UR5 workspace: `reset` loads the plane, workspace and UR5 URDFs and sets gravity to -9.8 m/s^2 | upstream_code | `vima_bench/env/base.py:248-287` |
| The constructor defaults are `hz=240` and `max_sim_steps_to_static=1000` | upstream_code | `vima_bench/env/base.py:36-37` |
| `VIMAEnvBase` sets `p.setTimeStep(1.0 / hz)`, the physics integration step | upstream_code | `vima_bench/env/base.py:131` |
| One `VIMAEnvBase.step` with an action executes one pick-and-place primitive and then steps the simulation until the rigid bodies are static, for at most `max_sim_steps_to_static` steps | upstream_code | `vima_bench/env/base.py:391-433` |
| The action space is a `Dict` of four `Box`es: `pose0_position` and `pose1_position` are `[0.25, -0.5]` to `[0.75, 0.50]`, and `pose0_rotation` and `pose1_rotation` are -1.0 to 1.0 with four elements | upstream_code | `vima_bench/env/base.py:181-196` |
| `step` reads the four action keys `pose0_position`, `pose0_rotation`, `pose1_position` and `pose1_rotation` | upstream_code | `vima_bench/env/base.py:402-408` |
| `step` returns the legacy four-tuple `(obs, reward, done, info)` | upstream_code | `vima_bench/env/base.py:455` |
| The reward is always 0 in VIMA-Bench | upstream_code | `vima_bench/env/base.py:437-438` |
| `done` is the task's success or failure flag | upstream_code | `vima_bench/env/base.py:452-455` |
| The `info` dict carries the prompt, success and failure | upstream_code | `vima_bench/env/base.py:675-682` |
| The default observation modalities are `rgb` and `segm`, each a `Dict` over the camera views, plus an `ee` `Discrete(2)` indicator | upstream_code | `vima_bench/env/base.py:69-106` |
| A task's default observation image size is (128, 256) and its default views are `front` and `top` | upstream_code | `vima_bench/tasks/task_suite/base.py:67-114` |
| The observations are rendered per view; `ee` is 0 for the `Suction` end effector and 1 for `Spatula` | upstream_code | `vima_bench/env/base.py:663-671` |
| `reset` reloads the scene, resets the task, generates the prompt and returns the first observation | upstream_code | `vima_bench/env/base.py:248-389` |
| `reset` generates the prompt with `Task.generate_prompt`, which returns the prompt string and an assets dict | upstream_code | `vima_bench/env/base.py:330` |
| `seed` creates a numpy `default_rng`, stores the seed and seeds the task generator | upstream_code | `vima_bench/env/base.py:224-229` |
| `Task.set_seed` creates the task's numpy `default_rng` and stores the seed | upstream_code | `vima_bench/tasks/task_suite/base.py:141-143` |
| Some task code draws from Python's global random and numpy's global generator, which `VIMAEnvBase.seed` does not set | upstream_code | `vima_bench/tasks/task_suite/base.py:560-599` |
| `close` disconnects the PyBullet client | upstream_code | `vima_bench/env/base.py:221-222` |
| The install requirements are `pybullet` and `gym==0.21.0` | vendor_doc | `requirements.txt:1-2` |

## Limits in this package

| capability | path | bound | source | ref |
|---|---|---|---|---|
| `cap.world.step.v1` | `action.pose0_position` | `[0.25, -0.5]` to `[0.75, 0.50]` (x, y, metres) | upstream_code | `vima_bench/env/base.py:181-196` |
| `cap.world.step.v1` | `action.pose1_position` | `[0.25, -0.5]` to `[0.75, 0.50]` (x, y, metres) | upstream_code | `vima_bench/env/base.py:181-196` |
| `cap.world.step.v1` | `action.pose0_rotation` | -1.0 to 1.0 per quaternion element | upstream_code | `vima_bench/env/base.py:190-196` |
| `cap.world.step.v1` | `action.pose1_rotation` | -1.0 to 1.0 per quaternion element | upstream_code | `vima_bench/env/base.py:193-196` |

The `ticks` schema bounds (1 to 10000) and the reset/seed `seed` minimum (0) come from the catalogue classes
`cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1`; the driver does not restate them as Limits.

## Contract notes

- `cap.world.step.v1` takes `{ticks, action}`; the `action` object is closed to the four upstream action-space
  fields. One tick is one `VIMAEnvBase.step` primitive, which runs a variable number of PyBullet physics steps
  (1/hz, default 240, so 4.166666666666667 ms) until the objects are static; `fidelity.timestep_ms` names the
  physics step, and the fidelity `gaps` say the control period is not fixed.
- `cap.world.reset.v1` takes `{seed}` (required): the driver calls `VIMAEnvBase.seed(seed)` and then `reset()`, so
  the task's numpy generator is seeded. Some task code also uses Python's global random and numpy's global generator,
  which `VIMAEnvBase.seed` does not set (`vima_bench/tasks/task_suite/base.py:560-599`), so the upstream path is not
  fully reproducible from the seed alone. `cap.world.seed.v1` takes `{seed}` and calls the same `seed` without a reset.
- The observation, reward, terminated, truncated, tick, episode and info reads are the driver's own world state,
  not class fields; the prompt string is in the info read after a reset or a step.
- The package fake is a pure Python kinematic stand-in. Its image arrays are 3 x 2 x 2 rgb and 2 x 2 segm
  placeholders; the real arrays are 3 x 128 x 256 and 128 x 256 per view by `tasks/task_suite/base.py:67`.

Tags: `vima`, `robot-manipulation`, `pybullet`, `tabletop`, `multimodal-prompt`, `reinforcement-learning`,
`simulation`, `gym`.
