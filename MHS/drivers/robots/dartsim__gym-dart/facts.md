OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.dartsim/gym-dart

Every fact cites its source at commit `bf915eaa3baa70a3a4d0fd42e024694e7825d5fe`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DartCartPole-v0 is registered with entry point gym_dart.envs:DartCartPoleEnv, max_episode_steps=200 and reward_threshold=195.0 | upstream_code | gym_dart/__init__.py:8-14 |
| The observation space is Box(-high, high) with high = [x_threshold * 2, float32 max, theta_threshold_radians * 2, float32 max], where x_threshold is 2.4 and theta_threshold_radians is 12 degrees in radians | upstream_code | gym_dart/envs/dart_cartpole_env.py:13-33 |
| The action space is a one-element Box from -5 to 5 with dtype float32 | upstream_code | gym_dart/envs/dart_cartpole_env.py:59-66 |
| The world timestep is set to 0.01 s and gravity to (0, 0, -9.8) after the skeleton is loaded | upstream_code | gym_dart/envs/dart_cartpole_env.py:35-36 |
| get_state returns [pole angle, pole angular velocity, cart position, cart velocity] | upstream_code | gym_dart/envs/dart_cartpole_env.py:91-94 |
| The initial state limits are +-0.1 in all four dimensions | upstream_code | gym_dart/envs/dart_cartpole_env.py:47-50 |
| The public reset takes no seed and returns only the observation (no info dict) | upstream_code | gym_dart/envs/dart_cartpole_env.py:70-72 |
| reset draws the four state values uniformly from the initial state limits and applies them to the cart and pole positions and velocities | upstream_code | gym_dart/envs/dart_cartpole_env.py:133-139 |
| The reset draw uses numpy's global np.random.uniform | upstream_code | gym_dart/envs/dart_cartpole_env.py:133-135 |
| step sets the cart velocity to the action, clipped into the action-space bounds, and advances the world one timestep | upstream_code | gym_dart/envs/dart_cartpole_env.py:158-168 |
| step returns the legacy 3-tuple (observation, reward, done), not the gymnasium 5-tuple | upstream_code | gym_dart/envs/dart_cartpole_env.py:74-80 |
| The episode is done when the absolute pole angle exceeds theta_threshold_radians, the absolute cart position exceeds 1.0, or current_step reaches max_time_steps | upstream_code | gym_dart/envs/dart_cartpole_env.py:175-186 |
| max_time_steps is 10000 | upstream_code | gym_dart/envs/dart_cartpole_env.py:40 |
| The reward is (theta_threshold - \|pole angle\|) / theta_threshold + exp(-cart position) while the angle is below theta_threshold, otherwise 0.0 | upstream_code | gym_dart/envs/dart_cartpole_env.py:144-156 |

Limits: The checked fake keeps one cart-velocity action value in -5..5. The Gymnasium bridge derives these unchanged action bounds with source `upstream_code` and ref `gym_dart/envs/dart_cartpole_env.py:59-66`, where the same-span ones assignment and Box construction state the bounds. The selected environment and width were source-reviewed separately; symbolic shapes alone do not prove a width. `ticks` remains the SDK bridge budget (1 to max_ticks, 10000 by default), not a device limit. This simulated R0 package declares no operator-required hardware limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym_dart:DartCartPole-v0`, level F1 (a rigid-body
cart-pole model, with no contact, friction, actuator or sensor model), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms (the world is configured with `setTimeStep(0.01)`, `dart_cartpole_env.py:36`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
that the packaged fake is a pure-Python stand-in and was not compared with the upstream environment, and that the
upstream 3-tuple `step()` and seedless `reset()` cannot be served by the gymnasium bridge as committed.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware was attached or claimed.

Tags: cartpole, dart, reinforcement-learning, simulation, gymnasium
