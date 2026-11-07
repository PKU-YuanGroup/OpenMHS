# Facts and tags for gh.metadriverse/metadrive

Every fact cites its source at commit `325d9e2f9c20e495bde66f30e0ef2b40efbce39c`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MetaDrive is a driving simulator with synthesised road maps and traffic, sensor simulation, and point-cloud, RGB/depth/semantic, top-down map and first-person view inputs | vendor_doc | README.md:35-39 |
| The documented usage imports MetaDriveEnv, calls reset() for (obs, info), calls step() for the five-value (obs, reward, terminated, truncated, info) tuple and calls close() | vendor_doc | README.md:106-117 |
| BaseEnv subclasses gymnasium.Env, so MetaDriveEnv (a BaseEnv) is a Gymnasium environment | upstream_code | metadrive/envs/base_env.py:279 |
| BaseEnv.step takes one action (or a per-agent dict), preprocesses it, steps the simulator and returns through _get_step_return | upstream_code | metadrive/envs/base_env.py:435-440 |
| For a single agent, _get_step_return returns observation, reward, terminated and truncated values and an info dict | upstream_code | metadrive/envs/base_env.py:638-643 |
| BaseEnv.reset(seed) resets the simulation, clears the episode counters and returns _get_reset_return(reset_info) | upstream_code | metadrive/envs/base_env.py:512-547 |
| The reset seed is applied through _reset_global_seed(seed) | upstream_code | metadrive/envs/base_env.py:523-524 |
| The seed(seed) method calls set_global_random_seed(seed) | upstream_code | metadrive/envs/base_env.py:684-686 |
| When discrete_action is False, the input space is a Box from -1.0 to 1.0 with shape (2,) | upstream_code | metadrive/policy/env_input_policy.py:61-62 |
| The continuous action is converted to a (steering, throttle) pair and clipped to -1.0..1.0 | upstream_code | metadrive/policy/env_input_policy.py:34-48 |
| discrete_action defaults to False | upstream_code | metadrive/envs/base_env.py:60-61 |
| The state observation is a Box from -0.0 to 1.0 whose width is ego_state_obs_dim (6) plus the navigation dimension plus the line-detector dimension | upstream_code | metadrive/obs/state_obs.py:9-28 |
| The default lidar state observation adds the lidar rays (num_lasers plus 4 * num_others) to the state width and is likewise bounded by 0.0..1.0 | upstream_code | metadrive/obs/state_obs.py:175-186 |
| The default vehicle lidar has 240 lasers, 0 others and a 50 m distance | upstream_code | metadrive/envs/base_env.py:170 |
| The navigation constants are NUM_WAY_POINT 2 and CHECK_POINT_INFO_DIM 5 | upstream_code | metadrive/component/navigation_module/base_navigation.py:18-19 |
| A physics step is 0.02 s and decision_repeat repeats it 5 times per env.step, so one environment step advances 0.1 s of simulated time | upstream_code | metadrive/envs/base_env.py:189-191 |
| The default horizon is 1000 environment steps | upstream_code | metadrive/envs/metadrive_env.py:58 |
| MAX_STEP is true when episode_lengths reaches the horizon | upstream_code | metadrive/envs/metadrive_env.py:133-145 |
| truncated is derived from the MAX_STEP entry of the step info | upstream_code | metadrive/envs/base_env.py:623-625 |
| start_seed defaults to 0 and num_scenarios to 1 | upstream_code | metadrive/envs/metadrive_env.py:18-19 |
| The default map is 3 blocks with lane width 3.5 and 3 lanes | upstream_code | metadrive/envs/metadrive_env.py:22-30 |
| close() closes the engine when one exists | upstream_code | metadrive/envs/base_env.py:645-647 |
| The generic install requirements contain no serial, VISA, USB or vendor hardware SDK | upstream_code | setup.py:39-52 |

## Limits

The driver declares no explicit `Limit`.  The only bound is the action space the gymnasium bridge derives from the
environment: the default `Box(-1.0, 1.0, shape=(2,))` gives `cap.world.step.v1` the per-element bounds -1.0 and 1.0
on `action.values`, and the bridge refuses a value outside them with `MHS.SAFETY.ENVELOPE_VIOLATION` before calling
`step()` (the source of the bounds is `metadrive/policy/env_input_policy.py:61-62`).  The device is simulated (R0),
so no bound is `operator_required` and there is no hardware overlay to narrow.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `analytic`, level F0 (a kinematic fake with no dynamics), determinism `seeded`
with `seed_control` `parameter`, timestep 100 ms (one environment step is 5 x 0.02 s), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore.  The gaps say that the package's fake is not the upstream Panda3D
simulator: it has no map, traffic, contacts, actuator, sensor or noise model, its 259-float observation is synthetic,
it integrates one 0.1 s step per tick, it has no rendering or wall-clock pacing, reset `options` are not applied by
the upstream `reset(seed)` signature, snapshots are not offered, and it was never compared with upstream or a
vehicle.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it no step or reset is accepted until
`mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the world state stays readable.
No hardware backend exists, so no physical e-stop applies.

## Tags

driving-simulator, reinforcement-learning, simulation, gymnasium, world-model
