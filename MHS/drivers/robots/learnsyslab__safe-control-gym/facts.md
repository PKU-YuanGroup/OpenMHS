# Facts and tags for gh.learnsyslab/safe-control-gym

Every fact cites its source at commit `6b5391d014f36fdfa0f9d22d92c77387e5274308`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone:LINE`). The same facts are written into `facts = [...]` in `driver.py`; `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered under the id 'cartpole' with entry point 'safe_control_gym.envs.gym_control.cartpole:CartPole' | upstream_code | safe_control_gym/envs/__init__.py:5-7 |
| CartPole extends BenchmarkEnv, the benchmark's base gymnasium environment | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:29 |
| CartPole is a physics-based environment that uses PyBullet | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:1-8 |
| The action space is a one-element Box with low -10 and high 10; the physical action bounds are also -10 and 10 and the action unit is N unless normalized_rl_action_space is set | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:439-447 |
| A control action is denormalized when needed, disturbed, and clipped to the physical action bounds before it is applied | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:479-500 |
| The state and observation labels are x, x_dot, theta and theta_dot with units m, m/s, rad and rad/s | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:475-477 |
| The state and observation spaces are Box spaces bounded by +-4.8 for x, +-20 for x_dot, +-pi for theta and +-20 for theta_dot; the state bound is twice the failure threshold | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:449-473 |
| The failure thresholds are +-2.4 for the cart position and +-90 degrees (pi/2 rad) for the pole angle | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:452-454 |
| The stabilization goal tolerance is 0.05 in the state norm | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:115-123 |
| The episode terminates when the cart position or the pole angle passes its threshold, or when the stabilization goal is reached | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:654-672 |
| The default reward is the exponential of the negative quadratic state error plus an action penalty, so it lies in (0, 1] | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:611-635 |
| The default physics and control frequencies are both 50 Hz | upstream_code | safe_control_gym/envs/benchmark_env.py:64-65 |
| The control timestep is 1/ctrl_freq = 0.02 s and the physics timestep is 1/pyb_freq; the default frequencies give one physics step per control step | upstream_code | safe_control_gym/envs/benchmark_env.py:143-145 |
| The default episode length is 5 s | upstream_code | safe_control_gym/envs/benchmark_env.py:66 |
| after_step marks the episode done at the control-step limit and records info['TimeLimit.truncated'] when it was not already done | upstream_code | safe_control_gym/envs/benchmark_env.py:497-501 |
| The initial state is randomized by default (randomized_init=True) | upstream_code | safe_control_gym/envs/benchmark_env.py:69 |
| The initial-state randomization draws x, x_dot, theta and theta_dot uniformly from (-0.05, 0.05) | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:88-112 |
| BenchmarkEnv.seed seeds numpy's generator and the action space and returns the seed | upstream_code | safe_control_gym/envs/benchmark_env.py:193-214 |
| reset accepts an optional seed and passes it to before_reset, which reseeds when it is not None | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:266-279 |
| step returns the legacy (observation, reward, done, info) tuple; done covers failure, goal and the time limit | upstream_code | safe_control_gym/envs/gym_control/cartpole.py:238-264 |

Limits: the driver declares none. The only bounds are derived from the environment's action space by the Gymnasium
bridge: `action.values` from the one-element `Box(-10, 10)`, and `ticks` from the bridge's `max_ticks` (1 to 10000).
The device is simulated (R0), so no limit is `operator_required`, and there is no hardware stop path.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `safe-control-gym:cartpole`, level F1 (rigid-body
dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (1/50 s, `benchmark_env.py:143-145`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that
the package's pure Python fake was not compared with the upstream PyBullet environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
last state stays readable.

Tags: cartpole, safe-control-gym, pybullet, reinforcement-learning, simulation, gymnasium
