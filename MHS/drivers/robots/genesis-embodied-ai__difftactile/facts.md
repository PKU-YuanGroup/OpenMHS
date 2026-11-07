# Facts and tags for gh.genesis-embodied-ai/difftactile

Every fact cites its source at commit `c4bf43d44071758aea68a5c7ae125fc8257bb8e1` (`upstream_code`, a code line of
the clone). The same facts are written into `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TactileEnv is a Gymnasium environment: the class inherits from gym.Env | upstream_code | difftactile/baseline/tactile_env.py:23 |
| The action space is Box(low=-0.015, high=0.015, shape=(n_actions,), dtype=float32) | upstream_code | difftactile/baseline/tactile_env.py:45 |
| The observation space is Box(low=-1000, high=1000, shape=(n_observations,), dtype=float32) | upstream_code | difftactile/baseline/tactile_env.py:46 |
| The environment downsamples the object to 2 * 136 * 2 = 544 particle indices, or uses every particle when the object has fewer | upstream_code | difftactile/baseline/tactile_env.py:55-67 |
| step increments time_step, applies the action, computes the observation and reward, calls check_termination and returns (observation, reward, terminated, truncated, info) | upstream_code | difftactile/baseline/tactile_env.py:85-102 |
| reset accepts seed and options but never reads either: it re-initialises the contact model and returns (observation, info) | upstream_code | difftactile/baseline/tactile_env.py:104-123 |
| For task box_open, get_observations concatenates the downsampled object particle positions with the sensor translation (3 values) and Euler angles (3 values); with obs_tactile it also appends the tactile marker positions and the predicted force | upstream_code | difftactile/baseline/tactile_env.py:130-140 |
| compute_rewards uses scale = 1.0 for task box_open and returns scale * 2000 - delta_loss | upstream_code | difftactile/baseline/tactile_env.py:211-218 |
| check_termination returns True when time_step reaches time_limit | upstream_code | difftactile/baseline/tactile_env.py:220-224 |
| TactileEnv.close is a no-op | upstream_code | difftactile/baseline/tactile_env.py:230-231 |
| The box_open task is registered with n_actions = 6, state_n_observations = 2 * 136 * 2 * 3 + 6, tactile_n_observations = 2 * 136 + 4 * 136 * 3 + 3 + 6, dt = 5e-5 s, total_steps = 600, sub_steps = 50 and obj = earpod-case.stl | upstream_code | difftactile/baseline/register_tasks.py:70-80 |
| The baseline passes time_limit = task.total_steps to the environment | upstream_code | difftactile/baseline/training_rl.py:78 |
| Contact.apply_action for box_open reads the six action elements as a position delta and an orientation delta, adds a 0.8 offset on one position axis depending on the phase, and runs sub_steps - 1 solver updates | upstream_code | difftactile/tasks/box_open.py:513-527 |

Limits: the driver declares none. The only bound is the environment's action space, which the Gymnasium bridge
derives from `spaces.Box(low=-0.015, high=0.015, shape=(n_actions,), dtype=np.float32)`
(`difftactile/baseline/tactile_env.py:45`), so every element of `action.values` is bounded by -0.015 and 0.015 and an
out-of-range action is refused before any `env.step`. `ticks` is bounded by the bridge's `max_ticks` (10000 by
default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `difftactile:TactileEnv(box_open)`, level F0 (the fake
does not integrate the FEM/MPM model), determinism `seeded` with `seed_control` `parameter`, timestep 2.45 ms (one
transition runs `sub_steps - 1 = 49` solver updates at `dt = 5e-5` s; `difftactile/tasks/box_open.py:526-527` and
`difftactile/baseline/register_tasks.py:76`, `:78`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The observation of the registered box_open task has 1638 state values (544 particles times 3
coordinates plus 6 sensor pose values) and 1913 tactile values (`register_tasks.py:74-75`); the fake returns the 1638
state values only, and its own gaps say the tactile branch is NOT COVERED.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware was attached
and no hardware or `sim` backend was run.

Mock path: `fake.py` is a pure Python stand-in for `difftactile.baseline.tactile_env:TactileEnv`; the upstream
Taichi/FEM/MPM simulator is never imported or run. The clone registers no Gymnasium id (the baseline constructs
TactileEnv directly with `make_vec_env` at `difftactile/baseline/training_rl.py:95-96`), so the bridge's
`gym.make(env_id)` path has no id to open and the package lists only the `fake` backend.

Tags: tactile, contact-rich-manipulation, differentiable-physics, reinforcement-learning, simulation, gymnasium
