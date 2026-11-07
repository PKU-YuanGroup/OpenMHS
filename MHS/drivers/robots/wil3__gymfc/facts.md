# Facts and tags for gh.wil3/gymfc

Every fact cites its source at commit `08df94b06a5d7f8fb6d2cb2c155751f5336720e7` (`vendor_doc` is documentation text
of the clone, `upstream_code` is code or a comment). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GymFC uses Gazebo v10.1.0 with Dart v6.7.0 as the backend simulator | vendor_doc | README.md:97 |
| FlightControlEnv is a generic OpenAI flight control gym environment; a subclass must set the OpenAI gym action_space and observation_space attributes | upstream_code | gymfc/envs/fc_env.py:107-119 |
| The constructor connects an asyncio UDP datagram endpoint to the Aircraft plugin's host and port | upstream_code | gymfc/envs/fc_env.py:167-174 |
| The simulator starts gzserver with the configured world file | upstream_code | gymfc/envs/fc_env.py:488-493 |
| step_sim runs one asynchronous simulation step and returns the flattened observation | upstream_code | gymfc/envs/fc_env.py:237-248 |
| reset sends an Action_pb2.Action.RESET message to the simulator and returns the observation | upstream_code | gymfc/envs/fc_env.py:548-560 |
| The default configuration selects attitude.world | upstream_code | gymfc/gymfc.ini:7 |
| The configured attitude.world declares the Dart physics engine and a max_step_size of 0.001 s | upstream_code | gymfc/envs/assets/gazebo/worlds/attitude.world:14-16 |
| FlightControlEnv.sdf_max_step_size reads the world's physics max_step_size element and returns its float value as the simulation step size | upstream_code | gymfc/envs/fc_env.py:499-510 |
| BaseEnv declares a four-element Box action space between -np.ones(4) and np.ones(4), i.e. -1 and 1 | upstream_code | examples/gymfc_nf/envs/base.py:37 |
| BaseEnv.step maps the action with action_to_control_signal(action, 0, 1), so each element is clipped to [0, 1] before it becomes a motor control signal despite the [-1, 1] action space | upstream_code | examples/gymfc_nf/envs/base.py:79 |
| action_to_control_signal clips the action to [action_low, action_high] and maps it linearly to [y_low, y_high] | upstream_code | examples/gymfc_nf/envs/base.py:107-116 |
| The observation space is an unbounded Box (-inf to inf) with as many elements as the state function returns | upstream_code | examples/gymfc_nf/envs/base.py:39-41 |
| BaseEnv.step returns (state, reward, done, {}) and sets done when sim_time reaches max_sim_time | upstream_code | examples/gymfc_nf/envs/base.py:67-105 |
| BaseEnv.reset re-initialises the state arrays, resets the simulator and returns state_fn(self); seed() initialises the environment generator through gym.utils.seeding | upstream_code | examples/gymfc_nf/envs/base.py:144-152 |
| StepEnv generates step setpoints: it holds a sampled target for pulse_width seconds and then returns to zero | upstream_code | examples/gymfc_nf/envs/step.py:46-54 |
| StepEnv.reset samples a new target with the seeded generator as np_random.normal(0, max_rate, size=3) | upstream_code | examples/gymfc_nf/envs/step.py:56-68 |
| The registered state function state_degrees_error_deltaerror returns the measured angular-rate error and its delta, six values in total | upstream_code | examples/gymfc_nf/envs/states.py:19-21 |
| gymfc_nf-step-v1 is registered with max_rate 100, pulse_width 2.048 s, max_sim_time 4.608 s and that state function | upstream_code | examples/gymfc_nf/envs/__init__.py:6-14 |
| RewardEnv.compute_reward combines an angular-rate error shaping term, control-output and oscillation penalties, an error-band reward and a doing-nothing penalty | upstream_code | examples/gymfc_nf/envs/rewards.py:33-77 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-np.ones(4), np.ones(4))` at `examples/gymfc_nf/envs/base.py:37`: `action.values` from -1 to 1 per element, with
the source `upstream_code` and the ref `examples/gymfc_nf/envs/base.py:37`), and `ticks` (1 to `max_ticks`, 10000 by
default, from the bridge). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gazebo`, level F1 (rigid-body dynamics with contacts in
the upstream simulator; the package's fake is a reduced stand-in), determinism `seeded` with `seed_control`
`parameter`, timestep 1 ms (`max_step_size` 0.001 s, `attitude.world:16`), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say that the fake does not reproduce the Gazebo/Dart dynamics, the
sensors, noise, the UDP channel or the digital twin, that no wall-clock pacing is modelled, and that the fake was not
compared with the upstream simulator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the environment has no native stop); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the state stays readable.

Tags: gymfc, flight-control, attitude-control, reinforcement-learning, gazebo, simulation
