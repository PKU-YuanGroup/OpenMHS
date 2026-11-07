# Facts and tags for gh.hanruihua/rl_rvo_nav

Every fact cites its source at commit `6cdb70c731293dd92fa6f84cd6878a28bf259191`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`).  The `facts` list in `driver.py` is the source
of the generated reference file; this page records the same claims and the decisions that have no bound.

| fact | source | ref |
|---|---|---|
| `mrnav-v1` is registered with entry point `gym_env.envs:mrnav` | upstream_code | `gym_env/gym_env/__init__.py:3-6` |
| The environment class is `mrnav`, a `gym.Env` subclass with `__init__`, `step_ir`, `render`, `reset`, `reset_one` and `show` | upstream_code | `gym_env/gym_env/envs/mrnav.py:4-46` |
| `mrnav` wraps `ir_gym` and copies its observation and action spaces | upstream_code | `gym_env/gym_env/envs/mrnav.py:7-10` |
| The declared observation space is `Box(-inf, inf, shape=(5,), dtype=float32)` | upstream_code | `gym_env/gym_env/envs/ir_gym.py:23` |
| The declared action space is `Box(low=[-1, -1], high=[1, 1], dtype=float32)` | upstream_code | `gym_env/gym_env/envs/ir_gym.py:24` |
| `step_ir(action, vel_type='omni', stop=True)` returns `obs_list, reward_list, done_list, info_list` | upstream_code | `gym_env/gym_env/envs/mrnav.py:18-30` |
| A robot observation concatenates current velocity, desired velocity, heading and collision radius with the RVO neighbour features, rounded to two decimals | upstream_code | `gym_env/gym_env/envs/ir_gym.py:96-109` |
| `rvo_state_dim` is 8 | upstream_code | `gym_env/gym_env/envs/ir_gym.py:30` |
| A collision sets `done` true and the robot's arrival flag is returned as `info` | upstream_code | `gym_env/gym_env/envs/ir_gym.py:116-117` |
| The movement reward is the collision parameter `p7` on a collision plus the arrival parameter `p8` on the first arrival | upstream_code | `gym_env/gym_env/envs/ir_gym.py:121-131` |
| The per-robot reward is the RVO reward plus the movement reward | upstream_code | `gym_env/gym_env/envs/mrnav.py:28-29` |
| `reset(mode=0, **kwargs)` forwards to `ir_gym.env_reset` and returns the list of robot observations | upstream_code | `gym_env/gym_env/envs/mrnav.py:38-40` |
| `env_reset` calls `robots_reset` and then rebuilds the observations; the method does not reset obstacle state | upstream_code | `gym_env/gym_env/envs/ir_gym.py:173-179` |
| The reset path takes a mode and forwards it to `robots_reset`; it supplies no seed value | upstream_code | `gym_env/gym_env/envs/ir_gym.py:175` |
| The world configuration sets the simulation `step_time` to 0.1 s | upstream_code | `gym_env/gym_test_world.yaml:4` |
| The training loop builds the absolute velocity command as `acceler * policy action + current velocity` before calling `step_ir` | upstream_code | `rl_rvo_nav/policy_train/multi_ppo.py:184-187` |
| The simulator is the external intelligent-robot-simulator (ir-sim) v2.5 | vendor_doc | `README.md:21` |
| The class defines no `get_state`/`set_state` and the clone exposes no snapshot or restore path | upstream_code | `gym_env/gym_env/envs/mrnav.py:4-46` |

## Decisions without a device bound

**No limit on the velocity commands.**  The declared action space `Box([-1,-1],[1,1])` (`ir_gym.py:24`) is the space of
the policy's normalised output.  The training loop scales that output by `ir_gym.acceler` and adds the robot's current
velocity before it calls `step_ir` (`multi_ppo.py:183-187`), so the values `step_ir` receives are absolute velocities
and the `[-1, 1]` box does not bound them.  The clone states no bound on the absolute command; the world YAML's
`vel_max` belongs to a particular world file and a particular robot mode, so it is not cited as a deployment limit.
This is a simulated R0 driver: G3 requires every numeric bind on hardware/hybrid R1+ only, and the gate's conformance
SAFE-014 is not applicable because no limit is declared.

**The reset seed.**  `reset` takes a mode and forwards it to `robots_reset` (`mrnav.py:38-40`, `ir_gym.py:175`); the
clone has no seed parameter.  The standard `cap.world.reset.v1` output requires a `seed`, so the binding reports `0` and
the fidelity contract declares `determinism.kind = none` instead of claiming a repeatable seed.  `cap.world.seed.v1` is
not bound: no clone method sets a seed for a later reset.

**No truncation and no snapshot.**  `step_ir` returns only the four per-robot lists; the clone has no step limit
wrapper and no `get_state`/`set_state`, so the binding reports `truncated` false and the fidelity contract reports
`snapshot_restore` false.

**The fake.**  `fake.py` is a two-robot kinematic stand-in with no obstacles, not the upstream ir-sim engine.  Its
start positions, reward values and time constant are test data marked `# placeholder`; they are not facts, limits or
references.  The upstream package was never imported or run.

Tags: `multi-robot`, `navigation`, `reinforcement-learning`, `rvo`, `simulation`, `gym`.
