# Facts and tags for gh.rlagent/factor-world

Every fact cites its source at commit `01df1f18f7e532afda0a38169356fa637d24e432`: `vendor_doc` (a text file of the
clone such as README.md or conda_env.yml) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository provides MetaWorld environments with factors of variation including arm position, camera position, floor texture, lighting, object position, object size, object texture, table position, table texture and distractor objects | vendor_doc | README.md:15-25 |
| The make_wrapped_env factory selects the goal-hidden class for env_name unless observe_goal is true | upstream_code | wrappers.py:83-87 |
| The assembly-v2 environment name is registered to the SawyerNutAssemblyEnvV2 class | upstream_code | envs/env_dict.py:75-76 |
| SawyerNutAssemblyEnvV2 uses the MJCF model sawyer_xyz/sawyer_assembly_peg.xml | upstream_code | envs/tasks/sawyer_assembly_peg_v2.py:25-26 |
| The environment action space is a Box of four elements, each from -1 to +1 | upstream_code | envs/sawyer_xyz_env.py:164-167 |
| A step applies action[:3] as a mocap hand displacement through set_xyz_action and action[-1] as the two gripper actuator commands [action[-1], -action[-1]] | upstream_code | envs/sawyer_xyz_env.py:486-488 |
| set_xyz_action clips the action to -1..1, scales it by action_scale and clips the mocap position to mocap_low..mocap_high | upstream_code | envs/sawyer_xyz_env.py:206-217 |
| SawyerXYZEnv defaults frame_skip to 5 | upstream_code | envs/sawyer_xyz_env.py:111 |
| SawyerXYZEnv defaults action_scale to 1/100 | upstream_code | envs/sawyer_xyz_env.py:116 |
| MujocoEnv.dt is model.opt.timestep times frame_skip | upstream_code | envs/mujoco_env.py:118-120 |
| The MJCF basic scene sets the physics timestep to 0.0025 s | upstream_code | third_party/metaworld/metaworld/envs/assets_v2/scene/basic_scene.xml:2 |
| The assembly model has two position actuators, r_close and l_close, with ctrlrange -1 to +1, and a weld equality attaches the mocap body to the hand | upstream_code | third_party/metaworld/metaworld/envs/assets_v2/sawyer_xyz/sawyer_assembly_peg.xml:22-28 |
| MujocoEnv loads the model with mujoco_py.load_model_from_path and creates a mujoco_py.MjSim | upstream_code | envs/mujoco_env.py:58-59 |
| SawyerXYZEnv sets max_path_length to 500 | upstream_code | envs/sawyer_xyz_env.py:100 |
| A step ends the episode when info['success'] is true or curr_path_length reaches max_path_length | upstream_code | envs/sawyer_xyz_env.py:522 |
| The step returns the observation dictionary, info['success'] as the reward, the done flag and the info dictionary | upstream_code | envs/sawyer_xyz_env.py:520-523 |
| The v2 observation is a 39-element flat proprio array made of 18 current elements, 18 previous elements and a 3-element goal, and the image is None unless get_image_obs is set | upstream_code | envs/sawyer_xyz_env.py:391-425 |
| The proprio observation is cast to np.float32 | upstream_code | envs/sawyer_xyz_env.py:422 |
| Without images the observation space is a Dict with a single proprio Box | upstream_code | envs/sawyer_xyz_env.py:474-483 |
| SawyerXYZEnv.reset resets curr_path_length to 0 and calls the base reset | upstream_code | envs/sawyer_xyz_env.py:540-542 |
| MujocoEnv.reset calls sim.reset and reset_model and returns the observation reset_model produced | upstream_code | envs/mujoco_env.py:99-108 |
| The assembly reset_model resets the hand, sets the target to the goal, places the object and the peg, and returns the observation | upstream_code | envs/tasks/sawyer_assembly_peg_v2.py:100-117 |
| The goal-hidden class sets _set_task_called to True in its constructor, so the configured task does not need an external set_task before reset | upstream_code | envs/env_dict.py:348-355 |
| The factor wrapper generates a model XML that includes factors/factors_train.xml or factors/factors_eval.xml, so factors change the model file | upstream_code | envs/factors/utils.py:61-72 |
| The project pins python 3.8, mujoco_py >=2.1,<2.2 and gym 0.25.1 | vendor_doc | conda_env.yml:19-46 |

## Native interface, units and stop path

- The native class is `envs.tasks.sawyer_assembly_peg_v2:SawyerNutAssemblyEnvV2` (card entry symbol). Its readable
  state is the observation dictionary returned by `reset()`/`step()` and the `dt` property; its writable state is
  none. `seed(seed)` returns `[seed]` and `close()` destroys the viewer window if one exists
  (`envs/mujoco_env.py:75-81`, `:157-160`, `envs/sawyer_xyz_env.py:540-542`).
- Actions: `cap.world.step.v1` takes `{ticks, action}` with `action.values` as four numbers from -1 to +1
  (`envs/sawyer_xyz_env.py:164-167`); `cap.world.reset.v1` takes `{seed, options}` and resets the episode
  (`envs/sawyer_xyz_env.py:540-542`); `cap.world.seed.v1` records the seed used by the next reset
  (`envs/mujoco_env.py:75-81`). There are no other writes.
- Units and ranges: the action is a normalised four-element command (hand x, y, z and gripper); the first three move
  the mocap at `action_scale` 1/100 (`envs/sawyer_xyz_env.py:116`, `:206-217`), and the last drives the two gripper
  actuators (`envs/sawyer_xyz_env.py:486-488`). Hand and object positions are MuJoCo position values; the clone
  states no physical unit, so this package does not claim one. One environment step is
  `frame_skip` 5 physics frames (`envs/sawyer_xyz_env.py:111`), each 0.0025 s
  (`third_party/metaworld/metaworld/envs/assets_v2/scene/basic_scene.xml:2`), so a tick is 12.5 ms. The v2 proprio
  observation has 39 elements (`envs/sawyer_xyz_env.py:396`) and the episode limit is 500 steps
  (`envs/sawyer_xyz_env.py:100`).
- Stop path: this is a simulated R0 device. There is no hardware stop, no `@estop` and no independent physical
  e-stop; the runtime's software latch refuses every step and reset after an e-stop, and the last observation stays
  readable. The `safe_state` sentence says this. No `Limit` is declared by the driver: the only numeric bound is the
  action space, which the Gymnasium bridge derives from the environment itself (`action.values` -1..1,
  `envs/sawyer_xyz_env.py:164-167`); `ticks` is bounded by the bridge's `max_ticks`. The device is R0, so no
  `operator_required` limit and no `site-limits.example.json` are needed.

## Fidelity contract and fake difference

The package serves the goal-hidden configuration of the assembly-v2 task, not the wrapper's factor variants: the
factory selects the goal-hidden subclass (`wrappers.py:83-87`) and that subclass sets `_set_task_called`
(`envs/env_dict.py:348-355`), while the factor wrappers change the MJCF XML (`envs/factors/utils.py:61-72`). The
fidelity is F0: the package's `fake.py` is a pure-Python kinematic stand-in, not MuJoCo. The `fidelity` mapping in
`driver.py` declares engine `factor-world:assembly-v2/SawyerNutAssemblyEnvV2`, level F0, determinism seeded with
`seed_control` none, a 12.5 ms timestep, `realtime_factor` 0, the lockstep clock, a full reset and no snapshot/restore;
its `gaps` list every difference (no MJCF, contacts, weld, gripper, object physics, reward, render, factor XML, or
upstream comparison). The default reset is deterministic because `random_init` is false
(`envs/sawyer_xyz_env.py:107`, `:135`); the legacy seed is recorded but does not select a different start.

## Safety and tags

The package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null); no human reviewed or tested
anything and no hardware was attached. It is checked on the fake backend only; its evidence is `contract_checked`,
never an MHS-Device level.

Tags: factor-world, metaworld, assembly, sawyer, mujoco, manipulation, simulation, gym.
