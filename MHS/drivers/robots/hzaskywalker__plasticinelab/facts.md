# Facts and tags for gh.hzaskywalker/plasticinelab

Every fact cites its source at commit `ac1a2f7b0bbbe88706b51bf3aa9d72483e1d05b6`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PlasticineEnv subclasses gym.Env, takes cfg_path, version and nn, builds a Taichi environment and initializes it | upstream_code | plb/envs/env.py:12-18 |
| The environment id is built at import as f'{env_name}-v{id+1}' for ten names and variants 1 to 5, registered with entry_point plb.envs.env:PlasticineEnv, kwargs cfg_path and version, and max_episode_steps 50 | upstream_code | plb/envs/__init__.py:6-13 |
| The README's usage example runs Move-v1 | vendor_doc | README.md:6 |
| The action space is Box(-1, 1, (action_dim,)) and the observation space is Box(-inf, inf, obs.shape) | upstream_code | plb/envs/env.py:25-26 |
| __init__ captures the initial state with taichi_env.get_state() and then calls reset() | upstream_code | plb/envs/env.py:21-24 |
| reset() takes no seed or options, restores the initial state captured at construction, clears the recorded actions and returns _get_obs() | upstream_code | plb/envs/env.py:28-31 |
| _get_obs concatenates every step_size-th particle's position and velocity with the state of every primitive | upstream_code | plb/envs/env.py:33-41 |
| step() advances the Taichi environment, computes the loss, appends the action, and returns (observation, reward, False, loss_info); the done flag is always False | upstream_code | plb/envs/env.py:43-57 |
| The observation stride is len(x) // n_observed_particles | upstream_code | plb/envs/env.py:40-41 |
| Move has two Sphere primitives and each declares a 3-dimensional action with scale (0.01, 0.01, 0.01) | upstream_code | plb/envs/move.yml:10-26 |
| Primitives.action_dim is the sum of the action dims of its primitives | upstream_code | plb/engine/primitive/primitives.py:274-283 |
| Primitives.set_action flattens the action and clips every element to the interval [-1, 1] | upstream_code | plb/engine/primitive/primitives.py:290-294 |
| A primitive state is a 3-value position plus a 4-value rotation quaternion, returned by get_state | upstream_code | plb/engine/primitive/primive_base.py:130-146 |
| The default number of observed particles is 200 | upstream_code | plb/config/default_config.py:72 |
| Move sets the particle count to 10000 | upstream_code | plb/envs/move.yml:3 |
| SIMULATOR.quality defaults to 1 | upstream_code | plb/config/default_config.py:14 |
| SIMULATOR.dt is 0.5e-4 / quality seconds and SIMULATOR.substeps is int(2e-3 / dt), so at the default quality 1 one environment step is 40 physics substeps of 0.05 ms (2 ms) | upstream_code | plb/engine/mpm_simulator.py:22-34 |
| MPMSimulator.step advances the simulation from the current frame by substeps frames | upstream_code | plb/engine/mpm_simulator.py:365-376 |
| The reward is the start loss minus the step's incremental loss, returned inside loss_info | upstream_code | plb/engine/losses/loss.py:288-298 |
| Taichi is initialized on the GPU at import | upstream_code | plb/engine/taichi_env.py:6 |

## Limits

The driver declares no `Limit`. `GymnasiumDriver` derives the only bound at run time from the environment object's
`action_space`: `action.values` is the `Box(-1, 1, (6,))` of `plb/envs/env.py:26`, so every element is bounded by
-1 and 1 with source `upstream_code` and ref `plb/envs/env.py:26` (the driver's `action_space_ref`, which G4
checks). The `ticks` input is bounded by the class schema at 1 to 10000 and the `seed`
inputs by the class schema at 0 and above; those are schema bounds, not driver Limits. The device is simulated
(R0), so no limit is `operator_required`.

## Fidelity contract

`driver.py` publishes engine `taichi-mpm:PlasticineLab-Move-v1`, level `F1` (a physics model with contacts; no
actuator, sensor or noise model, so not F2), determinism `seeded` with `seed_control` `none` (the upstream
`reset()` takes no seed and restores the state captured at construction; the bridge's seed labels the episode),
`timestep_ms` 2.0 (one environment step: 40 physics substeps of `0.5e-4` s, `plb/engine/mpm_simulator.py:22-34`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot/restore. The gaps say what is not modelled: the
fake's placeholder particles, the absent soft-body physics, loss/reward, the 50-step wrapper's implementation in
the fake, the seed and options being ignored, the unrun sim backend, snapshots and rendering.

The real Move-v1 observation is 1214 values: with `n_particles` 10000 (`plb/envs/move.yml:3`) and
`n_observed_particles` 200 (`plb/config/default_config.py:72`) the stride is 50 (`plb/envs/env.py:40`), so the
`x` and `v` blocks contribute 200 x 6 = 1200 values and the two primitives 2 x 7 = 14
(`plb/engine/primitive/primive_base.py:130-146`); the fake returns the same length with placeholder particle data.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch; no native stop exists, so the runtime reports a
software-only e-stop. After it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last
world state stays readable. No hardware is attached and no hardware backend is declared.

## Tags

plasticinelab, soft-body, mpm, taichi, manipulation, reinforcement-learning, simulation, gymnasium
