# Facts and tags for gh.paddlepaddle/metagym

Every fact cites its source at commit `ca724c22fd0c2ade8ec905edc688a1befdf98a3c` (`upstream_code`, a code
line or comment of the clone, or a path relative to the clone root).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Bandits is a gym.Env whose action space is spaces.Discrete(arms) and whose observation space is None | upstream_code | metagym/bandits/bandits_env.py:12-24 |
| The constructor takes arms and max_steps and asserts that both are greater than 1 | upstream_code | metagym/bandits/bandits_env.py:13-31 |
| sample_task supports the Classical, Uniform and Gaussian distribution settings, with default mean 0.50 and dev 0.05 | upstream_code | metagym/bandits/bandits_env.py:33-55 |
| set_task stores task_config as exp_gains and asserts that its shape is (K,) | upstream_code | metagym/bandits/bandits_env.py:57-60 |
| reset raises an exception unless set_task set exp_gains first; a successful reset sets steps to 0 and need_reset to False | upstream_code | metagym/bandits/bandits_env.py:62-67 |
| step raises unless reset was called, indexes exp_gains by the action, draws a Bernoulli reward with that expected gain, and reports steps and expected_gain in info | upstream_code | metagym/bandits/bandits_env.py:69-75 |
| An episode is done when steps reaches max_steps, and a done episode requires a reset before the next step | upstream_code | metagym/bandits/bandits_env.py:76-78 |
| step returns the legacy Gymnasium 4-tuple (observation, reward, done, info) | upstream_code | metagym/bandits/bandits_env.py:80 |
| expected_upperbound returns max_steps multiplied by the largest expected gain | upstream_code | metagym/bandits/bandits_env.py:82-83 |
| The module imports numpy's global random generator | upstream_code | metagym/bandits/bandits_env.py:7 |
| step draws its Bernoulli reward from numpy's global random generator | upstream_code | metagym/bandits/bandits_env.py:73 |
| The class body defines __init__, reset, step, sample_task, set_task and expected_upperbound, and defines no seed method | upstream_code | metagym/bandits/bandits_env.py:12-83 |
| The registered bandits-v0 environment passes arms=50 and max_steps=1000 | upstream_code | metagym/bandits/__init__.py:18-23 |
| Importing metagym.bandits imports register from gym.envs.registration and registers bandits-v0 with entry point metagym.bandits:Bandits | upstream_code | metagym/bandits/__init__.py:15-24 |
| bandits_env.py imports pygame at module scope, on the import that registers bandits-v0 | upstream_code | metagym/bandits/bandits_env.py:6 |
| The quick start imports metagym.bandits, makes bandits-v0, samples a task, calls set_task and then reset | vendor_doc | metagym/bandits/README.md:30-44 |

Limits: the driver declares none of its own.  The only bound is the action space, which the bridge derives
from the environment at runtime (`Discrete(50)` gives `action.index` 0 through 49, from the registered
`arms=50` at `metagym/bandits/__init__.py:21`; the bridge reports the bound with no source and the ref
`action_space of the fake backend .fake:FakeBandits`).  The device is simulated (R0), so no limit is
`operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `metagym:bandits-v0`, level F0 (an analytic
bandit model: no dynamics, contacts, actuator, sensor or noise model), determinism `statistical` (Bandits
draws its task and Bernoulli reward from numpy's global generator rather than a per-environment
generator; the bridge records a supplied seed, but the class's own draws are not tied to it), timestep
0 ms, `realtime_factor` 0, clock `lockstep`, reset `partial` (the step counter restarts, the gain table
and random stream continue), no snapshot and restore.  The gaps say what is not modelled, including that
the fake installs a placeholder gain table, uses Python's `random.Random` instead of numpy, and omits the
inherited `gym.Env` helpers (`close`, `render`, `seed`).

Safety: simulated R0 device.  The e-stop is the runtime's software latch; there is no native stop to reach
and no hardware backend.  After an e-stop no step, reset or seed is accepted until `mhs.safety.reset`
clears the latch (a simulator needs no operator for that), and the gain table and step counter stay
readable.

Sim path (`driver.py`): `env_module = "metagym.bandits"` names the module whose import runs the registration
at `metagym/bandits/__init__.py:15-24`. The package `__init__` does not import that module
(`metagym/__init__.py:16-17` tells the caller to `import metagym.xxxenv` and then use `gym.make`). The `sim`
backend is `open_sim`. It imports `metagym.bandits` and constructs `Bandits(arms=50, max_steps=1000)`, the
entry point and kwargs at `metagym/bandits/__init__.py:18-23` (the constructor defaults are `arms=10` and
`max_steps=5000` at `metagym/bandits/bandits_env.py:14-15`). It then calls `sample_task()` and `set_task` as
the quick start does (`metagym/bandits/README.md:37-44`). `reset` raises until that call
(`metagym/bandits/bandits_env.py:62-64`). `gym.make` is not used: `observation_space` is `None`
(`metagym/bandits/bandits_env.py:24`), and the pinned `gym==0.25.2` wraps `make`'s result in a checker that
rejects a space that is not a `gym.spaces.Space`. The fake backend stays `.fake:FakeBandits` and does not
import `env_module`.

Coverage: this package covers the card's `metagym.bandits:Bandits` entry symbol through `bandits-v0`.  The
other four entry symbols of the card (`LiftSim`, `MetaLM`, `MetaAntEnv`, `MetaHumanoidEnv`) are not covered
by this package; they would each need their own environment contract and fake.

Tags: bandits, meta-reinforcement-learning, reinforcement-learning, simulation, gymnasium
