# Facts and tags for gh.hewlettpackard/sustain-cluster

Every fact cites its source at commit `3f6ea95cb835b89ba50b0ef76d66d14b8037643e`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TaskSchedulingEnv subclasses gymnasium.Env: it is the Gymnasium interface of the benchmark | upstream_code | envs/task_scheduling_env.py:18 |
| The number of datacenters is read from the cluster manager (self.num_dcs = len(...)) | upstream_code | envs/task_scheduling_env.py:51 |
| One simulation step advances the clock by 15 minutes (pd.Timedelta(minutes=15)) | upstream_code | envs/task_scheduling_env.py:37 |
| In single-action mode with deferral disabled, the action space is Discrete(num_dcs) | upstream_code | envs/task_scheduling_env.py:90-92 |
| With deferral disabled, an agent action 0..N-1 is shifted by one and assigned to datacenter 1..N | upstream_code | envs/task_scheduling_env.py:280-282 |
| The aggregated observation dimension is 4 time features + 5 aggregated task features + 5 features per datacenter | upstream_code | envs/task_scheduling_env.py:81-86 |
| The time features are the sine and cosine of the day of year and of the hour of day | upstream_code | envs/task_scheduling_env.py:188-195 |
| The per-task features are origin datacenter id, cores, GPUs, duration and minutes to the SLA deadline | upstream_code | envs/task_scheduling_env.py:209-220 |
| The datacenter features are available/total cores, GPUs and memory, carbon intensity/1000 and price/100 | upstream_code | envs/task_scheduling_env.py:197-207 |
| reset(seed) increments the episode count, seeds Python's random generator and the cluster manager, and returns (observation, info) | upstream_code | envs/task_scheduling_env.py:226-252 |
| step returns (observation, reward, terminated, truncated, info) after advancing the clock and loading the next tasks | upstream_code | envs/task_scheduling_env.py:370-386 |
| An episode is done and truncated when current_time reaches end_time | upstream_code | envs/task_scheduling_env.py:375-376 |
| The reward is 0.0 when the environment is constructed without a reward function | upstream_code | envs/task_scheduling_env.py:360-362 |
| The shipped simulation config enables single_action_mode and disable_defer_action | upstream_code | configs/env/sim_config.yaml:16-17 |
| The README documents a Gymnasium-compatible environment interface for RL agents | vendor_doc | README.md:124 |
| The README documents the simulation timestep as 15 minutes | vendor_doc | README.md:194 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(num_dcs)`: `action.index` from 0 to `num_dcs - 1`, with no source and the ref
`action_space of the fake backend .fake:FakeTaskSchedulingEnv`) plus the bridge's `ticks` 1 to 10000. The device is
simulated (R0), so no limit is `operator_required`. The fake's five datacenters, its start time, its task sizes and its
resource totals are test data marked `# placeholder` in `fake.py`; they are not facts and not limits.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sustain-cluster:TaskSchedulingEnv`, level F0 (kinematic
and analytic: the environment advances a scheduler clock and state transitions, not rigid-body dynamics, contacts,
actuators or sensors), determinism `seeded` with `seed_control` `parameter`, timestep 900000 ms (15 minutes,
`envs/task_scheduling_env.py:37`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say that the fake does not run the cluster manager, SustainDC, the workload trace, the reward engine or the
energy, carbon and thermal models, and that it was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: sustain-cluster, datacenter, scheduling, energy, carbon, reinforcement-learning, simulation, gymnasium
