# Facts and tags for gh.openmoss/vlabench

Every fact cites its source at commit `cf588fe60c0c7282174fe979f5913170cfe69017`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The package serves a listed MJCF scene of the card as a `MujocoDriver`. The card's `models[0]` is the Franka panda
scene; the package serves `models[1]`, the xarm7 scene, because the panda model leaves its seven arm actuators without
a `ctrlrange` and the MuJoCo bridge would publish them as unlimited, so the gate could not build an out-of-envelope
probe for them. Every one of the xarm7 model's eight actuators states a control range. The card's entry symbol,
`VLABench.envs.dm_env:LM4ManipDMEnv`, is a dm_control composer environment wrapper, not a model file: the MuJoCo
family serves the model, not the environment, and the package neither imports nor runs the clone or its environment.
The model file and its mesh assets are read from the read-only clone; neither is copied into this package.

| fact | source | ref |
|---|---|---|
| The card's entry symbol LM4ManipDMEnv is a dm_control composer.Environment subclass that overrides reset and step | upstream_code | VLABench/envs/dm_env.py:7-41 |
| The card lists the xarm7 scene as models[1]: its root is '<mujoco model="xarm7 scene">' and it includes xarm7.xml | upstream_code | VLABench/assets/robots/xarm7/scene.xml:1-2 |
| The xarm7 model root is '<mujoco model="xarm7">' and its compiler sets autolimits=true | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:1-2 |
| The robot config maps the xarm robot to xarm7/xarm7.xml and gives it 8 default_qpos values | upstream_code | VLABench/configs/robot_config.json:8-12 |
| The model sets no option timestep: its <option> element carries only integrator=implicitfast | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:4 |
| The model has 8 actuators: act1 to act7 on the seven arm joints and a gripper actuator on the split tendon | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:171-180 |
| The default class xarm7 states a general ctrlrange of -6.28319 to 6.28319 for the arm actuators | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:30-33 |
| act2 states ctrlrange -2.059 to 2.0944, act4 -0.19198 to 3.927, act6 -1.69297 to 3.14159 and the gripper 0 to 255 | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:173-179 |
| The model has 13 hinge joints: joint1 to joint7, the left and right driver, finger and inner-knuckle joints | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:64-136 |
| The gripper tendon couples the left and right driver joints with coef 0.5 | upstream_code | VLABench/assets/robots/xarm7/xarm7.xml:158-161 |
| The scene adds a floor plane and a cylindrical pad to the xarm7 model | upstream_code | VLABench/assets/robots/xarm7/scene.xml:19-22 |
| The env factory loads the robot from robot_config and constructs LM4ManipDMEnv(task, time_limit, reset_wait_step) | upstream_code | VLABench/envs/__init__.py:42-54 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`, with `autolimits="true"` inferring the limited flag from a stated range), so no
`operator_required` bound is needed and no limit number is written by this package. The eight intervals in the
reference are the model's own values, cited above; the reference they carry is the model path plus
`:actuator_ctrlrange`, not a line of the clone.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It parses the scene's MJCF,
expands the include of `xarm7.xml`, resolves the default classes for the actuator control ranges and counts the
joints, but its integration is a placeholder first-order motion of each actuated joint toward its control target; it
loads no mesh, resolves no contact, tendon or equality constraint and has no actuator or sensor dynamics. The model
sets no `<option timestep>` (`xarm7.xml:4`), so the stand-in uses 0.002 s as a placeholder for the MuJoCo library
default and the reference's `timestep_ms` (2 ms) is that stand-in value, not a measurement. MuJoCo was not importable
where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are listed in
the `fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that imports
MuJoCo.

NOT COVERED: the dm_control environment's `rgb`, `depth`, `segmentation` and point-cloud observation arrays
(`VLABench/envs/dm_env.py:118-160`), the task scene, the reset wait steps and the random layout of
`LM4ManipDMEnv`; this package serves the xarm7 model's `qpos`/`qvel`/`ctrl` state and the `cap.world.step.v1` /
`cap.world.reset.v1` contract, not the environment.

Tags: vlabench, xarm7, manipulation, mujoco, simulation, robot
