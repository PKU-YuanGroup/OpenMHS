# Facts and tags for gh.isaac-sim/isaaclab-arena

Every fact cites its source at commit `2cc9e9766f1f62a500b85c92207192d8c60fcce5`: `upstream_code` (code of the clone)
or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| IsaacLabArenaManagerBasedRLEnv extends Isaac Lab's vectorized ManagerBasedRLEnv | upstream_code | isaaclab_arena/environments/isaaclab_arena_manager_based_env.py:34 |
| The environment is constructed from a composed IsaacLabArenaManagerBasedRLEnvCfg and an optional render_mode | upstream_code | isaaclab_arena/environments/isaaclab_arena_manager_based_env.py:39-45 |
| reset(seed, env_ids, options) forwards to ManagerBasedRLEnv.reset; with an episode limit only the initial explicit reset is allowed | upstream_code | isaaclab_arena/environments/isaaclab_arena_manager_based_env.py:173-181 |
| step takes a torch action tensor and returns the vectorized step tuple, reporting completions only for environments that were assigned an episode before the step | upstream_code | isaaclab_arena/environments/isaaclab_arena_manager_based_env.py:183-189 |
| The Arena environment cfg sets sim.dt to 1/120 s and decimation to 8, a 15 Hz control rate by default | upstream_code | isaaclab_arena/environments/isaaclab_arena_manager_based_env_cfg.py:103-108 |
| An embodiment offers one or more control variants, for example franka_ik uses differential IK control while franka_joint_pos uses direct joint position control, so the composed embodiment selects the action terms | vendor_doc | docs/pages/concepts/embodiment/index.rst:32-35 |
| A policy receives the observation as a Gymnasium spaces Dict and returns an action tensor shaped like env.action_space | vendor_doc | docs/pages/concepts/policy/index.rst:64-66 |
| Setting --seed fixes the simulation and the run-time variation draws | vendor_doc | docs/pages/concepts/environment/env_builder.rst:121 |
| build_registered takes the Gymnasium id from self.arena_env.name | upstream_code | isaaclab_arena/environments/arena_env_builder.py:578 |
| ArenaEnvBuilder registers the composed environment with gym.register(id=name, entry_point=...); the id is therefore chosen by the composed IsaacLabArenaEnvironment | upstream_code | isaaclab_arena/environments/arena_env_builder.py:600-605 |
| Documentation states that the compiled config is registered with the gym registry under the environment's name and gym.make() returns the environment | vendor_doc | docs/pages/concepts/environment/env_builder.rst:125-126 |
| make_registered calls gym.make(name, cfg=cfg, render_mode=render_mode, **env_kwargs) | upstream_code | isaaclab_arena/environments/arena_env_builder.py:655-656 |
| The default Gymnasium entry point is IsaacLabArenaManagerBasedRLEnv; mimic mode uses the embodiment's mimic environment instead | upstream_code | isaaclab_arena/environments/arena_env_builder.py:548-557 |
| The README example composes an environment with ArenaEnvBuilder.make_registered and calls env.reset() | vendor_doc | README.md:167-170 |
| The package requires Python >=3.12,<3.13 | vendor_doc | pyproject.toml:12 |
| The prerequisites are Linux (Ubuntu 22.04+) and an NVIDIA GPU | vendor_doc | README.md:79-80 |

## Limits

The driver declares no numeric bound of its own. The fake backend's action Box is unbounded and the bridge therefore
publishes no finite action limit; no fake test number enters a Limit. The catalogued `cap.world.step.v1` schema bounds
`ticks` (1 to the bridge's `max_ticks`, 10000) and `cap.world.seed.v1` bounds `seed` to a non-negative integer, both
enforced by the runtime. No field is `operator_required`: the device is simulated R0 and the operator has no device
bound to supply.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `isaaclab_arena:IsaacLabArenaManagerBasedRLEnv`, determinism
`seeded` with `seed_control` `parameter`, `timestep_ms` 0 (the fake is event-driven per tick; the upstream Arena cfg
uses a 15 Hz control step by default), `realtime_factor` 0, clock `lockstep`, reset `full`, `snapshot_restore` false.
The gaps in `driver.py` state what is not modelled, including the smaller fake action/observation arrays, the
vectorized-to-single-environment reduction, the absence of a fixed `env_id` to `gym.make`, and that the upstream stack
was never run here.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, the fake is not advanced, and the state stays readable. No physical stop exists
and none is claimed.

Tags: isaac-lab, isaac-sim, arena, reinforcement-learning, simulation, gymnasium
