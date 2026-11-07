# Facts and tags for gh.darshmenon/quadruped-robotics-stack

Every fact cites its source at commit `fe3c2e7457f9caaaa30b5669daba184394173a5f`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`, or an MJCF path with a line range). The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

The package serves the card's first model, `training/envs/go2_parkour_scene.xml` (`models[0]`), as a `MujocoDriver`.
The scene is a flat world with the floating-base Go2, its five-joint arm and a two-finger gripper, nineteen position
actuators and parkour obstacles that are parked underground by default (`go2_parkour_scene.xml:15-20`). The model file
is read from the read-only clone; neither the model nor its assets are copied into this package and the clone is never
imported.

| fact | source | ref |
|---|---|---|
| The repository is a ROS2 + Gazebo + MuJoCo workspace for simulating and walking quadruped robots | vendor_doc | README.md:8 |
| The README identifies Go2 as the only fully working robot | vendor_doc | README.md:18 |
| The Python requirements include gymnasium 0.29 or newer and mujoco 3.0 or newer | upstream_code | requirements.txt:4-8 |
| The MuJoCo environment points SCENE_XML at training/envs/go2_scene.xml | upstream_code | training/envs/go2_mujoco_env.py:11 |
| Go2MujocoEnv is the Gymnasium environment class the training code constructs | upstream_code | training/envs/go2_mujoco_env.py:206 |
| Go2MujocoEnv loads the MJCF with mujoco.MjModel.from_xml_path and builds the data with mujoco.MjData | upstream_code | training/envs/go2_mujoco_env.py:215-216 |
| Go2MujocoEnv sets model.opt.timestep to SIM_DT | upstream_code | training/envs/go2_mujoco_env.py:217 |
| SIM_DT is 0.005 s and CTRL_DECIMATION is 4, so one policy step is 0.02 s | upstream_code | training/envs/go2_mujoco_env.py:78-80 |
| ACT_DIM is 19 | upstream_code | training/envs/go2_mujoco_env.py:74 |
| The action space is a Box from -1.0 to 1.0 with one element per action dimension | upstream_code | training/envs/go2_mujoco_env.py:326-327 |
| The step writes the control vector to data.ctrl and calls mujoco.mj_step once per decimation step | upstream_code | training/envs/go2_mujoco_env.py:871-873 |
| The parkour scene sets the integration time step to 0.005 s in its option element | upstream_code | training/envs/go2_parkour_scene.xml:4 |
| The floating base body starts at 0 0 0.42 and carries the root free joint | upstream_code | training/envs/go2_parkour_scene.xml:23-24 |
| The arm and two-finger gripper add seven joints after the twelve leg joints and must stay the last child of base | upstream_code | training/envs/go2_parkour_scene.xml:121-125 |
| The scene declares nineteen position actuators, one per leg, arm and gripper joint, each with a ctrlrange | upstream_code | training/envs/go2_parkour_scene.xml:164-189 |
| The four hip actuators have ctrlrange -1.0472 to 1.0472 | upstream_code | training/envs/go2_parkour_scene.xml:166-169 |
| The front thigh actuators have ctrlrange -1.5708 to 3.4907 and the rear thigh actuators -0.5236 to 4.5379 | upstream_code | training/envs/go2_parkour_scene.xml:171-174 |
| The four calf actuators have ctrlrange -2.7227 to -0.83776 | upstream_code | training/envs/go2_parkour_scene.xml:176-179 |
| The five arm joints have ctrlrange -1.5708 to 1.5708 and the two finger joints 0 to 0.025 and -0.025 to 0 | upstream_code | training/envs/go2_parkour_scene.xml:183-189 |
| The parkour hurdles and platforms are parked at z -5 by default and the parkour environment rewrites their position and size at reset | upstream_code | training/envs/go2_parkour_scene.xml:15-20 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the loaded model itself, one interval per
actuator (`actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file). The package
declares no limit of its own and no `operator_required` bound, because the model file is the system of record for the
control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It parses the scene's MJCF,
resolves the MJCF default classes, and derives the nineteen actuator control ranges, the twenty-six qpos / twenty-five
qvel dimensions and the option time step from the same text. Its integration is a placeholder joint motion, not the
engine's dynamics, and it resolves no mesh, contact, equality or sensor constraint. MuJoCo was not importable where the
gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are listed in the
`fidelity` attribute of `driver.py`.

The served scene differs from the one the entry class loads: `Go2MujocoEnv` points `SCENE_XML` at
`training/envs/go2_scene.xml` (`training/envs/go2_mujoco_env.py:11`), while this package serves the card's `models[0]`,
`training/envs/go2_parkour_scene.xml`. Both files carry the same robot, arm and actuator block; the parkour variant
adds the parked obstacles and is not the flat training scene.

Licence: the card pins `license_spdx` `NOASSERTION`, and the clone has no top-level licence file. The README badge
says MIT (`README.md:6`), the training setup metadata declares `BSD-3-Clause` (`training/setup.py:7`) and `ros2/LICENSE`
is a BSD-3-style text naming Juan Miguel Jimeno (`ros2/LICENSE:1-6`). The package does not copy or redistribute upstream
code or model files; it reads the pinned model from the clone.

Tags: unitree, go2, quadruped, mujoco, simulation, parkour, robot
