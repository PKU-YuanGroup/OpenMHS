# Facts and tags for gh.umass-foundation-model/co-llm-agents

Every fact cites the clone at commit `3e12dea925d735eefce33da71806ae9da6fcaf3f`: `vendor_doc` for README text and
`upstream_code` for a Python line. The same list is in `driver.py` as `facts = [Fact(...)]`; the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TDW-MAT extends the ThreeDWorld Transport Challenge into a multi-agent setting on top of the TDW platform | vendor_doc | `tdw_mat/README.md:77` |
| The environment class is TDW, a subclass of the legacy Gym Env | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:50` |
| gym id transport_challenge_MA is registered with entry point tdw_gym:TDW | upstream_code | `tdw_mat/tdw-gym/__init__.py:4-7` |
| The single-agent action space is a Dict of type Discrete(7), object Discrete(30), arm Discrete(2) and a message Text of at most 1000 characters | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:104-108` |
| Action type 0 moves forward 0.5 m, 1 turns left 15 degrees, 2 turns right 15 degrees, 3 reaches for and grasps, 4 puts in a container, 5 drops, 6 sends a message, and another type asserts False | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:628-644` |
| The observation space declares rgb (3, screen_size, screen_size), seg_mask (screen_size, screen_size, 3), depth (screen_size, screen_size), an agent pose Box(-30, 30, (6,)), two hand slots, 50 visible-object slots, status Discrete(4), valid Discrete(2), FOV Box(0, 120, (1,)), a 4x4 camera matrix, two message slots and current_frames Discrete(30) | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:119-133` |
| action_space is built from observation_space_single, not from action_space_single | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:139-140` |
| step compares action['arm'] with the strings left and right, while the declared arm space is Discrete(2) | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:624-627` |
| reset takes keyword-only seed, options and output_dir; options must carry scene and layout and reset raises ValueError without it | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:194-227` |
| reset launches the external ThreeDWorld build through TransportChallenge with launch_build | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:211` |
| reset calls super().reset(seed=seed) and creates np.random.RandomState(seed) | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:228-229` |
| step returns the legacy four-tuple (observation, reward, done, info) | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:754` |
| reset returns (observation, info, env_api), a three-tuple | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:346` |
| reward is reduced by 0.1 for each agent whose action status is neither success nor ongoing | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:725-726` |
| done becomes True when num_frames reaches max_frame or the goal is achieved | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:731` |
| screen_size defaults to 512 and max_frames to 3000 (constructor parameters, not bounds) | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:52` |
| reset opens ./dataset/room_types.json from the working directory | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:312-313` |
| reset opens ./dataset/name_map.json from the working directory | upstream_code | `tdw_mat/tdw-gym/tdw_gym.py:269` |
| TDW-MAT pins tdw==1.11.23.5 | upstream_code | `tdw_mat/requirements.txt:17` |
| The setup uses Python 3.9 and an editable install | vendor_doc | `tdw_mat/README.md:28-30` |
| The transport challenge asset bundles must be downloaded and unzipped under TDW_MAT | vendor_doc | `tdw_mat/README.md:59` |

## What the fake covers and what it does not

The fake is an analytic F0 stand-in, not TDW. It serves the declared single-agent action space (the corrected
space; the bridge's limit paths cannot address an upstream agent-map key such as `"0"`), keeps a seeded point-agent
pose and two hand slots, applies the seven action types of `tdw_gym.py:628-644`, charges the 0.1 penalty of
`tdw_gym.py:725-726` and returns the legacy three- and four-tuples, wrapping the action under agent `"0"` for
`TDW.step`'s agent map. It accepts a seed-only
reset and uses a placeholder scene, while upstream requires `options['scene']` and `options['layout']`
(`tdw_gym.py:227`) and reads the dataset JSON files. The image arrays are 2x2 placeholders instead of the
`screen_size`-sized camera frames (512 by default), and the visible-object ids, camera matrix and object positions
are test data, each marked `# placeholder` in `fake.py`; empty object and hand slots use -1, outside the declared
Discrete range, because the bridge needs an integer where upstream pads with None. Python's `random.Random` is used where upstream uses
`np.random.RandomState`, so one seed repeats a fake trajectory but not an upstream one. The declared action field
`message` is a Text space, which the bridge has no string kind for, so its published schema is an open object; the
fake accepts a string and uses it for action type 6. The e-stop is the runtime's software latch: the simulation
stops advancing and stays readable, and there is no hardware backend.

Tags: `gymnasium`, `simulation`, `multi-agent`, `transport`, `threedworld`, `reinforcement-learning`.
