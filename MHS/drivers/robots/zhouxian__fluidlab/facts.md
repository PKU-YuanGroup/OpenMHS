# Facts and tags for gh.zhouxian/fluidlab

Every fact cites its source at commit `7295eb6ed7ee92b2be471fd30b432238577f28ce`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a Python or YAML source file of the clone as `path/in/clone:LINE`). The
same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| FluidLab is a set of standardized complex robotic fluid manipulation tasks powered by FluidEngine, a multi-material fully differentiable physics engine supporting liquids, solids and gases | vendor_doc | README.md:21-23 |
| Every environment is registered as <env_name>-v<id> with entry point fluidlab.envs.<env_name.lower()>_env:<EnvName>Env, kwargs version and loss_type='default', and max_episode_steps=10000 | upstream_code | fluidlab/envs/__init__.py:4-10 |
| CirculationEnv requires the version argument and takes loss=True, loss_type='diff' and seed=None | upstream_code | fluidlab/envs/circulation_env.py:16 |
| CirculationEnv has horizon 1000 and horizon_action 1000 | upstream_code | fluidlab/envs/circulation_env.py:21-22 |
| With loss_type='default' gym_misc replaces the horizon with horizon_action | upstream_code | fluidlab/envs/fluid_env.py:86-87 |
| The action range of the circulation environment is [-0.1, 0.1] | upstream_code | fluidlab/envs/circulation_env.py:27 |
| The circulation agent has 8 action dimensions | upstream_code | fluidlab/envs/configs/agent_circulation.yaml:6 |
| The action velocity scales are 1 for the first six dimensions, 100000 for dimension seven and 50 for dimension eight | upstream_code | fluidlab/envs/configs/agent_circulation.yaml:8 |
| The environment is a 3-D Taichi MPM simulation with particle density 1e6, 100 local substeps, gravity (0, -20, 0), horizon 1000 and CPU checkpoints | upstream_code | fluidlab/envs/circulation_env.py:30-37 |
| The scene adds a room static mesh at position (0.5, 0.5, 0.5), euler (0, 0, 0), scale (1.4, 3.0, 1.4), SDF resolution 128, material PILLAR and dynamics enabled | upstream_code | fluidlab/envs/circulation_env.py:48-57 |
| The scene adds one 'nowhere' body of 10 water particles | upstream_code | fluidlab/envs/circulation_env.py:60-64 |
| The smoke field is resolved at 128, with dt 0.03, 50 solver iterations, decay 0.99 and q_dim 1 | upstream_code | fluidlab/envs/circulation_env.py:67-72 |
| The observation samples at most 200 particles per body | upstream_code | fluidlab/envs/circulation_env.py:24 |
| gym_misc builds observation_space as Box(-inf, inf, obs.shape) and action_space as Box(action_range[0], action_range[1], (agent.action_dim,)) | upstream_code | fluidlab/envs/fluid_env.py:85-93 |
| reset restores the stored initial state and returns the observation | upstream_code | fluidlab/envs/fluid_env.py:95-97 |
| _get_obs concatenates each body's sampled positions, velocities and used flags, the agent state, and the smoke field's v and q slices taken as [::10, 60:68, ::10] | upstream_code | fluidlab/envs/fluid_env.py:99-125 |
| step clips the action to action_range before advancing the simulator | upstream_code | fluidlab/envs/fluid_env.py:131-134 |
| The episode ends when t equals horizon; a NaN reward is replaced with -1000 and also ends the episode | upstream_code | fluidlab/envs/fluid_env.py:139-147 |
| seed calls the base environment's seed and then sets the process random seeds | upstream_code | fluidlab/envs/fluid_env.py:31-33 |
| The step reward of the circulation loss is 11 minus the current step loss | upstream_code | fluidlab/fluidengine/losses/circulation_loss.py:134-136 |
| The air-conditioner effector's get_state output is a 9-element vector: position (3), quaternion (4), strength s and radius r | upstream_code | fluidlab/fluidengine/effectors/aircon.py:175-195 |
| The MPM physics timestep is 2e-4 s and one environment step covers int(2e-3 / self.dt) substeps | upstream_code | fluidlab/fluidengine/simulators/mpm_simulator.py:24-30 |

Limits: the driver declares none. The only bounds are the action space, which the bridge derives from the environment
(`action.values`, one bound per element, source `upstream_code`, ref `fluidlab/envs/circulation_env.py:27`): the
range `[-0.1, 0.1]` of `circulation_env.py:27` for all 8 elements of `agent_circulation.yaml:6`. `ticks` is bounded
by the bridge's declared maximum. The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `fluidlab:FluidLab (MPM + smoke field)`, level F1 (the
upstream is a multi-material differentiable physics engine, not a rigid-body-only model), determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 2.0 for one environment step (the MPM physics `dt` is 2e-4 s and one step
runs `int(2e-3 / self.dt)` substeps, `mpm_simulator.py:24-30`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The gaps name the fake's omissions and the real observation size of this scene (5487 floats:
70 body state, 9 agent state, 4056 smoke velocity and 1352 smoke q samples).

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware was attached, run or tested.

Tags: fluidlab, fluid-simulation, differentiable-physics, reinforcement-learning, simulation, gym.
