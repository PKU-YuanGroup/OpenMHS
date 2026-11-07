# Facts and tags for gh.swirl-uk/bigym2

Every fact cites its source at commit `f1b846216b3f985d8640e5703112980de05c0d22`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GymnasiumEnv is the gymnasium.Env view of a bigym.loco controller-in-the-loop environment; the adapter owns no physics and reports everything from the wrapped environment | upstream_code | bigym/loco/gym_adapter.py:16-19 |
| make_gym(task_name) builds GymnasiumEnv(make(task_name, config, **overrides)); it does not call gymnasium.make | upstream_code | bigym/loco/gym_adapter.py:305-322 |
| The action space is a Box that copies the wrapped environment's low, high and shape | upstream_code | bigym/loco/gym_adapter.py:104-112 |
| step casts the action to float32, reshapes it to the action space and clips it into the action space before stepping the environment | upstream_code | bigym/loco/gym_adapter.py:160-164 |
| The observation space is a Dict with an rgb uint8 0..255 field and a state float32 field | upstream_code | bigym/loco/gym_adapter.py:91-102 |
| reset(seed=s) passes the seed to the wrapped environment; a reset without a seed draws one from the adapter's np_random | upstream_code | bigym/loco/gym_adapter.py:139-150 |
| A step returns terminated = last and discount == 0, and truncated = last and not terminated | upstream_code | bigym/loco/gym_adapter.py:166-170 |
| The observation returned by reset and step is a dict with rgb and state arrays | upstream_code | bigym/loco/gym_adapter.py:270-276 |
| The render metadata is render_fps = round(1 / control_step_seconds) | upstream_code | bigym/loco/gym_adapter.py:117-119 |
| The step info carries success, fell, event_progress and discount, and a terminal step adds termination and truncation_reason | upstream_code | bigym/loco/gym_adapter.py:278-293 |
| The default camera keys are head, right_wrist and left_wrist | upstream_code | bigym/loco/config.py:33 |
| The default state keys are proprioception, proprioception_grippers and proprioception_floating_base | upstream_code | bigym/loco/config.py:34-38 |
| The episode budget is in inner environment steps and one outer control step is demo_down_sample_rate inner steps; the default 10 is 50 Hz | upstream_code | bigym/loco/config.py:138-141 |
| The default camera shape is 84x84 and the default frame_stack is 1 | upstream_code | bigym/loco/config.py:154-164 |
| The outer action dimension is the outer base slots plus the selected limb actuators plus the gripper count | upstream_code | bigym/loco/env.py:921-923 |
| The outer action space is Box(-1, 1) over the computed action dimension | upstream_code | bigym/loco/env.py:1004-1009 |
| The low-dim observation length is summed over the configured state keys and frame-stacked | upstream_code | bigym/loco/env.py:1011-1039 |
| The rgb observation space is uint8 0..255 with shape (num_cameras, 3 * frame_stack, H, W) | upstream_code | bigym/loco/env.py:1048-1056 |
| The task drawer_top_open is registered with DrawerTopOpenG1 and a 13500-step budget | upstream_code | bigym/loco/tasks.py:158 |
| The default robot is the Unitree G1 with Dex1-1 parallel two-finger grippers | upstream_code | bigym/robots/configs/g1.py:237-238 |
| The G1 MJCF is bigym/envs/xmls/g1/g1_29dof_with_dex1_1.xml with model name g1_29dof_with_dex1_1 | upstream_code | bigym/envs/xmls/g1/g1_29dof_with_dex1_1.xml:1 |

Limits: the driver declares none.  The action bound is the environment's action space, which
`bigym/loco/env.py:1009` states as `Box(-1, 1)`; the gymnasium bridge derives it from the fake's space and the
runtime enforces it before any native call.  The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `bigym2:gym_adapter` (fake backend: kinematic stand-in),
level F0 (no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (the upstream outer
control step: `bigym/loco/config.py:140-141` says 10 inner steps per outer step = 50 Hz), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore.  The gaps say what is not modelled (no rigid-body dynamics,
contacts, actuators, sensors or noise; placeholder array sizes; no rendering; no wall-clock pacing; no comparison
with upstream; no snapshot).

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: bigym2, humanoid, manipulation, mujoco, simulation, reinforcement-learning, gymnasium
