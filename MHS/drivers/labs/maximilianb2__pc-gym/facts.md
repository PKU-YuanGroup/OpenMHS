# Facts and tags for gh.maximilianb2/pc-gym

Every fact cites its source at commit `fbfb36bf84b494cd157cff88292e1fd1b864cee5`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). Copy each fact into
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| make_env is a Gymnasium environment class: the module imports gymnasium as gym and gymnasium's spaces, and the class subclasses gym.Env | upstream_code | src/pcgym/pcgym.py:3-5 |
| Users create the environment with make_env(env_params), where env_params is a dictionary | upstream_code | src/pcgym/pcgym.py:32 |
| env_params['model'] selects the process model by name, and the mapping binds 'cstr' to the cstr class | upstream_code | src/pcgym/pcgym.py:146-147 |
| The cstr model's states are Ca and T and its single input is Tc | upstream_code | src/pcgym/model_classes.py:41-44 |
| The CSTR balances are dcadt = q/V * (Caf - ca) - k0 * exp(-EA/R/T) * ca and dTdt = q/V * (Ti - T) - deltaHr * rA / (rho * C) + UA * (Tc - T) / (rho * C * V) | upstream_code | src/pcgym/model_classes.py:46-63 |
| The cstr default parameters are q=100, V=100, rho=1000, C=0.239, deltaHr=-5e4, EA_over_R=8750, k0=7.2e10, UA=5e4, Ti=350 and Caf=1 | upstream_code | src/pcgym/model_classes.py:25-34 |
| normalise_a and normalise_o default to True | upstream_code | src/pcgym/pcgym.py:61-62 |
| With normalisation the action space is Box(low=-1, high=1) with a dimension per a_space input (one for the CSTR) | upstream_code | src/pcgym/pcgym.py:70-72 |
| With normalisation the observation space is Box(low=-1, high=1) with a dimension per o_space bound (three in the README configuration) | upstream_code | src/pcgym/pcgym.py:82-84 |
| The simulation timestep is dt = tsim / N | upstream_code | src/pcgym/pcgym.py:104 |
| The README quick-start configuration sets nsteps=100 time steps over T=25 simulation seconds, a jacket-temperature action range of 295 to 302, observation bounds [0.7, 300, 0.8] to [1, 350, 0.9], initial state [0.8, 330, 0.8] and model 'cstr' | vendor_doc | README.md:23-45 |
| The README quick-start setpoint is 0.85 for the first 50 steps and 0.9 for the last 50 | vendor_doc | README.md:26-27 |
| step denormalises the action to the a_space range as (action + 1) * (high - low) / 2 + low | upstream_code | src/pcgym/pcgym.py:382-385 |
| step advances the model's ODE with the integration engine: casadi_step when integration_method is casadi and jax_step when it is jax | upstream_code | src/pcgym/pcgym.py:436-440 |
| step writes the setpoint value for each SP key at index t into the state after each transition | upstream_code | src/pcgym/pcgym.py:442-449 |
| step sets done when t reaches N-1 | upstream_code | src/pcgym/pcgym.py:459-460 |
| step returns (observation, reward, done, False, info) | upstream_code | src/pcgym/pcgym.py:508 |
| With SP set and no custom reward the reward is -sum over the SP states of (state - setpoint)^2 scaled by r_scale | upstream_code | src/pcgym/pcgym.py:544-560 |
| The CSTR documentation gives the observation space bounds as [[0.7,1],[300,350],[0.8,0.9]] | vendor_doc | docs/env/cstr.md:40-42 |
| The CSTR documentation describes the action as a ContinuousBox of [290,302], the jacket temperature in kelvin | vendor_doc | docs/env/cstr.md:49-50 |

Limits: the driver declares none. The only bound is the environment's action space, which the bridge derives from the
served environment: with `normalise_a` at its default the CSTR action space is `Box(-1, 1)` and `cap.world.step.v1`
bounds `action.values[0]` to -1..1. The derived limit carries source `upstream_code` and the ref
`src/pcgym/pcgym.py:72`; the -1..1 bounds come from the normalised action space of `src/pcgym/pcgym.py:70-72`. The
device is simulated (R0), so no limit is `operator_required` and no site-limits overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pcgym:cstr`, level F1 (the CSTR ODE balances are
integrated; no contacts, actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`
(reset restores the fixed x0 and echoes the seed, but the served configuration has no randomness), timestep 250 ms
(`dt = tsim / N = 25 / 100` s, `src/pcgym/pcgym.py:104` with the README values), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that this package's fake was
not compared with a real pc-gym run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: cstr, process-control, reinforcement-learning, simulation, gymnasium
