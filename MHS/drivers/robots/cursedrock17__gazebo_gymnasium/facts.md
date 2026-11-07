# Facts and tags for gh.cursedrock17/gazebo_gymnasium

Every fact cites its source at commit `a9d142db85b619a299a7eb29461532cade1c20ac`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a code/comment line of the clone).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Scope and card deviation

The task card says `family: ros` / `helper: RosDriver`, but the confirmed entry symbol is a standard Gymnasium
environment: `gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:49` (`class GazeboEnv(gym.Env)`).
`GazeboEnv` builds one in-process `InProcessHarnessVecEnv` from an `AgentSpec` and exposes the Gymnasium
`reset`/`step` interface (`gym_env.py:54-79`).  The repository's ROS 2 packages supply message types and launch
files around the environment; they are not the environment's transport.  The package therefore uses
`GymnasiumDriver` and serves the shipped `GazeboCartPole-v0` registration.  No ROS endpoint or type is invented.

## Facts

| fact | source | ref |
|---|---|---|
| gazebo_gymnasium_bridge documents reinforcement-learning agents training in Gazebo through the standard Gymnasium API | vendor_doc | README.md:3-4 |
| The clone targets Linux x86-64 only and its locked environment provides ROS 2 Jazzy and Gazebo Harmonic | vendor_doc | README.md:61-63 |
| The Pixi environment supplies Gazebo Harmonic with its gz.sim Python bindings | vendor_doc | README.md:71-72 |
| The registered env ids map GazeboCartPole-v0 to the cartpole agent spec; GazeboCartPoleContinuous-v0 is a separate registration | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:37-46 |
| register_envs registers each id with entry point gazebo_gymnasium_bridge.envs.gym_env:GazeboEnv and kwargs {'agent': agent} | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:92-99 |
| GazeboEnv.__init__ takes agent='cartpole' by default, reads its spaces from get_spec(agent), and builds InProcessHarnessVecEnv with n_agents=1 and autoreset=False | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:54-64 |
| GazeboEnv.reset calls gym.Env.reset(seed=seed), seeds the vector environment only when a seed is given, calls its reset(), and returns the first observation with an empty info dictionary | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:66-71 |
| GazeboEnv.step sends one action through step_async/step_wait, pops TimeLimit.truncated from info, reports terminated only when done and not truncated, and returns the five-value Gymnasium tuple | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py:73-79 |
| _cartpole_action_to_commands rounds the action to an integer and commands a slider_to_cart force of +_CART_FORCE (10.0) for action 1 and -10.0 for any other action | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:740-749 |
| The cartpole spec declares action_space=spaces.Discrete(2) | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:773 |
| The cartpole observation space is Box with low [-4.8, -inf, -0.41887903, -inf], high [4.8, inf, 0.41887903, inf] and shape (4,), in float32 | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:762-767 |
| The observation order is cart position, cart velocity, pole angle and pole angular velocity from the slider_to_cart and cart_to_pole joints | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:774-775 |
| Cartpole reset puts the cart at zero position and velocity and draws the pole angle uniformly from -0.05 to 0.05 with zero angular velocity | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:752-758 |
| The cartpole pole-angle threshold is 0.20944 and the cart-position threshold is 2.4 | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:730-731 |
| The cartpole terminated_fn returns true when the absolute pole angle or the absolute cart position exceeds its threshold | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:776-779 |
| The cartpole reward function always returns 1.0 | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:776 |
| AgentSpec defaults frame_skip to 5 physics ticks per environment step and max_episode_steps to 500 | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:221-222 |
| The in-process world sets a 0.01 s maximum physics step and real_time_factor 0 | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:56-59 |
| step_wait calls _step_server(self.frame_skip) in both its image and its non-image branch | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:1115-1121 |
| _step_server calls self._server.run(True, ticks, False) and does not use its return value | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:810-814 |
| InProcessHarnessVecEnv truncates at max_episode_steps and sets info['TimeLimit.truncated'] only when the episode truncated without terminating | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:1168-1181 |
| InProcessHarnessVecEnv.seed replaces its generator with numpy.random.default_rng(seed) | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:1225-1227 |
| The reset path passes that generator into Core.reset_agent for each reset agent | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:816-823 |
| Core.reset_agent calls reset_joint_state(rng) and applies every returned joint position and velocity | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/harness/harness_core.py:317-324 |
| InProcessHarnessVecEnv imports the native gz.sim8 bindings in its constructor | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:476-480 |
| The constructor writes the generated world SDF to a tempfile.mkstemp file, hosts it in gz_sim.TestFixture with pre- and post-update callbacks, and steps the server once | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:769-779 |
| The constructor prints a ready line naming the agent, n_agents and frame_skip | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:802-806 |
| close() unsubscribes the camera topics in image mode and removes the temporary world file; it calls no method of the TestFixture or its server | upstream_code | gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py:1190-1207 |
| The cartpole_bare model is an SDF with a prismatic slider_to_cart joint limited to -4..4, a revolute cart_to_pole joint with effort 1000 and velocity 8, and mass-1 slider, cart and pole links | upstream_code | gazebo_gymnasium_examples/gazebo_gymnasium_resources/models/cartpole_bare/model.sdf:9-46 |

## Limits

The driver declares no `Limit` of its own.  The only action bound is derived by the Gymnasium bridge from the
served action space: `action_space_ref = "gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py:773"`
defines `spaces.Discrete(2)`, so `cap.world.step.v1` accepts `action.index` 0 or 1 (`upstream_code`).  `ticks` is
bounded by the family's `max_ticks` (1 to 10000 by default), a bridge limit, not a device fact.  The device is
simulated at R0, so no limit is `operator_required` and no `site-limits.example.json` is needed.

## Fidelity contract

`engine` is the package's analytic cartpole fake; `fidelity_level` is F0 because the fake has no Gazebo physics,
contacts or actuator model, `determinism.kind` is `seeded` with `seed_control` `parameter`, `timestep_ms` is 50 ms
(5 frame-skip ticks times the 0.01 s maximum physics step), `realtime_factor` is 0, `clock` is `lockstep`, `reset` is
`full`, and `snapshot_restore` is false.  The gaps state that the equations and constants are placeholders, that
Python's `random.Random` differs from the upstream `numpy.random.default_rng`, that no rendering or camera
environment is served, that only `GazeboCartPole-v0` is covered, and that no Gazebo or ROS graph was opened.
Model review (2026-11-05) added three gaps: the upstream reset steps one 0.01 s tick before its first observation; the
upstream step ignores the boolean return of `server.run`; and live construction, never run here, would host gz-sim
inside the server process, write a temporary world SDF, print a ready line to standard output (which corrupts an MHS
server that speaks over stdio) and leave the TestFixture server alive on `close()`.

## Safety

Simulated R0 device.  There is no native hardware stop and no physical e-stop reference; the runtime's software
e-stop latch refuses every subsequent step and reset until `mhs.safety.reset` clears it, and the last observation
and world state remain readable.  Normal safe-state invocation does not command a robot or a physical actuator.
The upstream in-process world is lockstep: `_step_server` runs the server for a fixed number of ticks with
`server.run(True, ticks, False)` (`inprocess_vec_env.py:810-814`), so a refused step leaves it where it was.

Tags: gymnasium, gazebo, gz-sim, cartpole, reinforcement-learning, simulation
