# Facts and tags for gh.linden713/humanoid_amp

Every fact cites its source at commit `99efa6d60e351ec3def0dc6e983baf143fd31328`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers Isaac-Humanoid-AMP-Dance-Direct-v0, Isaac-Humanoid-AMP-Run-Direct-v0 and Isaac-Humanoid-AMP-Walk-Direct-v0 with entry point humanoid_amp_env:HumanoidAmpEnv | upstream_code | __init__.py:18-44 |
| HumanoidAmpEnv is an Isaac Lab DirectRLEnv | upstream_code | humanoid_amp_env.py:22 |
| The scene spawns the robot with Articulation and the ground with spawn_ground_plane | upstream_code | humanoid_amp_env.py:52-57 |
| The configured observation space is 81 values, the action space 28 values and the state space 0 | upstream_code | humanoid_amp_env_cfg.py:32-34 |
| The config keeps two AMP observations of 81 values each | upstream_code | humanoid_amp_env_cfg.py:35-36 |
| The action offset is the midpoint of the robot's soft joint-position limits and the action scale is their span | upstream_code | humanoid_amp_env.py:28-32 |
| Each applied action becomes the joint-position target action_offset + action_scale * action | upstream_code | humanoid_amp_env.py:80-82 |
| The episode is configured to last 10.0 s and each environment step decimates 2 physics steps | upstream_code | humanoid_amp_env_cfg.py:28-29 |
| The physics step is 1/60 s and the simulation configures PhysX | upstream_code | humanoid_amp_env_cfg.py:52-58 |
| Early termination is enabled with a termination height of 0.5 | upstream_code | humanoid_amp_env_cfg.py:38-39 |
| The reference body of the generic humanoid environment is the torso | upstream_code | humanoid_amp_env_cfg.py:42 |
| The default reset strategy is random: it samples motion times unless the strategy is random-start or default | upstream_code | humanoid_amp_env_cfg.py:43-49 |
| The scene config sets num_envs 4096 and env_spacing 10.0 | upstream_code | humanoid_amp_env_cfg.py:62 |
| The observation concatenates joint positions, joint velocities, the root height, tangent and normal vectors, root linear and angular velocities and the key-body positions relative to the root | upstream_code | humanoid_amp_env.py:221-240 |
| The generic humanoid reward is one for every environment at every step | upstream_code | humanoid_amp_env.py:105-106 |
| The episode truncates when the episode-length buffer reaches max_episode_length - 1 and terminates early when the reference body is below termination_height | upstream_code | humanoid_amp_env.py:108-114 |
| A random reset samples motion times, writes the sampled root pose and velocity plus joint positions and velocities, and updates the AMP observation buffer | upstream_code | humanoid_amp_env.py:143-175 |
| The AMP observation buffer holds num_amp_observations times amp_observation_space values per environment | upstream_code | humanoid_amp_env.py:45-50 |

Limits: the driver declares none. The bridge derives the action schema from the fake environment's action space;
that Box is unbounded, so no `action.values` limit is published and `cap.world.step.v1` has no bound to enforce.
The upstream `DirectRLEnv` base lies outside the clone and the clone states only the action count 28
(`humanoid_amp_env_cfg.py:33`), not bounds, so this package neither invents nor narrows one. The bridge's own
schema bounds `ticks` (1 to `max_ticks`, 10000 by default), which is a bridge setting, not a device limit. The device
is simulated (R0), so no limit is `operator_required`.

Scope: one package per repository. This package models the generic `HumanoidAmpEnv` through the dance registration
`Isaac-Humanoid-AMP-Dance-Direct-v0`. The clone also registers `Isaac-Humanoid-AMP-Run-Direct-v0` and
`Isaac-Humanoid-AMP-Walk-Direct-v0` on the same class with other motion files (`__init__.py:29-49`), and the G1
environments `Isaac-G1-AMP-Dance-Direct-v0` and `Isaac-G1-AMP-Walk-Direct-v0` on `G1AmpEnv` (`__init__.py:51-71`);
those are other configurations/devices and are not covered by this package. The checked backend is the package's
kinematic fake; the Isaac Sim/PhysX environment was not run.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Isaac-Humanoid-AMP-Dance-Direct-v0 (Isaac
Sim/PhysX)`, level F1 (rigid-body dynamics with contacts in the upstream environment), determinism `seeded` with
`seed_control` `parameter`, timestep 16.67 ms (the 1/60 s physics step, `humanoid_amp_env_cfg.py:53`; the control
period is two such steps, `:29`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say what the checked fake does not model and that the Isaac Sim/PhysX environment was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware
backend exists, so no physical stop is declared.

Tags: humanoid, amp, unitree, isaac-lab, isaac-sim, physx, reinforcement-learning, simulation, gymnasium
