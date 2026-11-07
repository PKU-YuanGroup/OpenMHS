# Facts and tags for gh.cai23sbp/go2_parkour_deploy

Every fact cites its source at commit `5f04c3b51dcef3629a9500aef16e247d756fcd61`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE` or an MJCF path with a line range). The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, `core/go2/scene.xml` (`models[0]`), as a `MujocoDriver`. The scene includes
the robot model `core/go2/go2.xml` and adds a ground plane (`scene.xml:2`, `scene.xml:19-21`), so the loaded world
contains the twelve-actuator GO2 and a floor. The model files are read from the read-only clone; neither the models nor
their assets are copied into this package and the clone is never imported.

| fact | source | ref |
|---|---|---|
| The repository is a Unitree GO2 deployment trained with IsaacLab | vendor_doc | README.md:3 |
| The repository supports deployment in a MuJoCo simulation and in the real world | vendor_doc | README.md:5 |
| Real-world deployment code is still an unchecked TODO item | vendor_doc | README.md:43 |
| The simulation entry point uses the 'lo' network interface to build a MujocoWrapper with core/go2/scene_parkour.xml | upstream_code | core/deployment_player.py:21-22 |
| MujocoEnv loads the MJCF with mujoco.MjModel.from_xml_path and creates the data with mujoco.MjData | upstream_code | mujoco_deploy/mujoco_env.py:53-54 |
| MujocoEnv.reset restores the model with mujoco.mj_resetData | upstream_code | mujoco_deploy/mujoco_env.py:71-72 |
| MujocoEnv.step writes the action to data.ctrl and advances the model with mujoco.mj_step | upstream_code | mujoco_deploy/mujoco_env.py:86-93 |
| The upstream sets model.opt.timestep from the environment configuration's sim.dt | upstream_code | mujoco_deploy/mujoco_env.py:67 |
| The served scene core/go2/scene.xml includes the robot model go2.xml | upstream_code | core/go2/scene.xml:1-2 |
| The parkour scene core/go2/scene_parkour.xml includes go2.xml and adds a height-field terrain from ../terrain.png | upstream_code | core/go2/scene_parkour.xml:1-16 |
| The go2 model compiles angles in radians and looks for meshes in the assets directory | upstream_code | core/go2/go2.xml:2 |
| The go2 model option sets an elliptic cone and impratio 100 and states no timestep | upstream_code | core/go2/go2.xml:4 |
| The go2 robot body starts at pos -7.5 0 0.5 and carries a free joint | upstream_code | core/go2/go2.xml:64-70 |
| The go2 default class gives every motor a control range of -23.7 to 23.7 | upstream_code | core/go2/go2.xml:10 |
| The knee default class narrows the motor control range to -45.43 to 45.43 | upstream_code | core/go2/go2.xml:24 |
| The model declares twelve motor actuators, one for each hip, thigh and calf joint of the four legs | upstream_code | core/go2/go2.xml:224-237 |
| The model declares twelve named hinge joints, three on each leg | upstream_code | core/go2/go2.xml:84-208 |
| The model has a home keyframe with a 19-value qpos and a 12-value ctrl | upstream_code | core/go2/go2.xml:288-289 |
| The model declares joint position, joint velocity, actuator force, IMU orientation, gyro and accelerometer sensors | upstream_code | core/go2/go2.xml:239-285 |
| The flat scene adds a ground plane and a directional light | upstream_code | core/go2/scene.xml:19-21 |
| The parkour terrain is a 200 by 50 height field of size 8.0 2.0 0.3 0.001 | upstream_code | core/go2/scene_parkour.xml:13-16 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the loaded model itself, one interval per
actuator (`actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file). The package
declares no limit of its own and no `operator_required` bound, because the model file is the system of record for the
control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It expands the scene's
`go2.xml` include, resolves the MJCF default classes, and derives the twelve actuator control ranges, the nineteen
qpos and eighteen qvel dimensions and the option time step from the same text. Its integration is a placeholder joint
motion, not the engine's dynamics, and it resolves no mesh, contact, equality or sensor constraint. MuJoCo was not
importable where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are
listed in the `fidelity` attribute of `driver.py`.

Tags: unitree, go2, quadruped, parkour, mujoco, simulation, robot
