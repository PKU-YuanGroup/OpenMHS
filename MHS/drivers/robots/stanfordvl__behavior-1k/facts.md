# Facts and tags for gh.stanfordvl/behavior-1k

Every fact cites its source at commit `cd484e0477e79bf1f17d373af232c53431ccc660`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same rows are
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The environment module imports gymnasium as gym | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:6` |
| Environment is a gym.Env subclass and its docstring says it follows the OpenAI Gym interface | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:38-40` |
| Environment(configs) takes a config file path or raw config dictionaries, merged sequentially | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:43-49` |
| The default env config uses gm.DEFAULT_SIM_STEP_FREQ for action_frequency, gm.DEFAULT_PHYSICS_FREQ for physics_frequency, gm.DEFAULT_RENDERING_FREQ for rendering_frequency, automatic_reset False, flatten_action_space False, flatten_obs_space False and num_envs 1 | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:1023-1031` |
| gm.DEFAULT_SIM_STEP_FREQ is 30 | upstream_code | `OmniGibson/omnigibson/macros.py:219` |
| A simulator step interval is sim_step_dt = 1.0 / action_frequency, so the 30 Hz default is 1/30 s | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:83` |
| The action space is a Dict of each robot's name to robot.action_space; flatten_action_space replaces it with one Box | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:425-451` |
| The observation space is assembled from every robot's, the task's and the external sensors' spaces and stored as a Dict; flatten_obs_space keeps a flattened Dict | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:386-423` |
| step takes an action and n_render_iterations and calls og.sim.step() once | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:718-762` |
| step returns the five-tuple (obs_list, rewards, terminateds, truncateds, infos) | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:807` |
| A termination condition named timeout sets truncated; every other done condition sets terminated | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:782-790` |
| automatic_reset resets only the environments whose done flag is set | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:794-803` |
| reset takes env_indices, get_obs and **kwargs (it declares no seed parameter) and resets the task and the step and episode counters | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:838-854` |
| reset returns (obs_list, {"obs_info": info_list}) | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:903` |
| close is a no-op to satisfy RL frameworks | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:523-525` |
| render returns None when the environment has no external sensors | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:809-813` |
| The default config has no robots and its task type is DummyTask | upstream_code | `OmniGibson/omnigibson/envs/env_base.py:1052-1057` |
| DummyTask creates no termination conditions and no reward functions | upstream_code | `OmniGibson/omnigibson/tasks/dummy_task.py:15-21` |
| BaseTask._step_reward starts from zeros and adds every reward function's output | upstream_code | `OmniGibson/omnigibson/tasks/task_base.py:299-312` |
| The docs call Environment an OpenAI gym-compatible interface and the main entry point for interacting with the simulation | vendor_doc | `docs/omnigibson/environments.md:5` |
| The docs step the environment with obs, reward, terminated, truncated, info = env.step(action) | vendor_doc | `docs/omnigibson/environments.md:41` |
| The docs list step, reset, render, observation_space and action_space as the Gym-like interface | vendor_doc | `docs/omnigibson/environments.md:46` |
| The documented construction is env = og.Environment(cfg) | vendor_doc | `docs/getting_started/quickstart.md:134` |
| Installation requires an NVIDIA RTX 2070+ GPU with 8GB+ of VRAM | vendor_doc | `docs/getting_started/installation.md:9-10` |

### Notes that are not facts

- The upstream environment was never imported or run: its stack is Isaac Sim 5.1.0 (`setup.sh:339`) on an NVIDIA RTX
  GPU (`docs/getting_started/installation.md:9-10`), and package code never imports the clone.
- `reset(..., **kwargs)` swallows the bridge's `seed` and `options` keywords without reading them. The package
  therefore declares `determinism.kind = "none"` and `seed_control = "none"`; `cap.world.seed.v1` is served by the
  bridge (it stores the seed for the next reset) but cannot make a run reproducible.
- `timestep_ms` is 1000/30, the upstream default action interval (`OmniGibson/omnigibson/envs/env_base.py:83` with
  `OmniGibson/omnigibson/macros.py:219`); a config may set another `action_frequency`.
- The fake's joint count, bounds and reset pose are placeholder test data, not facts about the device.

Tags (short lowercase keywords): `behavior-1k`, `omnigibson`, `household`, `embodied-ai`, `reinforcement-learning`,
`simulation`, `gymnasium`.
