# Facts and tags for gh.openai/multi-agent-emergence-environments

Every fact cites its source at commit `bafaf1e11e6398624116761f91ae7c93b136f395`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Base is the multi-agent environment base class; users start from it, add environment modules and stack wrappers on top | vendor_doc | README.md:18 |
| The repository depends on the separate mujoco-worldgen package, must install it and its requirements before this package, and was tested only on Mac OS X and Ubuntu 16.04 with Python 3.6 | vendor_doc | README.md:7-14 |
| The Base constructor defaults are horizon 250, n_substeps 5, n_agents 2, floor_size 6.0, grid_size 30 and action_lims (-1.0, 1.0), with deterministic_mode False | upstream_code | mae_envs/envs/base.py:27-29 |
| n_substeps is the number of internal MuJoCo steps per outer environment step, described as action repeat | upstream_code | mae_envs/envs/base.py:18-19 |
| Base passes tuple(action_lims) as the action_space, horizon and deterministic_mode to the mujoco-worldgen Env constructor | upstream_code | mae_envs/envs/base.py:31-35 |
| The world parameters use size (floor_size, floor_size, 2.5) and num_substeps n_substeps | upstream_code | mae_envs/envs/base.py:70-71 |
| The episode draws floor_size uniformly from floor_size_dist, builds each attempt with WorldBuilder(world_params, seed) and returns builder.get_sim() | upstream_code | mae_envs/envs/base.py:68-88 |
| The hide-and-seek factory defaults are n_substeps 15, horizon 80, floor_size 6.0, grid_size 30 and action_lims (-0.9, 0.9) | upstream_code | mae_envs/envs/hide_and_seek.py:219-231 |
| The hide-and-seek factory constructs Base with n_hiders + n_seekers agents | upstream_code | mae_envs/envs/hide_and_seek.py:248-251 |
| The hide-and-seek factory stacks SplitMultiAgentActions, AgentAgentObsMask2D, an observation wrapper, a reward wrapper, PreparationPhase and DiscretizeActionWrapper on Base | upstream_code | mae_envs/envs/hide_and_seek.py:350-362 |

Limits: the driver declares none. These are constructor arguments of a simulated environment, not physical bounds,
and the action values the bridge accepts are derived from the fake's Box action space (a placeholder in fake.py).
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco-worldgen:mae_envs`, level F1 (MuJoCo rigid-body
dynamics with contacts), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 because the pinned
clone does not state the physics timestep (`n_substeps` is action repeat, `base.py:18-19`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: the fake is a reduced
stand-in, the action and observation dimensions are placeholders, no wall-clock pacing, no rendering, and nothing was
validated against a physical device.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: multi-agent, mujoco, hide-and-seek, reinforcement-learning, simulation, gymnasium
