# Facts and tags for gh.hewlettpackard/dc-rl

Every fact cites its source at commit `a92b4755aca560e34a98d14028dda629eb968482`; the same facts are in
`driver.py` (`facts = [...]`) and the reference file is generated from the driver, not from this page. All refs are
`upstream_code` lines of the clone or `vendor_doc` lines of `README.md`.

| fact | source | ref |
|---|---|---|
| SustainDC subclasses gymnasium.Env | upstream_code | sustaindc_env.py:90 |
| SustainDC is constructed from an EnvConfig mapping, not through a gymnasium.make registration | upstream_code | sustaindc_env.py:91-99 |
| The default EnvConfig runs three agents: agent_ls, agent_dc and agent_bat | upstream_code | sustaindc_env.py:40 |
| EnvConfig copies DEFAULT_CONFIG and overrides the keys of the mapping passed to the constructor | upstream_code | sustaindc_env.py:82-87 |
| When the config has no worker_index, the constructor reads month and passes month + 1 to make_dc_pyeplus_env | upstream_code | sustaindc_env.py:126-152 |
| The training configuration sets month to 6 | upstream_code | harl/configs/envs_cfgs/sustaindc.yaml:14 |
| observation_space and action_space are lists, one sub-space for each configured agent, and a missing agent is given a base controller | upstream_code | sustaindc_env.py:164-190 |
| SustainDC builds the load-shifting, data-center and battery environments with make_ls_env, make_dc_pyeplus_env and make_bat_fwd_env | upstream_code | sustaindc_env.py:148-153 |
| The load-shifting action space is Discrete(3): 0 defers all shiftable tasks, 1 does nothing and 2 processes all deferred tasks | upstream_code | envs/carbon_ls.py:36-40 |
| The data-center action space is Discrete(3): a -1, 0 or +1 delta to the cooling setpoint | upstream_code | utils/make_envs_pyenv.py:127-132 |
| The battery action space is Discrete(3): 0 charge, 1 discharge and 2 idle | upstream_code | envs/bat_env_fwd_view.py:27-28 |
| The load-shifting observation is a Box of 26 elements from -2 to 2 | upstream_code | envs/carbon_ls.py:45 |
| The data-center observation is a Box of 14 elements from -1 to 1 | upstream_code | utils/make_envs_pyenv.py:114-116 |
| The battery observation is a Box of 13 elements from -1 to 1 | upstream_code | envs/bat_env_fwd_view.py:23-24 |
| reset returns one state per configured agent in a dict | upstream_code | sustaindc_env.py:499-531 |
| step takes an action dict and returns observation, reward, terminated and truncated dicts plus an info dict | upstream_code | sustaindc_env.py:533-621 |
| _perform_actions reads the agent_ls, agent_dc and agent_bat keys of the action dict | upstream_code | sustaindc_env.py:624-653 |
| When agent_dc is not configured, _perform_actions calls base_agents['agent_dc'].act | upstream_code | sustaindc_env.py:637-641 |
| BaseHVACAgent defines do_nothing_action and has no act method | upstream_code | utils/base_agents.py:29-58 |
| The reward, terminated and truncated dicts receive one entry per configured agent | upstream_code | sustaindc_env.py:686-699 |
| seed() seeds numpy, Python's random generator and torch | upstream_code | sustaindc_env.py:241-249 |
| The simulation advances in quarter-hour steps: four timesteps per hour | upstream_code | utils/make_envs_pyenv.py:194 |
| At the end of an episode every agent is marked truncated and terminated stays false | upstream_code | sustaindc_env.py:713-718 |
| The three individual rewards are produced by the ls, dc and bat reward methods | upstream_code | sustaindc_env.py:721-739 |
| The README describes SustainDC as a set of environments for benchmarking multi-agent reinforcement learning in data centers | vendor_doc | README.md:25 |
| The README says the environments are wrapped in the Gymnasium Env class | vendor_doc | README.md:41 |
| The README says three interconnected environments simulate data-center operations | vendor_doc | README.md:113 |

Limits: the driver declares none.  The published bounds are the three `Discrete(3)` action spaces the Gymnasium
bridge derives from the fake (`cap.world.step.v1` input paths `action.agent_ls`, `action.agent_dc` and
`action.agent_bat`, each 0 to 2), plus the integer count bounds `ticks` and `seed` the bridge itself applies.  The
device is simulated (R0), so no limit is `operator_required`.  The sim backend builds `SustainDC` with
`agents: ['agent_dc']` (`sustaindc_env.py:174-184`), so its live action space is that one data-center `Discrete`
(`utils/make_envs_pyenv.py:127-132`).  The committed reference stays the fake's three-agent surface.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sustaindc:SustainDC`, level F0 (analytic state
transitions; no rigid-body dynamics, contacts, actuators or sensors), determinism `seeded` with `seed_control`
`parameter`, timestep 900000 ms (15 minutes, four timesteps per hour at `utils/make_envs_pyenv.py:194`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say what the fake does
not model, including that the fake's bridge reward is the sum of three placeholder rewards, and one gap states
that the sim backend returns `reward['agent_dc']` unchanged (`sustaindc_env.py:692-694`).

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.  No hardware is
attached and no hardware run is claimed.

Tags: sustaindc, datacenter, multi-agent, energy, carbon, battery, reinforcement-learning, simulation, gymnasium
