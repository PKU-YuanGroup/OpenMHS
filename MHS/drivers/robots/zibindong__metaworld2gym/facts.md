# Facts and tags for gh.zibindong/metaworld2gym

Every fact cites its source at commit `9e7d3da16a86b6bed1353e1c2042115ed75edb1a`: `vendor_doc` for the text files of
the clone (README.md) or `upstream_code` for a code line. The same facts are written into `driver.py`; the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository contains a gym wrapper and an automatic demonstration-collection script for Meta-World | vendor_doc | README.md:3 |
| The README creates an environment with metaworld2gym.make("door-open"), calls reset() and step(), and unpacks the step result as next_obs, reward, done, info | vendor_doc | README.md:30-33 |
| The default observation dictionary is image (3, 224, 224), depth (224, 224), point_cloud (1024, 6), agent_pos (9,) and full_state (39,) | vendor_doc | README.md:39-43 |
| MetaWorldEnv defaults observation_meta to image, depth, agent_pos, point_cloud and full_state | upstream_code | metaworld2gym/metaworld_env.py:121-127 |
| MetaWorldEnv appends -v2-goal-observable to a task name and builds that class from metaworld.envs.ALL_V2_ENVIRONMENTS_GOAL_OBSERVABLE | upstream_code | metaworld2gym/metaworld_env.py:135-138 |
| MetaWorldEnv sets the episode length to 200 steps and takes its action_space from the wrapped Meta-World environment | upstream_code | metaworld2gym/metaworld_env.py:207-208 |
| MetaWorldEnv.step returns (observation dictionary, reward, done, info) and forces done at the 200-step episode length | upstream_code | metaworld2gym/metaworld_env.py:295-300 |
| MetaWorldEnv.reset resets the wrapped environment and returns the observation dictionary | upstream_code | metaworld2gym/metaworld_env.py:302-308 |
| The wrapped Meta-World environment's action space is a four-element Box from -1 to +1 | upstream_code | metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:128-131 |
| SawyerXYZEnv.step applies the first three action elements through set_xyz_action and the last element through do_simulation | upstream_code | metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:406-408 |
| SawyerXYZEnv defaults frame_skip to 5 and action_scale to 1/100 | upstream_code | metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:93-98 |
| The MJCF basic scene sets the physics timestep to 0.0025 s | upstream_code | metaworld/envs/assets_v2/scene/basic_scene.xml:2 |
| The base environment's dt is model.opt.timestep multiplied by frame_skip | upstream_code | metaworld/envs/mujoco/mujoco_env.py:104-106 |
| The package requires gym>=0.15.4, mujoco-py>=2.0,<2.2, numpy>=1.18, torch, termcolor, zarr and numba | upstream_code | setup.py:9-16 |

Tags (short lowercase keywords): metaworld, metaworld2gym, assembly, mujoco, manipulation, simulation, gym

## Limits

The driver declares no `Limit`; the only bound is the wrapped environment's four-element action space (-1 to +1 per
element, `metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:128-131`), which the Gymnasium bridge derives from the
simulator object at run time (so it is not a driver `Limit` and carries no `path:LINE` reference). `ticks` is bounded
by the catalogue class schema (1 to 10000). The device is simulated (R0): no limit is `operator_required` and no
`site-limits.example.json` is needed.

## Fidelity

The package serves an F0 kinematic fake, not the MuJoCo scene: `timestep_ms` is the MJCF physics step of 2.5 ms
(`metaworld/envs/assets_v2/scene/basic_scene.xml:2`), one wrapper step advances `frame_skip=5` frames (a 12.5 ms
control period, `metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:93-98`), `realtime_factor` is 0 and the clock is
`lockstep`. `determinism.kind` is `seeded` with `seed_control` `none`, because `MetaWorldEnv.reset` takes no seed and
the wrapped v2 environment samples its reset vector from numpy's generator. `snapshot_restore` is false: the wrapper
exposes no `get_state`/`set_state` pair. The image, depth and point-cloud arrays of the fake are smaller than the
configured device; the real sizes are in the table above and in the driver's fidelity `gaps`.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or reset is
accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable.
