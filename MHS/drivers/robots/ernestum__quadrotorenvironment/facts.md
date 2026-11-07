# Facts and tags for gh.ernestum/quadrotorenvironment

Every fact cites its source at commit `597f8e3294c6a5d3ffc6907749f94a97dee700f3`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| QuadrotorEnvironment is a Gym environment that simulates a quadrotor; it is not a hardware interface | upstream_code | quadrotor_environment/quadrotor_environment.py:26-28 |
| The action space is Box(-1, 1, (4,), dtype float32): four continuous command values in [-1, 1] | upstream_code | quadrotor_environment/quadrotor_environment.py:132 |
| step() returns (observation, reward, done, {}) and done is delayed_model.time >= max_time | upstream_code | quadrotor_environment/quadrotor_environment.py:178 |
| The max_time constructor default is 10 seconds and the controller_period default is 0.01 seconds | upstream_code | quadrotor_environment/quadrotor_environment.py:58 |
| The default initial state parameters are box_side_length 2, velocity 1 and angular_velocity 1 | upstream_code | quadrotor_environment/quadrotor_environment.py:57 |
| random_state draws the position uniformly from [-box_side_length, box_side_length], the velocity and angular velocity uniformly from their bounds, a random rotation, and sets all four propeller speeds to the hovering speed | upstream_code | quadrotor_environment/quadrotor_environment.py:187-194 |
| QuadrotorEnvironment.step computes the reward from the current state before advancing the model when reward_base is 'current_state' (the default) | upstream_code | quadrotor_environment/quadrotor_environment.py:151-153 |
| SPRWrappedQuadrotorEnvironment is a second Gym wrapper around the same environment that may replace a value with a ('randomize', low, high) triple on each reset | upstream_code | quadrotor_environment/simulation_parameter_randomization.py:30-38 |
| QuadrotorModel defaults: gravity 9.80665 m/s^2, mass 1.43805 kg, moments of inertia (0.01467, 0.01441, 0.02441), propeller half side length 0.16 m, thrust coefficient 1.018841e-5, propeller inertia coefficient 6.32180911740998e-09 and drag coefficient 4.82e-8 | upstream_code | quadrotor_environment/quadrotor_model.py:41-48 |
| The hovering speed is sqrt((mass * gravity / thrust coefficient) / 4) | upstream_code | quadrotor_environment/quadrotor_model.py:74 |
| QuadrotorModel is an explicit model that does not rely on euler or RK-4 integration | upstream_code | quadrotor_environment/quadrotor_model.py:34-37 |
| The mixer matrix M maps the squared propeller speeds to three moments and the collective thrust | upstream_code | quadrotor_environment/quadrotor_model.py:65-68 |
| The next propeller speed follows next_prop_rate = x.propeller_speed - (ip ** h - 1) * (u - x.propeller_speed) | upstream_code | quadrotor_environment/quadrotor_model.py:85-86 |
| next_state computes the next position, velocity, rotation and angular velocity for an explicit step of h seconds | upstream_code | quadrotor_environment/quadrotor_model.py:76-109 |
| PropellerSpeedMapping defaults: relative_min_speed 0, relative_max_speed 3, an infinite relative propeller acceleration bound, clip acceleration constraint and direct output control | upstream_code | quadrotor_environment/propeller_speed_mapping.py:13-15 |
| In direct output mode the action element a sets the relative target speed to (a + 1) / 2 * (relative_max_speed - relative_min_speed) + relative_min_speed | upstream_code | quadrotor_environment/propeller_speed_mapping.py:49-52 |
| ModelDelayWrapper defaults: delay_scale 1, controller_period 0.01 seconds and no observation, action or controller delay or jitter | upstream_code | quadrotor_environment/model_delay_wrapper.py:16-23 |
| ModelDelayWrapper.step advances the simulated time by the sampled controller period | upstream_code | quadrotor_environment/model_delay_wrapper.py:134-135 |
| StateClippingWrapper defaults clip velocity to [-5, 5] and angular velocity to [-20, 20] and leave the position unbounded | upstream_code | quadrotor_environment/model_state_clipping_wrapper.py:13-16 |
| ToObservationMap defaults scale position by 0.5, velocity by 0.5 and angular velocity by 0.15, set the propeller speed, dt and observation-age scales to 0, and observe the rotation | upstream_code | quadrotor_environment/observation_mapping.py:22-25 |
| The rotmat_global rotation observation mode returns the rotation matrix flattened row-major | upstream_code | quadrotor_environment/observation_mapping.py:73-74 |
| A zero scale removes that state component from the observation | upstream_code | quadrotor_environment/observation_mapping.py:100-120 |
| The observation concatenates the observed position, velocity, rotation and angular velocity, then the optional propeller speed, dt and observation age | upstream_code | quadrotor_environment/observation_mapping.py:139-145 |
| NoisedStateMap defaults every noise argument to None, so the default observation has no added noise | upstream_code | quadrotor_environment/noise_model.py:24-29 |
| RewardFunction defaults: reward_scale 0.00076, position weights 9.5 horizontal and 2.2 vertical, velocity 0.9/1.5, rotation 2/2, angular velocity 2/2, propeller speed deviation 1 and propeller acceleration 1 | upstream_code | quadrotor_environment/reward_function.py:21-39 |
| The default reward applies inverted huber scaling to the state terms, sums the propeller speed deviation and acceleration terms, and returns the negative scaled sum | upstream_code | quadrotor_environment/reward_function.py:121-129 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1, (4,))`: `action.values` from -1 to 1 per element, with no source and the ref
`action_space of the fake backend .fake:FakeQuadrotorEnvironment`), and `ticks` (1 to `max_ticks`, 10000 by default).
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `custom:quadrotor_environment`, level F1 (explicit
rigid-body dynamics, no contacts, no actuator/sensor noise in the default configuration), determinism `seeded` with
`seed_control` `parameter` (the package fake reseeds from `reset(seed)`; the upstream `reset` has no seed argument and
draws from numpy's global generator), timestep 10 ms (the default `controller_period` of 0.01 s,
`quadrotor_environment.py:58`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
say what is not modelled and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: quadrotor, drone, reinforcement-learning, simulation, gym
