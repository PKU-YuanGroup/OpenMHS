# Facts and tags for gh.confeitohs/arcle

Every fact cites its source at commit `311be9db018ed5f17fff2f7891251f965ea7aa2e`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RawARCEnv's constructor defaults are max_grid_size (30, 30), colors 10 and max_trial -1 | upstream_code | arcle/envs/arcenv.py:17 |
| The observation space is a Dict of trials_remain, terminated, input, input_dim, grid and grid_dim | upstream_code | arcle/envs/base.py:121-131 |
| The state document carries trials_remain (max_trial), terminated 0, the zero-padded input and grid, input_dim and grid_dim | upstream_code | arcle/envs/base.py:155-166 |
| The action space is a Dict of a selection Box with 0 or 1 on every grid cell and an operation Discrete over the operation count | upstream_code | arcle/envs/base.py:134-138 |
| RawARCEnv's operations are ten color operations (0-9), resize_to_answer (10) and submit (11) | upstream_code | arcle/envs/arcenv.py:26-41 |
| The reward is 1 only when the last operation is submit and the visible grid equals the answer; otherwise it is 0 | upstream_code | arcle/envs/arcenv.py:51-58 |
| step applies the operation, increments action_steps, updates info steps and returns the state, reward, terminated, truncated and info | upstream_code | arcle/envs/arcenv.py:60-76 |
| A submit decrements trials_remain, terminates when the grid equals the answer, and terminates when trials_remain reaches 0 | upstream_code | arcle/envs/base.py:172-183 |
| reset passes seed and options to gym.Env.reset, accepts prob_index, subprob_index, adaptation and reset_on_submit, and draws the problem from the data loader | upstream_code | arcle/envs/base.py:69-108 |
| The reset info carries the zero-padded input and answer with their dimensions | upstream_code | arcle/envs/base.py:145-153 |
| ARCLE/RawARCEnv-v0 is registered with entry point arcle.envs.arcenv:RawARCEnv and without max_episode_steps | upstream_code | arcle/envs/__init__.py:7-10 |
| RawARCEnv.step returns self.truncated | upstream_code | arcle/envs/arcenv.py:76 |
| reset sets self.truncated to False | upstream_code | arcle/envs/base.py:73 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`action.selection` 0 to 1 per cell and `action.operation` 0 to 11, with no source and the ref
`action_space of the fake backend .fake:FakeRawARCEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:ARCLE/RawARCEnv-v0`, level F0 (discrete ARC
grid state transitions, no physics or dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 0 ms
(event-driven analytic model; one tick is one operation), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled and that the fake was never compared with the upstream
environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the upstream class has no native stop);
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: arc, arc-agi, reinforcement-learning, simulation, gymnasium
