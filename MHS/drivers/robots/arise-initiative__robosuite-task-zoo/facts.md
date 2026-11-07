# Facts and tags for gh.arise-initiative/robosuite-task-zoo

Every fact cites its source at commit `74eab7f88214c21ca1ae8617c2b2f8d19718a9ed`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The list is copied into `facts = [Fact(...)]` in `driver.py`; the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository hosts a collection of robosuite tasks designed by community users and is intended to standardize experimental validation of simulated tasks | vendor_doc | README.md:3-6 |
| Using the repository requires installing robosuite first, and the clone is then installed with pip install -e . | vendor_doc | README.md:8-13 |
| The environments are based on robosuite and refer to the robosuite documentation for how to create an environment | vendor_doc | environments.md:3-5 |
| The HammerPlace task is a single-arm tabletop domain in which the operator places a hammer into the cabinet and closes the cabinet | vendor_doc | environments.md:28-31 |
| The documented task action space is OSC_POSITION (3) plus Gripper (1) | vendor_doc | environments.md:39 |
| The documented HammerPlace observations are workspace images, eye-in-hand images and proprioception | vendor_doc | environments.md:40 |
| The hammer_place module imports robosuite's SingleArmEnv as the base environment | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:4 |
| HammerPlaceEnv is defined as a single-arm robosuite environment | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:19 |
| The HammerPlaceEnv constructor takes robots, an optional controller_configs, control_freq 20, horizon 1000 and camera defaults use_camera_obs=True, use_object_obs=True, camera_names agentview, camera_heights 256 and camera_widths 256 | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:20-48 |
| The constructor forwards robots, controller_configs, control_freq, horizon, camera options and the rest to SingleArmEnv | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:76-98 |
| _load_model builds the TableArena, the HammerObject named hammer and the CabinetObject, registers them with the ManipulationTask and stores hammer and CabinetObject in self.objects | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:138-303 |
| The placement sampler draws the hammer pose from x_range [0.10, 0.18] and y_range [-0.20, -0.13] on the table during a reset that is not deterministic | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:443-456 |
| The success predicate is true when the hammer is inside the drawer (1.0 > z > 0.94 and y > 0.22) and the cabinet is closed (qpos > -0.01) | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:463-475 |
| The sparse reward is 0.0, or 1.0 when _check_success is true, scaled by reward_scale | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:100-136 |
| HammerPlaceEnv.step maps a four-element action to action[:3] plus the gripper, calls the robosuite parent step and returns obs, reward, done and info | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:489-499 |
| step replaces the parent's done with the environment's _check_success result | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:495-499 |
| The custom observables include robot0_joint_pos (activated), the object pose/relative-pose sensors, robot0_contact and robot0_eef_force_norm | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:323-395 |
| get_state_vector reads the observation keys robot0_gripper_qpos, robot0_eef_pos and robot0_eef_quat | upstream_code | robosuite_task_zoo/environments/manipulation/hammer_place.py:530-533 |
| The clone's demo creates the environment, calls env.reset(), reads env.action_spec and unpacks obs, reward, done, _ from env.step(action) | upstream_code | demo.py:6-24 |
| The clone's example creates MultitaskKitchenDomain with the OSC_POSITION controller, calls env.reset() and steps a four-element action | upstream_code | examples/demo_env.py:15-35 |
| The clone also defines KitchenEnv in kitchen.py | upstream_code | robosuite_task_zoo/environments/manipulation/kitchen.py:18 |
| The clone also defines MultitaskKitchenDomain in multitask_kitchen.py | upstream_code | robosuite_task_zoo/environments/manipulation/multitask_kitchen.py:17 |
| The clone also defines ToolUseEnvBase in tool_use.py | upstream_code | robosuite_task_zoo/environments/manipulation/tool_use.py:17 |
| The clone defines the hardest tool-use variant ToolUseEnv with its own cube and tool ranges | upstream_code | robosuite_task_zoo/environments/manipulation/tool_use.py:545-552 |
| The package declares numpy, numba, scipy and mujoco-py as install dependencies; robosuite itself is installed separately | upstream_code | setup.py:19-24 |

Tags (short lowercase keywords): `robosuite`, `mujoco`, `manipulation`, `hammer`, `cabinet`, `simulation`,
`benchmark`.

No `Limit` is declared: the clone exposes no numeric bound on the action vector (the action space comes from the
robosuite controller selected by the constructor's `controller_configs`) and the documented four-element
OSC_POSITION plus gripper shape is a constructor default, not a device bound. The catalogue's own `ticks` 1 to
10000 and `seed` >= 0 schema bounds still apply.
