# Facts and tags for gh.erwincoumans/tiny-differentiable-simulator

Every fact cites its source at commit `8381b8c9ad7f0a959548e4982eb8a63431a842d2`: `upstream_code` is code or a comment
of the clone.  The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| CartpolePyTinyDiffSim is registered as CartpolePyTinyDiffSim-v0 with entry point tds_environments.cartpole_tds_env:CartpolePyTinyDiffSim and max_episode_steps 200 | upstream_code | python/tds_environments/__init__.py:12-17 |
| The wrapper creates pytinydiffsim.CartpoleEnv | upstream_code | python/tds_environments/cartpole_tds_env.py:14 |
| The action space is a one-dimensional Box bounded by +-force_mag, and force_mag is 10 | upstream_code | python/tds_environments/cartpole_tds_env.py:30-35 |
| x_threshold is 0.4 and theta_threshold_radians is 12 degrees; the observation space is a four-element Box with high [x_threshold*2, float32 max, theta_threshold*2, float32 max] | upstream_code | python/tds_environments/cartpole_tds_env.py:19-28 |
| step passes action[0] to the wrapped environment and returns its observation with reward 1.0 and the done flag | upstream_code | python/tds_environments/cartpole_tds_env.py:65-73 |
| reset returns the wrapped environment's reset state as the observation | upstream_code | python/tds_environments/cartpole_tds_env.py:75-79 |
| seed masks the seed to 32 bits, seeds the wrapped environment and returns [seed] | upstream_code | python/tds_environments/cartpole_tds_env.py:49-55 |
| The compiled step2 returns the observation in [q0, q1, qd0, qd1] order when COMPATIBILITY is not defined | upstream_code | examples/environments/cartpole_environment2.h:221-242 |
| A reset draws every state value uniformly from -0.05 to 0.05 with std::rand | upstream_code | examples/environments/cartpole_environment2.h:182-192 |
| The seed method calls std::srand(s) for the wrapped environment | upstream_code | examples/environments/cartpole_environment2.h:216-219 |
| The simulation timestep is 1/60 s | upstream_code | examples/environments/cartpole_environment2.h:27 |
| The world gravity is (0, 0, -10) | upstream_code | examples/environments/cartpole_environment2.h:37 |
| The constructor sets action_high_ = 10 and action_low_ = -action_high_ | upstream_code | examples/environments/cartpole_environment2.h:172-173 |
| The C++ step clips the action to action_low_ and action_high_ | upstream_code | examples/environments/cartpole_environment2.h:285-291 |
| The C++ step sets reward 1 and done when the cart position is beyond +-0.4 or the pole angle is beyond +-12 degrees | upstream_code | examples/environments/cartpole_environment2.h:298-307 |
| The cart has mass 1 and the pole has mass 0.1 with its inertial origin at 0.5 m | upstream_code | examples/environments/cartpole_urdf.h:38-65 |
| The pole is a 1.0 m box with iyy 0.00835 | upstream_code | examples/environments/cartpole_urdf.h:52-65 |

Observation layout: the wrapper's declared observation_space high vector follows the classic
`[x, x_dot, theta, theta_dot]` order (`cartpole_tds_env.py:19-28`), while the compiled `step2` returns
`[q0, q1, qd0, qd1]`, the position and rate pairs of the slider and the pole
(`examples/environments/cartpole_environment2.h:221-242`, `:301-307`).  The driver reports the compiled order
unchanged; the declared high vector is not used to reinterpret it.

Limits: the driver declares no limit.  The only envelope is the action space that the bridge derives from the
environment: `action.values` is one float bounded by -10 and 10 (`cartpole_tds_env.py:30-35`).  The device is
simulated (R0), so no limit is `operator_required`.  The C++ environment clips to the same bounds
(`cartpole_environment2.h:172-173`, `:285-291`), so the runtime refusal is a stricter duplicate of the device's own
clip, not a new limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `tds:pytinydiffsim.CartpoleEnv`, level F1, determinism
`seeded` with `seed_control` `parameter`, timestep 1000/60 ms (`cartpole_environment2.h:27`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say that the fake is an analytic cart-pole, not the
TDS engine, that its random stream differs from upstream, and that the 200-step TimeLimit wrapper is not reproduced.

Mock path: the card prefers `upstream-sim`; the upstream simulator is the `sim` backend that GymnasiumDriver would open
with `gymnasium.make("CartpolePyTinyDiffSim-v0")` (the bridge falls back to the legacy `gym` package).  That path needs
the compiled `pytinydiffsim` extension and `tds_environments` imported for its registration side effect, and it was
not run.  The gate runs the package's own fake backend (`fake.py`), a pure Python cart-pole.

Coverage: one device class, the first confirmed entry symbol, `CartpolePyTinyDiffSim-v0`.  The second entry symbol
`tds_environments.reacher_tds_env:ReacherPyTinyDiffSim` (registered as ReacherPyTinyDiffSim-v0 at
`python/tds_environments/__init__.py:19-24`) is not bound by this package.  The card's `models[0]`
(`data/swimmer/swimmer05/model.xml`) is a scene model, not an environment of this driver, and is not used.

Safety: simulated R0 device.  The e-stop is the runtime's software latch; after it no step, reset or seed is accepted
until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the environment state stays
readable.

Tags: cartpole, tds, differentiable-simulation, reinforcement-learning, simulation, gym
