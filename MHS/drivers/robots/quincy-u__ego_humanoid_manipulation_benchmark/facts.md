# Facts and tags for gh.quincy-u/ego_humanoid_manipulation_benchmark

Every fact cites its source at commit `4489a673153d40f0dcba84c9210c426edfc62812`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Humanoid-Base-v0 is registered with entry point humanoid.tasks.base_env:BaseEnv and BaseEnvCfg as its env_cfg_entry_point | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/__init__.py:13-20 |
| BaseEnv subclasses DirectRLEnv, the Isaac Lab direct reinforcement-learning environment class | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:134 |
| The default scene has four environments (num_envs=4) with 10.0 m spacing | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:50 |
| The physics simulation runs with dt = 1/120 s and render_interval = 4 | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:31-34 |
| BaseEnvCfg sets decimation = 4 | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:118 |
| BaseEnv sets self.dt = cfg.sim.dt * cfg.decimation, so its control timestep follows from those two settings | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:142 |
| BaseEnvCfg sets episode_length_s = 0.5 | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:117 |
| BaseEnvCfg sets action_scale = 1 | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:119 |
| BaseEnvCfg sets num_actions = 50 and action_space = num_actions | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:120-124 |
| BaseEnvCfg sets num_observations = 99 and observation_space = num_observations | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:121-123 |
| _apply_action multiplies the action by cfg.action_scale, clamps it to the robot's soft joint position limits and writes it as the joint position target | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:211-214 |
| _get_dones compares the episode length buffer with max_episode_length and returns the same tensor as terminated and truncated | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:217-219 |
| BaseEnv._get_rewards is empty, so the base environment defines no reward term | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:297-298 |
| _get_observations returns a dictionary with rgb, fixed_rgb, fixed_d, left_hand_rgb, right_hand_rgb, qpos, qvel, action, left/right end-effector poses and targets, finger tip positions and hand contact forces | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:278-295 |
| The left-eye and right-eye RGB images are concatenated along the width dimension (dim=2) | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:257-259 |
| The left-eye and right-eye cameras are 360 x 640 and capture rgb and distance_to_image_plane | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:63-82 |
| The main, left-hand and right-hand cameras are 720 x 1280 and capture rgb and distance_to_image_plane | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:83-112 |
| The default robot is the H1 Inspire configuration (H1_INSPIRE_CFG) with separate left/right arm and hand configs | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:52-56 |
| BaseEnvCfg enables object randomization with randomize = True, randomize_range = 1.0 and randomize_idx = -1 | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/base_env/base_env.py:130-132 |
| The random agent creates the environment with gym.make(task, cfg=env_cfg), resets it and drives it with env.step | upstream_code | scripts/random_agent.py:38-43 |
| The random agent samples actions uniformly in [-1, 1) using env.action_space.shape | upstream_code | scripts/random_agent.py:42 |
| The benchmark targets IsaacLab 1.2.0 and IsaacSim 4.2.0 | vendor_doc | README.md:17 |
| The asset data is hosted on Hugging Face, outside the clone | vendor_doc | README.md:23 |
| The humanoid.tasks extension is installed editable with the Isaac Lab Python | vendor_doc | README.md:36-39 |
| Humanoid-Close-Drawer-v0 is registered with entry point humanoid.tasks.close_drawer:CloseDrawerEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/close_drawer/__init__.py:13-16 |
| CloseDrawerEnv subclasses BaseEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/close_drawer/close_drawer.py:35 |
| Humanoid-Flip-Mug-v0 is registered with entry point humanoid.tasks.flip_mug:FlipMugEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/flip_mug/__init__.py:13-16 |
| FlipMugEnv subclasses BaseEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/flip_mug/flip_mug.py:48 |
| Humanoid-Insert-And-Unload-Cans-v0 is registered with entry point humanoid.tasks.insert_and_unload_cans:InsertAndUnloadCansEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/insert_and_unload_cans/__init__.py:13-16 |
| InsertAndUnloadCansEnv subclasses BaseEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/insert_and_unload_cans/insert_and_unload_cans.py:27 |
| Humanoid-Insert-Cans-v0 is registered with entry point humanoid.tasks.insert_cans:InsertCansEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/insert_cans/__init__.py:13-16 |
| InsertCansEnv subclasses BaseEnv | upstream_code | source/extensions/humanoid.tasks/humanoid/tasks/insert_cans/insert_cans_env.py:27 |

## Limits

The driver declares no `Limit`. The action space has 50 elements (`num_actions`, `base_env.py:120-124`), which is a
structure (array length), not a numeric bound. `_apply_action` clamps the action to the robot's soft joint position
limits (`base_env.py:211-214`), but those limits live in the H1 asset data, which the clone does not contain
(`README.md:23`); the clone states no numeric joint range. The driver therefore publishes no numeric bound instead of
inventing one. `scripts/random_agent.py:42` samples actions in [-1, 1), but that is a property of the documented random
agent, not a bound of the environment, so it is a Fact and is not used as a Limit. `ticks` is bounded by the
Gymnasium bridge's own `max_ticks` (1 to 10000, an SDK input bound), not by a device limit.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `isaaclab:Humanoid-Base-v0`, level `F0` (the package's fake is kinematic: it
writes the action vector to joint positions directly and has no rigid-body dynamics or contacts), determinism `seeded`
with `seed_control` `parameter`, timestep 1000/30 ms (sim dt 1/120 s at decimation 4, `base_env.py:32`, `:118`,
`:142`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore, and eight gaps. The gaps name
the real camera sizes (360 x 640 per eye, concatenated to 360 x 1280; 720 x 1280 for the main and hand cameras,
`base_env.py:63-112`, `:257-259`) and say that the fake does not model them, that only Humanoid-Base-v0 is bound, that
the USD assets and the Isaac Sim/Isaac Lab runtime are absent, and that no upstream run was made.

## Safety

Simulated R0 device (`world.sim`). `BaseEnv` is a simulator; the driver has no hardware backend and no path to a
machine. The e-stop is the runtime's software latch (no native stop exists); after it no step or reset is accepted
until `mhs.safety.reset` clears the latch, and the state stays readable. No operator-required bound is declared
because the clone states no numeric action range.

## Tags

humanoid, manipulation, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium
