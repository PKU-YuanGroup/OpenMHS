# Facts and tags for gh.sryu1/jsbgym

Every fact cites its source at commit `80adc75514ac2cf2d7120cc436a1cbfa49ba0bc8`: `vendor_doc` (README.md) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| JSBGym provides reinforcement learning environments for the control of fixed-wing aircraft using the JSBSim flight dynamics model and implements the Gymnasium interface | vendor_doc | README.md:8 |
| The documented use is gym.make(ENV_ID), then env.reset() and env.step(action), which returns observation, reward, terminated, truncated and info | vendor_doc | README.md:67-73 |
| The FlightGear-disabled Cessna 172 HeadingControlTask environment is registered as C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0 | vendor_doc | README.md:129 |
| The observation is an 11-tuple: altitude, pitch, roll, body velocities u, v, w, body rates p, q, r, altitude error and track error | vendor_doc | README.md:158-172 |
| Actions are 3-tuples of floats in the range [-1, +1] describing the aileron, elevator and rudder commands | vendor_doc | README.md:174-180 |
| The state space is a Box built from each state variable's min and max with dtype float64 | upstream_code | jsbgym/tasks.py:231-234 |
| The action space is a Box built from each action variable's min and max with dtype float64 | upstream_code | jsbgym/tasks.py:236-239 |
| The HeadingControlTask action variables are the aileron, elevator and rudder commands | upstream_code | jsbgym/tasks.py:279 |
| The altitude bound is -1400 to 85000 ft, the pitch bound is -pi/2 to pi/2 and the roll bound is -pi to pi | upstream_code | jsbgym/properties.py:19-26 |
| The body-frame velocity bounds u, v and w are -2200 to 2200 ft/s | upstream_code | jsbgym/properties.py:40-48 |
| The body-rate bounds p, q and r are -2*pi to 2*pi rad/s | upstream_code | jsbgym/properties.py:58-66 |
| The aileron, elevator and rudder command bounds are -1.0 to 1.0 | upstream_code | jsbgym/properties.py:93-101 |
| The task's nine base state variables are altitude, pitch, roll, u, v, w, p, q and r | upstream_code | jsbgym/tasks.py:98-108 |
| The HeadingControlTask state adds the altitude error and the track error to the nine base variables | upstream_code | jsbgym/tasks.py:301-307 |
| The altitude error is bounded by the altitude bounds and the track error is bounded -180 to 180 deg | upstream_code | jsbgym/tasks.py:270-278 |
| The initial altitude is 5000 ft | upstream_code | jsbgym/tasks.py:97 |
| The initial heading is 270 deg | upstream_code | jsbgym/tasks.py:256 |
| The default episode time is 60 s | upstream_code | jsbgym/tasks.py:257 |
| The default agent interaction frequency is 5 Hz | upstream_code | jsbgym/environment.py:35 |
| The episode step budget is ceil(episode_time_s * step_frequency_hz) agent steps and steps_left is bounded 0 to that budget | upstream_code | jsbgym/tasks.py:295-299 |
| Each task step decrements steps_left and the task terminates when steps_left is zero or less, the last assessment reward is below MIN_STATE_QUALITY, or the altitude error exceeds MAX_ALTITUDE_DEVIATION_FT | upstream_code | jsbgym/tasks.py:418-431 |
| MIN_STATE_QUALITY is 0.0 and MAX_ALTITUDE_DEVIATION_FT is 1000 ft | upstream_code | jsbgym/tasks.py:262-263 |
| JSBSim integrates at 60 Hz and the environment runs JSBSIM_DT_HZ // agent_interaction_freq integration steps per agent step | upstream_code | jsbgym/environment.py:25-57 |
| The environment rejects an agent interaction frequency above JSBSIM_DT_HZ | upstream_code | jsbgym/environment.py:50-55 |
| The environment constructs the task with the agent interaction frequency and then takes the observation and action spaces from the task | upstream_code | jsbgym/environment.py:59-62 |
| step() calls the task for sim_steps_per_agent_step integration steps and returns observation, reward, terminated, False and info | upstream_code | jsbgym/environment.py:96-100 |
| reset(seed, options) seeds the environment, reinitialises or creates the simulation and returns the first observation and an info dict | upstream_code | jsbgym/environment.py:102-134 |
| NoFGJsbSimEnv is the training variant: it constructs the simulation with allow_flightgear_output=False | upstream_code | jsbgym/environment.py:225-246 |
| The package registers every aircraft/task/shaping setting and uses NoFGJsbSimEnv as the entry point when FlightGear is disabled | upstream_code | jsbgym/__init__.py:18-29 |
| Environment ids are built as aircraft-task-shaping-FG or NoFG-v0 | upstream_code | jsbgym/utils.py:39-51 |
| The simulation constructs an in-process jsbsim.FGFDMExec and sets sim_dt to 1/sim_frequency_hz | upstream_code | jsbgym/simulation.py:39-46 |

Limits: the driver declares none of its own. The only bounds are derived by the Gymnasium bridge from the
environment's spaces: `action.values` per element from the three control-surface commands (`Box(-1, +1, (3,))`,
`properties.py:93-101`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no
bound is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `jsbgym:JSBSim flight dynamics
(C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0)`, level F0 because the package deploys a kinematic stand-in and
does not execute JSBSim; determinism `seeded` with `seed_control` `parameter`; timestep 200 ms (one agent
interaction: 12 integration steps of 1/60 s, `environment.py:25-57`); `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps state the missing aerodynamics, the placeholder reward, the lack of
pacing, rendering and snapshot/restore, and that the fake was never compared with a JSBSim run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it step,
reset and seed are refused until `mhs.safety.reset` clears the latch, and the last observation stays readable.

Tags: fixed-wing, flight-control, jsbsim, reinforcement-learning, simulation, gymnasium

Honest limits of this package:

- The fake is a hand-written kinematic stand-in, not JSBSim and not a recorded JSBSim transcript. Its observation,
  reward and terminal behaviour are test data; only the interface shape and the action space come from the upstream
  environment.
- The upstream package needs Python 3.10 or newer plus numpy, gymnasium, jsbsim and matplotlib
  (`pyproject.toml:22-23`); none of them is installed where the gate runs, and the package never imports or installs
  the clone. The `sim` backend (`gymnasium.make(env_id)`) was not run.
- The seed is accepted and recorded, but the default HeadingControlTask initial conditions are fixed, so a seed
  alone does not change the first observation.
